# autodev

Runs the full pipeline over a milestone, or a single Story within one,
by composing the three worker roles — `planner` → `coder` (per task) →
`validator` — with three human gates between them. Stops rather than
merging anything.

This is a Workflow, not a Skill: it does no GitHub or git work itself.
Every action happens inside a role Workflow, and inside the Skills
those roles invoke. Its job is ordering, gating, verifying what the
workers claim, and reporting across a run that can span hours and
several sessions.

## Purpose

Take a milestone from "requirements written down" to "every task
implemented, tested, and sitting in review-ready PRs," with the fewest
engineer touch-points that still keep each gate intact.

## Preconditions

- A milestone number, or a milestone plus a Story number to run just
  that Story.
- Everything each invoked role and Skill requires. This Workflow
  inherits their preconditions rather than restating them.
- A mode, chosen once at the start and held for the run:

  - **Interactive run** — a human is present at each gate. The default.
  - **Autonomous run** — gates a Skill defines as "ask the engineer"
    resolve to the conservative default that Skill's own Errors section
    specifies (skip, warn-and-continue, or stop — never "guess and
    proceed" past a stop). Use only when told to run unattended, and
    still stop at anything marked a hard stop rather than a warning.

    One gate is **never** auto-approved in either mode:
    `enhance-debugger`'s review gate. See `AGENT.md` § Boundaries.

## Running the Workers

The three roles are ordinary Workflows
(`Workflows/{planner,coder,validator}.md`). How they run is this
Workflow's decision, made once, from what the harness can do:

- **Harness with a subagent primitive:** run each role in its own
  worker with its own context. Independent tasks — no `Blocked by:`
  between them — may run their `coder` workers **concurrently**.
- **Harness without one:** run the same role Workflows **inline and
  sequentially** in this session. Identical steps, gates, and output
  contracts.

State which mode is in use in the opening summary. Inline runs share
one context, so on a long run `checkpoint` between Stories and tell the
engineer that resuming means `resume`, not restarting.

**Nothing else changes between the two.** That is the point of the
roles being Workflows rather than harness agent definitions: the
degradation is a scheduling difference, not a behavioural one.

### Stall prevention

**A returned worker is done.** Act within one turn of it returning —
record the result and move on, or loop for a continuation. **Never
wait, sleep, or poll for a worker.** There is nothing to wait for; the
return *is* the completion signal.

### Verifying what a worker claims

**Do not trust a worker's self-report.** A write can fail in ways the
worker does not notice — `gh` exiting 0 having done nothing is a
documented failure mode (`References/gh-error-handling.md` § 12). A
`coder` reporting `RESOLVED` while the issue carries no
`status:resolved` label would corrupt pipeline state silently, and
every later decision would be made against a lie.

After **every** worker returns, re-read GitHub and reconcile:

```bash
gh issue view {issue} --repo {repo} --json state,labels,comments
gh pr list --repo {repo} --head "task/{issue}-*" --state all \
  --json number,state,isDraft
```

| Claim | Check | On mismatch |
|---|---|---|
| `RESOLVED` | Issue carries `status:resolved` | Apply the label; note the correction |
| `RESOLVED` | A PR exists and is ready, not draft | Mark it ready; note it |
| `IMPLEMENTED` | PR exists in draft | Report the gap; do not resolve |
| any | Claimed commit SHA exists on the branch | Re-run the task; the work is not there |
| any | Claimed artifact sentinel is on the issue | Note it missing; the artifact is unreachable to later steps |

Correct what is correctable, report every correction, and treat a
worker whose claims repeatedly fail verification as `BLOCKED` rather
than continuing to trust it.

A first line that matches none of a role's documented statuses — or an
empty return — is **`BLOCKED`**. Do not guess at intent.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` once, up
front, so every role and Skill in this run reuses the same `{repo}`,
`{build_targets}`, `{commands}` instead of re-discovering them.

**Command pre-flight:** report a missing `build` or `test` command as a
**warning, not a blocker** — a task with no test command completes as
`IMPLEMENTED` rather than `RESOLVED`, which is a legitimate outcome the
engineer should know about at the start rather than discover at the
end.

**2. Plan.** Run the `planner` role against the milestone (or the
Story). It creates Stories, designs each, sizes it, generates its test
plan, and creates its tasks — see `Workflows/planner.md`.

Present its returned plan and, in an interactive run, confirm which
Stories this run carries forward: a milestone can hold Stories nobody
wants automated yet.

### Gate 1 — design review

Present, per Story: the design doc permalink, the effort estimate, the
test plan's case count and P0 count, and the task table with build
targets.

Options: **approve** (continue), **request changes** (feed them back
to `story-design` for that Story and re-present; a change driven by
*changed requirements* rather than a bad design is `replan`'s job, not
another design pass), or **stop**.

A Story rejected repeatedly stops **that Story** — report it and carry
on with the others.

**3. Per Story, implement.** For each task in dependency order,
respecting the `Blocked by:` links `task-create` wrote:

Run the `coder` role, one per task. Independent tasks may run
concurrently where the harness allows; a blocked task waits for its
blocker to resolve.

Each task goes all the way through its `coder` chain — implement,
generate unit tests, run them — **before the next task starts**, per
task. Never batch every implementation and test at the end: a broken
build target should surface before three more are built on the same
misunderstanding.

Then, per returned worker:

  a. **Parse the first line** — `RESOLVED`, `IMPLEMENTED`, `PARTIAL`,
     or `BLOCKED` (`Workflows/coder.md` § Output Contract).

  b. **Verify the claim** against GitHub, per § Verifying What a Worker
     Claims.

  c. **`PARTIAL` → continue it**, passing the code path to resume from
     and what is already done. **At most 3 continuations per task**;
     still partial after that is `BLOCKED`.

  d. **`IMPLEMENTED` → attempt test recovery.** The cause is a missing
     `test` command. If one can be resolved now, run `task-test`
     directly and re-verify; otherwise carry `IMPLEMENTED` forward to
     Gate 2 as a known gap.

  e. **Squash the task's commits**, if the coder left more than one,
     and push with `--force-with-lease`.

     **Guard first: every commit being squashed must belong to this
     task.** Check the range before rewriting anything — a squash that
     swallows a sibling task's commit destroys work that another
     worker, or another engineer, is relying on. On any doubt, leave
     the history alone and report it. Never force-push without
     `--force-with-lease` (`AGENT.md` § Boundaries).

  f. **`BLOCKED` → hold that task**, report it, and continue with its
     runnable siblings. A Story with a stuck task does not block
     sibling Stories.

### Gate 2 — implementation review

Present the task table — task, build target, status, tests, PR — plus
the counts resolved / implemented / blocked, and any corrections
verification had to make.

Build the options from what is actually present: **configure a test
command and run tests** (when any `IMPLEMENTED`), **continue partial**
(when any `PARTIAL`), **re-run blocked** (when any `BLOCKED`),
**approve** to proceed to validation, or **stop**. Run an action option
and loop back to this gate.

**4. Per Story, validate.** Once every implementation task is resolved
or closed, run the `validator` role. It regrounds the test plan on what
was built, runs it, and returns PASS / FAIL / PARTIAL /
TESTS_SKIPPED — see `Workflows/validator.md`.

`FAIL` → hold the Story, report the failing cases, and do not proceed
to Gate 3 for it.

### Gate 3 — closure review

Per Story: the verdict and counts, the integration PR, any cases
flagged OUTDATED, and any regressions.

Options: **approve** (the Story is done from this Workflow's side),
**re-run validation**, or **stop**.

This gate does **not** authorize opening the integration PR — the
`validator` already opened it, opening PRs being inside this pipeline's
boundaries. What it gates is the merge, which is a human action this
Workflow cannot take at all. See `Workflows/validator.md` § What This
Role Does Not Withhold.

**5. Between Stories on a long run, `checkpoint`.** Especially in an
inline run, where every Story shares one context. A run that dies
mid-milestone is resumable from the checkpoint; one that dies without
is resumable only from whatever landed on GitHub.

**6. End-of-run summary.** Stories completed with their integration PR
links, Stories held and why, tasks blocked with their reasons, every
correction verification made, and the suggestion to run the Epic-level
checks in `References/workflow-states.md` once those PRs merge.

Once every Story in the milestone is closed, `enhance-debugger` is the
close-out step — it captures the milestone's learnings and closes it.
Suggest it; do not run it unasked.

This Workflow never merges a PR, so the run's actual completion —
Stories and tasks closing — happens after a human merges what it
opened.

## Deferred Steps

Nothing from Forge's orchestration is now unported. The mid-run
`replan` loop is present as a Gate 1 option rather than an automatic
step, deliberately: a requirement change is a decision, and detecting
drift is not the same as being authorized to act on it.

`autodev-mytasks` covers the multi-engineer case, and `bug-fix` the
bug track; both are separate Workflows rather than modes of this one,
because their gates and scopes genuinely differ.

## Outputs

Whatever the invoked roles and Skills produce, accumulated across the
run: Story and task issues, design docs, effort estimates, test plans,
task and integration PRs, test results, checkpoints. This Workflow
writes nothing itself beyond its gate presentations and summaries.

## Errors

- **A Story's design is rejected repeatedly:** stop that Story, report,
  continue with the others.
- **A task is `BLOCKED`:** hold it, report, continue with runnable
  siblings and other Stories.
- **A worker returns an unrecognized or empty first line:** treat as
  `BLOCKED`. Do not guess.
- **A worker's claims fail verification repeatedly:** treat as
  `BLOCKED` rather than continuing to trust it.
- **A squash range contains another task's commits:** do not rewrite.
  Report and leave the history alone.
- **`context-discovery` cannot resolve `{build_targets}`:** stop the
  whole run — every downstream step needs it.
- Anything a called Skill treats as a hard stop is a hard stop here
  too; this Workflow does not override a Skill's error handling.

This Workflow never merges a PR, deletes a branch or an issue,
force-pushes without `--force-with-lease`, or resets or cleans a
working tree — see `AGENT.md` § Boundaries, which binds every role and
Skill it calls as much as it binds this Workflow.
