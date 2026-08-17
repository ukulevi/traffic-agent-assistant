# STWI Repository Structure and Ownership

This repository keeps runtime contracts stable while separating reusable implementation from command-line and presentation artifacts.

## Runtime and entrypoints

- `src/stwi/` contains importable runtime code. `src/stwi/demo/` provides aggregate-only, simulation-first evidence helpers; production API and safety orchestration remain under `src/stwi/t4_orchestrator/`.
- `src/stwi/app.py` is the application entrypoint. Production configuration and deployment guides live under `infra/production/`.
- `scripts/` contains thin wrappers: `data_prep/`, `training/`, `validation/`, `infra/`, `demo/`, and `project_management/`. Reusable logic belongs under `src/stwi/`, not in a wrapper.

## Tests and documentation

- `tests/` mirrors contracts, tiers, frontend, demo, validation, and vision tooling.
- `docs/` contains canonical specifications, guides, operations, and `project_management/` evidence. `docs/archive/` and `docs/superpowers/` are historical/audit material only.
- `report/` and `slides/` contain public technical artifacts derived from canonical documents. Slides load sections through `slides/js/presentation.js`.

## Data and release boundaries

- `data/manifests/` may contain public, versioned manifests.
- `data/external/`, `data/quarantine/`, `data/derived/private/`, raw media, model weights, and generated output are local only.
- Local internship assembly tooling, internship forms, signatures, and internship report sources are excluded from the public repository.
- `tmp/`, `output/`, build caches, PDFs, logs, and render scratch output must be regenerated locally and must not be committed.

## Refactor policy

Large API or orchestrator splits are deferred while they overlap an active product feature. Small contract-preserving extractions may proceed only with focused tests and synchronized documentation.
