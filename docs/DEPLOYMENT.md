# Hosted backend

The Modal entry point is `deploy/modal_app.py`. It serves the same console and Python backend on one origin, runs CPU-only, scales to zero, and permits only one container. A persistent Volume holds run artifacts and the shared $1 inference reservation ledger. Reservations commit before model requests; if persistence fails, no request is sent. No API key or local `.env` is included in the image.

Requirements: an approved Modal account with usable compute credits, authenticated official Modal CLI, and a named `factory-meta` Secret containing `META_API_KEY`, `META_MODEL=muse-spark-1.3`. No payment method is part of this procedure. Stop if the account requires billing setup.

Install the SDK in the project environment, authenticate with `modal token new`, then deploy with `modal deploy deploy/modal_app.py`. The server resolves its exact deployed hostname through Modal; it does not trust arbitrary forwarded hosts. Use Modal's Secrets dashboard or the SDK; never paste API keys into shell commands, source, browser URLs, or chat. Deployment and uploading the Meta credential require authorization for that destination.

Verify the public console, a fresh conventional episode, one deliberately paid Meta execution, and the durable ledger after restart before supplying the URL to judges. This entry point is prepared but does not itself prove deployment has completed. Idle cold starts may take several seconds. In-memory job handles expire when the container shuts down; durable run artifacts remain on the Volume.

The inference allowance is an application estimate, not a provider billing cap or a cap on Modal compute. One container and scale-to-zero reduce compute consumption; confirm remaining Modal credits in the account before launch. The GitHub Pages replay remains available independently.
