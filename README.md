# Meta Autonomous Lab

An autonomous engineering experiment lab being developed for the Meta Global AI Developer Hackathon 2026, Indie Developer track, under the **Push the Frontier** problem statement.

**Status: planning.** The name is provisional. No working implementation or performance claims are available yet. The engineering application has not been selected.

## Proposed direction

Given an engineering objective, constraints, and an experiment budget, a Meta-model-powered agent would plan experiments, call simulation and optimization tools, inspect measured outcomes, and decide whether to persist with its current strategy or revise it.

The intended contribution is evidence-based experimental supervision: measure whether the agent's decisions improve outcomes beyond conventional search and strong fixed revision schedules.

Candidate applications include simulated motor control and thermal control. Selection depends on a short feasibility test and the developer's domain preference.

## Research foundations

- [When to Re-Plan: Subgoal Persistence in Hierarchical Latent Reasoning](https://arxiv.org/abs/2606.03741), Ayushi Chadha; accepted at the ICML 2026 Workshop on Compositional Learning.
- [A Score Is Not a Policy: Measuring the Value of Adaptive Revision](https://arxiv.org/abs/2609.00874), Ayushi Chadha; preprint, under review.

These are prior research, not hackathon contributions. Their results concern hierarchical latent reasoning; transfer to engineering experiment agents is a hypothesis to test.

## Proposed infrastructure

- Python for simulations, experiment tools, and evaluation.
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
