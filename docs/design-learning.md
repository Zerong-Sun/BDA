# Design learning before and after execution

Every project has a **Design lesson library** on its Learning page. It is independent
of the assay / dataset / model-learning module. Every new workflow and every existing
unsubmitted draft must complete a **Design learning loop** review before submission.
The same backend check serves preflight and actual submission.

## Before design

1. Read the project's current lessons, including contrary and uncertain evidence.
2. Check identity and inputs; objective and score direction; mechanism and scope;
   factors and controls; feasibility and method limits; readouts and feedback.
3. For each core question and prior lesson, choose **apply**, **test**, or **not
   applicable** and explain conditions. Applicable/uncertain items require a
   hypothesis, action, matched comparison, readout, and predefined decision rule.
4. Add design-specific questions. Save a frozen review of the executable design and
   the evidence consulted. Input, parameter, connection, or project-memory changes
   invalidate a draft review; presentation and layout changes do not.

The library starts empty. No scientific conclusions are shipped as universal rules.
Lessons from other accessible projects can be explicitly imported with a source
snapshot; the new design still evaluates applicability. Importing a snapshot does
not subscribe to future changes in the source project.

## After execution

The workflow shows outstanding feedback for each applicable question. Record the
outcome with source references, conditions, uncertainty and the next design change.
Outcomes distinguish support, refutation, inconclusive evidence, invalid methods and
execution blocked (the hypothesis was not tested). A successful compute job is never
automatically treated as scientific support. Sources are researcher-supplied
references, not automatically validated findings.

Saving feedback appends a project lesson automatically. The original hypothesis and
review remain unchanged. Revisions append a new lesson linked to its predecessor.
A derived design cannot submit while the executed parent has missing feedback;
new feedback also forces the child's evidence review to be refreshed. Feedback can
record partial results after submission, and never marks compute as successful.

## API and scope

- `GET/POST /projects/{id}/design-lessons`; `POST .../design-lessons/import`
- `GET /workflow-runs/{id}/design-learning` includes current state and review history.
- `POST .../design-learning/reviews` requires the workflow ETag plus design and
  memory digests; `POST .../design-learning/feedback` links an outcome to a review item.
- Project permissions and database project fences apply. Reviews/lessons are
  append-only through the API, and all writes are audited.
- Planning and interpretation bot recipes read `list_design_lessons` first. Its
  bounded, paginated output explicitly reports remaining lessons.
- This gate governs workflow designs, including autopilot-created workflow drafts.
  Standalone infrastructure compute-draft commands are not scientific design reviews.
  Historical submitted runs are not retroactively described as reviewed.
- Migration `0078_design_memory` creates the records and enables the review gate on
  pending drafts; it does not submit jobs or infer outcomes. A rollback can leave
  the additive graph flag in old records; old software ignores it.

The loop records the predeclared criteria; domain-specific numerical gates remain
in their existing workflow connections. A human judgment in the lesson library
does not override those execution gates.
