---
name: stwi-release-qa
description: Validate STWI before handoff, commit, release, or documentation publication by checking contracts, tests, JavaScript, Git diffs, PDF build health, and slide behavior. Use after cross-artifact edits or when asked whether the repository is release-ready.
---

# STWI Release QA

Run the bundled verifier from the repository root:

powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1

Add -BuildPdf after report or appendix changes.

## Verification workflow

1. Run the verifier and preserve the first failing command.
2. If PDF was built, render and inspect affected pages; command success alone is not visual QA.
3. If slides/index.html, CSS, JavaScript, or slides/sections changed, serve the slides/ directory over local HTTP and verify:
   - all slide files load;
   - navigation and counter work;
   - browser console has no errors;
   - canonical terms and shapes are present;
   - content does not overflow except intentional decorative elements.
4. Inspect git status for cache, logs, PDFs, temporary renders, or unrelated files.
5. Re-run scripts/validate_docs.py after any corrective edit.
6. Report exact pass/fail results, warnings, untested areas, and release blockers. Do not stage, commit, or push unless requested.

## Release blockers

Treat these as blockers:

- Any project validator or contract test failure.
- Missing or stale canonical artifact.
- Undefined LaTeX reference or fatal build error.
- Missing slide, JavaScript error, or renamed section not listed in slides/js/presentation.js.
- Active legacy architecture terminology.
- Any fail-open, privacy, legal-grounding, OOD, or human-approval regression.