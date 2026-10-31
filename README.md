# Factory Recovery Lab

An autonomous engineering experiment lab being developed for the Meta Global AI Developer Hackathon 2026, Indie Developer track, under the **Push the Frontier** problem statement.

**Status: planning; factory recovery selected October 31, 2026.** No working implementation or performance claims are available yet. The repository retains its original name, `meta-autonomous-lab`.

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
- Muse Spark Open through Baseten as a candidate experiment manager. The participant guide specifies `meta-models/muse-spark-open-1026`; availability and tool behavior must be verified before implementation.
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
