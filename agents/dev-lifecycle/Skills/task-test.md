# task-test

Runs unit tests for a task's implementation, records the results, and
— on a pass — marks the task Resolved and its PR ready for review.
Runs after `task-implement`.

## Purpose

Validate one task's build-target slice in isolation before it goes to
human review, and drive the task issue and its PR forward once that
validation passes.

## Preconditions

- A task issue with a PR opened by `task-implement` (draft or already
  merged — this Skill handles both, see step 6).
- `gh` authenticated with write access.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{build_targets}`, `{commands}`.

**2. Fetch the task** (`number,title,body,state,labels,assignees,
comments`) and its PR:

```bash
pr=$(gh pr list --repo {repo} --head "task/{issue}-*" \
       --json number,state,isDraft,baseRefName --jq '.[0]')
```

No PR found and the task is not already marked resolved/closed → this
task has no implementation yet; route to `task-implement`. Not
`type:task` → route: `type:story` to `task-create`, anything else warn
and ask.

**3. Check out the task branch.**

```bash
git fetch origin
git switch "task/{issue}-{slug}"
git pull --ff-only
```

A non-fast-forward pull means someone pushed since the PR was opened —
continue on the up-to-date branch; do not force it.

**4. Resolve the test command.** Prefer a target-specific test command
if `{commands}` distinguishes one for this build target, else the
project's general test command. Not configured → stop and ask (unlike
`task-implement`'s build-verification step, skipping tests silently
here would mark work "Resolved" without ever having run one).

**5. Run the tests.**

```bash
{test_command}
```

Capture full output, pass/fail counts, and duration.

**On failure:** use a systematic debugging approach if the harness
offers one — read the failure output, isolate the failing case,
inspect the relevant code from the design's build-target slice, form a
hypothesis, make the smallest fix, re-run. Up to 3 fix-and-rerun
iterations; still failing after that, stop and report the failures
verbatim rather than iterating further — this is a signal the
implementation or the test plan needs human attention, not more
automated guessing.

**6. Handle the PR state.**

   - **PR is a merged draft or already ready:** someone merged before
     tests ran, or this is a re-run. Fetch its state
     (`References/branch-and-pr-model.md` § Closing Task Issues) and,
     if `MERGED`, close the task issue right there per that section —
     do not wait for a later sweep.
   - **PR is open and draft, tests passed:**

     ```bash
     gh pr ready {pr} --repo {repo}
     ```

   - **No PR at all** (implementation needed no commits): skip this
     step; the task still resolves on test results alone.

**7. Record test results** via `References/artifact-resolution.md`,
sentinel `## dev-lifecycle-test-results`, path
`docs/test-results/{issue}-{timestamp}.md` — pass/fail counts, failing
test names (if any), duration, command used, commit SHA tested.

**8. On a pass, transition the task to Resolved:**

```bash
gh issue edit {issue} --repo {repo} \
  --add-label status:resolved --remove-label status:in-progress
```

Comment the test summary and a link to the PR (if one exists).

**9. Run the All Tasks Resolved Check**
(`References/workflow-states.md` § All Tasks Resolved Check). If every
non-test-execution sub-issue of the parent Story is now resolved or
closed, transition the Story to Resolved and comment that `story-test`
is next; otherwise report how many tasks remain.

**10. Report** pass/fail counts, the task's new state, the PR's new
state, and (if applicable) that the Story is ready for `story-test`.

## Outputs

- A `## dev-lifecycle-test-results` sentinel comment plus a committed
  `docs/test-results/{issue}-{timestamp}.md`.
- The task's draft PR marked ready for review (or closed, if merged).
- Task issue moved to Resolved (or Closed, if its PR had already
  merged).
- Possibly: the parent Story moved to Resolved.

## State Transitions

Task: In Progress → Resolved (step 8), or → Closed directly (step 6,
already-merged case). Story: In Progress → Resolved (step 9), when
this is the last task.

## Errors

- **No test command configured:** stop and ask — do not silently skip.
- **Tests fail after 3 fix iterations:** stop, report failures
  verbatim, leave the task `status:in-progress`.
- **PR already merged into the story branch:** close the task issue
  immediately (step 6); still run and record tests against that
  commit for the results artifact.
- **Task already `status:resolved` or closed:** idempotent — re-run
  tests if asked, but do not re-transition or re-comment redundantly.

Once this task is resolved, stop. Do not chain into `story-test` on
your own initiative — that Skill runs once per Story, not per task.
