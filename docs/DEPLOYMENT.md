# Hosted backend

The Modal entry point is `deploy/modal_app.py`. It serves the same console and Python backend on one origin, runs CPU-only and scales to zero after 60 idle seconds. It permits one small web container and one execution worker. A shared admission lease permits only one execution at a time. A persistent Volume holds run artifacts and the shared $1 inference reservation ledger. Reservations commit before model requests; if persistence fails, no request is sent. No API key or local `.env` is included in the image.

Requirements: an approved Modal account with usable compute credits, authenticated official Modal CLI, and a named `factory-meta` Secret containing `META_API_KEY`, `META_MODEL=muse-spark-1.3`. No payment method is part of this procedure. Stop if the account requires billing setup.

Install the SDK in the project environment, authenticate with `modal token new`, then deploy with `modal deploy deploy/modal_app.py`. The server resolves its exact deployed hostname through Modal; it does not trust arbitrary forwarded hosts. Use Modal's Secrets dashboard or the SDK; never paste API keys into shell commands, source, browser URLs, or chat. Deployment and uploading the Meta credential require authorization for that destination.

Job states and progress are held in Modal Dict; executions run as detached Modal functions, independently of browser polling and web-container restarts. Durable run artifacts and the inference ledger remain on the Volume. Idle cold starts may take several seconds. Hosted live inference supports Meta episodes. Maintenance-note interpretation remains local; the hosted recorded note workflow is available.

The inference allowance is an application estimate, not a provider billing cap or a cap on Modal compute. Bounded web/worker containers and scale-to-zero reduce compute consumption; confirm remaining Modal credits in the account before launch. The GitHub Pages replay remains available independently.

## Deployment — November 4, 2026

Live URL: https://ayushichadha--factory-recovery-lab-web.us-east.modal.run/ . Deployed to the participant’s approved Modal workspace using its existing $1 credit; no payment method was added. Conventional execution was verified through the public browser. The full offline suite passes 60 tests. The shared inference ledger was seeded from prior development usage, rather than reset at deployment. The original GitHub Pages URL remains the recorded replay.

The first web-thread-based cloud Meta verification stalled; it is not counted as a successful run. The deployment was changed to detached workers with persistent job state and serialized admission. Failed attempts and unknown-usage reservations remain in the ledger.

Detached-worker verification completed successfully on November 4: job `d1dc7820471f4adf`, eight actual Meta requests, estimated token cost $0.0566821, no failure/fallback. The normalized result was saved locally as `runs/hosted-meta-verification.json`. This checks the hosted integration; it is not an additional frozen evaluation claim.
