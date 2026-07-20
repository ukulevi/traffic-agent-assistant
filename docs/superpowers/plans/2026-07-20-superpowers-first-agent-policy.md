# Superpowers-First Agent Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce a documented, testable Superpowers-first workflow for every agent surface working in the STWI repository.

**Architecture:** `AGENTS.md` becomes the canonical policy and states the mandatory process-to-domain skill order. Claude, Gemini, and Symphony/Hermes instructions mirror that policy. A focused Python validator reads only instruction/template files and reports missing or contradictory policy markers; unit tests pin the validator behavior.

**Tech Stack:** Markdown instruction files, Python standard library (`pathlib`, `re`, `unittest`), existing STWI documentation validation.

## Global Constraints

- Preserve all `project_contract.json` invariants, no-actuation and aggregate-only boundaries.
- Do not install, vendor, or copy the Superpowers plugin into `.agents/skills`.
- Do not inspect conversation logs, prompts, secrets, provider traffic, or token usage.
- Do not alter model routing, provider credentials, Linear state, deployment, API, safety, legal, or data behavior.
- Retain `stwi-implement`, `stwi-review`, and `stwi-release-qa` as mandatory STWI domain workflows.
- Keep `AGENTS.md` as the source of truth; derived agent instructions must defer to it.

---

### Task 1: Add a focused policy validator and unit tests

**Files:**
- Create: `scripts/validation/validate_agent_skill_policy.py`
- Create: `tests/validation/test_agent_skill_policy.py`

**Interfaces:**
- Produces `validate_policy(root: Path) -> list[str]`, returning human-readable violations and no side effects.
- Produces `main() -> None`, which prints every violation and exits `1`, or prints `Agent skill policy validation passed.` and exits `0`.
- Consumes repository instruction files: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `WORKFLOW.md`, `docs/project_management/symphony/current_dispatch_packet.md`, and `docs/project_management/symphony/hermes_worker_prompts.md`.

- [ ] **Step 1: Write the failing validator tests**

```python
def test_policy_passes_for_repository_instructions(self) -> None:
    self.assertEqual(policy.validate_policy(ROOT), [])

def test_policy_reports_missing_superpowers_marker(self) -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = make_policy_fixture(Path(temp), agents_text="STWI only")
        self.assertIn("AGENTS.md: missing Superpowers-first marker", policy.validate_policy(root))
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest tests.validation.test_agent_skill_policy
```

Expected: FAIL because `validate_agent_skill_policy.py` does not exist.

- [ ] **Step 3: Implement the minimal validator**

```python
REQUIRED_FILES = {
    "AGENTS.md": ("using-superpowers", "stwi-implement", "verification-before-completion"),
    "CLAUDE.md": ("Superpowers-first", "AGENTS.md"),
    "GEMINI.md": ("Superpowers-first", "AGENTS.md"),
    "WORKFLOW.md": ("using-superpowers", "stwi-implement"),
    "docs/project_management/symphony/current_dispatch_packet.md": (
        "Superpowers process skill", "STWI domain skill",
    ),
    "docs/project_management/symphony/hermes_worker_prompts.md": (
        "Superpowers process skill", "STWI domain skill",
    ),
}

def validate_policy(root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path, markers in REQUIRED_FILES.items():
        path = root / relative_path
        if not path.is_file():
            errors.append(f"{relative_path}: missing policy file")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(f"{relative_path}: missing policy marker {marker!r}")
    return errors
```

`main()` must derive the repository root from `Path(__file__).resolve().parents[2]`, print one error per line, and use `raise SystemExit(1)` only when errors exist.

- [ ] **Step 4: Run the focused validator tests**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest tests.validation.test_agent_skill_policy
python scripts/validation/validate_agent_skill_policy.py
```

Expected: all tests pass and the CLI prints `Agent skill policy validation passed.`

- [ ] **Step 5: Commit the isolated validator change**

```powershell
git add scripts/validation/validate_agent_skill_policy.py tests/validation/test_agent_skill_policy.py
git commit -m "test: validate superpowers-first agent policy"
```

### Task 2: Make `AGENTS.md` the explicit Superpowers-first source of truth

**Files:**
- Modify: `AGENTS.md:7-19`

**Interfaces:**
- Consumes Superpowers process skill names and local STWI skill names.
- Produces one canonical “Skill Execution Policy” used by all other instruction files.

- [ ] **Step 1: Add a failing policy fixture assertion**

Extend `tests/validation/test_agent_skill_policy.py`:

```python
def test_agents_policy_requires_process_before_domain_skills(self) -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    self.assertLess(text.index("using-superpowers"), text.index("stwi-implement"))
    self.assertIn("verification-before-completion", text)
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```powershell
python -m unittest tests.validation.test_agent_skill_policy.TestAgentSkillPolicy.test_agents_policy_requires_process_before_domain_skills
```

Expected: FAIL because the canonical order is not yet explicit.

- [ ] **Step 3: Replace the existing skills introduction with the canonical policy**

Add a compact Vietnamese-first section that states exactly:

```markdown
1. Invoke `using-superpowers` before any question, inspection, edit, test, or plan.
2. Invoke the matching Superpowers process skill before the local domain skill.
3. Invoke `stwi-implement`, `stwi-review`, or `stwi-release-qa` for STWI-specific work.
4. Invoke `verification-before-completion` before claiming a change is complete.
```

Include a routing table for feature/configuration, bug investigation, review, release QA, and parallel delegation. State that a missing or unavailable process skill must stop work or use the documented checklist with an explicit limitation; it cannot be silently skipped.

- [ ] **Step 4: Run the focused validator tests**

Run:

```powershell
python -m unittest tests.validation.test_agent_skill_policy
python scripts/validation/validate_agent_skill_policy.py
```

Expected: PASS.

- [ ] **Step 5: Commit the canonical instruction update**

```powershell
git add AGENTS.md tests/validation/test_agent_skill_policy.py
git commit -m "docs: make superpowers the default agent workflow"
```

### Task 3: Synchronize Claude and Gemini bridge instructions

**Files:**
- Modify: `CLAUDE.md:1-16`
- Modify: `GEMINI.md:1-16`
- Test: `tests/validation/test_agent_skill_policy.py`

**Interfaces:**
- Consumes `AGENTS.md` as source of truth.
- Produces a concise bridge policy for non-Codex surfaces without claiming plugin availability.

- [ ] **Step 1: Add failing synchronization tests**

```python
for filename in ("CLAUDE.md", "GEMINI.md"):
    text = (ROOT / filename).read_text(encoding="utf-8")
    self.assertIn("Superpowers-first", text)
    self.assertIn("AGENTS.md", text)
    self.assertIn("stwi-release-qa", text)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m unittest tests.validation.test_agent_skill_policy.TestAgentSkillPolicy.test_bridge_files_defer_to_canonical_policy
```

Expected: FAIL because the bridge files currently name only local STWI skills.

- [ ] **Step 3: Add the bridge policy**

For both files, add a section that requires the documented Superpowers-first order, names the core process skills, and says that an unavailable plugin must be represented by the equivalent checklist in `AGENTS.md` with the limitation stated in the handoff. Retain all existing STWI decision-support and safety constraints.

- [ ] **Step 4: Run synchronization and CLI validation**

Run:

```powershell
python -m unittest tests.validation.test_agent_skill_policy
python scripts/validation/validate_agent_skill_policy.py
```

Expected: PASS.

- [ ] **Step 5: Commit the bridge synchronization**

```powershell
git add CLAUDE.md GEMINI.md tests/validation/test_agent_skill_policy.py
git commit -m "docs: align agent bridges with superpowers policy"
```

### Task 4: Require skills in Hermes/Symphony execution packets

**Files:**
- Modify: `WORKFLOW.md` required startup and packet requirements sections
- Modify: `docs/project_management/symphony/current_dispatch_packet.md`
- Modify: `docs/project_management/symphony/hermes_worker_prompts.md`
- Modify: `scripts/project_management/hermes_runner_bridge.py`
- Modify: `tests/project_management/test_hermes_runner_bridge.py`
- Test: `tests/validation/test_agent_skill_policy.py`

**Interfaces:**
- `DispatchPacket.sections` gains required `Superpowers Process Skill` and `STWI Domain Skill` sections.
- `REQUIRED_SECTIONS` includes both section headings.
- `validate_packet(packet)` rejects values outside the documented allowlists.

- [ ] **Step 1: Add failing bridge tests**

```python
def test_rejects_packet_without_skill_sections(self) -> None:
    with self.assertRaisesRegex(ValueError, "Superpowers Process Skill"):
        self.bridge.parse_dispatch_packet(PACKET.replace(
            "## Superpowers Process Skill\n\n`test-driven-development`\n", ""
        ))

def test_rejects_unknown_domain_skill(self) -> None:
    packet = self.bridge.parse_dispatch_packet(PACKET.replace(
        "`stwi-implement`", "`stwi-unknown`"
    ))
    self.assertIn("unknown STWI domain skill", self.bridge.validate_packet(packet))
```

Update the shared `PACKET` fixture to include:

```markdown
## Superpowers Process Skill

`test-driven-development`

## STWI Domain Skill

`stwi-implement`
```

- [ ] **Step 2: Run bridge tests to verify they fail**

Run:

```powershell
python -m unittest tests.project_management.test_hermes_runner_bridge
```

Expected: FAIL until packet parsing and validation enforce the new sections.

- [ ] **Step 3: Implement packet validation and prompt propagation**

Add the two headings to `REQUIRED_SECTIONS`. Add constants:

```python
ALLOWED_PROCESS_SKILLS = {
    "brainstorming", "writing-plans", "test-driven-development",
    "systematic-debugging", "requesting-code-review",
    "verification-before-completion",
}
ALLOWED_STWI_SKILLS = {"stwi-implement", "stwi-review", "stwi-release-qa"}
```

Validate a single backticked skill token from each section and emit exact errors
for missing or unknown values. Add both selected skill names to
`build_hermes_prompt()` immediately before the dispatch packet, with an
instruction to follow the selected process before the STWI domain workflow.

Update `WORKFLOW.md`, the current packet template, and Hermes prompt templates
to require both sections and to preserve existing contract/data/export gates.

- [ ] **Step 4: Run focused Hermes and policy tests**

Run:

```powershell
python -m unittest tests.project_management.test_hermes_runner_bridge tests.validation.test_agent_skill_policy
python scripts/validation/validate_agent_skill_policy.py
```

Expected: PASS.

- [ ] **Step 5: Commit the packet contract update**

```powershell
git add WORKFLOW.md docs/project_management/symphony/current_dispatch_packet.md docs/project_management/symphony/hermes_worker_prompts.md scripts/project_management/hermes_runner_bridge.py tests/project_management/test_hermes_runner_bridge.py tests/validation/test_agent_skill_policy.py
git commit -m "feat: require skills in hermes dispatch packets"
```

### Task 5: Run full documentation and release-level verification

**Files:**
- Modify: `README.md:129-132` only if the existing skills paragraph needs a link to the canonical policy.
- Test: all files from Tasks 1–4.

**Interfaces:**
- README continues to direct contributors to `AGENTS.md`; it must not become a second policy source.

- [ ] **Step 1: Add the final README pointer only if absent**

Use this single sentence after the existing skills paragraph:

```markdown
Tất cả agent phải theo thứ tự Superpowers-first trong `AGENTS.md`; các skill STWI là lớp chuyên ngành kế tiếp.
```

- [ ] **Step 2: Run the exact verification suite once**

Run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest tests.validation.test_agent_skill_policy tests.project_management.test_hermes_runner_bridge
python scripts/validation/validate_agent_skill_policy.py
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1
git diff --check
```

Expected: all commands pass; no tests are weakened; no runtime product behavior changes.

- [ ] **Step 3: Inspect scope and commit the final documentation pointer**

```powershell
git status --short
git add README.md
git commit -m "docs: point contributors to superpowers-first policy"
```

Only commit `README.md` when it changed in Step 1. Do not stage unrelated files.

## Self-Review

- Spec coverage: Tasks 1–5 cover canonical policy, bridge synchronization,
  Hermes/Symphony packet enforcement, focused tests, and release verification.
- No placeholders: every task names exact files, commands, interfaces, and
  expected outcomes.
- Type consistency: `validate_policy(root: Path)` is the only validator API;
  `DispatchPacket.sections` remains the packet source for both added skills.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-20-superpowers-first-agent-policy.md`.

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task and review between tasks.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, with checkpoints.
