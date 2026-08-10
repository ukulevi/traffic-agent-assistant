# STWI Counterfactual Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace repeated safety checks with at most three distinct, validated candidate evaluations and real surrogate re-simulation.

**Architecture:** Add a narrow refiner protocol and immutable iteration evidence. The orchestrator owns the initial action and persists the selected action; the safety loop owns evaluation/refinement; the surrogate remains the only source of scenario metrics.

**Tech Stack:** Python 3.11, dataclasses, typing protocols, Pydantic contracts, unittest.

## Global Constraints

- Preserve all API statuses and action-field semantics in `project_contract.json`.
- Every returned action remains `executable=false` and requires operator approval.
- Refine only V/C failure; citation, OOD and uncertainty failures stop fail-closed.
- Evaluate at most three distinct candidates.
- Do not commit, stage, push or change branches.

---

### Task 1: Define refinement interfaces and iteration evidence

**Files:**
- Modify: `src/stwi/t4_orchestrator/interfaces.py`
- Modify: `src/stwi/t4_orchestrator/safety_loop.py`
- Test: `tests/t4_orchestrator/test_t4_safety.py`

**Interfaces:**
- Produces: `CandidateRefiner.refine(current_action, check, iteration) -> dict[str, Any] | None`
- Produces: `SafetyIteration(action, results, check)` and extended `SafetyLoopOutcome`

- [ ] **Step 1: Write failing tests for distinct iteration history**

```python
def test_refinement_outcome_records_distinct_actions(self):
    outcome = loop.run(
        node_ids=["node_00"],
        horizons_minutes=[5, 10],
        candidate_action={"node_id": "node_00", "green_time_ratio": 0.10},
        scenario_time=SCENARIO_TIME,
        has_citations=True,
    )
    self.assertEqual(
        [item.action["green_time_ratio"] for item in outcome.iterations],
        [0.10, 0.25],
    )
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest tests.t4_orchestrator.test_t4_safety -v`
Expected: fail because `CandidateRefiner`, iteration evidence and the new `run` signature do not exist.

- [ ] **Step 3: Add the protocol and immutable result types**

```python
class CandidateRefiner(Protocol):
    def refine(
        self,
        current_action: dict[str, Any],
        check: SafetyCheckResult,
        iteration: int,
    ) -> dict[str, Any] | None: ...
```

Add frozen `SafetyIteration` and make `SafetyLoopOutcome` carry
`iterations: tuple[SafetyIteration, ...]` plus `selected_action`.

- [ ] **Step 4: Run the focused test and retain the expected failure boundary**

Expected: type/interface assertions pass; behavior test still fails until Task 2.

### Task 2: Implement bounded V/C refinement and re-simulation

**Files:**
- Modify: `src/stwi/t4_orchestrator/safety_loop.py`
- Test: `tests/t4_orchestrator/test_t4_safety.py`

**Interfaces:**
- Produces: `GreenTimeRatioRefiner(step: float = 0.15)`
- Consumes: `ScenarioForecaster.predict(node_ids, horizons_minutes, candidate_action, scenario_time)`

- [ ] **Step 1: Add failing behavior tests**

```python
def test_vc_failure_repredicts_with_refined_action(self):
    outcome = loop.run(
        node_ids=["node_00"],
        horizons_minutes=[5, 10],
        candidate_action={"node_id": "node_00", "green_time_ratio": 0.10},
        scenario_time=SCENARIO_TIME,
        has_citations=True,
    )
    self.assertTrue(outcome.passed)
    self.assertEqual(forecaster.requested_ratios, [0.10, 0.25])

def test_ood_failure_does_not_refine(self):
    outcome = loop.run(
        node_ids=["node_02"],
        horizons_minutes=[5, 10],
        candidate_action={"node_id": "node_02", "green_time_ratio": 0.70},
        scenario_time=SCENARIO_TIME,
        has_citations=True,
    )
    self.assertFalse(outcome.passed)
    self.assertEqual(forecaster.predict_calls, 1)
```

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.t4_orchestrator.test_t4_safety -v`
Expected: predictions are not repeated with a changed candidate.

- [ ] **Step 3: Implement minimal refinement loop**

For each iteration, validate the action, call `surrogate.predict`, evaluate all
gates, and refine only when `vc_ratio_ok` is false while the other three gates
are true. Reject repeated, cross-node or out-of-range output.

- [ ] **Step 4: Verify GREEN**

Run the focused safety suite and confirm the responsive surrogate passes on its
second distinct candidate while OOD/uncertainty/citation cases use one call.

### Task 3: Bind the selected action into the orchestrator result

**Files:**
- Modify: `src/stwi/t4_orchestrator/orchestrator.py`
- Modify: `src/stwi/t4_orchestrator/contracts.py`
- Test: `tests/t4_orchestrator/test_t4_safety.py`
- Test: `tests/t4_orchestrator/test_t4_api_http.py`

**Interfaces:**
- Produces: `OrchestratorState.selected_action`
- Consumes: `SafetyLoopOutcome.selected_action`

- [ ] **Step 1: Write failing API assertions**

```python
self.assertEqual(result.recommended_action.green_time_ratio, 0.25)
self.assertFalse(result.recommended_action.executable)
self.assertTrue(result.recommended_action.requires_operator_approval)
```

- [ ] **Step 2: Verify RED**

Run the two focused modules; expected action still equals the request action.

- [ ] **Step 3: Store and serialize the selected action**

Use the selected action only for `succeeded`/`needs_review`. Preserve no-action
semantics for `failed` and `expired`.

- [ ] **Step 4: Verify GREEN and existing contract behavior**

Run both focused modules and `tests.contracts.test_project_contract`.

### Task 4: Synchronize canonical and presentation artifacts

**Files:**
- Modify: `docs/04_AI_Agent_Orchestrator_CF_VLA.md`
- Modify: `report/chapters/ch07_agent.tex`
- Modify: `report/chapters/appendix_api.tex`
- Modify: `docs/guides/mvp_demo_runbook.md`

- [ ] **Step 1:** Replace placeholder/repeated-loop wording with bounded refinement semantics.
- [ ] **Step 2:** Add one API/audit example with two distinct candidate ratios.
- [ ] **Step 3:** Run docs validation and targeted text searches for contradictory placeholder wording.

### Task 5: Verify the refinement slice

- [ ] Run focused Python safety/API tests.
- [ ] Run full Python discovery.
- [ ] Run the release verifier and `git diff --check`.
