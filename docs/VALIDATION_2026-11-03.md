# Validation — November 3, 2026

Source tested: b056967 (maintenance-note recovery and public replay).

`PYTHONPATH=src .venv/bin/python -m pytest -q`: **56 tests passed** locally. The same source passed GitHub Actions on Python 3.12: https://github.com/Ayushichadha/meta-autonomous-lab/actions/runs/41419659076 . Test source and the CI workflow are committed; generated pytest caches and local logs are not needed in Git.

Coverage added in this milestone includes maintenance-note quote grounding, relative/absolute/delayed estimates, clarification on missing information, unknown-machine rejection, negated/future repair rejection, atomic conflict rejection, independent branch revalidation, source immutability, completed-work preservation, and static-publication allowlisting.

## Fresh offline examples

Re-executed the bundled synthetic outage/update/repair scenario with three conventional policies. All completed with zero policy failures, zero feasibility violations and zero model requests. These examples are a functionality check, not an additional benchmark or evidence of Meta superiority.

| Policy | Realized priority-weighted delay (minutes) | Orders on time | Optional revisions |
| --- | ---: | ---: | ---: |
| Preserve | 989 | 1/8 | 0 |
| Always replan | 403 | 2/8 | 2 |
| Solver selection | 403 | 2/8 | 2 |

Reproduce with `PYTHONPATH=src python -m factory_lab.cli episode --policy POLICY --output runs/example-POLICY.json`. Local artifacts from this check are under `runs/examples-2026-11-03/` and ignored by Git.

The GitHub Pages site is read-only recorded inspection. New executions require the local server: `PYTHONPATH=src python -m factory_lab.cli serve`. This is separate from test success: passing tests does not establish industrial validity or model superiority.
