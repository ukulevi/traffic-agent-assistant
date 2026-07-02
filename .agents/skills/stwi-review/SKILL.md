---
name: stwi-review
description: Review STWI implementation plans, code changes, specifications, APIs, ML/data pipelines, RAG/legal behavior, UI, CI, or release artifacts for correctness, necessity, safety, privacy, and contract drift. Use for review, audit, readiness assessment, and pre-merge checks.
---

# STWI Review

Review read-only unless the user also asks for fixes.

## Workflow

1. Read AGENTS.md, project_contract.json, and the canonical document for the changed subsystem.
2. Inspect git status, diff, tests, and generated artifacts. Separate pre-existing changes from the reviewed change.
3. Review in this priority order:
   - P0: automatic actuation, privacy/raw video, unsafe SQL, missing human approval, fail-open paths.
   - P1: tensor/feature/API/status/SLA/stack drift; leakage; uncalibrated uncertainty; invalid or expired citations.
   - P2: functional correctness, error handling, idempotency, async job/SSE behavior, observability, and test gaps.
   - P3: maintainability, accessibility, artifact synchronization, and documentation clarity.
4. For plans, challenge necessity, dependency order, 13-week feasibility, acceptance criteria, ownership, and claims unsupported by benchmarks.
5. For ML/data, verify chronological split, scenario-family isolation, scaler fit on train only, calibration on validation, and fixed node order.
6. For RAG/query, verify structured citations, effective-date filtering, prompt-injection isolation, typed query validation, parameter binding, allowlists, and read-only database access.
7. For UI/API, verify terminal states, needs_review semantics, visible uncertainty/citations, keyboard access, and no implication of automatic approval.
8. Run targeted checks when useful. Do not claim a check passed without command evidence.

## Findings format

List findings before the summary. For each finding include:

- Severity P0 to P3 and a short title.
- Exact file and tight line range.
- Concrete failure mode and affected user or contract.
- Minimal corrective direction.

Do not invent findings to fill categories. If there are no actionable findings, say so and list residual test or evidence gaps.