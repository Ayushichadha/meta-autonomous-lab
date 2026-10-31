# Factory recovery development plan

Factory recovery was selected on October 31, 2026. The [MVP specification](FACTORY_MVP.md) defines the product, evaluation, and scope boundaries.

## Implementation progress

- Implemented: scenario models, SimPy execution, CP-SAT scheduling, independent schedule validation, pause/resume semantics, three conventional recovery candidates, and repair-uncertainty trials.
- Implemented but not live-verified: bounded model tool loop and Baseten/Meta API clients. Credentials are not yet configured locally.
- Remaining: sequential updates, event extraction, policy-level benchmark, Modal batches, demo-quality interface, and submission assets.

## Confirmed constraints

- Solo participant in the Indie Developer track.
- Preferred problem statement: Push the Frontier.
- Selected concept: autonomous factory recovery lab.
- Python and PyTorch experience; MacBook Air for local development.
- Approximately 5-6 working hours per day.
- Meta Model API credits activated; Baseten and Modal access available.
- Dedicated public repository, with meaningful commits from the beginning.
- Participant-guide deadline: November 4, 2026, 9 PM EST / November 5, 2026, 7:30 AM IST.

## Decisions still open

1. Final model/provider choice following a small tool-use test.
2. UI framework after the simulator proof.
3. Scenario parameters and objective weights, to be frozen before held-out evaluation.

## Proposed milestones

These are planning targets, not completed work.

| Date (IST) | Target |
| --- | --- |
| October 31 | Prove the factory simulator, independent validator, and baseline work; test a real model tool call. |
| November 1 | Complete the recovery loop with structured events, experiments, and recorded decisions. |
| November 2 | Run comparative evaluation and held-out scenarios; build the functional dashboard. |
| November 3 | Refine the interface and demonstration; address failure cases. |
| November 4 | Freeze scope, record the three-minute video, verify public artifacts, and submit with buffer. |

## Feasibility gate

Before investing in presentation, demonstrate a trustworthy simulation, a functioning conventional baseline, and an agent capable of completing the experiment loop. Choose a smaller scope if simulation or integration takes too long. If adaptive supervision does not improve outcomes, investigate and report the evidence rather than claiming an advantage.

## Repository practice

- Make small commits after coherent changes: simulator, baseline, agent tools, evaluation, interface, and demo.
- Record actual development history without backdating commits.
- Stage specific files and inspect staged changes before pushing.
- Keep credentials in local environment variables or provider secret stores.
- Publish curated evaluation artifacts with configurations and seeds; inspect raw provider logs before publication.
- Attribute reused work and distinguish it from new hackathon contributions.

## Prize strategy

Prioritize the main judging rubric: impact (30%), Meta tooling (25%), execution (20%), and demo (25%). Open-weight and agentic bonus awards are potential additional fits under the participant guide, not guaranteed eligibility or outcomes. Do not add features solely to chase additional categories.
