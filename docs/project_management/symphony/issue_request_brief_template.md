# Issue Request Brief Conversion Guide

Use this as a **conversion aid**, not a replacement for the original request.
The brief exists to reduce executor startup context, but the human lead keeps
final authority over intent and scope.

## Convert any request into these fields

### Ticket
Linear issue id/proposed seed and short title. If missing, propose one.

### Original Request
Copy or summarize the human request verbatim enough that the coordinator or
executor can verify intent was preserved. For vague requests, this must still
capture the human's actual goal, not just a guessed narrow version.

### Interpretation Notes
Document assumptions made during conversion, especially:
- inferred lane/phase
- inferred allowed files when none were named
- inferred checks when none were provided
- anything that might change if the original request is interpreted differently

### Goal
One paragraph outcome derived from the original request. If the original
request is vague, state the inferred outcome and flag it in interpretation
notes rather than silently broadening or narrowing scope.

### Allowed Files
Concrete files or globs the executor may touch. If inferred, mark it as an
inference in interpretation notes.

### Acceptance Criteria
Two to four concrete check bullets derived from the original request. Do not
invent new requirements; convert implied expectations into observable checks.

### Exact Checks
Exact commands that prove the issue is complete. If the request is short and
no checks are obvious, fall back to the default verification matrix from
`WORKFLOW.md`.

### Gap Check
Before dispatch, mark one of:
- `complete`: brief fully represents original intent
- `inferred`: some fields were inferred; coordinator should confirm with human
- `blocked`: brief cannot safely represent original request; stop for `Human Review`

Do not dispatch a `blocked` brief. Send an `inferred` brief for human
confirmation first when the inferred fields affect scope, safety, contract,
or legal boundaries.

## Example conversions

- Long request => preserve original text, then bullet the goal, allowed files,
  criteria, and checks underneath it.
- Short note => turn it into one ticket line, one goal line, one criterion,
  and one check; mark inferences explicitly.

## Forbidden shortcut

Do not hand Codex/Symphony broad narrative alone and ask it to reconstruct the
operational brief. Normalize first, preserve the original request, and confirm
inferred fields before dispatch.
