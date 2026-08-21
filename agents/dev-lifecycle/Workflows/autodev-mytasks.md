# autodev-mytasks

Implements only the task issues assigned to one engineer. Unlike
`autodev` it does no planning and creates no issues — it picks up
existing tasks and takes each from Open to Resolved, with a single
human gate at the end.

**This is the multi-engineer mode.** Two people can run it at the same
time on the same Story without colliding, because each touches only its
own tasks and every task has its own branch and PR.

## Purpose

Preserve module ownership. `autodev` drives a whole milestone and makes
Story-level decisions; this Workflow deliberately cannot, because those
decisions affect work that belongs to other people.

## Preconditions

- Task issues already exist — `task-create`, or `autodev`'s planner
  phase, has run.
- `gh` authenticated with write access.
- Scope, defaulting to every open task assigned to the current user:
  a milestone, a Story, or another engineer's login narrows it.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{default_branch}`, `{commands}`,
`{build_targets}`.

Resolve `{assignee}` — the login given, else the authenticated user
(`gh api user --jq .login`).

**2. Discover the tasks.**

```bash
gh issue list --repo {repo} --label type:task --assignee "{assignee}" \
  --state open --limit 200 \
  --json number,title,labels,milestone,assignees,body
```

Add `--milestone "{title}"` for a milestone scope; for a Story scope,
list that Story's sub-issues and filter by assignee.

Filter out tasks already carrying `status:resolved`, and the
test-execution tasks — those belong to `story-test`, not here.

Nothing left → say so and stop.

**Group by parent Story.** Tasks under one Story share a story branch
and their order matters.

**Check blockers.** A task carrying `status:blocked` with an unresolved
`Blocked by: #N` runs after its blocker. Where the blocker belongs to
someone else and is unresolved, the task is **not startable** — report
it and skip:

> "#{task} is blocked by #{blocker} ({state}, assigned to @{login}).
> Skipping until it resolves."

**Do not implement the blocker.** It is not yours, and picking it up is
exactly the collision this Workflow exists to avoid.

**3. Present the plan** — a table of task, build target, Story, state,
and blocker — with the counts implementable now and blocked, and a note
that each task gets its own branch and draft PR off its Story's branch.

Ask: all of them, a selected subset, or stop.

**4. Check prerequisites.** For each Story owning a selected task,
verify a design doc exists — the `coder` role aborts in preflight
without one:

```bash
gh issue view {story} --repo {repo} --json comments \
  --jq '[.comments[] | select(.body | startswith("## dev-lifecycle-design-doc"))] | length'
```

Zero → that is a **planning gap, not something this Workflow fixes.**
Report which tasks are affected and ask whether to skip them, run them
anyway with reduced context, or stop. Creating the design here would be
making a Story-level decision on someone else's behalf.

Also run the command pre-flight from `Workflows/autodev.md` step 1 —
missing `build` and `test` are warnings, not blockers.

**5. Implement, one task at a time.** For each selected task,
**sequentially**, run the `coder` role (`Workflows/coder.md`).

Sequential is deliberate here even where the harness could parallelize:
this mode exists to be run alongside other engineers doing the same
thing, and a predictable one-at-a-time footprint is easier to reason
about when several runs share a story branch.

Per returned worker, exactly as `Workflows/autodev.md` step 3 does it:

  a. **Parse the first line** — `RESOLVED` / `IMPLEMENTED` / `PARTIAL`
     / `BLOCKED`. Unrecognized or empty → `BLOCKED`; move on.
  b. **Verify the claim against GitHub**, per
     `Workflows/autodev.md` § Verifying What a Worker Claims. The same
     rule applies here and for the same reason.
  c. **`PARTIAL` → continue**, at most 3 continuations per task.
  d. **`IMPLEMENTED` → attempt test recovery.**
  e. **Squash and push with `--force-with-lease`**, with the same guard
     that every squashed commit belongs to this task.
  f. **`BLOCKED` → report and move on.**

**Stall prevention:** act within one turn of each worker returning.
Never wait, sleep, or poll.

**6. Roll up each affected Story — report only, never close.** Sibling
tasks may belong to other engineers, and this Workflow does not decide
anything about their work.

> "**Story #{story} — {title}:**
> Your tasks: {n}/{n} resolved
> All tasks: {n}/{m} resolved
> Waiting on: #{n} ({target}, @{login})"

Where **every** task across all owners is now resolved, `task-test`
already rolled the Story up to `status:resolved` during step 5 — note
that it is ready for `story-test`, and leave it there.

### Gate — implementation review

The single gate. Present the task table (task, build target, status,
tests, PR), the counts, the per-Story roll-up, and any corrections
verification had to make.

Build the options from what is present: **configure a test command and
run tests** (when any `IMPLEMENTED`), **continue partial**, **re-run
blocked**, or **done**. Run an action option and loop back to this
gate.

**7. Summarize** — tasks resolved and implemented, PR numbers and
states, blocked tasks with reasons, and the per-Story roll-up. Next
step is requesting review on those PRs; `story-test` runs when every
task in a Story is resolved, **including other engineers'**.

## What This Workflow Does Not Do

Deliberately out of scope, because each affects other people's work:

- **Create issues** — no Stories, no tasks. That is `autodev`.
- **Close Stories** — a Story spans owners.
- **Open integration PRs** — a Story-level decision.
- **Touch unassigned tasks** — unassigned means unclaimed, not yours.
  Report it; never implement it.
- **Implement a blocker owned by someone else.**
- **Reassign anything.**

## Outputs

Per task: a branch, a squashed commit, a draft-or-ready PR against the
story branch, unit tests, and a results artifact — all produced by the
`coder` role. This Workflow itself writes nothing but its gate
presentation and summary.

## Errors

- **No tasks assigned:** report and stop.
- **Login does not resolve:** ask for the GitHub login rather than a
  display name or email.
- **Design doc missing for a Story:** the step 4 gate — skip those
  tasks, run anyway, or stop.
- **Task blocked by someone else's work:** skip, report the blocker and
  its owner.
- **Story branch missing:** the Story was never designed. The `coder`
  role creates the branch off the default branch and warns.
- **Two engineers on the same story branch:** expected and supported —
  each task has its own branch. Conflicts surface when the task PRs
  merge, and are handled per
  `References/branch-and-pr-model.md` § Rebasing and Conflicts.

Never merges, closes a Story, or deletes anything — see
`AGENT.md` § Boundaries.
