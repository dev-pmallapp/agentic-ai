# story-test

Validates a Story once every task resolves: sweeps any task issues left
open by an already-merged PR, runs the Story's aggregate tests, records
results, and opens the **integration PR** that closes the Story and
its tasks when a human merges it.

## Purpose

Confirm the Story works end to end — not just target by target — and
hand off a single reviewable PR (story branch → default branch) that
closes everything on merge.

## Preconditions

- A Story with every non-test-execution task at `status:resolved` or
  closed (the All Tasks Resolved Check in `task-test` step 9 sets
  this up; this Skill re-verifies rather than trusting a stale
  invocation).
- `gh` authenticated with write access.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{default_branch}`, `{build_targets}`,
`{commands}`.

**2. Fetch the Story and its sub-issues**
(`References/gh-operations.md` § Sub-issues), including the
test-execution task created by `task-create`. Not `type:story` → route.
Any implementation task not yet resolved or closed → warn and ask
before proceeding; running story-level tests against incomplete work
produces misleading results.

**3. Sweep straggler task closures.** For each implementation task
still open, check its PR:

```bash
gh pr list --repo {repo} --head "task/{task}-*" \
  --json number,state --jq '.[0]'
```

`MERGED` and the task issue is still open → close it now
(`References/branch-and-pr-model.md` § Closing Task Issues). This
covers the case where a task's PR merged after `task-test` last ran.

**4. Switch to the story branch** and pull latest:

```bash
git fetch origin
git switch "story/{story}-{slug}"
git pull --ff-only
```

**5. Run the Story's tests.** Resolve a story-level test plan via
`References/artifact-resolution.md` (sentinel
`## dev-lifecycle-test-plan`) — optional, since generating one is not
yet ported (see `AGENT.md`). If found, follow its test list. If
absent, fall back to running the full project test command from
`{commands}` scoped to the build targets this Story touched (from the
design doc's `## Build Targets` table), and say plainly that this is
reduced grounding without a formal story-level plan.

**On failure:** as in `task-test`, debug with a systematic approach
where the harness supports it, up to 3 fix-and-rerun iterations across
whichever task branch owns the failing area, then stop and report
verbatim rather than iterating further.

**6. Record results** via `References/artifact-resolution.md`,
sentinel `## dev-lifecycle-test-results`, path
`docs/test-results/{story}-{timestamp}.md`.

**7. On a pass, resolve the test-execution task:**

```bash
gh issue edit {test_execution_task} --repo {repo} \
  --add-label status:resolved --remove-label status:blocked
```

**8. Verify no task PR against the story branch is still open**
(`References/branch-and-pr-model.md` § Merge Order). Any open → report
it and confirm before proceeding; its changes are not yet in the story
branch the integration PR is about to represent.

**9. Open the integration PR**
(`References/branch-and-pr-model.md` § The Integration PR), with one
`Closes #N` line per line for the Story and every task, **including**
the test-execution task:

```markdown
Closes #{story}
Closes #{task_1}
Closes #{task_2}
Closes #{test_execution_task}
```

**10. Report** the integration PR link and that merging it (a human
decision — this pipeline never merges) closes the Story and every
task automatically via GitHub's closing keywords, because that merge
lands on `{default_branch}`.

**11. Opportunistic Epic check.** Run the All Stories Closed Check
(`References/workflow-states.md` § All Stories Closed Check). It will
typically only find every Story closed on a later invocation, once
this and other Stories' integration PRs have actually merged — running
it now is cheap and catches the case where this happens to be the
last one.

## Outputs

- A `## dev-lifecycle-test-results` sentinel comment plus a committed
  `docs/test-results/{story}-{timestamp}.md`.
- Any straggler task issues closed.
- The test-execution task resolved.
- An integration PR (story branch → default branch) with one `Closes`
  line per issue, open and ready for human review and merge.

## State Transitions

Test-execution task: Open/`status:blocked` → Resolved (step 7). Story
and implementation tasks: **not** transitioned to Closed by this
Skill — that happens when a human merges the integration PR and
GitHub's closing keywords fire (see `References/branch-and-pr-model.md`
§ Closing Task Issues and § The Integration PR).

## Errors

- **A task is not yet resolved:** warn and ask before running
  Story-level tests against incomplete work.
- **No story-level test plan and no general test command configured:**
  stop and ask — do not fabricate a pass.
- **A task PR is still open against the story branch:** report it;
  confirm before opening the integration PR anyway.
- **Integration PR already exists for this branch:** reuse it, do not
  create a duplicate.

This pipeline opens the integration PR and stops. Merging it is a
human decision — see `AGENT.md` `## Boundaries`.
