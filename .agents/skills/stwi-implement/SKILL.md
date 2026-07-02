---
name: stwi-implement
description: Implement STWI code, API, ML/data, RAG, UI, documentation, or architecture changes while preserving project contracts and synchronizing derived artifacts. Use for feature work, bug fixes, refactors, schema/API changes, and implementation-plan tasks in this repository.
---

# STWI Implement

Read AGENTS.md, project_contract.json, and the relevant canonical document before editing.

## Workflow

1. Inspect git status and the files in scope. Preserve unrelated user changes.
2. Classify the change:
   - Data/privacy: DOC-01, report/chapters 4, slides/sections 04, appendix schema.
   - ML/SUMO/surrogate: DOC-02, report/chapters 5, slides/sections 05.
   - RAG/legal/query: DOC-03, report/chapters 6, slides/sections 06.
   - Agent/API/safety: DOC-04, report/chapters 7, slides/sections 03 and 07, API appendix.
   - Timeline/release: DOC-05, report/chapters 8, slides/sections 08, changelog.
3. Check the requested behavior against project_contract.json. If it changes an invariant without explicit user approval, stop and report the decision needed.
4. Implement the smallest coherent change. Validate untrusted input at boundaries and keep every safety, legal, OOD, timeout, and uncertainty failure fail-closed.
5. Add or update tests before weakening any assertion.
6. Update the canonical source first, then synchronize every affected report, slide, appendix, example, and changelog entry.
7. Run the checks required by AGENTS.md (note: slides in `slides/`, report in `report/`). Use $stwi-release-qa for a full artifact pass.
8. Report outcome, files, tests, contract impact, and remaining risk. Do not commit or push unless requested.

## Guardrails

- Keep X[B,12,N,16], M[B,12,N,16], A[N,N], Y[B,6,N,2], feature order, API statuses, SLA, stack, and human approval unchanged unless the user explicitly changes the contract.
- Never add automatic actuation, raw-video retention, raw LLM SQL, or executable candidate actions.
- Never blend retrieved cases into online surrogate input.
- Do not revive legacy deployment technologies named in AGENTS.md.
- Keep Vietnamese user-facing copy concise and operational; keep identifiers in English.