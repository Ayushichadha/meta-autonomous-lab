# Evaluation methodology and findings

## Frozen test contracts

Version 1 was frozen at source revision `4191c52`, seeds 10000-10019, with Meta cases 10000-10002 selected before execution. Version 2 was frozen at `c476216`, seeds 11000-11019, with Meta cases 11000-11002 preselected. Both use the frozen `generate_case_v1` synthetic generator, 0.5-second single-worker solver caps, 30-minute ticks, six model requests per decision, and twelve per episode.

Each case has eight orders and four machines, a CNC outage, an updated repair estimate, an overlapping inspection-station outage, and confirmed repairs. Processing times and due dates vary by seed; alternate machining overhead remains explicit. The same exogenous trace is replayed across policies. All policies receive the same observations at the same timestamps; private future events do not reach the model.

Each policy shares the initial schedule. At every checkpoint, a preserve-order/routing feasibility guard updates the plan for actual progress and observed downtime. Optional policy changes are measured relative to this guard. Guard changes and runtime are reported separately. This avoids counting physically necessary delay propagation as an intelligent intervention.

## Policies and compute fairness

- Preserve: feasibility guards only.
- Always replan: reroute-enabled CP-SAT at each operational update.
- Fixed interval: reroute-enabled CP-SAT on 30-minute ticks, with immediate outage guards.
- Solver selection: all three candidate actions and the best nominal combined objective at each update.
- Meta: bounded tool-using supervision, selecting among independently validated experiments.

The combined objective is `100 * weighted tardiness + queued start shifts + 30 * reroutes + makespan`. Metrics are reported separately. Strong selection and Meta can use three experiment solves per decision; simpler policies consume less compute. All artifact runtimes and solve counts are retained, rather than claiming actual compute consumption is equal.

Candidate forecast trials use published repair estimates. The early/nominal/late stress tests vary only the focus outage; other outages remain nominal. They do not expose actual repair completion. Physical execution instead waits for confirmed repair events. Only realized completed-order times determine final tardiness.

## Metrics

Priority-weighted tardiness is the sum of order priority times minutes past its due date. Also recorded: on-time orders, makespan, cumulative optional reroute transitions, queued-start shifts, changed operations, actual plan revisions, guard shifts, enacted feasibility violations, policy failures, solver calls/runtime, model calls/tokens/cost estimates, and wall time.

A revision requires an actual change in queued starts or routes. Selecting a policy named `reroute` that returns the same plan is PERSIST. Repeated reversals count repeatedly. This is a plan-instability measure, not a monetary cost model.

The reported standard deviation is population SD across the stated cases. No statistical significance or generalization claim is made from three live Meta cases.

## Version 1: retained failure evidence

All 80 conventional runs completed. All three Meta cases reached the episode request budget and used a validated preserve fallback. Their status is `completed_with_failures`; fallback outcomes are not successful autonomous decisions.

The observed engineering problem was redundant baseline-request turns and large repeated evidence payloads. Version 2 preloads the mandatory baseline, retains its experiment accounting, sends compact evidence while preserving full artifacts, and reserves the final available model turn for selecting a tested candidate. No objective weights were tuned from outcomes. New seeds were used for version 2.

## Version 2 findings

All 80 conventional runs and three live Meta runs completed without fallback. The full conventional table and paired Meta subset are in the README and normalized summary.

Meta matched the strong conventional selector on seeds 11001 and 11002. On 11000 it made one fewer revision and fewer queued-start shifts but incurred 12 additional priority-weighted delay minutes. Across the paired three cases, mean weighted delay was 550.33 for Meta and 546.33 for the strong selector. This does not establish an optimization advantage.

The working capability demonstrated is a bounded, real-model experimental supervisor that can test alternatives, select an independently validated schedule, and reconsider it as the physical simulation evolves. Its usefulness beyond these conventional methods remains an empirical question.

## Artifact integrity and reproduction

`results/evaluation-v1/summary.json` and `results/evaluation-v2/summary.json` contain every attempted policy/scenario row, failures, aggregate variability, and the exact paired rows. Each row points to its `.json.gz` episode. Offline tests verify every distributed episode matches its summary metrics/status/revision. The configuration hash and source revision are embedded.

Normalized simulation and model-tool records are public. Credentials, spending-ledger files, raw HTTP responses, and hidden model reasoning are excluded. The local ledger uses a $1 allowance and retains unknown-usage reservations. Reported token charges for all development work through this evaluation were approximately $0.6633; an additional conservative $0.0099 reservation remains for an unsuccessful request with no usage report. These are not an account balance or an authoritative invoice.

## Limits

Synthetic, small instances; no real telemetry or industrial validation; known processing durations; failures independent of policy; no material shortages, scrap/rework, workforce or complex setup modelling; limited discrete recovery actions; current-outage-only stress variation; small Meta coverage; model sampling and wall-time solver variability. The live backend is deployed separately from these frozen evaluations; submission-video production remains packaging work.
