# autodev

Runs the full pipeline over a milestone (or a single Story within one):
`story-create` → per Story (`story-design` → `task-create` → per task
(`task-implement` → `task-test`) → `story-test`). Sequences the six
Skills in this port, owns the human approval gates between them, and
stops rather than merging anything.

This is a Workflow, not a Skill: it does not do any GitHub or git work
itself — every action happens inside the Skill it invokes at that
step — its job is ordering, gating, and reporting across a run that
can span hours and multiple sessions.

## Purpose

Take a milestone (or one of its Stories) from "requirements written
down" to "every task implemented, tested, and sitting in review-ready
PRs," with the fewest engineer touch-points that still keep each
step's approval gate intact.

## Preconditions

- A milestone number, or a milestone number plus a specific Story
  number to run just that Story's pipeline.
- Everything each invoked Skill itself requires — this Workflow does
  not re-state those preconditions, it inherits them.
- A decision, made once at the start of the run and held for its
  duration, between two modes:

  - **Interactive run** — a human is present at each gate (design
    approval, review approval, the choice to proceed past a warning).
    This is the default.
  - **Autonomous run** — gates that a Skill defines as "ask the
    engineer" are instead resolved by the conservative default that
    Skill's own Errors section specifies (skip, warn-and-continue, or
    stop — never "guess and proceed" past a stop). Use this only when
    told to run unattended; still stop at anything a Skill marks as a
    hard stop rather than a warning.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` once,
up front, so every Skill this run invokes reuses the same resolved
`{repo}`, `{build_targets}`, `{commands}` instead of re-discovering
them.

**2. Story generation.** If given a milestone with no Story number,
run `story-create` against it. Present the resulting Story list (or
the existing ones, if `story-create` found nothing new) and, in an
interactive run, get confirmation of which Stories this run should
carry forward before continuing — a milestone can hold Stories nobody
wants automated yet.

**3. Per Story, run the Story pipeline:**

   a. **`story-design`.** If a design doc already exists (the Skill's
      own existing-design gate), it reports and stops immediately —
      treat that as "already designed," not a failure, and continue to
      3b. Otherwise it runs the full design session with its own
      section-by-section approval gates; in an interactive run those
      gates are real pauses, in an autonomous run they resolve as
      described above, but the **final design approval** in that
      Skill's step 7 is never skipped — an unapproved design does not
      get committed, so this Workflow has nothing to hand `task-create`
      until a human (or the run's designated stand-in approval,
      explicitly configured) has signed off.

   b. **`task-create`.** Runs once the design doc is committed. Present
      the created/existing task table before moving on.

   c. **Per task, in dependency order** (respect any `Blocked by:`
      links `task-create` wrote — do not start a blocked task before
      the thing blocking it resolves):

      i.  **`task-implement`.**
      ii. **`task-test`**, immediately after, on the same task —
          never batch every task's implementation before testing any
          of them; a broken build target should surface before three
          more are built on top of the same misunderstanding.

      Independent tasks (no `Blocked by:` between them) may run
      concurrently — spawn one subagent per task if the harness
      supports running work in parallel, otherwise work through them
      one at a time in dependency order. Either way, each task still
      goes through `task-implement` then `task-test` as a pair before
      the next one starts, per task.

      A task that fails `task-test` after its own retry budget is
      **not** retried again here — report it and hold that Story at
      "tasks in progress," continuing with any of its still-runnable
      sibling tasks. A Story with a stuck task does not block sibling
      Stories.

   d. **`story-test`**, once every non-test-execution task for this
      Story is resolved or closed (the check `task-test` itself runs
      after the last one). Its output is the integration PR.

**4. Per-Story summary.** After `story-test` opens the integration PR,
report it and move to the next Story queued for this run. Do not open
a Story's integration PR and then keep making changes on that story
branch from a later step — once `story-test` has run, that Story is
done from this Workflow's side.

**5. End-of-run summary.** Once every queued Story has reached
`story-test` (or is parked on a reported failure), report: Stories
completed with their integration PR links, Stories still blocked and
why, and the suggestion to run the Epic-level checks in
`References/workflow-states.md` once those PRs merge. This Workflow
never merges a PR — see `AGENT.md` `## Boundaries` — so the run's
actual completion (Stories and tasks closing) happens after a human
merges what this run opened.

## Deferred Steps

Forge's fuller autodev pipeline includes a sizing pass, a mid-run
checkpoint/replan loop, and dedicated test-plan generation skills
(`task-test-plan`, `story-test-plan`) ahead of implementation. None of
those are ported yet — see `AGENT.md` for what is and is not in this
port. Their absence means: task granularity is whatever `task-create`
derived from the design doc with no separate sizing check, there is no
mid-run "are we still on track" gate beyond each Skill's own approval
gates, and `task-test` / `story-test` run against whatever test plan
`References/artifact-resolution.md` can resolve (optional, per those
Skills' own procedures) rather than a plan generated specifically for
this run.

## Outputs

Whatever the invoked Skills produce, accumulated across the run:
Story and task issues, design docs, task and integration PRs, test
results. This Workflow itself writes nothing new — it has no output
beyond the sequencing and the summaries in steps 4-5.

## Errors

- **A Story's design is rejected repeatedly:** stop that Story's
  pipeline, report it, continue with other queued Stories.
- **A task is stuck (failed retries in `task-test`):** hold that
  Story, report the specific task, continue with independent sibling
  tasks and other Stories.
- **`context-discovery` cannot resolve `{build_targets}` at all:**
  stop the whole run — every downstream Skill needs it.
- Anything a called Skill treats as a hard stop is a hard stop here
  too; this Workflow does not override a Skill's own error handling.

This Workflow never merges a PR, deletes a branch, deletes an issue,
force-pushes, or resets/cleans a working tree at any point in this
sequence — see `AGENT.md` `## Boundaries`, which binds every Skill it
calls as much as it binds this Workflow directly.
