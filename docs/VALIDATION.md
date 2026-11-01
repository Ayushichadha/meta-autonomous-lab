# First implementation validation: October 31, 2026

This is development validation, not a held-out benchmark or a claim of model benefit.

## Automated checks

18 tests pass locally on Python 3.13 / macOS arm64. Checks cover independent rejection of invalid schedules, hand-calculated execution outcomes, observation-boundary completions, incremental replay, pause/resume without lost progress, immutable completed work, routing/queue preservation, and separation of repair assumptions from physical replay outcomes.

Agent protocol tests use an explicitly scripted fixture, not a real model. They check rejection of untested selections, unknown tools, skipped baselines, duplicate experiment caching, and request-budget exhaustion. Missing credentials are checked without network calls.

Five seeded development shops each execute all three conventional recovery candidates without reported plan constraint violations. These cases are used during development and must not be relabelled as held-out evaluation.

## Default synthetic outage

At minute 25, CNC-A becomes unavailable with published repair estimate minute 115 (+/-20 minutes). The healthy forecast has eight on-time orders. With the outage, nominal forecasts are:

| Recovery action | Priority-weighted delay (minutes) | On-time orders | Rerouted operations | Queued start shifts (minutes) |
| --- | ---: | ---: | ---: | ---: |
| Preserve queue/routing | 919 | 1/8 | 0 | 1501 |
| Reschedule queue | 681 | 4/8 | 0 | 997 |
| Allow eligible reroutes | 401 | 2/8 | 3 | 913 |

These numbers come from one synthetic development scenario. The lowest weighted delay does not produce the largest count of on-time orders. They compare conventional candidates, not an AI policy with conventional methods. Exact schedules can vary with solver versions and time limits.

Reproduce with `factory-lab demo`. The JSON output contains scenario inputs, observations, candidate plans, solver status, objective bounds, independent validation output, and repair-assumption trial results.

## Browser checks

- Default outage runs and populates machine state, candidates, timeline, and order outcomes.
- Selecting a different candidate updates the schedule and delivery table.
- Repair times preceding the outage are rejected.
- An alternate CNC-B outage produces different recovery results.
- Narrow-screen layout was inspected; horizontal document overflow was fixed. Timelines intentionally retain a horizontally scrollable minimum width.
- Browser logs showed no warnings or errors during the inspected run.
- JavaScript syntax and Python compilation checks pass.

## Not yet verified

Update November 1: Meta tool calling and one complete recovery decision are live-verified; token-cost estimation uses published standard rates. See `examples/first-meta-run.summary.json`. Baseten, sequential-update policies, held-out performance, Modal, real factory assumptions, and deployment remain unverified. No API key is included in this repository.
