"""Sequential, simulation-based factory twin.

The runner owns the private physical event trace. Policies receive only a fresh
observation, past decisions, and the event(s) observed at the current timestamp.
"""

from collections import defaultdict
from time import perf_counter
from typing import Callable, Literal

from pydantic import Field, model_validator

from .domain import Incident, Model, Plan, Scenario, Snapshot
from .experiments import experiment
from .metrics import measure
from .scheduler import solve
from .simulator import simulate
from .validation import require_valid

POLICIES = ("preserve", "always_replan", "fixed_interval", "solver_selection", "meta")


class WorldEvent(Model):
    time: int = Field(ge=0)
    kind: Literal["outage", "repair_estimate", "repaired"]
    machine: str
    estimated_repair_at: int | None = Field(default=None, ge=1)
    uncertainty_minutes: int = Field(default=0, ge=0)
    source: str = "Synthetic maintenance event"

    @model_validator(mode="after")
    def valid_estimate(self):
        if self.kind != "repaired" and (self.estimated_repair_at is None or self.estimated_repair_at <= self.time):
            raise ValueError("Outage/update needs a future published estimate")
        if self.kind == "repaired" and self.estimated_repair_at is not None:
            raise ValueError("A confirmed repair is not a future estimate")
        return self


class EpisodeConfig(Model):
    interval_minutes: int = Field(default=30, ge=1, le=240)
    solve_seconds: float = Field(default=.5, gt=0, le=10)
    max_agent_requests: int = Field(default=12, ge=1, le=24)
    expired_estimate_extension: int = Field(default=30, ge=1)


def factory_observation(scenario: Scenario, state: Snapshot, plan: Plan) -> dict:
    """Pure observation projection; takes no private event trace."""
    machines, operations = [], []
    entries = plan.by_operation
    for order in scenario.orders:
        for i, op in enumerate(order.operations):
            record = state.progress.get(op.id)
            machine = record.machine if record else entries[op.id].machine
            previous = state.progress.get(order.operations[i - 1].id) if i else None
            blocked = record is None and (order.release > state.now or
                (i > 0 and (previous is None or previous.completed_at is None)) or machine in state.available_at)
            status = ("completed" if record and record.completed_at is not None else
                      "paused" if record and machine in state.available_at else
                      "active" if record else "blocked" if blocked else "queued")
            operations.append({"operation": op.id, "order": order.id, "machine": machine, "status": status,
                               "worked_minutes": record.worked if record else 0,
                               "remaining_minutes": op.durations[machine] - (record.worked if record else 0),
                               "due": order.due, "priority": order.priority})
    for machine in scenario.machines:
        current = next((o for o in operations if o["machine"] == machine and o["status"] in {"active", "paused"}), None)
        queue = sorted((entries[o["operation"]] for o in operations if o["machine"] == machine and o["status"] in {"queued", "blocked"}), key=lambda a: (a.start, a.operation))
        machines.append({"machine": machine, "status": "down" if machine in state.available_at else "running" if current else "idle",
                         "forecast_available_at": state.available_at.get(machine, state.now),
                         "current_operation": current["operation"] if current else None,
                         "queue": [a.operation for a in queue]})
    affected = sorted({o["order"] for o in operations if o["status"] != "completed" and o["machine"] in state.available_at})
    return {"time": state.now, "machines": machines, "operations": operations, "affected_orders": affected}


def candidate_score(candidate: dict) -> int:
    m = candidate["nominal_metrics"]
    return 100 * m["weighted_tardiness_minutes"] + m["queued_start_shift_minutes"] + 30 * m["rerouted_operations"] + m["makespan_minutes"]


def _decision(scenario, state, reference, incident, policy, config, callback, history, event):
    start = perf_counter()
    if policy == "meta":
        if callback is None:
            raise ValueError("Meta policy requires a real supervisor callback")
        result = callback(scenario, state, reference, incident, history, event)
        candidates = result["experiments"]
        chosen = result["selected_candidate"]
        evidence = result["evidence_summary"]
    else:
        actions = ("preserve", "reschedule", "reroute") if policy == "solver_selection" else ("reroute",)
        candidates = [experiment(scenario, state, reference, incident, action, config.solve_seconds) for action in actions]
        chosen = min(candidates, key=lambda c: (candidate_score(c), c["policy"]))
        evidence = "Conventional selection using the documented nominal objective; no model inference."
        result = {"model_requests": 0, "usage_by_request": [], "cost_usd": 0.0, "trace": []}
    plan = Plan.model_validate(chosen["plan"])
    require_valid(scenario, state, plan)
    return plan, {"selected_policy": chosen["policy"], "evidence_summary": evidence,
        "candidates": candidates, "predicted_metrics": chosen["nominal_metrics"],
        "model_requests": result["model_requests"], "usage_by_request": result["usage_by_request"],
        "estimated_cost_usd": result.get("cost_usd"), "tool_trace": result.get("trace", []),
        "wall_seconds": perf_counter() - start}


def run_episode(scenario: Scenario, events: list[WorldEvent], *, policy: str = "solver_selection",
                config: EpisodeConfig | None = None, supervisor: Callable | None = None,
                initial_plan: Plan | None = None, on_frame: Callable | None = None,
                starting_state: Snapshot | None = None) -> dict:
    """Run one policy on an exogenous trace. Future events never cross its boundary."""
    if policy not in POLICIES:
        raise ValueError("Unknown episode policy")
    config = config or EpisodeConfig()
    ordered = sorted(events, key=lambda event: event.time)
    grouped = defaultdict(list)
    state = starting_state or Snapshot()
    trace_down = set(state.available_at)
    for event in ordered:
        if event.time < state.now:
            raise ValueError("A branch cannot replay events earlier than its starting observation")
        if event.machine not in scenario.machines:
            raise ValueError("Trace references an unknown machine")
        if event.kind == "outage":
            if event.machine in trace_down:
                raise ValueError("A down machine cannot fail again before repair")
            trace_down.add(event.machine)
        else:
            if event.machine not in trace_down:
                raise ValueError("Repair/update requires a prior outage")
            if event.kind == "repaired":
                trace_down.remove(event.machine)
        grouped[event.time].append(event)
    if trace_down:
        raise ValueError("Every outage needs a physical repair in the private trace")
    started = perf_counter()
    plan = initial_plan or solve(scenario, state, time_limit=config.solve_seconds)
    require_valid(scenario, state, plan)
    original = plan
    down: dict[str, tuple[int, int]] = {m: (estimate, 0) for m, estimate in state.available_at.items()}
    history, frames, execution_events = [], [], []
    revisions = requests = reroutes = shifts = changed_operations = 0
    guard_seconds = experiment_seconds = 0.0
    failures = []
    frames.append({"time": state.now, "events": [], "state": state.model_dump(), "plan": plan.model_dump(),
                   "factory": factory_observation(scenario, state, plan), "decision": None})
    if on_frame:
        on_frame(frames[0])
    horizon = max([0, *(e.time for e in ordered), *(o.release for o in scenario.orders)]) + sum(max(o.durations.values()) for o in scenario.operations.values()) + 120
    event_times = set(grouped)
    ticks = {t for t in range(config.interval_minutes, horizon + 1, config.interval_minutes) if t > state.now}
    checkpoints = sorted(event_times | ticks)
    for time in checkpoints:
        if all(p.completed_at is not None for p in state.progress.values()) and len(state.progress) == len(scenario.operations):
            break
        # Actual failures block execution until a *confirmed* repair. The private
        # next-event time is used only to stop this segment, never to plan recovery.
        physical = {machine: time + 1 if machine in down else 0 for machine in scenario.machines}
        execution = simulate(scenario, state, plan, until=time, repair_overrides=physical)
        state = execution.snapshot
        execution_events.extend(execution.events)
        observed = []
        for event in grouped.get(time, []):
            observed.append(event.model_dump())
            if event.kind == "repaired":
                down.pop(event.machine)
            else:
                down[event.machine] = (event.estimated_repair_at, event.uncertainty_minutes)
        # An elapsed estimate is not permission to restart a failed machine.
        # This known-information fallback is identical across all policies.
        for machine, (estimate, uncertainty) in list(down.items()):
            if estimate <= time:
                down[machine] = (time + config.expired_estimate_extension, uncertainty)
                observed.append({"time": time, "kind": "estimate_expired", "machine": machine,
                                 "source": "Still down; no confirmed repair. Forecast extended by the fixed documented assumption."})
        state = state.model_copy(update={"available_at": {m: value[0] for m, value in down.items()}})
        before_guard = plan
        guard = solve(scenario, state, reference=plan, policy="preserve", time_limit=config.solve_seconds)
        guard_seconds += guard.solver_seconds
        plan = guard
        incident = None
        # Only a current observed estimate is passed into candidate stress tests.
        focus = next((e["machine"] for e in reversed(observed) if e["machine"] in down), None)
        if focus:
            estimate, uncertainty = down[focus]
            incident = Incident(machine=focus, observed_at=time, estimated_repair_at=estimate,
                                uncertainty_minutes=uncertainty, source=next(e["source"] for e in reversed(observed) if e["machine"] == focus))
        actionable = bool(observed)
        should_decide = (policy not in {"preserve", "fixed_interval"} and actionable) or (policy == "fixed_interval" and time in ticks)
        unfinished = len(state.progress) < len(scenario.operations) or any(p.completed_at is None for p in state.progress.values())
        decision = None
        if should_decide and unfinished:
            try:
                if policy == "meta" and requests >= config.max_agent_requests:
                    raise RuntimeError("Episode model-request budget reached")
                event_context = {"time": time, "events": observed, "factory": factory_observation(scenario, state, guard),
                                 "remaining_episode_model_requests": config.max_agent_requests - requests}
                proposed, decision = _decision(scenario, state, guard, incident, policy, config,
                                               supervisor, history, event_context)
                requests += decision["model_requests"]
                if requests > config.max_agent_requests:
                    raise RuntimeError("Supervisor exceeded the episode model-request budget")
                plan = proposed
                actual_change = any(a.operation not in state.progress and
                    (a.machine != guard.by_operation[a.operation].machine or a.start != guard.by_operation[a.operation].start)
                    for a in plan.assignments)
                decision["action"] = "REPLAN" if actual_change else "PERSIST"
                decision["time"] = time
                decision["constraint_errors"] = []
                objectives = {c["policy"]: candidate_score(c) for c in decision["candidates"]}
                chosen_metrics = decision["predicted_metrics"]
                decision["verified_evidence"] = {
                    "candidate_objectives": objectives,
                    "selected_objective": objectives[decision["selected_policy"]],
                    "best_tested_objective": min(objectives.values()),
                    "summary": f"{decision['action']}: forecast priority-weighted delay {chosen_metrics['weighted_tardiness_minutes']} min; "
                               f"{chosen_metrics['on_time_orders']}/{chosen_metrics['total_orders']} orders on time; "
                               f"{chosen_metrics['rerouted_operations']} reroutes; {chosen_metrics['queued_start_shift_minutes']} min queued start shifts. "
                               "These measurements are forecasts, not realized outcomes."}
                revisions += int(actual_change)
                m = measure(scenario, simulate(scenario, state, plan).snapshot, plan=plan, reference=guard, decision_state=state)
                reroutes += m["rerouted_operations"]
                shifts += m["queued_start_shift_minutes"]
                changed_operations += m["changed_queued_operations"]
                experiment_seconds += sum(c["plan"]["solver_seconds"] for c in decision["candidates"])
                history.append({"time": time, "action": decision["action"], "selected_policy": decision["selected_policy"],
                                "predicted_weighted_tardiness": decision["predicted_metrics"]["weighted_tardiness_minutes"]})
            except (ValueError, RuntimeError) as error:
                # Explicitly recorded feasible fallback, never a fake model answer.
                plan = guard
                failed_requests = getattr(error, "model_requests", 0)
                requests += failed_requests
                failure = {"time": time, "error": str(error).split("\n")[0][:250], "fallback": "preserve_validated_guard"}
                failures.append(failure)
                decision = {"time": time, "action": "FALLBACK", "failure": failure, "candidates": [],
                            "model_requests": failed_requests, "constraint_errors": [],
                            "tool_trace": getattr(error, "tool_trace", []),
                            "usage_by_request": getattr(error, "usage_by_request", [])}
        require_valid(scenario, state, plan)
        frame = {"time": time, "events": observed, "clock_tick": time in ticks,
                 "state": state.model_dump(), "plan": plan.model_dump(),
                 "factory": factory_observation(scenario, state, plan), "decision": decision,
                 "guard_start_shift_minutes": sum(abs(a.start - before_guard.by_operation[a.operation].start)
                    for a in guard.assignments if a.operation not in state.progress)}
        frames.append(frame)
        if on_frame:
            on_frame(frame)
    else:
        failures.append({"error": "Execution horizon exhausted", "time": state.now})
    complete = len(state.progress) == len(scenario.operations) and all(p.completed_at is not None for p in state.progress.values())
    realized = measure(scenario, state, plan=plan) if complete else None
    decisions = [f["decision"] for f in frames if f["decision"]]
    usages = [u for d in decisions for u in d.get("usage_by_request", [])]
    costs_known = all(d.get("estimated_cost_usd") is not None for d in decisions if d.get("model_requests", 0))
    if realized:
        realized.update(revision_count=revisions, rerouted_operations=reroutes, queued_start_shift_minutes=shifts,
                        changed_queued_operations=changed_operations, policy_failures=len(failures),
                        guard_start_shift_minutes=sum(f["guard_start_shift_minutes"] for f in frames if "guard_start_shift_minutes" in f),
                        feasibility_violations=0, model_calls=requests, guard_solver_seconds=guard_seconds,
                        guard_solver_calls=len(frames) - 1,
                        experiment_solver_calls=sum(len(d.get("candidates", [])) for d in decisions),
                        experiment_solver_seconds=experiment_seconds,
                        model_input_tokens=sum(u.get("prompt_tokens", u.get("input_tokens", 0)) for u in usages),
                        model_output_tokens=sum(u.get("completion_tokens", u.get("output_tokens", 0)) for u in usages),
                        estimated_model_cost_usd=sum(d.get("estimated_cost_usd") or 0 for d in decisions) if costs_known else None,
                        wall_seconds=perf_counter() - started)
    return {"schema_version": 2, "kind": "sequential_episode", "synthetic": True, "policy": policy,
            "scenario": scenario.model_dump(), "configuration": config.model_dump(),
            "private_trace_released_after_execution": [e.model_dump() for e in ordered],
            "original_plan": original.model_dump(), "frames": frames, "execution_events": execution_events,
            "realized_metrics": realized, "complete": complete, "failures": failures,
            "status": "completed" if complete and not failures else "completed_with_failures" if complete else "failed",
            "limitations": ["Synthetic simulation, no physical factory connection.",
                "Repair stress trials vary the current focus outage only; other forecasts remain nominal.",
                "Guard shifts are reported separately from optional policy revisions."]}


def demo_events() -> list[WorldEvent]:
    return [WorldEvent(time=25, kind="outage", machine="CNC-A", estimated_repair_at=115,
                       uncertainty_minutes=20, source="CNC-A spindle fault; maintenance estimates return at 115 +/-20 min."),
            WorldEvent(time=55, kind="repair_estimate", machine="CNC-A", estimated_repair_at=120,
                       uncertainty_minutes=10, source="Inspection complete; CNC-A estimate revised to 120 +/-10 min."),
            WorldEvent(time=118, kind="repaired", machine="CNC-A", source="Maintenance confirms CNC-A returned to service.")]


def live_supervisor(provider: str = "meta", *, solve_seconds: float = .5, on_progress=None):
    """New bounded client per decision; all share the persistent dollar ledger."""
    def decide(scenario, state, reference, incident, history, event):
        from .agent import supervise
        from .provider import ModelClient
        return supervise(ModelClient(provider), scenario, state, reference, incident,
                         time_limit=solve_seconds, observed_event=event, decision_history=history,
                         max_requests=min(6, event["remaining_episode_model_requests"]), on_progress=on_progress)
    return decide
