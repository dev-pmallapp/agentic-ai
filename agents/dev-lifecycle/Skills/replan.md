# replan

Detects that a Story's requirements changed after its design was
agreed, and proposes an **incremental** update to the design doc, the
task sub-issues, and the test plan.

## Purpose

Incremental is the whole point. Regenerating a design from scratch
throws away decisions that are still valid and orphans tasks that are
already implemented — so this Skill edits sections rather than
replacing documents, and classifies every affected task by what its
state actually permits.

## Preconditions

- A `type:story` issue with an existing design doc.
- `gh` authenticated with write access.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.

**2. Load the current state.**

- **Fetch the Story** with comments and its `updatedAt`. Not
  `type:story` → route and stop.
- **Resolve the design doc** via `References/artifact-resolution.md`
  § Resolution Chain — **required**. Note the timestamp of the sentinel
  comment carrying it: that is when the design was last agreed, and
  every comparison below is against that moment.
- **List the tasks** and record each one's state — resolved, in
  progress, or untouched. This drives everything; an implemented task
  cannot simply be deleted.
- **Resolve the test plan** — optional, but usually present.
- **Read the `## Milestone Source` block** from the Story body — the
  delimited section `story-create` wrote, holding the requirement text
  verbatim as it stood when the Story was created.

**3. Detect the change.** Compare three sources against the design:

*Milestone description versus `## Milestone Source`.* Fetch the
milestone and find this feature's row. Differs from the recorded text →
the upstream requirement changed. Report both texts and the difference,
rather than only your reading of it.

*Story body versus design doc.* The body may have been edited since —
compare the issue's `updatedAt` against the design comment's
`createdAt`, and diff requirements and acceptance criteria against the
design's problem statement and solution overview.

*Comments since the design.* Requirement changes often arrive in prose
("we also need…", "scrap the X approach"). **Surface them; do not
treat them as authoritative on your own** — a comment is a
conversation, not a decision, and deciding which is which is the
engineer's call.

No change detected anywhere → report the consistency check and then ask
for the change directly rather than stopping. The engineer invoked this
Skill for a reason; the absence of *detectable* drift does not mean
there is no drift.

**4. Analyze the impact.** Map the change onto the existing artifacts —
this is the core of the Skill.

| Change type | Design impact | Task impact | Test impact |
|---|---|---|---|
| New capability | New code path, possibly a new build target | New task, or extend an existing one | New cases |
| Removed capability | Delete a code path | Close or descope a task | Mark cases not-applicable |
| Changed behaviour | Revise a code path | Existing task, possibly reopened | Update cases |
| Changed interface | Revise interfaces and any cross-target contract | Every consuming task | Update the cases asserting it |
| Non-functional | Testing strategy | Usually none | New cases in that category |

Then classify each affected task **by its state**, which determines
what is possible rather than what is desirable:

| Task state | Change is | Proposal |
|---|---|---|
| Not started | anything | Update the body; retitle if the build target changed |
| In progress | additive | Comment the delta on the task; the engineer folds it in |
| In progress | contradictory | Flag it — the engineer decides whether to stop the work |
| Resolved | additive | New follow-up task; do not reopen |
| Resolved | contradictory | Reopen with an explanation, or a new task — engineer's call |
| Merged | anything | Never reopen. New task, referencing what it revises |

**An implemented, merged task is history. Revising history is a new
task, not an edit.**

**5. Present the delta** — the change and its source quoted, the
design-doc impact by section, the task impact table with a proposal per
task, the test-plan impact in counts, and the effort delta if known.

Then ask: apply everything; design only, leaving tasks and plan for
later; walk each proposed change individually; or stop and change
nothing.

**6. Apply, in this order** so downstream artifacts see updated
upstream ones.

*Design doc.* Edit the affected sections **in place** — do not
regenerate. Append a revision record naming the date, the source, what
changed and why, and the sections revised. Commit on the story branch,
push, and post a **new** `## dev-lifecycle-design-doc` sentinel
comment — new, not an edit: the history of what was agreed when is
worth keeping, and consumers take the most recent sentinel
automatically.

*Tasks.*

- **Not started:** edit the body; retitle if the build target changed.
- **In progress:** comment the delta. Do **not** silently edit the body
  of work someone is midway through — they may have read it already,
  and a changed spec they never saw is worse than no spec.
- **Resolved or merged:** create a follow-up task linked to the
  original (`Revises #{n}` in the body), as a sub-issue of the same
  Story.
- **New:** create per `Skills/task-create.md`, including the sub-issue
  link and the `Parent: #N` body line.
- **Descoped:** close with `--reason not_planned` and an explanation.
  **Never delete an issue** (`AGENT.md` § Boundaries).

*Test plan.* Where implementation exists, route to `story-test-replan`
— it regrounds on the code as well as the requirement change.
Otherwise edit the plan directly: add cases for new capability, mark
removed ones not-applicable, and flag changed ones outdated **without
rewriting their expectations**.

*Summary comment* on the Story: the change and its source, an
artifact/action table, and the effort delta.

**7. Report** sections revised, tasks updated, created and closed, the
test-plan delta, and the effort change. Where an in-progress task
received a contradictory change, say so prominently and name the
assignee — they should stop and read the delta before continuing.

## What This Skill Will Not Do

- **Regenerate the design from scratch.** Incremental only. For a
  wholesale rewrite the honest move is a new Story.
- **Reopen merged work.** A merged task is history; revisions are new
  tasks.
- **Delete issues.** Descoped work is closed as `not_planned`, with a
  reason, and stays readable.
- **Silently edit an in-progress task's body.** The assignee may have
  already read it.

## Outputs

- A revised design doc, committed, with a new sentinel comment and a
  revision-history entry.
- Task bodies edited, delta comments posted, follow-up tasks created,
  descoped tasks closed as `not_planned`.
- An updated test plan, or a `story-test-replan` run.
- A summary comment on the Story.

## State Transitions

No direct `status:` transitions on the Story. Tasks may be created
(Open), closed as `not_planned`, or — only on the engineer's explicit
decision — reopened to `status:reopened` per
`References/workflow-states.md`.

## Errors

- **No design doc:** there is nothing to replan — route to
  `story-design`.
- **No change detected:** report the consistency check and ask the
  engineer to describe the change.
- **No `## Milestone Source` block:** the Story predates that
  convention or was created by hand. Fall back to comparing the issue
  body against the design, and note the reduced detection.
- **Milestone deleted, or the feature row removed:** the requirement
  may have been descoped entirely. Flag this prominently — descoping a
  Story mid-implementation is a decision, not a detail.
- **Change contradicts merged work:** never reopen. Propose a follow-up
  task and state plainly that the merged behaviour will need reverting
  or superseding.
- **Standard `gh` failures:** `References/gh-error-handling.md`.
