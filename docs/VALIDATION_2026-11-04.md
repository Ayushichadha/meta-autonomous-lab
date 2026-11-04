# Validation — November 4, 2026

The offline suite passes **68 tests**, including the existing factory, supervision, billing, branching and publication checks. New image checks reject external URLs, SVG, invalid bytes, mismatched types, excessive dimensions and multiple images per call. They verify that visual reports require review and cannot directly create factory events, and that visual inputs still require a credit reservation.

JavaScript syntax and the static replay build pass. Local browser checks verified play/pause, automatic observation advancement, synthetic-image selection, and correct grounding at minute 55. Live hosted verification details are recorded below after execution.

These are software and integration checks on synthetic examples. They do not establish OCR reliability across images, industrial performance or superior scheduling.

## Hosted visual workflow

The actual public UI completed image reading, explicit review, note validation and a fresh conventional recovery branch. Vision job `e18cb4fa0c1447f6` used Muse Spark 1.3 and cost an estimated $0.0033505; note job `0bd719c3d6d44fd2` cost $0.00289275. The combined interpretation cost was $0.00624325. Branch `4390216c5da14524` completed with no failures and no additional model requests. The checked estimate became minute 160 from a previous estimate of 120; INSPECT stayed unchanged.

The source synthetic image and normalized proof are published in `results/vision/`. The proof records a single integration check, not a vision benchmark. No production image or credential is included. Browser console warnings/errors were empty during the checked interaction. Existing recorded observations and completed work were preserved.

After redeployment, the same demo image reused its durable cached result with no new inference charge. Browser checks confirmed that Interpret is disabled until review is checked and disabled again when review is unchecked.

## Final voice and research extension

The final offline suite passes **80 tests**. New checks cover actual WAV admission, duration-based billing, review-only transcription, bounded configuration, explicit stress assumptions, input immutability, duplicate reuse, rejection of a third distinct trial, and isolation from the old tool profile.

The real Muse Voice Transcribe request processed a 5.262-second synthetic clip; estimated billed cost was $0.00025. Its transcript repeated a word and punctuation. Review corrected those repetitions before a separate Muse Spark extraction validated CNC-A's repair estimate at minute 160. That extraction cost $0.0031685. Original and reviewed text remain published in `results/voice/`. The browser decoded, resampled and previewed the synthetic file locally; no microphone recording of the participant was made. A real microphone permission/capture session was not exercised by automation.

Research job `55f9bcbbd30542aa` completed without fallback: eight real Muse Spark calls, $0.067513 estimated token cost, and two agent-requested stress trials. At minute 25 it tested preserve with an extra 30-minute delay: weighted delay 919 nominal versus 1339 under that assumption. At minute 55 it tested reroute with another 30-minute delay: 409 nominal versus 643. These are forecasts; realized final weighted delay was 403 with two revisions. The run is a synthetic integration demonstration, not a held-out evaluation or evidence of superiority. The original benchmarks are unchanged.

Combined new verification estimate: $0.0709315. Artifacts: `results/research/meta-stress-demo.json`, `results/voice/verified-transcription.json`, and `results/voice/verified-note.json`. The replay can be inspected without further model calls. Hosted allowance is $3 total; local default is $1.
