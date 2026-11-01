# Factory Recovery Lab

An autonomous engineering experiment lab being developed for the Meta Global AI Developer Hackathon 2026, Indie Developer track, under the **Push the Frontier** problem statement.

**Status: first implementation, October 31, 2026.** The local simulator, constraint-checked scheduler, conventional recovery experiments, and browser dashboard work. A bounded Meta-model tool loop is implemented; a live Muse Spark 1.3 tool-call check and one complete factory decision succeeded on November 1. These are synthetic development experiments, not real-factory validation or evidence of AI superiority. The repository retains its original name, `meta-autonomous-lab`.

## Run locally

Requires Python 3.11 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
factory-lab demo
factory-lab serve
python -m pytest
```

The demo writes `runs/demo.json` and compares preserving queue/routing, rescheduling queued work, and allowing eligible reroutes. It uses no AI and spends no API credits. Outputs include forecasts under three published repair-time assumptions, actual constraint-check results, solver status, and per-order completion times. `runs/` is ignored by Git.

Open `http://127.0.0.1:8765` after running `factory-lab serve`. The local dashboard runs real solver/simulation experiments, displays schedule timelines and per-order outcomes, and exports run JSON. The live Meta button requires a configured local key and uses credits. The dashboard binds only to loopback; it is a development server, not a public deployment.

On macOS with Python 3.13, Finder-hidden editable `.pth` files may be skipped by Python. If an editable install succeeds but imports fail, use the source directly:

```bash
PYTHONPATH=src .venv/bin/python -m factory_lab.cli serve
```

The test configuration includes the source directory explicitly. A normal non-editable `python -m pip install .` is another option, but source changes then require reinstalling.

## Connect the Meta model

Copy `.env.example` to `.env` and add your key locally. `.env` is ignored by Git. The following commands use provider credits:

```bash
factory-lab smoke --provider meta
factory-lab agent --provider meta
```

`smoke` verifies the configured model is in the provider catalog and returns a real function call. `agent` lets the model choose bounded experiments and select a validated plan, saving `runs/agent.json`. Missing credentials or failed model requests produce an error; they never silently switch to a simulated model. Meta Model API is the default and uses `META_API_KEY` or `MODEL_API_KEY`. It draws from the activated $150 Meta credits. Partner credit applications are pending; use `--provider baseten` only when its account is ready.

Meta token cost is estimated from reported usage and standard prices checked November 1, 2026. The local `runs/meta-usage.jsonl` ledger enforces a conservative $1 development allowance; this is not a provider-side billing limit. Requests are capped at six per client, prompts at 60,000 serialized bytes, and output at 1,024 tokens by default. Unknown usage retains a reservation. No automatic network retries are made. The first complete live decision cost approximately $0.0199 in reported token usage; see `examples/first-meta-run.summary.json`.

## Implementation boundaries

- The current demonstration covers one outage decision. Sequential repair updates, fixed-interval policy comparisons, natural-language event extraction, and held-out agent evaluation remain to be built.
- Started work retains its machine. Interrupted work pauses and resumes after repair; queued eligible work can be rerouted with the scenario's explicit duration overhead.
- The scheduling objective is `100 * priority-weighted tardiness + queued start-time shifts + 30 * rerouted operations + makespan`. Displayed metrics remain separate.
- Uncertainty trials replay a plan at the early, nominal, and late published repair estimates. They are not a probability model or a robustness guarantee.
- `factory-lab development-batch --count 5` runs seeded development cases, explicitly labelled as development data.

## Proposed direction

When a machine fails or a repair estimate changes, a Meta-model-powered agent interprets the operational update, tests recovery plans in a simulated factory, and decides whether to preserve production commitments or revise them. A constraint solver constructs feasible schedules; simulation measures their outcomes.

The intended contribution is evidence-based experimental supervision: measure whether the agent's decisions improve outcomes beyond conventional search and strong fixed revision schedules.

The initial user is a production planner at a small component manufacturer. The MVP covers one synthetic shop, machine outages, repair-time updates, and bounded recovery actions. Satellite-component manufacturing is a possible later scenario using the same engine after the core demo and evaluation are complete. See the [factory MVP specification](docs/FACTORY_MVP.md).

## Research foundations

- [When to Re-Plan: Subgoal Persistence in Hierarchical Latent Reasoning](https://arxiv.org/abs/2606.03741), Ayushi Chadha; accepted at the ICML 2026 Workshop on Compositional Learning.
- [A Score Is Not a Policy: Measuring the Value of Adaptive Revision](https://arxiv.org/abs/2609.00874), Ayushi Chadha; preprint, under review.

These are prior research, not hackathon contributions. Their results concern hierarchical latent reasoning; transfer to engineering experiment agents is a hypothesis to test.

## Proposed infrastructure

- Python and SimPy for discrete-event simulation; OR-Tools CP-SAT for scheduling; a separate constraint checker for plan validation.
- Muse Spark 1.3 through Meta Model API is the initial primary experiment manager, using activated Meta credits.
- Muse Spark Open through Baseten is a later comparison candidate after partner credit approval. The participant guide specifies `meta-models/muse-spark-open-1026`; access and tool behavior still need verification.
- Modal for experiment batches or remote compute when needed.
- Meta Model API for comparison with hosted Muse models.

Provider access is available to the developer. Endpoint functionality, rate limits, and partner credit balances have not been verified by this project.

## Evaluation commitments

- Use explicit objectives and constraints, with measurements calculated by tools.
- Compare against a suitable conventional search method and fixed revision schedules.
- Separate development scenarios from held-out evaluation conditions.
- Match experiment budgets and report model calls, cost, and wall-clock time.
- Retain failed trials and report limitations and negative results.
- Treat simulator results as simulation evidence, not validation on physical hardware.

## Hackathon contributions

This repository starts on October 30, 2026. Its initial contribution is planning documentation. Implementation, evaluation, interface, and demo work will be identified as they are developed during the event. Any reused code or assets will be attributed with their source and license.

See [the development plan](docs/PLAN.md). Submission materials and setup instructions will be added after implementation.
