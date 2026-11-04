# Spoken reports and agent-designed stress tests

## Meta tooling and its purpose

- Muse Spark 1.3: structured recovery tool calls, visual evidence reading and typed maintenance claims.
- Muse Voice Transcribe 1.0: short maintenance dictation using the dedicated `/v1/asr/transcribe` endpoint. This is a separate Meta model, not browser speech recognition.
- `stress_test_plan`: an application tool called by Muse Spark to replay a tested candidate with an additional 15, 30 or 60 minutes of repair delay. The model chooses the candidate, assumption and hypothesis. SimPy supplies the measurements.

## Voice workflow

Record or upload up to 20 seconds. The browser decodes and converts the clip to mono 24 kHz, 16-bit PCM WAV and lets the user listen before submitting it. Microphone capture starts only on an explicit Record action and stops after 20 seconds or an explicit Stop. The API key stays server-side. Transcription is a detached, cached cloud job. A transcript must be reviewed before typed note validation and explicit branch application; audio does not create events by itself.

Server admission validates actual WAV encoding, duration, channel count, sample width, rate and byte bounds before any request. A shared persistent ledger reserves a conservative audio-duration amount before the call and records returned processed duration. Pricing checked November 4: $0.18/hour, metered in whole seconds. Unknown usage retains a reservation; no automatic retries.

Reference: https://dev.meta.ai/docs/speech-to-text and https://dev.meta.ai/docs/pricing-rate-limits .

The synthetic voice example is generated with macOS's built-in voice; it is not a real operator recording. Its real Meta transcript is published alongside it. The observed transcript contains a repeated word and punctuation, so this example must not be described as perfect ASR. Operator review exists to catch such errors. A single clip is an integration check, not an accuracy benchmark.

## Research tool profile

The live hosted Meta supervisor exposes the additional stress tool. To explicitly ask it to investigate, select Meta in New execution and check **Ask Meta to investigate late-repair risk**. That request is presented once, at the first observed outage. It does not supply future events or dictate a resulting plan.

Only an already tested, independently validated plan can be probed. The extra-delay choices are bounded; the tool cannot change capabilities, priorities, objective weights, processing times or schedule assignments. At most two distinct trials are executed per decision. Repeated identical requests reuse results. The original three-candidate solve cap and six-request decision/twelve-request episode limits remain in place. Extra simulation calls are reported separately, with nominal and delayed weighted tardiness shown in the console.

These trials are counterfactual forecasts, not probability estimates, real repair observations or robustness guarantees. Their purpose is to make investigation an actual decision about what evidence to obtain.

Frozen evaluation versions 1 and 2 retain their earlier protocol and results. The new profile is labelled `bounded_stress_v3` in live decision artifacts. Its live demonstration is not a new held-out evaluation and does not establish superiority over the conventional selector. CLI/evaluation defaults retain the older tool set unless explicitly enabled in code; the local UI enables the research tools when the investigation checkbox is selected.

The hosted Meta guard is now $3 total against existing Meta credits, including historical usage and ASR. Local default remains $1. This application estimate does not cap account-wide billing or Modal compute.
