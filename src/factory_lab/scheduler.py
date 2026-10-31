"""CP-SAT supplies candidate schedules; it never makes the agent's claims."""

from collections import defaultdict
from typing import Literal

from ortools.sat.python import cp_model

from .domain import Assignment, Plan, Scenario, Snapshot, check_snapshot
from .validation import require_valid

Policy = Literal["preserve", "reschedule", "reroute"]
TARDINESS_WEIGHT = 100
SHIFT_WEIGHT = 1
REROUTE_WEIGHT = 30


def solve(scenario: Scenario, snapshot: Snapshot, *, reference: Plan | None = None,
          policy: Policy = "reroute", time_limit: float = 3.0) -> Plan:
    check_snapshot(scenario, snapshot)
    if policy not in {"preserve", "reschedule", "reroute"}:
        raise ValueError("Unknown recovery policy")
    if time_limit <= 0:
        raise ValueError("Solve time limit must be positive")
    ops = scenario.operations
    old = reference.by_operation if reference else {}
    if reference and set(old) != set(ops):
        raise ValueError("Reference must contain every operation")
    horizon = max([snapshot.now, *snapshot.available_at.values(),
                   *(o.release for o in scenario.orders), *(a.start for a in old.values())])
    horizon += sum(max(op.durations.values()) for op in ops.values()) + 1
    model = cp_model.CpModel()
    starts, ends, selected = {}, {}, {}
    intervals = defaultdict(list)
    penalty_terms = []
    for machine in scenario.machines:
        until = snapshot.available_at.get(machine, snapshot.now)
        if until > snapshot.now:
            intervals[machine].append(model.new_fixed_size_interval_var(snapshot.now, until - snapshot.now, f"down:{machine}"))
    for op_id, op in ops.items():
        record = snapshot.progress.get(op_id)
        if record is not None:
            starts[op_id] = model.new_constant(record.started_at)
            if record.completed_at is not None:
                finish = record.completed_at
            else:
                resume = max(snapshot.now, snapshot.available_at.get(record.machine, 0))
                remaining = op.durations[record.machine] - record.worked
                finish = resume + remaining
                intervals[record.machine].append(model.new_fixed_size_interval_var(resume, remaining, op_id))
            ends[op_id] = model.new_constant(finish)
            selected[op_id] = {record.machine: model.new_constant(1)}
            continue
        starts[op_id] = model.new_int_var(snapshot.now, horizon, f"start:{op_id}")
        ends[op_id] = model.new_int_var(snapshot.now, horizon, f"end:{op_id}")
        routes = op.durations
        if policy != "reroute" and op_id in old:
            routes = {old[op_id].machine: op.durations[old[op_id].machine]}
        selected[op_id] = {}
        for machine, duration in routes.items():
            choice = model.new_bool_var(f"route:{op_id}:{machine}")
            selected[op_id][machine] = choice
            intervals[machine].append(model.new_optional_interval_var(
                starts[op_id], duration, ends[op_id], choice, f"run:{op_id}:{machine}"))
            if op_id in old and machine != old[op_id].machine:
                penalty_terms.append(REROUTE_WEIGHT * choice)
        model.add_exactly_one(selected[op_id].values())
        if op_id in old:
            shift = model.new_int_var(0, horizon, f"shift:{op_id}")
            model.add_abs_equality(shift, starts[op_id] - old[op_id].start)
            penalty_terms.append(SHIFT_WEIGHT * shift)
            if policy == "preserve":
                model.add(starts[op_id] >= old[op_id].start)
    for machine in scenario.machines:
        model.add_no_overlap(intervals[machine])
    if policy == "preserve" and reference:
        for machine in scenario.machines:
            queue = sorted((a for a in old.values() if a.machine == machine), key=lambda a: (a.start, a.operation))
            for left, right in zip(queue, queue[1:]):
                model.add(ends[left.operation] <= starts[right.operation])
    for order in scenario.orders:
        for i, op in enumerate(order.operations):
            model.add(starts[op.id] >= order.release)
            if i:
                model.add(starts[op.id] >= ends[order.operations[i - 1].id])
        late = model.new_int_var(0, horizon, f"late:{order.id}")
        model.add_max_equality(late, [0, ends[order.operations[-1].id] - order.due])
        penalty_terms.append(TARDINESS_WEIGHT * order.priority * late)
    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, list(ends.values()))
    model.minimize(sum(penalty_terms) + makespan)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"No recovery plan: {solver.status_name(status)}")
    plan = Plan(
        assignments=[Assignment(operation=op_id,
                                machine=next(m for m, choice in selected[op_id].items() if solver.value(choice)),
                                start=solver.value(starts[op_id]), end=solver.value(ends[op_id])) for op_id in ops],
        policy=policy, solver_status=solver.status_name(status), solver_seconds=solver.wall_time,
        objective=solver.objective_value, objective_bound=solver.best_objective_bound,
    )
    require_valid(scenario, snapshot, plan)
    return plan
