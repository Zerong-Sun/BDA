# Research summary adversarial fixes — 2026-10-19

## Changes

- A newer progress record owns the result and next-step summary. Unsectioned current prose is displayed instead of an older report's positive result, and missing current advancement conditions no longer inherit old instructions. The complete saved report remains accessible and collapsed by default.
- Summary extraction retains heading ancestry. Current hold statements in headings or prose take precedence over historical plans; historical/source sections and fenced examples cannot supply fallback action instructions.
- A references heading no longer discards an otherwise valid preamble. Methods and next-step sections are not relabeled as fallback results.

## Verification

- Added 10 regression cases, including all three adversarial failures. All 58 tests across the summary parser, summary component, research project switching and workflow journey suites passed.
- Changed-file ESLint, production build and bundle-size gate passed.
- Chromium checked actual saved data for Sweet proteins, both PD-1/PD-L1 projects, and an existing paused project. The latest sweet-protein progress was checked against the complete paginated records. The PD-L1 reports remained distinct, and the paused record retained its hold instead of its historical plan.
- Report opening, default report/reference folding and project-scoped review/workflow navigation passed. No page errors were observed in the four-project check.
- Separate, temporary browser response fixtures reproduced the three adversarial inputs on the sweet-protein and archived PD-L1 routes; all passed. These fixtures were removed and never written to the platform. Neither PD-L1 nor Sweet proteins was assigned a fabricated pause state.
- No model calls or research submissions were used. Application writes were blocked in the isolated test browser except authentication. Private evidence is stored outside Git.

This verifies presentation of saved records, not the underlying scientific conclusions. Main merge remains paused.
