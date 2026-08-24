# Internship Report CBHD Review Design

## Goal

Produce a clean English External Internship Report package for Le Hoang Chi Vi (2353336, CO3335, HK253) that can be reviewed by the enterprise supervisor before the required human signatures and company stamp are added.

## Scope

The package will contain the report cover, the approved signed D2 programme, and the English report body in the Faculty-required order. It will remain explicitly a review artifact until the company supplies the supervisor identity and completes the required confirmation.

## Required content and format

- Use A4 paper, Times New Roman body text at 12 pt, and an English cover because the student is in the English-taught CC programme.
- Keep the cover fields required by M1: University, Faculty, logo, course title and code, semester, major, programme, host organisation, enterprise supervisor, Faculty supervisor, student name and ID, and report date.
- Put signed D2 immediately after the cover. Do not include D3 because D2 already lists the student.
- Keep the required content sections: work process, outputs, acquired knowledge and skills, and personal reflection.
- Expand the company/programme and reflection content only with neutral, confirmable statements already supported by D2 and the confirmed STWI scope. Do not invent personal, confidential, or company-internal details.
- Use one enterprise confirmation block for the authorised company representative, including full name, title, signature, and company stamp. The student block must request a blue-ink signature.

## Changes

1. Remove the internal `Report Status and Required Company Confirmation` page and every stale statement that says a signed D2 scan is still required.
2. Refine the title page wording to mirror M1 in English and retain an enterprise-supervisor placeholder for the company to complete.
3. Add a short host-organisation/programme subsection and a neutral reflection paragraph that clearly addresses the enterprise and internship programme.
4. Improve table wrapping, page breaks, and table-of-contents density without changing STWI contract facts.
5. Build a review PDF containing `cover -> signed D2 -> report body`; its filename must communicate that company confirmation is still pending.

## Non-goals

- Do not enter a company supervisor name, signature, stamp, evaluation score, or D4/D5 information without an authorised source.
- Do not modify `project_contract.json`, the STWI architecture, API, safety rules, or internship D2 content.
- Do not claim the report is ready for official submission until the required signatures and stamp are present.

## Acceptance criteria

- The report source contains no internal status page and no stale D2-scan requirement.
- The generated review package starts with the cover, then all pages of the signed D2, then the report body.
- The report has no visible clipping, overlap, broken table, placeholder hidden by layout, or missing page transition.
- The report preserves the required English content sections and gives the company a single unambiguous confirmation area.
- The report builds with XeLaTeX, the report-assembly test passes, and the repository release QA passes with `-BuildPdf`.
