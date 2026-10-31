from .domain import Plan, Scenario, Snapshot


def measure(scenario: Scenario, final: Snapshot, *, plan: Plan, reference: Plan | None = None,
            decision_state: Snapshot | None = None) -> dict:
    outcomes = []
    for order in scenario.orders:
        record = final.progress.get(order.operations[-1].id)
        if record is None or record.completed_at is None:
            raise ValueError("Cannot score an unfinished simulation")
        late = max(0, record.completed_at - order.due)
        outcomes.append({"order": order.id, "due": order.due, "completed_at": record.completed_at,
                         "priority": order.priority, "tardiness_minutes": late})
    rerouted = shift = changed = 0
    if reference is not None:
        old = reference.by_operation
        for item in plan.assignments:
            if decision_state and item.operation in decision_state.progress:
                continue
            previous = old[item.operation]
            moved = item.machine != previous.machine
            delta = abs(item.start - previous.start)
            rerouted += int(moved)
            shift += delta
            changed += int(moved or delta > 0)
    return {
        "weighted_tardiness_minutes": sum(o["priority"] * o["tardiness_minutes"] for o in outcomes),
        "on_time_orders": sum(o["tardiness_minutes"] == 0 for o in outcomes),
        "total_orders": len(outcomes),
        "makespan_minutes": max(o["completed_at"] for o in outcomes),
        "rerouted_operations": rerouted,
        "queued_start_shift_minutes": shift,
        "changed_queued_operations": changed,
        "orders": outcomes,
    }
