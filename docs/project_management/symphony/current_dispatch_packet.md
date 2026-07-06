# Current Dispatch Packet

## Target Issue

- **ID:** STWI-SYM-020
- **Linear:** TRA-16
- **Lane:** Orchestrator/API/Release
- **Status:** In Progress
- **Priority:** P1

## Overview

Document fail-closed resilience policy for dependency failures.

## Context Files

- `project_contract.json`
- `docs/04_AI_Agent_Orchestrator_CF_VLA.md`
- `docs/project_management/symphony/roadmap_intelligence_2026-07-03.md`
- `tests/t4_orchestrator/`

## Allowed Files

- `docs/04_AI_Agent_Orchestrator_CF_VLA.md`

## Acceptance Criteria

1. Retries, timeout, circuit-breaker-style behavior, and dependency failure classes map to `needs_review`, `failed`, or `expired`.
2. No runtime path returns an executable action after tool, RAG, TimescaleDB, Qdrant, Celery, Redis, or model failure.
3. The rejected fail-open wording is replaced with an explicit fail-closed policy and focused tests are identified.

## Next Action

Write the policy and identify the smallest tests needed before any runtime hardening issue.

## Exact Checks

Run the following before claiming completion:
```powershell
python scripts/validation/validate_docs.py
python -m unittest discover -s tests/t4_orchestrator
git diff --check
```
