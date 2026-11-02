# Three-minute demonstration

Use the actual recorded Meta episode bundled with the repository. Keep its **RECORDED META EXECUTION** badge visible. This is a real provider run, not scripted model behavior, and replaying it uses no credits. The console also supports fresh conventional execution and fresh paid Meta execution.

## 0:00-0:25 — The operating problem

Open the console, select the recorded run, and start at minute 0. Show four machines, eight orders, the valid schedule, and queued/active states.

Suggested narration: "A production plan makes commitments. When a machine fails, changing everything can be expensive—but keeping an obsolete plan can miss deliveries. We built an agent that tests recovery options against a simulated factory before intervening."

## 0:25-1:10 — Unexpected outage and experiments

Select minute 25. CNC-A is down; interrupted work is retained. Show the current observation, routing eligibility, and live-run hypotheses in the recorded trace. Compare preserve, reorder, and reroute forecasts. Highlight the selected rerouting plan and independent constraint validation.

Keep forecast labels visible. Explain that the model chooses experiments and actions, the solver constructs plans, and the simulator measures them.

## 1:10-1:45 — New evidence and a real PERSIST decision

Select minute 55. Maintenance changes its estimate. Show that the three tested candidates now have identical forecasts and no queued-plan change is selected. The recorded Meta decision is PERSIST.

Suggested narration: "New information does not automatically justify a new plan. At this observation, the experiments offered no better alternative, so the supervisor preserved the existing commitments."

The main decision statement is calculated from tool metrics. Expand the model-generated rationale only as supplemental text; its narrative is not independently proven.

## 1:45-2:10 — Confirmed repair and continued production

Select minute 118, then completed execution. Show resumed progress, the revised plan, and the distinction between solid executed work and translucent forecasts. Final delivery metrics come from realized simulation outcomes, not the original forecast.

## 2:10-2:45 — Comparisons and honest evidence

Show the frozen evaluation: 20 cases for four conventional policies, and the three predeclared paired Meta cases. Version 2 completed without fallback; version 1 budget failures remain public.

State the actual result: Meta matched the strong selector on two paired cases; on one it traded fewer plan changes for higher delay. Do not claim better scheduling or industrial performance.

## 2:45-3:00 — Contribution and reproducibility

Show the architecture, public code, source/configuration hashes, and new hackathon contributions. Connect the question of when to revise to the author's prior research, while making clear that manufacturing transfer is newly tested.

Suggested closing: "The contribution is a working, constrained experimentation loop with explicit evidence and failure handling. The next research question is when model supervision adds value beyond strong conventional control."

## Before recording

- Run the offline tests and a fresh conventional episode.
- Verify that the recorded artifact, evaluation tables, and source links load from a clean checkout.
- Keep simulated/recorded/forecast/realized labels visible.
- No invented percentage improvements, model capabilities, customer claims, or telemetry.
- The console defaults to conventional new executions. Choose paid Meta execution deliberately; do not rerun inference just to capture an unchanged screen.
- Record the video, verify its public accessibility and duration, and link it from the submission. A finished video and public hosting are not yet produced by this repository.

## Maintenance-note alternative (stronger interaction demo)

At minute 55, show the maintenance inbox and choose **Replay verified note · no API**. The actual Meta extraction grounds the delay to a quoted sentence and changes the forecast from minute 120 to 160, not 95. INSPECT availability remains unchanged. The new branch tests preservation, reordering and rerouting, with separate forecasts and realized outcomes. The original recording remains available through **Load recorded Meta run**.

For a live local recording, interpret the same note once, inspect its claims, and explicitly apply it in a new branch. Interpretation uses credits; the conventional branch does not. Public GitHub Pages hosting supports recorded inspection only, with inference controls disabled.
