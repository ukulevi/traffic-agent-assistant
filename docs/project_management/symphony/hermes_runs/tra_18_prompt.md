# Hermes Step 3.7 Flash Oneshot Prompt

Ticket: STWI-SYM-022 / TRA-18
Status: Todo
Priority: P2
Linear: https://linear.app/traffic-agent-assistant/issue/TRA-18/finalize-symphony-automation-evidence-and-release-qa-snapshot

Working directory: C:/Users/PC/Downloads/DADN/traffic-agent-assistant

## Goal

Finalize Symphony automation evidence and release QA snapshot. Review modified/untracked workflow artifacts under `docs/project_management/symphony/**`, group them into one coherent change set, regenerate board/status markdown, verify against current Linear state, and produce a final report. Do not commit yet; only prepare evidence and report.

## Allowed Files

- docs/project_management/symphony/**
- scripts/project_management/symphony_report.py
- scripts/project_management/hermes_runner_bridge.py

## Forbidden Changes

Do not commit, push, update Linear state, restart Symphony, change `project_contract.json`, or edit files outside `Allowed Files`.

## Acceptance Criteria

1. All modified/untracked workflow artifacts under `docs/project_management/symphony/**` are reviewed, grouped, documented as a single coherent change set.
2. Generated `board.md`, `status_report.md`, and Hermes runner artifacts are regenerated and verified against current Linear state.
3. No secrets, `.env`, raw video, private weights, or private data are referenced or committed.
4. The ticket includes a final report with Result, Changed files, Checks, Contract/artifact impact, Risks/blockers, and Recommended next state.

## Exact Checks

Run the following and report pass/fail status:
- python scripts/validation/validate_docs.py
- python -m unittest tests.contracts.test_project_contract
- node --check slides/js/presentation.js
- node --check slides/js/presentation-tools.js
- git diff --check
- python scripts/project_management/symphony_report.py --write-markdown docs/project_management/symphony/board.md
- python scripts/project_management/symphony_report.py --write-markdown docs/project_management/symphony/status_report.md

## Required Final Report

Write a final report at: docs/project_management/symphony/hermes_runs/TRA-18_<timestamp>_report.md

The report must contain exactly:
Result:
Changed files:
Checks:
Contract/artifact impact:
Risks/blockers:
Recommended next state:

## Hard Constraints

- Do not change contract, safety, legal, API semantics, or stack.
- Fail closed on ambiguity, missing evidence, or scope violations.
- Do not read secrets, `.env`, raw video, private weights, or private data.
