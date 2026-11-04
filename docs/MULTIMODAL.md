# Visual evidence and interactive recovery

Muse Spark 1.3 image understanding is integrated through Meta Chat Completions using a text/image content array. The supervisor and image reader use the same server-side Meta API connection. No GPU model deployment is needed.

## Demonstration

1. Open the live hosted console and choose **Load synthetic board · no API**. This selects the recorded observation at minute 55 and creates a clearly labelled synthetic maintenance image.
2. Choose **Read image with Meta · uses API**. A detached worker transcribes visible evidence and reports uncertainty. Reading the image never changes the factory.
3. Compare the image with the editable transcription, correct any errors, then confirm the review checkbox. The resulting text is now an operator report; independent code cannot establish whether the visual transcription is true.
4. Choose **Interpret & validate · uses API**. Meta extracts typed claims. Deterministic checks enforce exact text quotations, known machines, current outage consistency and explicit time semantics. Ambiguous information requires clarification.
5. Choose **Apply in new branch · no API**, or deliberately choose the Meta supervisor. The update is revalidated against its exact source observation. Completed work and the original execution remain intact.
6. Use **Play shift**, pause, restart and speed controls to inspect production progress. Playback advances recorded observation frames, not a continuously recomputed physical simulation. It makes no inference calls.

For the synthetic board, CNC-A's previous estimate is minute 120. An additional 40-minute delay becomes minute 160; unchanged INSPECT availability causes no state change. These expectations are the demonstration case, not hardcoded model output.

## Input and cost boundaries

The browser accepts PNG/JPEG up to 5 MB, resizes to a maximum 1400-pixel side, strips metadata through canvas encoding and enforces a smaller transport limit. The server decodes and verifies image type, still-image format, dimensions and a maximum 512,000 decoded bytes. External URLs and SVG are rejected. User uploads are sent to Meta only after explicit Read image action. Source images are not written to the application result artifacts; cloud invocation and provider handling are separate services.

Only one image is allowed per call. Text still has the original prompt limit. The credit guard reserves an additional conservative 32,768 visual input-token allowance, then records reported usage. This is an application estimate, not a billing guarantee. No automatic retries occur. Cloud image and note results are cached by content, model and relevant state, so an identical analysis can be reused without inference. A shared admission lease serializes image, note and episode jobs.

The progress strip reflects actual worker events and tool callbacks. Forecast, realized outcome, synthetic data and recorded execution labels remain visible. This feature does not diagnose mechanical damage from photographs or prove factory-state truth from an alarm panel.

Official API reference: https://dev.meta.ai/docs/image-understanding .
