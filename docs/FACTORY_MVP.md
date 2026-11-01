# Factory Recovery Lab: MVP specification

Initial specification recorded October 31, 2026. The core is now implemented; see PLAN.md and EVALUATION.md for actual status, measured outcomes, and remaining limits.

## Product and user

A production planner at a small component manufacturer needs to recover delivery commitments when a machine fails or its repair estimate changes. The agent tests feasible alternatives before changing the production schedule, and records the evidence for preserving or revising commitments.

Proposed pitch: When production breaks, test recovery plans before changing the schedule, and measure whether replanning was worth it.

## Scope and assumptions

- One synthetic shop: two compatible machining stations, one inspection station, one assembly station, and approximately eight orders.
- Explicit operation precedence, machine eligibility, durations, release times, due dates, and order priorities.
- Machine downtime and repair-estimate updates are the initial disruption types.
- Compatibility and rerouting penalties come from scenario data; the agent cannot invent capabilities. Start with fixed per-operation rerouting penalties rather than general sequence-dependent setups.
- Completed work is immutable. Healthy in-progress work remains committed. A faulted operation pauses on its machine and resumes after repair; interrupted work is not silently moved or restarted.
- Policies receive the currently published repair estimate and stated uncertainty. Actual completion times and future events stay hidden until observed.
- Synthetic data is labelled. No real factory telemetry or deployment is claimed.

## Agent workflow

1. Read the observation and operational note.
2. Extract a typed event; validate machine IDs, units, ranges, and source. Ambiguity produces a clarification state, not an invented fact.
3. Inspect affected orders and current commitments.
4. Choose bounded experiments: retain queue order/routing, reschedule eligible queued work, or reroute eligible queued work.
5. Call the solver and simulate candidates across the published uncertainty range.
6. Compare measured delivery performance and disruption; decide PERSIST or REPLAN.
7. Independently validate the selected plan, apply it to the simulated shop, and log the evidence.

Outages always block impossible starts. PERSIST means preserving viable commitments while obeying downtime, not running a failed machine.

The model supplies structured decisions and concise evidence summaries. Simulator outputs supply performance numbers. A deterministic checker rejects invalid plans regardless of model confidence.

## Architecture

- Shared Python domain models for simulator, solver, agent, and validator.
- SimPy for event-based factory execution.
- OR-Tools CP-SAT for scheduling; record time limits and solution status. Do not claim optimality for an unproven feasible solution.
- Primary: Muse Spark 1.3 on Meta Model API, using the activated $150 credits.
- Later candidate after partner credit approval: Muse Spark Open via Baseten; verify the guide's `meta-models/muse-spark-open-1026` endpoint and tool support.
- First verify a real structured-output/tool-use call, then compare hosted Meta models on our task.
- Modal for independent scenario batches when useful, retaining local execution.
- One browser dashboard: factory state, schedule timeline, event feed, candidate comparison, and outcomes. Choose UI framework after the simulator proof.
- Credentials stay server-side and out of Git. Partner balances and endpoint behavior still need verification.

## Evaluation

Hypothesis: evidence-dependent revision improves the trade-off between delivery performance and unnecessary schedule disruption. Prior latent-reasoning findings do not establish this for manufacturing.

Primary metric: priority-weighted tardiness in minutes. Also report on-time orders, rerouted operations, absolute shifts in queued start times, revision count, feasibility violations, model cost, and latency. Display metrics separately; freeze any combined objective weights before evaluation.

Compare using the same shop, objective, solver, feasibility protections, observations, and uncertainty information:

1. Preserve queue order and routing where feasible, delaying blocked work.
2. Reoptimize after each actionable update.
3. Reoptimize at a fixed interval, with the same immediate outage protections.
4. Let the Meta model choose whether and how to revise using bounded experiments.

Use curated development cases and a separate set of at least 20 seeded evaluation scenarios if runtime permits. Freeze policies before the held-out run; replay the same event traces across policies. Report paired outcomes, all evaluated scenarios, and failures.

For revision comparisons, all policies receive the same canonical structured event. Evaluate natural-language extraction separately against manually specified ground truth so parser differences do not masquerade as revision benefits.

Initially cap the agent at three candidate experiments per decision. Record solver time and total compute for every policy. Report model cost separately. No future simulator state is available to candidate generation.

## Three-minute demonstration

- 0:00-0:25: Introduce the planner's problem and original schedule.
- 0:25-0:55: Introduce an outage and show orders at risk.
- 0:55-1:40: Run real model tool calls, compare experiments, and validate recovery.
- 1:40-2:10: Introduce a small repair-estimate update; show evidence for retaining or revising the plan. The decision comes from execution, not a scripted answer.
- 2:10-2:40: Show measured outcomes and held-out comparisons, including limitations.
- 2:40-3:00: Explain Meta's role, research inspiration, and new hackathon work.

No invented improvement percentages. Recorded replays are labelled; the product also supports a working live run.

## Scope gates

First prove a machine outage changes execution, a solver can produce a recovery schedule, an independent checker accepts it, and outcomes reproduce. Then integrate the agent.

If adaptive timing adds no value, report it and reassess the claim. Preserve useful event interpretation and validated recovery features without claiming superior adaptive control.

Defer ERP integrations, physical machine control, model training, elaborate 3D graphics, multi-agent orchestration, and arbitrary factory imports.

Satellite manufacturing, orbital simulation, drones, robotics hardware, ERP integration, and unrelated extensions are excluded from this submission scope.

## Technical references

- https://developers.google.com/optimization/scheduling/job_shop
- https://simpy.readthedocs.io/en/latest/
