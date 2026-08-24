# Internship Report CBHD Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a clean, review-ready English TTNT report package in the Faculty-required order while preserving all fields that require company confirmation.

**Architecture:** `report/internship_main.tex` remains the single source for the cover and report body. `scripts/report/assemble_internship_report.py` merges its cover with the signed D2 and body; a focused source-regression test prevents the internal status page and duplicate company signature blocks from returning.

**Tech Stack:** XeLaTeX, Times New Roman, `pypdf`, Python `unittest`, the existing report assembly script, and the STWI release-QA PowerShell verifier.

## Global Constraints

- Use A4 and Times New Roman at 12 pt for report body text; retain English because the student is in the CC programme.
- Preserve `project_contract.json`, all STWI safety/decision-support facts, and the signed D2 scan unchanged.
- Preserve the only company-controlled fields as visible placeholders: enterprise supervisor identity and authorised representative signature, title, and stamp.
- Final package order is cover, signed D2, then the report body; D3 remains omitted because D2 contains the student.
- Do not stage, commit, push, or modify D4/D5 without an explicit user request.

---

### Task 1: Add a source-level regression test for the final-review format

**Files:**
- Create: `tests/report/test_internship_report_source.py`
- Read: `report/internship_main.tex`

**Interfaces:**
- Consumes: UTF-8 LaTeX source at `report/internship_main.tex`.
- Produces: `unittest` assertions that protect required final-review text structure.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import unittest


REPORT_SOURCE = Path(__file__).resolve().parents[2] / "report" / "internship_main.tex"


class InternshipReportSourceTests(unittest.TestCase):
    def test_final_review_source_has_no_internal_status_page(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("Report Status and Required Company Confirmation", source)
        self.assertNotIn("signed colour scan still required", source)

    def test_final_review_source_has_one_company_confirmation_block(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        self.assertEqual(1, source.count("AUTHORISED COMPANY REPRESENTATIVE"))
        self.assertNotIn("ENTERPRISE SUPERVISOR}\\\\[0.1cm]", source)
```

- [ ] **Step 2: Run the test and confirm the expected failure**

Run: `python -m unittest tests.report.test_internship_report_source`

Expected: failure because the current source still contains the status page and the separate enterprise-supervisor signature block.

- [ ] **Step 3: Leave the test unchanged until Task 2 changes the source**

The test must continue to express the approved final-review requirements; it must not be weakened to match the old draft.

### Task 2: Refine the LaTeX source for CBHD review

**Files:**
- Modify: `report/internship_main.tex:40-100`
- Modify: `report/internship_main.tex:108-145`
- Modify: `report/internship_main.tex:230-278`

**Interfaces:**
- Consumes: the signed D2 content already selected by the assembly script and the D2-approved company/programme facts in the report.
- Produces: a cover and report body without internal completion checklist text, with one company confirmation area.

- [ ] **Step 1: Replace the cover title and retain company-owned data fields**

Set the title to `COURSE REPORT: EXTERNAL INTERNSHIP`, keep `Course code: CO3335`, and retain `\pending` only for the enterprise-supervisor identity. Preserve all other verified student, Faculty, host, and date fields.

- [ ] **Step 2: Delete the internal status chapter and table**

Delete the `Report Status and Required Company Confirmation` chapter, its table, and all references to a signed D2 scan still being required. Start Roman pagination with `Acknowledgements`.

- [ ] **Step 3: Strengthen the company/programme and reflection sections using only confirmed facts**

Add a compact subsection after `Host organisation` that states the host's approved AI-agent, backend, data-platform, metadata-governance, testing, documentation, and demonstration scope. Add one reflection paragraph that explicitly describes the value of a professional data-solutions environment and the reviewed internship programme without inventing people, confidential data, or unverified events.

- [ ] **Step 4: Make table and confirmation layout unambiguous**

Apply left-aligned paragraph columns to the D2-to-STWI mapping table, prevent an isolated first table row at the bottom of a page, and remove the separate `ENTERPRISE SUPERVISOR` signature minipage. Keep one `AUTHORISED COMPANY REPRESENTATIVE` block with visible instructions for full name, title, signature, and company stamp.

- [ ] **Step 5: Reduce front-matter waste without removing required sections**

Keep acknowledgements, executive summary, and table of contents. Adjust the table-of-contents spacing so that its final entries do not occupy an otherwise nearly blank page.

- [ ] **Step 6: Run the new and existing report tests**

Run: `python -m unittest tests.report.test_internship_report_source tests.report.test_assemble_internship_report`

Expected: all tests pass.

### Task 3: Build and assemble the CBHD-review PDF package

**Files:**
- Modify generated artifact: `output/pdf/STWI_Internship_Report_HK253_LeHoangChiVi_CBHD_REVIEW.pdf`
- Modify generated artifact: `output/pdf/STWI_Internship_Submission_HK253_LeHoangChiVi_CBHD_REVIEW.pdf`
- Read: `scripts/report/assemble_internship_report.py`
- Read: `docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB/HK253_TTNT_ShareSV+CB/HK253_TTNT_D2&3/VNPT_IT_D2_TTNT_HK253_2026-05-04.pdf`

**Interfaces:**
- Consumes: the compiled `report/internship_main.pdf` and the six-page signed D2 PDF.
- Produces: an 17-page review report and a 23-page package ordered cover, D2, and report body.

- [ ] **Step 1: Compile the report source twice with XeLaTeX**

Run from `report/`:

```powershell
xelatex -interaction=nonstopmode -halt-on-error internship_main.tex
xelatex -interaction=nonstopmode -halt-on-error internship_main.tex
```

- [ ] **Step 2: Copy the compiled report to the review artifact name**

Copy `report/internship_main.pdf` to `output/pdf/STWI_Internship_Report_HK253_LeHoangChiVi_CBHD_REVIEW.pdf`.

- [ ] **Step 3: Assemble the review package with signed D2**

Run:

```powershell
python scripts/report/assemble_internship_report.py `
  --main-pdf output/pdf/STWI_Internship_Report_HK253_LeHoangChiVi_CBHD_REVIEW.pdf `
  --d2-pdf docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB/HK253_TTNT_ShareSV+CB/HK253_TTNT_D2&3/VNPT_IT_D2_TTNT_HK253_2026-05-04.pdf `
  --output output/pdf/STWI_Internship_Submission_HK253_LeHoangChiVi_CBHD_REVIEW.pdf
```

- [ ] **Step 4: Check package structure with pypdf**

Assert that the report has no text `Report Status and Required Company Confirmation`, the review package starts with the cover, contains six D2 pages after it, and contains no duplicated cover.

### Task 4: Render, inspect, and run repository QA

**Files:**
- Read: both `CBHD_REVIEW.pdf` artifacts.
- Read: `report/internship_main.tex`

**Interfaces:**
- Consumes: Task 3 PDFs.
- Produces: visual QA evidence and full repository validation result.

- [ ] **Step 1: Render all report and assembled-package pages to temporary PNGs**

Use `pypdfium2` to rasterize every page of both PDFs into separate folders under `tmp/pdfs/`.

- [ ] **Step 2: Inspect every rendered page**

Verify the cover, six D2 pages, page transitions, all tables, table of contents, signatures, and references for clipping, overlap, unintended blank pages, unreadable glyphs, and hidden company placeholders.

- [ ] **Step 3: Run the full STWI release QA**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1 -BuildPdf
```

- [ ] **Step 4: Inspect the scope diff and keep Git untouched**

Run `git diff --check` and `git status --short`; report only files changed for this report work. Do not stage, commit, or push.

## Plan self-review

- Spec coverage: Tasks 1–2 cover source content, company-confirmation layout, and table polish; Task 3 covers package order; Task 4 covers visual and repository verification.
- Placeholder scan: the plan contains no implementation-time `TODO`, `TBD`, or deferred requirement. Company placeholders are intentional visible report fields required by the approved design.
- Consistency: Task 1 protects the source structure that Task 2 produces; Task 3 consumes the single compiled report and fixed D2 input; Task 4 validates both generated outputs.
