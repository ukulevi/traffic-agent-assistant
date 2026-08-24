# Internship Report Vietnamese Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Vietnamese comparison PDF while updating the confirmed enterprise mentor in the English TTNT report and submission package.

**Architecture:** Keep `report/internship_main.tex` as the official English source. Add a separate Vietnamese LaTeX source with the same verified facts and section order, visibly labelled as a comparison-only artifact. Reuse the existing package assembler for the English cover → D2 → report package.

**Tech Stack:** XeLaTeX, Times New Roman, pypdf, pypdfium2, Python unittest.

## Global Constraints

- The official submission remains English because the student is in the CC programme.
- The Vietnamese PDF must display `BẢN ĐỐI CHIẾU – KHÔNG NỘP CHÍNH THỨC` on its cover.
- Enterprise mentor is Võ Tấn Phát (VNPT-IT); do not invent a title, signature, or stamp.
- Preserve M1/H1 order and keep D2 only in the English submission package.
- Preserve STWI contract, human-approval boundary, and privacy claims.
- Do not stage, commit, push, or overwrite the two legacy root PDFs.

---

### Task 1: Update verified enterprise-mentor data in the English source

**Files:**
- Modify: `report/internship_main.tex:32-75,235-267`
- Modify: `tests/report/test_internship_report_source.py`

**Interfaces:**
- Consumes: confirmed text `Võ Tấn Phát (VNPT-IT)`.
- Produces: official English source with the same mentor value on the cover and enterprise-confirmation block.

- [ ] **Step 1: Add a failing source assertion**

```python
def test_source_uses_confirmed_enterprise_mentor(self) -> None:
    source = self.source_path.read_text(encoding="utf-8")
    self.assertIn("Vo Tan Phat (VNPT-IT)", source)
    self.assertNotIn("[TO BE CONFIRMED BY THE COMPANY]", source)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m unittest tests.report.test_internship_report_source`

Expected: FAIL because the source contains the pending placeholder.

- [ ] **Step 3: Replace the pending marker with the confirmed mentor**

```tex
\newcommand{\enterpriseMentor}{Vo Tan Phat (VNPT-IT)}
...
Industrial mentor: & \enterpriseMentor\\
...
\textbf{\enterpriseMentor}
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `python -m unittest tests.report.test_internship_report_source`

Expected: PASS.

### Task 2: Add the Vietnamese comparison source

**Files:**
- Create: `report/internship_main_vi.tex`
- Modify: `tests/report/test_internship_report_source.py`

**Interfaces:**
- Consumes: the verified English report’s facts, headings, work table, and confirmed mentor.
- Produces: a Vietnamese source that has the same 16-page structural intent but is marked comparison-only.

- [ ] **Step 1: Add a failing Vietnamese-source test**

```python
def test_vietnamese_comparison_source_is_clearly_non_submission(self) -> None:
    source = Path("report/internship_main_vi.tex").read_text(encoding="utf-8")
    self.assertIn("BẢN ĐỐI CHIẾU -- KHÔNG NỘP CHÍNH THỨC", source)
    self.assertIn("Võ Tấn Phát (VNPT-IT)", source)
    self.assertIn("BÁO CÁO MÔN HỌC THỰC TẬP NGOÀI TRƯỜNG", source)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m unittest tests.report.test_internship_report_source`

Expected: FAIL because `internship_main_vi.tex` does not exist.

- [ ] **Step 3: Create the Vietnamese source**

```tex
\documentclass[12pt,a4paper]{report}
% Reuse the M1 border, Times New Roman, footer, D2-aligned cover fields,
% and section order from internship_main.tex.
{\large\bfseries BẢN ĐỐI CHIẾU -- KHÔNG NỘP CHÍNH THỨC}
```

Translate prose and headings only. Keep identifiers such as `STWI`, `GCN-LSTM`,
`FastAPI`, `LangGraph`, `Qdrant`, `BGE-m3`, job statuses, tensors, and legal
numbers unchanged.

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `python -m unittest tests.report.test_internship_report_source`

Expected: PASS.

### Task 3: Build, assemble, and inspect final PDFs

**Files:**
- Create: `output/pdf/STWI_Internship_Report_HK253_LeHoangChiVi_CBHD_REVIEW.pdf`
- Create: `output/pdf/STWI_Internship_Submission_HK253_LeHoangChiVi_CBHD_REVIEW.pdf`
- Create: `output/pdf/STWI_Internship_Report_HK253_LeHoangChiVi_VI_COMPARISON.pdf`

**Interfaces:**
- Consumes: `report/internship_main.tex`, `report/internship_main_vi.tex`, the signed D2 PDF, and `scripts/report/assemble_internship_report.py`.
- Produces: one official-review report, one English submission package, and one comparison-only Vietnamese PDF.

- [ ] **Step 1: Build both LaTeX sources twice**

Run:

```powershell
xelatex -interaction=nonstopmode -halt-on-error internship_main.tex
xelatex -interaction=nonstopmode -halt-on-error internship_main_vi.tex
```

Repeat each command once to update contents and PDF links.

- [ ] **Step 2: Assemble the English package**

Run:

```powershell
python scripts/report/assemble_internship_report.py --main-pdf output/pdf/STWI_Internship_Report_HK253_LeHoangChiVi_CBHD_REVIEW.pdf --d2-pdf docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB/HK253_TTNT_ShareSV+CB/HK253_TTNT_ShareDN+SV+GV/HK253_TTNT_D2&3/VNPT_IT_D2_TTNT_HK253_2026-05-04.pdf --output output/pdf/STWI_Internship_Submission_HK253_LeHoangChiVi_CBHD_REVIEW.pdf
```

- [ ] **Step 3: Perform structural and visual checks**

Check report/page counts with `pypdf`; render each page with `pypdfium2`; inspect the English cover, D2 transition, enterprise confirmation, Vietnamese cover, contents, tables, and final page.

- [ ] **Step 4: Run project QA**

Run:

```powershell
python -m unittest tests.report.test_internship_report_source tests.report.test_assemble_internship_report
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1 -BuildPdf
git diff --check
```

Expected: all commands pass; report any pre-existing warnings separately.
