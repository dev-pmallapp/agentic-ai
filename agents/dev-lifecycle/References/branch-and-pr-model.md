# Branch and PR Model

This pipeline uses **stacked branches**: each task gets its own branch
and PR targeting a shared story branch; the story branch merges to the
default branch through one integration PR.

```
task/61-libtelemetry ─┐
                      ├─► story/57-flow-export ──► main
task/62-exporter-svc ─┘        (integration PR at story-test)
```

This gives review at both levels: a focused PR per build target (the
unit that has its own tests), and one integration PR that shows the
whole feature.

## Branch Naming

| Kind | Pattern | Base | Created by |
|---|---|---|---|
| Story | `story/{story}-{slug}` | `{default_branch}` | `story-design` (or `task-implement`, if absent) |
| Task | `task/{task}-{slug}` | the story branch | `task-implement` |

`{slug}` is lowercase kebab-case — derived from the build target name
for tasks, the issue title for stories — truncated to 40 characters,
with runs of non-alphanumerics collapsed to a single `-` and
leading/trailing `-` stripped. `libhft.lib` → `libhft-lib`. `Live flow
export!` → `live-flow-export`.

The issue number lives in the branch name so a branch is always
traceable, and so `git ls-remote --heads origin "task/61-*"` finds an
existing branch regardless of the slug.

## Creating the Story Branch

```bash
git fetch origin
git switch --create "story/{story}-{slug}" "origin/{default_branch}"
git push -u origin "story/{story}-{slug}"
```

If it already exists (locally or on the remote), reuse it:

```bash
git ls-remote --heads origin "story/{story}-*"
git switch "story/{story}-{slug}"
git pull --ff-only
```

A non-fast-forward pull means someone else advanced the branch — stop
and report; never merge or rebase unasked.

## Creating a Task Branch and Draft PR

```bash
git fetch origin
git switch "story/{story}-{slug}"
git pull --ff-only
git switch --create "task/{task}-{slug}"
```

Implement, commit (`#{task}: message`), then push and open the PR:

```bash
git push -u origin "task/{task}-{slug}"

gh pr create --repo {repo} --draft \
  --base "story/{story}-{slug}" \
  --head "task/{task}-{slug}" \
  --title "#{task}: Implement {build_target}" \
  --body-file /tmp/dl-pr-body.md
```

**Do not write `Closes #{task}` in this PR body.** The PR targets the
story branch, so the keyword never fires there — see the closing-
keyword gotcha below — and its presence would falsely imply that
merging closes the task. Mark the PR with an HTML comment
(`<!-- dev-lifecycle:task-pr {task} -->`) so a later pass can identify
which PRs this pipeline opened.

The PR is created **draft**. `task-test` marks it ready once unit
tests pass.

**Nothing to push:** `gh pr create` fails with "No commits between..."
when implementation produced no commits (for example, when
`task-implement` detects the code already exists and only verifies
it). Skip PR creation, note it, and continue — there is no change to
review.

## Marking Ready for Review

```bash
pr=$(gh pr list --repo {repo} --head "task/{task}-{slug}" \
       --state open --json number --jq '.[0].number')
[ -n "$pr" ] && gh pr ready "$pr" --repo {repo}
```

No PR exists (implementation ran without one) → skip silently; the
task is still resolvable without one.

## Closing Task Issues — the part that differs from every other issue tracker

GitHub honours closing keywords (`Closes`, `Fixes`, `Resolves`) **only
when the PR merges into the repository's default branch.** A task PR
merges into the *story* branch, so:

- `Closes #{task}` in a task PR body does **nothing** on merge.
- The task issue stays open until something closes it explicitly.

Getting this wrong looks fine in testing — the task issue just quietly
stays open forever, which is exactly why it is called out here rather
than left implicit. This pipeline closes task issues explicitly, once
their PR merges:

```bash
state=$(gh pr view {pr} --repo {repo} --json state --jq .state)
if [ "$state" = "MERGED" ]; then
  gh issue close {task} --repo {repo} --reason completed \
    --comment "Merged into \`story/{story}-{slug}\` via #{pr}."
fi
```

`task-test` performs this check when it runs against an
already-merged PR; `story-test` sweeps any stragglers before opening
the integration PR. Only the **integration PR** — story branch to
default branch — carries `Closes`, and it fires because that merge
lands on the default branch.

## The Integration PR

```bash
gh pr create --repo {repo} \
  --base "{default_branch}" \
  --head "story/{story}-{slug}" \
  --title "#{story}: {story_title}" \
  --body-file /tmp/dl-integration-pr.md
```

Body lists **one `Closes #N` per line** — for the Story and every
task. GitHub does not parse a comma-separated list (`Closes #1, #2`)
as multiple references; only the first would link.

## Merge Order

```
1. Task PRs      → story branch     (review per build target)
2. Integration PR → default branch  (review the feature end to end)
```

This pipeline **opens** PRs and marks them ready; it never merges
them. Merging is a human decision, gated by review and CI.

Before opening the integration PR, verify every task PR against the
story branch is merged or closed:

```bash
gh pr list --repo {repo} --base "story/{story}-{slug}" \
  --state open --json number,title,isDraft
```

Any still open → report it and ask before opening the integration PR
anyway; its changes are not in the story branch yet.

## Rebasing and Conflicts

Task branches are siblings off the same story branch. When two tasks
touch the same file, the second PR conflicts. This pipeline does
**not** auto-rebase or auto-resolve — it reports the conflicting files
and the rebase command:

```bash
git switch task/{task}-{slug} && git rebase origin/story/{story}-{slug}
```

The one-build-target-per-task rule exists partly to make this rare:
two tasks should not own the same source files. Frequent conflicts are
a signal the task decomposition is wrong.

## Detached and Dirty States

Before any branch operation:

```bash
git rev-parse --abbrev-ref HEAD          # not "HEAD" (detached)
git status --porcelain                   # empty, or only expected files
```

- **Detached HEAD** → stop: check out a branch before continuing.
- **Uncommitted changes** → in an interactive run, ask whether to
  stash, commit as WIP, or abort. In an autonomous run, commit them as
  `#{issue}: WIP` before switching, so nothing is lost.
- **Never** `git checkout -f`, `git reset --hard`, or `git clean` to
  clear the way. Losing an engineer's uncommitted work is
  unrecoverable — see `AGENT.md` `## Boundaries`.

## Stale Branch Cleanup

After the integration PR merges, a human deletes the story branch and
any merged task branches:

```bash
gh pr merge {integration_pr} --repo {repo} --delete-branch   # human-run
git fetch --prune
git branch --merged "origin/{default_branch}" \
  | grep -E '^\s+(task|story)/' | xargs -r git branch -d
```

This pipeline suggests the cleanup in its final summary; it does not
delete branches on its own — see `AGENT.md` `## Boundaries`.
