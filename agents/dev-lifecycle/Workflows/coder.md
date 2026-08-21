# coder

The implementation role: takes one task from Open to Resolved —
implements its build target, generates and runs unit tests, and leaves
a PR ready for review. Composed by `autodev` and `autodev-mytasks`;
independently invocable on its own.

## Purpose

One of three worker roles — `planner`, `coder`, `validator`. Scoped to
**exactly one task**, which is what makes it safe to run several in
parallel: one build target, one branch, one PR, no shared files.

## Preconditions

- A `type:task` issue whose parent Story has a design doc.
- `gh` authenticated with write access.
- Everything the invoked Skills require.

## Running This Role

As `Workflows/planner.md` § Running This Role. With a subagent
primitive, one worker per task — that is the arrangement this role is
shaped for, and it is why the context-budget check in step 4 exists.
Without one, the orchestrator runs tasks **sequentially** inline; the
steps and the output contract are unchanged.

## Procedure

**1. Preflight — validate the whole chain before starting.** The point
is to avoid doing significant work and then hitting a blocker.

Run `References/context-discovery.md` in full. Then fetch the task
(`number,title,body,state,labels,assignees,milestone,comments`) and
check:

- **Type:** `type:task`, else **abort** — do not prompt, fail fast.
  The orchestrator routed wrongly and should learn that immediately.
- **Parent Story:** resolve it (`References/gh-operations.md`
  § Sub-issues, or the `Parent: #N` body line). None → abort; there is
  no design context to implement against.
- **Blocker:** `status:blocked` with an unresolved `Blocked by: #N` →
  abort. Sequencing blockers is the orchestrator's job, not this
  role's.
- **Design doc:** resolve for the parent Story via
  `References/artifact-resolution.md` § Resolution Chain. Found in the
  chain → record it. Only the final prompt-the-engineer step would
  match → abort; a worker has no engineer to prompt.
- **Build and test commands:** resolve from
  `References/project-commands.md`. **These two are warnings, never
  aborts** — see step 5 for what a missing test command does.

Report the preflight result as a short checklist before proceeding, so
a failure is legible without reading the whole run.

**2. Apply the idempotency rules** in `## Idempotency` below, and
reuse any existing branch and PR rather than creating duplicates:

```bash
git ls-remote --heads origin "task/{task}-*"
gh pr list --repo {repo} --head "task/{task}-*" --state all \
  --json number,state,isDraft
```

**3. Implement.** Run `task-implement`. It loads design context and
coding conventions, creates the task branch off the story branch,
implements the build target, verifies the build (or skips with a
warning), reviews, squashes to one commit, and opens a **draft PR**
against the story branch.

**4. Check the context budget after each code path.** If work is done
and the context is running low — output limits approaching, many tool
calls spent — **do not start the next code path.** Instead: commit
everything completed, push the branch so nothing is lost if this worker
dies, and return `PARTIAL` with the completed and remaining lists plus
a resume line.

Stopping deliberately is far better than hitting the limit mid-way,
which leaves uncommitted work and a state nobody can resume from.

**5. Generate unit tests.** Run `task-test-plan`, which grounds the
cases on the implementation diff. In a worker there is no engineer, so
it auto-selects the framework from existing tests and proceeds without
its review gate — the autonomous path that Skill already describes.

**6. Run the tests.** No test command configured → **skip this step
and step 7.** The task stays In Progress, its PR stays draft, and this
role returns `IMPLEMENTED` rather than `RESOLVED`. Resolving work whose
tests never ran would put a false signal into pipeline state, which is
the thing the whole verify-don't-assume discipline exists to prevent.

Otherwise run `task-test`. It runs the tests, records results, and on a
pass marks the PR ready and labels the task `status:resolved`.

**7. Retry on failure, at most 3 attempts.** Each attempt reads the
failure output, forms a hypothesis, makes a **targeted** fix rather
than shotgun changes, and re-runs — narrowed to the failing tests where
the framework allows it. Use a systematic debugging aid if the harness
offers one, and the project's `debug` command if
`References/project-commands.md` resolves one.

Still failing after the third → **stop and question whether the
approach is sound.** Return `BLOCKED` with the analysis. More
automated attempts past this point produce noise, not fixes; this is a
signal for human attention.

Intermediate fix commits are squashed before the PR is finalized.

**8. Return** per the output contract.

## Output Contract

**The first line is parsed by the orchestrator. Keep its shape exact.**

```
#{task} ({target}): RESOLVED
Build: {command} ✓ | ⚠ SKIPPED (not configured)
Branch: task/{task}-{slug}
Commit: {sha} (squashed)
PR: #{pr} (ready for review) → story/{story}-{slug}
Tests: {passed}/{total} PASS
Results: docs/test-results/{task}-{timestamp}.md
```

```
#{task} ({target}): IMPLEMENTED (tests pending)
Build: {command} ✓ | ⚠ SKIPPED (not configured)
Branch: task/{task}-{slug}
Commit: {sha} (squashed)
PR: #{pr} (draft) → story/{story}-{slug}
Tests: ⚠ DEFERRED (no `test` command in CONTRIBUTING.md)
Unit tests: generated by task-test-plan
Resume: add a `test` command, then run task-test {task}
```

```
#{task} ({target}): PARTIAL
Completed: {list} ({done}/{total} code paths)
Remaining: {list}
Branch: task/{task}-{slug} (pushed)
Commit: {sha}
PR: #{pr} (draft)
Last code path completed: {name}
Resume: implement task #{task}, continuing from code path {next};
already completed {list}
```

```
#{task} ({target}): BLOCKED
Branch: task/{task}-{slug} (pushed)
PR: #{pr} (draft)
Tests: {passed}/{total} PASS, {failed} FAIL
Failures: {test}, {test}
Analysis: {why three attempts did not fix it}
```

An orchestrator that cannot match one of these four first words treats
the result as `BLOCKED` and moves on — see
`Workflows/autodev.md` § Running the Workers.

## Idempotency

| Task state | Action |
|---|---|
| Closed | Skip — return `RESOLVED (already complete)` |
| `status:resolved` | Skip — return `RESOLVED (already complete)` |
| `status:in-progress` | Resume — find the existing branch and PR, continue from there |
| `status:in-progress`, resuming a `PARTIAL` | The orchestrator names the code path to continue from and what is already done. Skip the completed ones |
| No `status:` label | Start fresh |

## Outputs

A task branch, one squashed commit, a PR against the story branch,
generated unit tests, a test-results artifact, and the task issue moved
to Resolved (or left In Progress on `IMPLEMENTED` / `PARTIAL` /
`BLOCKED`).

## Errors

- **Not a task, no parent, blocked, or no design doc:** abort in
  preflight. All four are the orchestrator's sequencing errors, and
  failing fast is what lets it correct them.
- **No build command:** warning. Skip build verification and say so —
  in a compiled language this makes a test failure more likely, which
  the preflight report should call out.
- **No test command:** return `IMPLEMENTED`, never `RESOLVED`.
- **Tests fail after 3 attempts:** return `BLOCKED` with the analysis;
  leave the task `status:in-progress`.
- **Context exhausted mid-task:** commit, push, return `PARTIAL`.

Never merges, deletes a branch or issue, or resets a working tree —
see `AGENT.md` § Boundaries.
