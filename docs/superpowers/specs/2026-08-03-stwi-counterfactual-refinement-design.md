# STWI Counterfactual Refinement Design

**Status:** Approved for implementation on 2026-08-03
**Scope:** Replace repeated safety checks with bounded candidate refinement
**Contract:** Maximum three iterations, fail-closed, human approval required

## 1. Problem

The current safety loop evaluates identical scenario results up to three times.
It produces an audit trace but does not correct the candidate or re-run the
surrogate, while canonical documentation describes a correction loop.

## 2. Boundaries

Introduce a narrow `CandidateRefiner` protocol. It receives the current typed
action, the latest safety check and the iteration number, and either returns a
new typed action or declines refinement. The safety loop remains responsible
for policy evaluation; the surrogate remains responsible for scenario metrics.

The orchestrator supplies node IDs, horizons, scenario time, initial action and
validated citation availability. It stores the evaluated action and result for
each iteration.

## 3. Refinement Policy

- Refine only when V/C is the failing adjustable gate.
- Do not refine missing citation, OOD, uncertainty, invalid input, dependency
  failure or deadline failure.
- The MVP refiner may adjust only `green_time_ratio` for the already selected
  node; it cannot add nodes, change event type, or expand operator scope.
- Every action is schema-validated and bounded to `[0,1]` before inference.
- A repeated or invalid candidate terminates as `needs_review`.
- At most three distinct candidates are evaluated.

The deterministic policy increases `green_time_ratio` in a bounded step selected
from configuration and capped by the request boundary. It makes no legal or
field-control claim; it only asks the surrogate to evaluate another hypothesis.

## 4. Outcomes

`SafetyLoopOutcome` records:

- pass/fail and total iterations;
- the per-iteration safety checks;
- an immutable history of candidate actions;
- the selected final action;
- a stable failure reason when refinement is disallowed or exhausted.

On pass, the selected action becomes `recommended_action` with
`executable=false` and `requires_operator_approval=true`. On failure, the last
evaluated action becomes `candidate_action` with the same non-executable
boundary. No action is returned for `failed` or `expired`.

## 5. Error and Deadline Behavior

Surrogate exceptions map to `failed`; deadline exhaustion maps to `expired`.
Neither is converted to `needs_review` merely to retain an action. Refinement
must use the job's remaining deadline and must not start another iteration when
the deadline is exhausted.

## 6. Verification

TDD tests prove:

- a responsive surrogate changes metrics and succeeds after refinement;
- history contains distinct, validated actions;
- V/C non-convergence stops after three candidates;
- citation/OOD/uncertainty failures perform one evaluation and no refinement;
- duplicate/invalid refiner output fails closed;
- recommended/candidate action semantics remain contract-compliant;
- operator approval remains audit-only and no actuation path is introduced.

Canonical DOC-04, report chapter 7, API examples and demo evidence are updated
