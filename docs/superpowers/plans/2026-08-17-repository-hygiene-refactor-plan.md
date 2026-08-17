# STWI Repository Hygiene Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Stop at the review checkpoint before Task 1; do not use subagents for this cross-repository cleanup.

**Goal:** Publish the existing network-impact feature without private files, then harden and simplify the public STWI repository without changing runtime or project contracts.

**Architecture:** Keep the existing src, scripts, tests, docs, report, slides, infra, and data boundaries. Extend the current CI guard, validate active documentation paths, move reusable benchmark orchestration into src/stwi, and clean only generated paths that have passed an explicit safety check.

**Tech Stack:** Python 3.11, unittest, pathlib, regular expressions, GitHub Actions, PowerShell, Node.js, GitHub CLI, and the STWI release verifier.

## Global Constraints

- Preserve X[B,12,N,16], M[B,12,N,16], A[N,N], Y[B,6,N,2], feature order, API statuses, SLA, stack, fail-closed behavior, and human approval.
- Do not change project_contract.json, report semantics, slides, API behavior, or orchestration behavior in the refactor PR.
- Do not add a dependency, framework, service, or automatic actuation.
- Do not edit, relocate, stage, print, or delete internship forms, signatures, .env.local, raw media, private datasets, private weights, or private report sources.
- Keep the feature and refactor in separate worktrees and draft PRs. Never use git add -A or push directly to main.
- Use apply_patch for repository edits and native PowerShell end-to-end for local cleanup.
- Resolve and validate every absolute cleanup target before recursive deletion.
- Report to the user before starting Task 1.

## File Structure Map

- .gitignore and .codexignore define local/private/generated boundaries.
- scripts/validation/validate_ci_guardrails.py is the single public-repository guard.
- scripts/validation/validate_docs.py checks canonical content and active documented script paths.
- README.md, docs/README.md, and docs/guides/repository_structure.md define navigation and ownership.
- src/stwi/tooling/vision_training/benchmark.py owns reusable external-model benchmark orchestration.
- scripts/benchmark_external_vision_model.py remains a compatibility CLI adapter.

---

### Task 1: Safely publish the existing network-impact feature

**Worktree:** C:\Users\PC\Downloads\DADN\traffic-agent-assistant

**Files eligible for staging:**

- docs/guides/mvp_dashboard_demo_walkthrough.md
- report/chapters/ch11_ket_luan.tex
- report/main.tex
- src/stwi/app.py
- src/stwi/t4_orchestrator/__init__.py
- src/stwi/t4_orchestrator/api.py
- src/stwi/t4_orchestrator/contracts.py
- src/stwi/t4_orchestrator/network_impact.py
- src/stwi/t4_orchestrator/orchestrator.py
- src/stwi/t4_orchestrator/static/dashboard-state.js
- src/stwi/t4_orchestrator/static/dashboard-view.js
- src/stwi/t4_orchestrator/static/dashboard.css
- src/stwi/t4_orchestrator/static/dashboard.js
- src/stwi/t4_orchestrator/static/index.html
- scripts/demo/capture_network_impact_showcase.ps1
- tests/demo/test_comprehensive_demo.py
- tests/frontend/dashboard-state.test.mjs
- tests/frontend/dashboard-view.test.mjs
- tests/t4_orchestrator/test_t4_contracts.py
- tests/t4_orchestrator/test_t4_network_impact.py
- docs/superpowers/plans/2026-08-14-network-impact-evidence-showcase-plan.md

**Explicitly excluded:** .github/workflows/build.yml, docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB, internship plans/specs, report/internship_main.tex, report/chapters/ch00_thong_tin_thuc_tap.tex, report/chapters/ch12_xac_nhan_doanh_nghiep.tex, report/figures, scripts/report, tests/report, and tmp.

- [ ] **Step 1: Reconfirm scope**

    git status --short
    git diff -- .github/workflows/build.yml
    git diff --stat -- docs/guides/mvp_dashboard_demo_walkthrough.md report src/stwi tests scripts/demo

Expected: the workflow diff contains only internship build/upload and stays unstaged.

- [ ] **Step 2: Run focused tests**

    python -m unittest tests.t4_orchestrator.test_t4_network_impact tests.t4_orchestrator.test_t4_contracts tests.demo.test_comprehensive_demo
    node --test tests/frontend/dashboard-state.test.mjs tests/frontend/dashboard-view.test.mjs
    node --check src/stwi/t4_orchestrator/static/dashboard-state.js
    node --check src/stwi/t4_orchestrator/static/dashboard-view.js

Expected: all focused tests pass.

- [ ] **Step 3: Stage only the eligible paths**

Run git add -- followed by the exact list above. Do not stage a whole directory.

- [ ] **Step 4: Fail if staged paths are private**

    $staged = git diff --cached --name-only
    $forbidden = $staged | Where-Object {
        $_ -match '(^|/)(TTNT_HD_BM_|tmp|output|tests/report|scripts/report)(/|$)' -or
        $_ -match 'internship|ch00_thong_tin_thuc_tap|ch12_xac_nhan_doanh_nghiep' -or
        $_ -match '(^|/)\.env($|\.)'
    }
    if ($forbidden) { throw "Forbidden staged paths detected" }
    if ($staged -contains '.github/workflows/build.yml') {
        throw "Private internship workflow diff is staged"
    }

- [ ] **Step 5: Run release QA with PDF**

    powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1 -BuildPdf
    git diff --cached --check

Render and inspect pages affected by report/main.tex and ch11_ket_luan.tex. The technical PDF must contain no internship content.

- [ ] **Step 6: Commit and publish as draft**

    git commit -m "feat: present validated network impact evidence"

Use github:yeet to push codex/network-impact-video-design and open a draft PR to main. Wait for checks and do not merge.

---

### Task 2: Harden public/private boundaries

**Worktree:** C:\Users\PC\AppData\Local\Temp\stwi-repository-hygiene-refactor

**Files:**

- Modify: .gitignore:1
- Modify: .codexignore:1
- Modify: scripts/validation/validate_ci_guardrails.py:16
- Modify: tests/validation/test_validate_ci_guardrails.py:1
- Modify: .github/workflows/build.yml:61

**Interfaces:**

- git_staged_files(root: Path) -> list[str]
- candidate_repository_files(root: Path) -> list[str]
- validate_forbidden_files(paths: list[str]) -> list[str]
- validate_sensitive_content(root: Path, paths: list[str]) -> list[str]
- validate_public_workflows(root: Path) -> list[str]
- validate(root: Path) -> list[str]

- [ ] **Step 1: Write failing tests**

Add tests that assert:

    candidate_repository_files = tracked union staged, sorted and deduplicated

    validate_forbidden_files([
        "docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB/form.docx",
        "report/internship_main.tex",
        "tmp/render/page-01.png",
        "output/pdf/report.pdf",
    ])

returns four errors.

Create src/leak.py in a temporary root containing the private-key header marker and assert the only message is:

    Sensitive content (private-key): src/leak.py

Create .github/workflows/build.yml containing internship_main.tex and assert validate_public_workflows rejects it.

- [ ] **Step 2: Verify RED**

    python -m unittest tests.validation.test_validate_ci_guardrails -v

Expected: missing-function failures.

- [ ] **Step 3: Add exact ignore rules**

Add to both ignore files where applicable:

    tmp/
    output/
    .superpowers/
    docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB/
    report/internship_main.tex
    report/chapters/ch00_thong_tin_thuc_tap.tex
    report/chapters/ch12_xac_nhan_doanh_nghiep.tex
    report/figures/M2_Logo_BK.png
    scripts/report/
    tests/report/
    docs/superpowers/plans/2026-08-17-internship-report-cbhd-review.md
    docs/superpowers/specs/2026-08-17-internship-report-cbhd-review-design.md

Keep .env.example allowed and keep .env, .env.local, and .env.*.local ignored.

- [ ] **Step 4: Implement the fail-closed guard**

Use high-confidence rules only:

    SENSITIVE_TEXT_PATTERNS = (
        ("private-key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        ("github-token", r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
        ("aws-access-key", r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
        ("google-api-key", r"\bAIza[0-9A-Za-z_-]{30,}\b"),
        ("slack-token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        ("openai-key", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    )

Scan only known text suffixes, cap each read at 2 MiB, catch UnicodeDecodeError, and report rule plus path without the matched value. Candidate paths are git ls-files union git diff --cached --name-only --diff-filter=ACMR.

- [ ] **Step 5: Call the guard from report CI**

Change the build validation step to run:

    python scripts/validation/validate_ci_guardrails.py
    python scripts/validation/validate_docs.py
    python -m unittest tests.contracts.test_project_contract

- [ ] **Step 6: Verify GREEN and commit**

    python -m unittest tests.validation.test_validate_ci_guardrails -v
    python scripts/validation/validate_ci_guardrails.py
    git add -- .gitignore .codexignore scripts/validation/validate_ci_guardrails.py tests/validation/test_validate_ci_guardrails.py .github/workflows/build.yml
    git diff --cached --check
    git commit -m "chore: guard public repository boundaries"

---

### Task 3: Validate and repair active documented script paths

**Files:**

- Modify: scripts/validation/validate_docs.py:42
- Create: tests/validation/test_validate_docs.py
- Modify: README.md:1
- Modify: docs/01_System_Architecture_Data_Pipeline.md:83
- Modify: docs/guides/model_registry_evidence.md:84
- Modify: docs/guides/ROBOFLOW_MCP.md:15
- Modify: docs/guides/rtsp_smoke_test_runbook.md:97
- Modify: docs/guides/vision_local_training_runbook.md:67
- Modify: infra/harness/README.md:93

**Interfaces:**

- iter_active_documentation(root: Path) -> tuple[Path, ...]
- documented_script_paths(text: str) -> tuple[str, ...]
- validate_documented_script_paths(errors: list[str], root: Path = ROOT) -> None

Active scope is README.md, docs/*.md, docs/guides/*.md, docs/ops/*.md, and infra/**/*.md. Exclude docs/archive and docs/superpowers.

- [ ] **Step 1: Write failing tests**

Create tests/validation/test_validate_docs.py. One temporary root contains README.md with python scripts/missing.py and must produce:

    README.md: missing documented script scripts/missing.py

A second root contains scripts/validation/check.py, an active README reference to it, and a historical docs/superpowers/plans/old.md reference to scripts/removed.py. It must produce no errors.

- [ ] **Step 2: Verify RED**

    python -m unittest tests.validation.test_validate_docs -v

Expected: validate_documented_script_paths is absent.

- [ ] **Step 3: Implement the resolver**

Use:

    SCRIPT_REFERENCE_PATTERN = re.compile(
        r"(?<![A-Za-z0-9_./-])(scripts/[A-Za-z0-9_./-]+\.py)"
    )

Return sorted unique references, check root/reference existence, and call the new validator from main after Markdown-link validation.

- [ ] **Step 4: Demonstrate repository RED**

    python scripts/validation/validate_docs.py

Expected: old root-level vision commands are listed.

- [ ] **Step 5: Apply the canonical path map**

Use these directory rules:

    data preparation:
      augment_*, build_stwi_vehicle_yolo_dataset.py,
      build_vision_error_review_pack.py,
      build_vision_label_fix_candidates.py,
      prepare_roboflow_yolo_dataset.py,
      prepare_vision_review_batch.py,
      relabel_helmet_dataset_for_motorcycle.py
      -> scripts/data_prep/

    training:
      apply_vision_review_batch.py, promote_vision_model.py,
      rebalance_vehicle_training_dataset.py,
      rebalance_vehicle_training_dataset_from_errors.py,
      train_vision_model.py
      -> scripts/training/

    validation:
      analyze_vision_sliced_validation.py,
      analyze_vision_validation_errors.py,
      evaluate_vision_roi_ap.py,
      validate_vision_dataset.py
      -> scripts/validation/

    infrastructure:
      cleanup_vision_data_artifacts.py,
      fetch_external_vision_model.py,
      finalize_motorcycle_relabel_review.py,
      finalize_vision_label_fix_candidates.py,
      register_external_vision_model.py,
      roboflow_mcp_server.py
      -> scripts/infra/

Confirm every replacement with Test-Path. Do not rewrite the historical validate_agent_skill_policy.py plan reference.

- [ ] **Step 6: Verify GREEN and commit**

    python -m unittest tests.validation.test_validate_docs -v
    python scripts/validation/validate_docs.py
    git add -- scripts/validation/validate_docs.py tests/validation/test_validate_docs.py README.md docs/01_System_Architecture_Data_Pipeline.md docs/guides/model_registry_evidence.md docs/guides/ROBOFLOW_MCP.md docs/guides/rtsp_smoke_test_runbook.md docs/guides/vision_local_training_runbook.md infra/harness/README.md
    git diff --cached --check
    git commit -m "docs: repair canonical tooling paths"

---

### Task 4: Refresh repository navigation and ownership docs

**Files:**

- Modify: README.md:1
- Modify: docs/README.md:1
- Modify: docs/guides/repository_structure.md:1
- Modify: docs/superpowers/plans/2026-08-03-stwi-dashboard-demo-user-guide.md:300

- [ ] **Step 1: Capture missing sections**

    rg -n '^## (Repository map|Public/private boundary|Local verification)$' README.md
    rg -n '^## (Canonical documents|Guides|Operations|Historical material)$' docs/README.md

Expected: at least one required section is absent.

- [ ] **Step 2: Rewrite README as a concise public entrypoint**

Use these exact sections:

    # SmartTraffic What-If (STWI)
    ## Scope and safety
    ## Source of truth
    ## Local verification
    ## Repository map
    ## Public/private boundary
    ## Development and demo runbooks

Move detailed detector commands to links for docs/guides/vision_local_training_runbook.md and docs/guides/ROBOFLOW_MCP.md. Preserve simulation-first, privacy, fail-closed, and no-automatic-actuation language.

- [ ] **Step 3: Turn docs/README.md into an index**

Link canonical DOC-00 through DOC-05, guides/repository_structure.md,
guides/mvp_demo_runbook.md, ops/demo_operator_sop_v1.md,
../infra/production/README.md, archive, specs, and plans. Mark archive and
superpowers as historical/audit material.

- [ ] **Step 4: Expand repository_structure.md**

Cover src/stwi/demo, production entrypoints, scripts/demo,
scripts/project_management, docs/project_management, report/slides, public
manifests, local-private sources, and generated outputs. State that local
internship assembly tooling is excluded from the public repository and that
large API/orchestrator splits are deferred until they no longer overlap an
active feature.

- [ ] **Step 5: Repair the historical link**

In docs/superpowers/plans/2026-08-03-stwi-dashboard-demo-user-guide.md change ./mvp_dashboard_demo_walkthrough.md to ../../guides/mvp_dashboard_demo_walkthrough.md only.

- [ ] **Step 6: Verify and commit**

    python scripts/validation/validate_docs.py
    rg -n '^## (Repository map|Public/private boundary|Local verification)$' README.md
    rg -n '^## (Canonical documents|Guides|Operations|Historical material)$' docs/README.md
    git diff --check
    git add -- README.md docs/README.md docs/guides/repository_structure.md docs/superpowers/plans/2026-08-03-stwi-dashboard-demo-user-guide.md
    git commit -m "docs: clarify repository ownership boundaries"

---

### Task 5: Extract external-vision benchmark logic

**Files:**

- Create: src/stwi/tooling/vision_training/benchmark.py
- Modify: scripts/benchmark_external_vision_model.py:1
- Create: tests/vision/test_external_vision_benchmark.py

**Interface:** `run_external_benchmark` is keyword-only and accepts
`manifest_path: Path`, `source_root: Path`, `output_root: Path`,
`splits: list[str]`, `confidence: float`, `iou_threshold: float`,
`image_size: int`, `device: str`, `min_box_area: float`,
`max_images: int | None`, `baseline_map50: float | None`,
`evaluator: Callable[..., dict[str, Any]]`, and
`generated_at: datetime | None = None`; it returns `dict[str, Any]`.

The CLI compatibility function keeps its current explicit signature and passes evaluate_roi_ap as evaluator.

- [ ] **Step 1: Write failing tests**

Create a package test that patches load_external_manifest, supplies a Mock evaluator returning mAP50_roi 0.90 and seconds_per_image 0.05, passes a fixed UTC timestamp, and asserts:

    written = json.loads(
        (output / "external_benchmark_summary.json").read_text(encoding="utf-8")
    )
    self.assertEqual(written, summary)
    self.assertTrue(summary["promotion_boundary"]["requires_human_approval"])
    self.assertTrue(summary["promotion_boundary"]["not_promoted_by_this_script"])

Add a wrapper test patching run_external_benchmark and asserting the old benchmark_external_model signature forwards unchanged arguments plus evaluate_roi_ap.

- [ ] **Step 2: Verify RED**

    python -m unittest tests.vision.test_external_vision_benchmark -v

Expected: the benchmark package module does not exist.

- [ ] **Step 3: Implement the package function**

Move manifest loading, evaluator invocation, verdict construction, summary creation, timestamp, output directory creation, and JSON writing into benchmark.py. Use generated_at or datetime.now(timezone.utc). Preserve the schema and promotion boundary exactly.

- [ ] **Step 4: Make the script a thin adapter**

Keep argument parsing and console output in scripts/benchmark_external_vision_model.py. Retain the public compatibility signature and replace its body with a run_external_benchmark call passing evaluator=evaluate_roi_ap.

- [ ] **Step 5: Verify and commit**

    python -m unittest tests.vision.test_external_vision_benchmark -v
    python -m unittest tests.vision.test_external_vision_models tests.vision.test_local_vision_training
    git add -- src/stwi/tooling/vision_training/benchmark.py scripts/benchmark_external_vision_model.py tests/vision/test_external_vision_benchmark.py
    git diff --cached --check
    git commit -m "refactor: extract external vision benchmark logic"

---

### Task 6: Clean verified generated local artifacts

**Worktree:** C:\Users\PC\Downloads\DADN\traffic-agent-assistant

**Files:** Ignored/generated local files only; no commit.

- [ ] **Step 1: Resolve candidate paths**

    $repoRoot = [IO.Path]::GetFullPath(
        'C:\Users\PC\Downloads\DADN\traffic-agent-assistant'
    )
    $repoPrefix = $repoRoot.TrimEnd(
        [IO.Path]::DirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    $fixedRelative = @('tmp', 'output', '.pytest_cache', 'src/stwi.egg-info')
    $targets = @()
    foreach ($relative in $fixedRelative) {
        $candidate = [IO.Path]::GetFullPath((Join-Path $repoRoot $relative))
        if (-not $candidate.StartsWith(
            $repoPrefix, [StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Cleanup target escaped repository: $candidate"
        }
        if (Test-Path -LiteralPath $candidate) { $targets += $candidate }
    }
    $cacheDirs = Get-ChildItem -LiteralPath $repoRoot -Recurse -Force -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue
    foreach ($directory in $cacheDirs) {
        $candidate = [IO.Path]::GetFullPath($directory.FullName)
        if (-not $candidate.StartsWith(
            $repoPrefix, [StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Cache target escaped repository: $candidate"
        }
        $targets += $candidate
    }
    $targets = $targets | Sort-Object -Unique
    $targets

- [ ] **Step 2: Prove targets are untracked and non-private**

For each target, derive its repository-relative path and run git ls-files -- relative-path. Abort on any tracked output or any path containing TTNT_HD_BM_, internship, data\derived\private, or .env.local.

- [ ] **Step 3: Delete the validated list only**

    foreach ($target in $targets) {
        Remove-Item -Recurse -Force -LiteralPath $target
    }

Do not recompute or broaden the list between validation and deletion.

- [ ] **Step 4: Verify preservation**

    git status --short
    Test-Path -LiteralPath 'docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB'
    Test-Path -LiteralPath 'report/internship_main.tex'
    Test-Path -LiteralPath '.env.local'

Expected: private checks remain True. Report exact removed paths and note that deleted cache/render data must be regenerated.

---

### Task 7: Run final QA and publish the refactor draft PR

**Worktree:** C:\Users\PC\AppData\Local\Temp\stwi-repository-hygiene-refactor

- [ ] **Step 1: Run focused tests**

    python -m unittest tests.validation.test_validate_ci_guardrails tests.validation.test_validate_docs -v
    python -m unittest tests.vision.test_external_vision_benchmark tests.vision.test_external_vision_models tests.vision.test_local_vision_training
    python scripts/validation/validate_ci_guardrails.py
    python scripts/validation/validate_docs.py

- [ ] **Step 2: Run mandatory verification**

    python -m unittest tests.contracts.test_project_contract
    node --check slides/js/presentation.js
    node --check slides/js/presentation-tools.js
    git diff --check
    powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1

Expected: all checks pass. The refactor PR does not require -BuildPdf because it does not edit report or appendices.

- [ ] **Step 3: Prove contract/artifact isolation**

    git status --short
    git diff main...HEAD --stat
    git diff main...HEAD -- project_contract.json report slides src/stwi/t4_orchestrator
    python scripts/validation/validate_ci_guardrails.py

Expected: no contract, report, slide, API, or orchestrator diff and no private/generated tracked path.

- [ ] **Step 4: Verify GitHub access**

    gh --version
    gh auth status
    git remote -v
    git branch --show-current

Expected: authenticated gh, the correct origin, and branch codex/repository-hygiene-refactor.

- [ ] **Step 5: Push and open a draft PR**

Use github:yeet. The PR body must summarize the privacy guard, documented-path repairs, navigation updates, benchmark extraction, cleanup outcome, exact verification, and zero contract impact.

- [ ] **Step 6: Wait for checks and stop at review**

Fix only failures caused by this PR, rerun the failed command plus the full verifier, and push a corrective commit. Do not merge either draft PR. Report both PR URLs, commits, check results, removed generated paths, and residual risks.
