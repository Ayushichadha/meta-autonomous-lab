"""Independent schedule checks: no dependency on the solver implementation."""

from .domain import Plan, Scenario, Snapshot, check_snapshot


def validate_plan(scenario: Scenario, snapshot: Snapshot, plan: Plan) -> list[str]:
    check_snapshot(scenario, snapshot)
    errors: list[str] = []
    ops = scenario.operations
    entries = plan.by_operation
    if len(entries) != len(plan.assignments):
        errors.append("Duplicate operation assignment")
    if set(entries) != set(ops):
        errors.append("Plan must contain exactly the scenario's operations")
        return errors
    intervals: dict[str, list[tuple[int, int, str]]] = {m: [] for m in scenario.machines}
    for op_id, entry in entries.items():
        op = ops[op_id]
        if entry.machine not in op.durations:
            errors.append(f"{op_id}: ineligible machine {entry.machine}")
            continue
        record = snapshot.progress.get(op_id)
        if record is not None:
            if entry.machine != record.machine or entry.start != record.started_at:
                errors.append(f"{op_id}: started work must retain its machine and start")
            if record.completed_at is not None:
                if entry.end != record.completed_at:
                    errors.append(f"{op_id}: completed work is immutable")
                continue
            resume = max(snapshot.now, snapshot.available_at.get(record.machine, 0))
            finish = resume + op.durations[record.machine] - record.worked
            if entry.end != finish:
                errors.append(f"{op_id}: active work must resume and finish without losing progress")
            intervals[entry.machine].append((snapshot.now, entry.end, op_id))
        else:
            if entry.start < max(snapshot.now, snapshot.available_at.get(entry.machine, 0)):
                errors.append(f"{op_id}: starts in the past or during downtime")
            if entry.end - entry.start != op.durations[entry.machine]:
                errors.append(f"{op_id}: incorrect processing duration")
            intervals[entry.machine].append((entry.start, entry.end, op_id))
    for order in scenario.orders:
        for i, op in enumerate(order.operations):
            entry = entries[op.id]
            if entry.start < order.release:
                errors.append(f"{op.id}: starts before order release")
            if i and entry.start < entries[order.operations[i - 1].id].end:
                errors.append(f"{op.id}: violates operation precedence")
    for machine, spans in intervals.items():
        spans.sort()
        for left, right in zip(spans, spans[1:]):
            if left[1] > right[0]:
                errors.append(f"{machine}: overlapping {left[2]} and {right[2]}")
    return errors


def require_valid(scenario: Scenario, snapshot: Snapshot, plan: Plan) -> None:
    errors = validate_plan(scenario, snapshot, plan)
    if errors:
        raise ValueError("Invalid plan: " + "; ".join(errors))
