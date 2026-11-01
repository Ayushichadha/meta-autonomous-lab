# Sequential prototype validation — November 1, 2026

## Automated checks

41 offline tests pass locally on Python 3.13 / macOS arm64. No unit test uses the real API key or paid inference.

Coverage includes hand-calculated execution, independent invalid-plan rejection, downtime, precedence, eligibility, completed-work immutability, repeated and simultaneous outages, preserved interrupted progress, strict queue replay under delay, hidden-future-information checks, deterministic physical replay, baseline information/configuration equality, malformed/unknown model tool calls, one-request PERSIST, request and experiment limits, provider failure fallback, no automatic retry, echoed-key redaction, local estimated-dollar reservations, and every published episode's agreement with its summary.

JavaScript syntax checks pass for the original interface and the new console. Python compilation and Git whitespace checks pass.

## Real provider checks

Muse Spark 1.3 on Meta Model API passed a real function-calling smoke test, a complete one-decision run, a three-update sequential demo, and the frozen evaluation attempts. Version 1 failures remain published. Version 2's three predeclared cases completed without fallback. These are the actual executions described in EVALUATION.md; no mock inference was substituted.

Development token usage was approximately $0.6633 at published rates, plus a $0.0099 conservative reservation for unreported usage. No further inference was used for console verification. The provider's invoice is authoritative.

## Console checks

- Loads the distributed recorded Meta episode and frozen version 2 evaluation with no paid requests.
- Replays minute 25's REPLAN and minute 55's PERSIST with the actual recorded hypotheses, candidate measurements, and tool trace.
- Displays model rationale separately from metric-calculated evidence.
- A fresh conventional episode completes from the UI with zero model requests and no fallback.
- Changes observation boundaries and candidate previews without modifying the enacted artifact.
- Separates solid executed work from translucent forecast work and labels final realized metrics explicitly.
- Exposes operation progress, paused work, machine queues, scenario results, and all failures.
- Narrow 403-pixel preview has no document overflow; Gantt/table containers intentionally scroll horizontally. Browser logs were clear of warnings and errors in the inspected run.

Only the in-app narrow browser preview was available. The desktop layout is implemented but was not visually inspected at a wide viewport. New live-model progress events are instrumented in the actual request/tool loop; browser verification used conventional execution and recorded Meta data to conserve credits.

## Remaining limits

No real factory telemetry, industrial validation, broad Meta reliability evidence, public deployment, or completed submission video. Baseten/Modal/Fireworks remain unverified/unimplemented as documented. The demo script is ready, and the local application is reproducible from the repository.
