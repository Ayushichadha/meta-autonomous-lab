"""Bounded candidate experiments exposed to a supervisor."""

from .domain import Incident, Plan, Scenario, Snapshot, apply_incident
from .metrics import measure
from .scheduler import Policy, solve
from .simulator import simulate
from .validation import validate_plan


def experiment(scenario: Scenario, state: Snapshot, reference: Plan, incident: Incident | None,
               policy: Policy, time_limit: float = 3.0) -> dict:
    if incident is not None and incident.observed_at != state.now:
        raise ValueError("Incident and decision state times differ")
    if incident is not None and state.available_at.get(incident.machine) != incident.estimated_repair_at:
        raise ValueError("Apply the current incident before experimenting")
    plan = solve(scenario, state, reference=reference, policy=policy, time_limit=time_limit)
    finishes = sorted({max(state.now + 1, incident.estimated_repair_at - incident.uncertainty_minutes),
                       incident.estimated_repair_at,
                       incident.estimated_repair_at + incident.uncertainty_minutes}) if incident else [None]
    trials = []
    for repair_at in finishes:
        assumptions = {incident.machine: repair_at} if incident else {}
        run = simulate(scenario, state, plan, repair_overrides=assumptions)
        trials.append({"assumed_repair_at": repair_at,
                       "repair_assumptions": {**state.available_at, **assumptions},
                       "metrics": measure(scenario, run.snapshot, plan=plan, reference=reference, decision_state=state)})
    nominal = next(t["metrics"] for t in trials if t["assumed_repair_at"] == (incident.estimated_repair_at if incident else None))
    return {"policy": policy, "plan": plan.model_dump(), "nominal_metrics": nominal,
            "worst_tested_weighted_tardiness": max(t["metrics"]["weighted_tardiness_minutes"] for t in trials),
            "uncertainty_trials": trials, "constraint_errors": validate_plan(scenario, state, plan),
            "note": "Forecasts under three stated repair assumptions, not observed outcomes or a probability guarantee."}


def prepare(scenario: Scenario, *, outage_at: int = 25, repair_at: int = 115,
            machine: str = "CNC-A", time_limit: float = 3.0) -> tuple[Plan, Snapshot, Incident]:
    original = solve(scenario, Snapshot(), time_limit=time_limit)
    observation = simulate(scenario, Snapshot(), original, until=outage_at).snapshot
    incident = Incident(machine=machine, observed_at=outage_at, estimated_repair_at=repair_at,
                        uncertainty_minutes=20,
                        source=f"Synthetic maintenance update: {machine} unavailable; estimated return at minute {repair_at}, +/-20 minutes.")
    return original, apply_incident(scenario, observation, incident), incident


def run_comparison(scenario: Scenario, *, time_limit: float = 3.0,
                   repair_at: int = 115, outage_at: int = 25, machine: str = "CNC-A") -> dict:
    original, state, incident = prepare(scenario, repair_at=repair_at, outage_at=outage_at,
                                       machine=machine, time_limit=time_limit)
    healthy = simulate(scenario, Snapshot(), original)
    candidates = [experiment(scenario, state, original, incident, policy, time_limit)
                  for policy in ("preserve", "reschedule", "reroute")]
    return {
        "schema_version": 1, "kind": "development_simulation", "synthetic": True,
        "ai_used": False,
        "scope": "Single-disruption feasibility demonstration; not a held-out policy benchmark.",
        "scenario": scenario.model_dump(), "original_plan": original.model_dump(),
        "healthy_metrics": measure(scenario, healthy.snapshot, plan=original),
        "observation": state.model_dump(), "incident": incident.model_dump(),
        "candidates": candidates,
        "objective_weights": {"priority_weighted_tardiness": 100, "queued_start_shift": 1,
                              "rerouted_operation": 30, "makespan": 1},
    }
