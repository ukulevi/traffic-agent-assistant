# SmartTraffic What-If (STWI)

## Scope and safety

STWI is a 13-week, decision-support MVP for evaluating traffic What-if scenarios. It uses aggregate-only evidence, a GCN-LSTM baseline, a SUMO-trained surrogate, structured legal citations, and a fail-closed Counterfactual Safety Loop. It supports human review only: it does not retain raw video or automatically actuate field equipment.

The MVP covers a functional 20-node network, at most 20 prerecorded/RTSP camera sources, and synthetic aggregate producers for scale tests. `V/C 0.9` is configurable MVP policy, not a legal threshold.

## Source of truth

1. [project_contract.json](./project_contract.json) defines machine-readable contracts, schemas, SLA, and invariants.
2. [DOC-00](./docs/00_STWI_Summary_and_Guidelines.md) defines architecture and project guidance.
3. [DOC-01 to DOC-05](./docs/README.md) define the tier specifications and delivery plan.

Report and slide artifacts are derived from these sources. [docs/archive](./docs/archive/) is historical reference only.

## Local verification

```powershell
python scripts/validation/validate_ci_guardrails.py
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

Use `.agents/skills/stwi-release-qa` before release or handoff. Build `report/main.tex` with XeLaTeX only when technical report artifacts change.

## Repository map

- `src/stwi/`: importable runtime and reusable tooling.
- `scripts/`: thin command-line wrappers grouped by data preparation, training, validation, infrastructure, and demo use.
- `tests/`: contract, tier, integration, frontend, demo, and tooling tests.
- `docs/`, `report/`, `slides/`: public documentation and presentation artifacts.
- `infra/`: production and harness entrypoints.
- `data/manifests/`: versioned, public manifests only.

See [repository structure](./docs/guides/repository_structure.md) for ownership boundaries.

## Public/private boundary

Public commits may contain STWI code, tests, canonical docs, technical report sources, slides, and public manifests. Never commit `.env*`, raw video, datasets, model weights, generated outputs, internship forms, signatures, or internship-report assembly sources. The CI guard validates tracked and staged files and never prints secret values.

## Development and demo runbooks

- [MVP demo runbook](./docs/guides/mvp_demo_runbook.md) for the simulation-first operator demonstration.
- [Dashboard walkthrough](./docs/guides/mvp_dashboard_demo_walkthrough.md) for UI evidence and review flows.
- [Local vision-training runbook](./docs/guides/vision_local_training_runbook.md) for private detector data, validation, and promotion gates.
- [Roboflow MCP guide](./docs/guides/ROBOFLOW_MCP.md) for optional hosted workflow integration. `ROBOFLOW_API_KEY` must come from the environment and is never committed.

## AI agent workflow

[AGENTS.md](./AGENTS.md) and [project-local skills](./.agents/skills/) define implementation, review, and release QA workflows.
