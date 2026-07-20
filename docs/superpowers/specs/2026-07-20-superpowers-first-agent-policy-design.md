# Superpowers-First Agent Policy Design

## Goal

Make Superpowers the mandatory process layer for every agent that works in this
repository, while retaining the project-local STWI skills as the required
domain layer for implementation, review, and release QA.

## Scope

The policy applies to Codex, Hermes/Symphony, Claude, Gemini, and any future
agent that reads repository instructions. It governs repository work only; it
does not install plugins, transmit source code, alter runtime contracts, or
change product behavior.

## Decision

Adopt this execution order for all repository work:

```text
using-superpowers
→ relevant Superpowers process skill
→ relevant STWI domain skill
→ verification-before-completion
→ stwi-release-qa when the change requires release-level validation
```

`using-superpowers` is the first mandatory skill for a new task. The process
skill is selected before any file inspection, question, plan, code edit, or
test command. The STWI skill is then selected by subsystem and work type.

## Routing Rules

| Work | Required Superpowers workflow | Required STWI workflow |
| --- | --- | --- |
| New feature, design, configuration, or behavior change | `brainstorming`, then `writing-plans`, then the approved execution workflow | `stwi-implement` |
| Defect investigation | `systematic-debugging`; use `test-driven-development` for the repair | `stwi-implement` |
| Code, plan, contract, safety, API, UI, or artifact review | `requesting-code-review` or `receiving-code-review` when applicable | `stwi-review` |
| Pre-commit, PR, handoff, release, report, or artifact validation | `verification-before-completion` | `stwi-release-qa` |
| Independent parallel work | `dispatching-parallel-agents` before dispatch | the lane-appropriate STWI skill in every packet |

If no listed Superpowers skill matches, the agent must stop and explain why it
cannot safely select a process workflow. It must not use a local STWI skill as
a substitute for the mandatory Superpowers step.

## Agent-Surface Integration

`AGENTS.md` becomes the canonical policy. `CLAUDE.md` and `GEMINI.md` must
reference the same order and defer to `AGENTS.md` for STWI contract rules.

Hermes/Symphony packets must name the selected Superpowers process skill and
the selected STWI domain skill in their required startup section. Hermes still
cannot perform contract, safety, legal, secret, private-data, live-service,
release, or merge decisions. Its packet must remain bounded by the existing
allowed-file and external-transfer checks.

Agents that cannot invoke a named Superpowers plugin must follow the written
equivalent checklist in `AGENTS.md`, state that limitation in their report,
and stop before an action whose required workflow cannot be represented.

## Enforcement and Evidence

The repository will add a lightweight policy validator that checks the
canonical instruction files and Symphony/Hermes templates for:

- the mandatory Superpowers-first order;
- the required STWI skill mapping;
- explicit verification before completion;
- no implication that Hermes may bypass contract or data-safety gates.

The validator is documentation/configuration-only. It does not inspect agent
conversation logs, tokens, secrets, prompts, or external provider traffic.

## Error Handling

- Missing process skill: stop before work and request a suitable workflow.
- Missing STWI skill for a repository change: stop and use the closest
  documented STWI domain workflow only after naming the gap.
- Conflicting instruction files: `AGENTS.md` wins; update the derived files in
  the same change.
- Hermes packet missing either skill: fail packet validation before dispatch.
- An unavailable plugin on a non-Codex surface: use the written checklist,
  disclose the limitation, and preserve all existing STWI safety boundaries.

## Non-Goals

- Do not vendor or copy Superpowers into `.agents/skills`.
- Do not alter `project_contract.json`, product API, safety semantics, model
  routing, provider credentials, Linear states, or deployment settings.
- Do not make skill compliance depend on hidden telemetry or provider logs.

## Acceptance Criteria

1. `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and Hermes/Symphony templates state
   the same Superpowers-first execution order.
2. Every listed work category maps to one Superpowers process skill and one
   STWI domain skill where applicable.
3. A focused validator and tests fail if the policy is removed or contradictory.
4. Existing STWI contract, privacy, no-actuation, external-transfer, and
   release boundaries remain unchanged.
5. Documentation validation, focused policy tests, and `git diff --check`
   pass before handoff.
