import pytest

from factory_lab.domain import Assignment, Incident, Operation, Order, Plan, Scenario, Snapshot, apply_incident
from factory_lab.experiments import experiment, prepare
from factory_lab.scheduler import solve
from factory_lab.simulator import simulate
from factory_lab.validation import validate_plan


def small_shop():
    return Scenario(name="Test shop", description="Hand-checkable fixture", machines=["A", "B", "Q"], orders=[
        Order(id="one", due=20, priority=2, operations=[
            Operation(id="one/cut", durations={"A": 10, "B": 13}, preferred_machine="A"),
            Operation(id="one/check", durations={"Q": 5}, preferred_machine="Q")]),
        Order(id="two", due=25, operations=[
            Operation(id="two/cut", durations={"A": 8, "B": 10}, preferred_machine="A"),
            Operation(id="two/check", durations={"Q": 4}, preferred_machine="Q")]),
    ])


def hand_plan():
    return Plan(policy="fixture", solver_status="MANUAL", assignments=[
        Assignment(operation="one/cut", machine="A", start=0, end=10),
        Assignment(operation="one/check", machine="Q", start=10, end=15),
        Assignment(operation="two/cut", machine="B", start=0, end=10),
        Assignment(operation="two/check", machine="Q", start=15, end=19),
    ])


def change(plan, op_id, **updates):
    return plan.model_copy(update={"assignments": [a.model_copy(update=updates) if a.operation == op_id else a
                                                  for a in plan.assignments]})


def test_independent_validator_rejects_overlaps_and_precedence():
    scenario, state, plan = small_shop(), Snapshot(), hand_plan()
    assert not validate_plan(scenario, state, plan)
    invalid = change(plan, "two/check", start=12, end=16)
    assert any("overlapping" in e for e in validate_plan(scenario, state, invalid))
    invalid = change(plan, "one/check", start=5, end=10)
    assert any("precedence" in e for e in validate_plan(scenario, state, invalid))


def test_validator_rejects_missing_duplicate_ineligible_and_bad_duration():
    scenario, plan = small_shop(), hand_plan()
    assert validate_plan(scenario, Snapshot(), plan.model_copy(update={"assignments": plan.assignments[:-1]}))
    assert validate_plan(scenario, Snapshot(), plan.model_copy(update={"assignments": plan.assignments + [plan.assignments[0]]}))
    assert any("ineligible" in e for e in validate_plan(scenario, Snapshot(), change(plan, "one/cut", machine="Q")))
    assert any("duration" in e for e in validate_plan(scenario, Snapshot(), change(plan, "one/cut", end=9)))


def test_simulation_matches_hand_calculation():
    run = simulate(small_shop(), Snapshot(), hand_plan())
    assert run.snapshot.now == 19
    assert run.snapshot.progress["one/check"].completed_at == 15
    assert run.snapshot.progress["two/check"].completed_at == 19


def test_boundary_completion_and_incremental_execution():
    scenario, plan = small_shop(), hand_plan()
    state = simulate(scenario, Snapshot(), plan, until=10).snapshot
    assert state.progress["one/cut"].completed_at == 10
    assert state.progress["one/check"].started_at == 10
    full = simulate(scenario, Snapshot(), plan).snapshot
    resumed = simulate(scenario, state, plan).snapshot
    assert full == resumed


def test_interrupted_work_pauses_and_retains_progress():
    scenario, plan = small_shop(), hand_plan()
    state = simulate(scenario, Snapshot(), plan, until=4).snapshot
    assert state.progress["one/cut"].worked == 4
    state = apply_incident(scenario, state, Incident(machine="A", observed_at=4,
                           estimated_repair_at=14, source="Fixture"))
    recovery = solve(scenario, state, reference=plan, policy="reroute", time_limit=.2)
    cut = recovery.by_operation["one/cut"]
    assert (cut.machine, cut.start, cut.end) == ("A", 0, 20)
    assert not validate_plan(scenario, state, recovery)
    mid = simulate(scenario, state, recovery, until=8).snapshot
    assert mid.progress["one/cut"].worked == 4
    assert mid.progress["two/cut"].worked == 8
    final = simulate(scenario, mid, recovery).snapshot
    assert final.progress["one/cut"].completed_at == 20
    assert final.progress["one/cut"].worked == 10


def test_completed_work_cannot_be_rewritten():
    scenario, plan = small_shop(), hand_plan()
    state = simulate(scenario, Snapshot(), plan, until=15).snapshot
    invalid = change(plan, "one/cut", end=11)
    assert any("immutable" in e for e in validate_plan(scenario, state, invalid))


def test_actual_repair_outcome_is_separate_from_forecast():
    scenario, plan = small_shop(), hand_plan()
    state = simulate(scenario, Snapshot(), plan, until=4).snapshot
    incident = Incident(machine="A", observed_at=4, estimated_repair_at=14,
                        uncertainty_minutes=5, source="Fixture")
    state = apply_incident(scenario, state, incident)
    candidate = experiment(scenario, state, plan, incident, "reroute", .2)
    recovery = Plan.model_validate(candidate["plan"])
    late_repair = simulate(scenario, state, recovery, repair_overrides={"A": 19})
    assert late_repair.snapshot.progress["one/cut"].completed_at == 25
    assert state.available_at["A"] == 14
    assert candidate["plan"]["assignments"] == recovery.model_dump()["assignments"]
    assert len(candidate["uncertainty_trials"]) == 3


def test_preserve_keeps_routing_queue_and_no_early_starts():
    scenario, plan = small_shop(), hand_plan()
    state = simulate(scenario, Snapshot(), plan, until=4).snapshot
    state = apply_incident(scenario, state, Incident(machine="A", observed_at=4, estimated_repair_at=14, source="Fixture"))
    recovery = solve(scenario, state, reference=plan, policy="preserve", time_limit=.2)
    assert recovery.by_operation["one/check"].end <= recovery.by_operation["two/check"].start
    for item in recovery.assignments:
        assert item.machine == plan.by_operation[item.operation].machine
        assert item.start >= plan.by_operation[item.operation].start


def test_incident_requires_known_machine_and_current_time():
    scenario = small_shop()
    with pytest.raises(ValueError, match="unknown machine"):
        apply_incident(scenario, Snapshot(), Incident(machine="X", observed_at=0, estimated_repair_at=10, source="Fixture"))
    with pytest.raises(ValueError, match="Advance"):
        apply_incident(scenario, Snapshot(), Incident(machine="A", observed_at=5, estimated_repair_at=10, source="Fixture"))


@pytest.mark.parametrize("seed", range(5))
def test_generated_development_cases_execute_without_constraint_violations(seed):
    from factory_lab.scenarios import development_scenario
    scenario = development_scenario(seed)
    reference, state, incident = prepare(scenario, time_limit=.3)
    for policy in ("preserve", "reschedule", "reroute"):
        candidate = experiment(scenario, state, reference, incident, policy, .3)
        assert candidate["constraint_errors"] == []
        assert candidate["nominal_metrics"]["total_orders"] == 8
