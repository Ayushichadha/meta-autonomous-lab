"""Execute schedules with SimPy, preserving progress at observation boundaries."""

from dataclasses import dataclass

import simpy

from .domain import Plan, Progress, Scenario, Snapshot, check_snapshot
from .validation import require_valid


@dataclass(frozen=True)
class Execution:
    snapshot: Snapshot
    events: list[dict]


def simulate(scenario: Scenario, snapshot: Snapshot, plan: Plan, *, until: int | None = None,
             repair_overrides: dict[str, int] | None = None) -> Execution:
    """Private evaluator overrides test possible repair times, never exposed to the agent.

    Decisions use snapshot.available_at. The simulator can replay the candidate under
    different physical repair completions. Later starts follow the submitted schedule;
    blocked tasks queue and wait for dependencies rather than running impossibly.
    """
    require_valid(scenario, snapshot, plan)
    if until is not None and until < snapshot.now:
        raise ValueError("Cannot simulate backwards")
    availability = {**snapshot.available_at, **(repair_overrides or {})}
    if set(availability) - set(scenario.machines):
        raise ValueError("Unknown machine in physical availability")
    env = simpy.Environment(initial_time=snapshot.now)
    machines = {m: simpy.PriorityResource(env, capacity=1) for m in scenario.machines}
    done = {op_id: env.event() for op_id in scenario.operations}
    records = dict(snapshot.progress)
    working_since: dict[str, int] = {}
    events: list[dict] = []
    entries = plan.by_operation
    machine_previous = {}
    for machine in scenario.machines:
        queue = sorted((a for a in plan.assignments if a.machine == machine), key=lambda a: (a.start, a.operation))
        for previous, following in zip(queue, queue[1:]):
            machine_previous[following.operation] = previous.operation
    predecessor = {}
    release = {}
    for order in scenario.orders:
        for i, op in enumerate(order.operations):
            predecessor[op.id] = order.operations[i - 1].id if i else None
            release[op.id] = order.release
    for op_id, record in records.items():
        if record.completed_at is not None:
            done[op_id].succeed()

    def run_operation(op_id):
        entry = entries[op_id]
        prior = records.get(op_id)
        active = prior is not None
        if not active:
            previous = predecessor[op_id]
            if previous:
                yield done[previous]
            if op_id in machine_previous:
                yield done[machine_previous[op_id]]
            earliest = max(env.now, entry.start, release[op_id])
            yield env.timeout(earliest - env.now)
        # Active work always retains the machine, including while paused.
        priority = -1 if active else entry.start
        with machines[entry.machine].request(priority=priority) as request:
            yield request
            ready = max(env.now, availability.get(entry.machine, 0))
            if ready > env.now:
                events.append({"time": env.now, "operation": op_id, "kind": "waiting_for_repair", "machine": entry.machine})
                yield env.timeout(ready - env.now)
            duration = scenario.operations[op_id].durations[entry.machine]
            if prior is None:
                prior = Progress(machine=entry.machine, started_at=env.now, worked=0)
                records[op_id] = prior
            working_since[op_id] = env.now
            events.append({"time": env.now, "operation": op_id, "kind": "resumed" if active else "started", "machine": entry.machine})
            yield env.timeout(duration - prior.worked)
            records[op_id] = prior.model_copy(update={"worked": duration, "completed_at": env.now})
            working_since.pop(op_id)
            events.append({"time": env.now, "operation": op_id, "kind": "completed", "machine": entry.machine})
            done[op_id].succeed()

    # Register retained work before pending requests to avoid resource races.
    ids = sorted(scenario.operations, key=lambda op_id: (op_id not in records, entries[op_id].start, op_id))
    for op_id in ids:
        if op_id not in records or records[op_id].completed_at is None:
            env.process(run_operation(op_id))
    if until is None:
        env.run()
    else:
        # Include completions exactly at the observation boundary.
        while env.peek() <= until:
            env.step()
        if env.now < until:
            env.run(until=until)
    for op_id, started in working_since.items():
        prior = records[op_id]
        records[op_id] = prior.model_copy(update={"worked": prior.worked + env.now - started})
    result = Snapshot(now=env.now, progress=records, available_at=snapshot.available_at)
    check_snapshot(scenario, result)
    if until is None and any(op not in records or records[op].completed_at is None for op in scenario.operations):
        raise RuntimeError("Simulation stalled before every operation completed")
    return Execution(snapshot=result, events=events)
