# Sequential twin and comparison contract, version 1

The physical event runner owns the complete exogenous trace. A policy receives only current observations, current incident(s), and past decision summaries. The trace is released in the artifact after execution for reproducibility, never supplied to the model.

## Time and physics

Integer minutes from shift start. At a checkpoint, SimPy completes events and dispatches at that timestamp before applying the external event group. Started work with zero elapsed minutes is consequently retained if its machine fails at the same timestamp. This tie convention is identical for every policy.

An outage blocks a machine until a confirmed `repaired` event. A published estimate affects planning and forecast trials, never physical execution. If the estimate expires while the machine is still down, the public forecasting assumption extends by 30 minutes at the next clock/event checkpoint. This is recorded as `estimate_expired`, not presented as a new maintenance fact.

Job precedence and the submitted machine queue are enforced during replay. No backfilling/overtaking is performed without a new schedule. Interrupted work pauses on its original machine with its progress retained. Completed work is immutable.

All policies receive the same 30-minute clock checkpoints and exogenous observations. They share a mandatory preserve-order/routing feasibility guard at each checkpoint. Guard changes account for execution delays and observed downtime; they are not optional replans. Guard solver runtime and queued start shifts are reported separately.

## Policies

- `preserve`: only the feasibility guard; retain machine routes and queue order.
- `always_replan`: reroute-enabled CP-SAT after each observed operational update, including confirmed repairs and expired estimates.
- `fixed_interval`: reroute-enabled CP-SAT at 30-minute ticks; immediate guards still protect feasibility at intervening disruptions.
- `solver_selection`: test preserve, reschedule, and reroute at each operational update and select the lowest nominal combined objective.
- `meta`: a real Meta model chooses bounded experiments and selects a tested candidate. It can inspect current operations and state a testable hypothesis. Failure or budget exhaustion is recorded and falls back to the validated guard, never a fake model decision.

## Budgets and objective

Common per-solve wall cap: 0.5 seconds in the frozen evaluation configuration. Single worker and fixed solver seed. Record feasible versus proven optimal status; wall-clock-limited solutions need not reproduce exactly across machines.

No policy can alter machine capabilities, durations, priorities, or objective weights. The objective is `100 * priority-weighted tardiness + queued start shifts + 30 * rerouted operations + makespan`. Each metric is also reported separately. The strong selector uses up to three candidate solves per decision, matching the supervisor's maximum experiment count. Simpler baselines deliberately use less compute; actual runtime and solve counts must be reported rather than described as equal compute consumption.

The Meta policy has at most six model calls per decision and twelve per episode. All clients share the local $1 estimated-dollar ledger. There are no automatic API retries. An episode failure preserves available evidence and receives a failure label; fallback outcomes cannot be presented as successful agent results.

## Forecasts versus outcomes

Candidate forecasts assume the current published repair times. Early/nominal/late trials vary only the focus outage; other down machines remain at their nominal estimates. They are representative stress tests, not an exhaustive robustness guarantee or a probability distribution.

Realized metrics come from physical trace execution to completion. Cumulative optional start shifts, reroutes, and changed-operation counts measure transitions relative to the guarded plan at each decision; repeated reversals count repeatedly. A revision is counted only when queued starts or machine routes actually change, not merely because a model selected an action named `reroute`.

## Evaluation separation

Development cases use seeds 0-4 and the hand-authored demo. A separate frozen configuration and seed list will define evaluation cases. Freeze generator, configuration, and code revision before executing them. Report every attempted case, explicit Meta coverage, all failures, variability, and compute costs. Results from a smaller live subset must not be compared with baseline averages over a larger set as if paired.

This is a simulation-based digital twin prototype without real-factory telemetry or validated industrial operating assumptions.
