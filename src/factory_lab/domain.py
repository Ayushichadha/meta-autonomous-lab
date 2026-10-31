"""Integer minutes throughout. Observations contain no future event timeline."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Operation(Model):
    id: str
    durations: dict[str, int]  # Includes fixed setup/reroute time for each route.
    preferred_machine: str

    @model_validator(mode="after")
    def valid_routes(self):
        if not self.durations or any(type(v) is not int or v <= 0 for v in self.durations.values()):
            raise ValueError("Every eligible machine needs a positive integer duration")
        if self.preferred_machine not in self.durations:
            raise ValueError("Preferred machine must be eligible")
        return self


class Order(Model):
    id: str
    release: int = Field(default=0, ge=0)
    due: int = Field(gt=0)
    priority: int = Field(default=1, ge=1)
    operations: list[Operation] = Field(min_length=1)


class Scenario(Model):
    name: str
    description: str
    synthetic: Literal[True] = True
    machines: list[str] = Field(min_length=1)
    orders: list[Order] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_graph(self):
        ids = [op.id for order in self.orders for op in order.operations]
        if len(ids) != len(set(ids)):
            raise ValueError("Operation IDs must be unique")
        if len({o.id for o in self.orders}) != len(self.orders):
            raise ValueError("Order IDs must be unique")
        if len(set(self.machines)) != len(self.machines):
            raise ValueError("Machine IDs must be unique")
        if any(set(op.durations) - set(self.machines) for o in self.orders for op in o.operations):
            raise ValueError("Unknown eligible machine")
        return self

    @property
    def operations(self) -> dict[str, Operation]:
        return {op.id: op for order in self.orders for op in order.operations}


class Progress(Model):
    machine: str
    started_at: int = Field(ge=0)
    worked: int = Field(ge=0)
    completed_at: int | None = Field(default=None, ge=0)


class Snapshot(Model):
    now: int = Field(default=0, ge=0)
    progress: dict[str, Progress] = Field(default_factory=dict)
    available_at: dict[str, int] = Field(default_factory=dict)


class Assignment(Model):
    operation: str
    machine: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def positive_span(self):
        if self.end <= self.start:
            raise ValueError("End must follow start")
        return self


class Plan(Model):
    assignments: list[Assignment]
    policy: str
    solver_status: str
    solver_seconds: float = 0.0
    objective: float | None = None
    objective_bound: float | None = None

    @property
    def by_operation(self) -> dict[str, Assignment]:
        return {a.operation: a for a in self.assignments}


class Incident(Model):
    """A current published estimate, never a hidden actual completion time."""

    machine: str
    observed_at: int = Field(ge=0)
    estimated_repair_at: int = Field(gt=0)
    uncertainty_minutes: int = Field(default=0, ge=0)
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def future_repair(self):
        if self.estimated_repair_at <= self.observed_at:
            raise ValueError("Repair estimate must be later than observation time")
        return self


def apply_incident(scenario: Scenario, snapshot: Snapshot, incident: Incident) -> Snapshot:
    if incident.machine not in scenario.machines:
        raise ValueError("Incident references an unknown machine")
    if incident.observed_at != snapshot.now:
        raise ValueError("Advance the simulator to the incident time first")
    return snapshot.model_copy(update={
        "available_at": {**snapshot.available_at, incident.machine: incident.estimated_repair_at}
    })


def check_snapshot(scenario: Scenario, snapshot: Snapshot) -> None:
    ops = scenario.operations
    active_machines: set[str] = set()
    if set(snapshot.available_at) - set(scenario.machines):
        raise ValueError("Unknown machine in availability map")
    for op_id, record in snapshot.progress.items():
        if op_id not in ops or record.machine not in ops[op_id].durations:
            raise ValueError("Unknown operation or ineligible machine in progress")
        duration = ops[op_id].durations[record.machine]
        if record.started_at > snapshot.now or record.worked > duration:
            raise ValueError("Invalid progress timing")
        if record.completed_at is not None:
            if not record.started_at < record.completed_at <= snapshot.now or record.worked != duration:
                raise ValueError("Invalid completion record")
        else:
            if record.worked >= duration or record.machine in active_machines:
                raise ValueError("Invalid active operation or duplicate machine occupancy")
            active_machines.add(record.machine)
    for order in scenario.orders:
        for i, op in enumerate(order.operations):
            record = snapshot.progress.get(op.id)
            if record and record.started_at < order.release:
                raise ValueError("Operation started before release")
            if record and i:
                predecessor = snapshot.progress.get(order.operations[i - 1].id)
                if predecessor is None or predecessor.completed_at is None or predecessor.completed_at > record.started_at:
                    raise ValueError("Progress violates operation precedence")
