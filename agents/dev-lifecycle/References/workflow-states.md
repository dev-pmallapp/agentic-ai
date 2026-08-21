# Workflow States

States: **Open → In Progress → Resolved → Closed** (+ Reopened).

Principle: **In Progress** = work actively happening. **Resolved** =
work done, pending validation. **Closed** = validated.

## Representation

Labels are the source of truth.

| State | GitHub issue state | `status:` label |
|---|---|---|
| Open | open | (none) |
| In Progress | open | `status:in-progress` |
| Resolved | open | `status:resolved` |
| Closed | closed (`completed`) | (labels left as-is) |
| Reopened | open | `status:reopened` |

An issue carries **at most one** `status:` label. Every transition
adds the new one and removes the old one in a single
`gh issue edit --add-label X --remove-label Y`.

Transitions are **idempotent**. Read the current labels from the fetch
already done for this issue, and skip when the target state is already
set — re-running a Skill must never error or produce a duplicate
comment.

```bash
# Open -> In Progress
gh issue edit {issue} --repo {repo} \
  --add-label status:in-progress --remove-label status:reopened

# In Progress -> Resolved
gh issue edit {issue} --repo {repo} \
  --add-label status:resolved --remove-label status:in-progress

# Resolved -> Closed
gh issue close {issue} --repo {repo} --reason completed \
  --comment "{closing note}"

# Reopen
gh issue reopen {issue} --repo {repo}
gh issue edit {issue} --repo {repo} \
  --add-label status:reopened --remove-label status:resolved
```

`--remove-label` on a label the issue does not carry is safe to
ignore — treat it as a no-op rather than an error.

## Epic (Milestone) Lifecycle

A milestone has only `open` / `closed`, so Epic state is **derived**:

```
Open         milestone open, no Stories yet
In Progress  milestone open, >=1 Story exists
Resolved     milestone open, all Stories closed
Closed       milestone closed
```

| State | Meaning | Who transitions |
|---|---|---|
| Open | Not started | — |
| In Progress | Stories being designed or implemented | `story-create`, implicitly, by creating Stories |
| Resolved | All Stories closed, pending handoff | `story-test`, on the last Story (posts to the tracker) |
| Closed | Handoff complete | `enhance-debugger`, after its review gate and only once every Story is closed — or a human |

`open_issues` / `closed_issues` on the milestone give the progress
numbers directly — no issue listing needed for a roll-up count.

Because there is nothing to label on a milestone, "Resolved" is
announced by a comment on the **epic tracker issue** (created on
demand — see `References/gh-operations.md` § Epic tracker issue) and
by labelling that tracker `status:resolved`. See `AGENT.md` `##
Gotchas` for why the tracker issue exists at all.

## Story Lifecycle

```
Open        --[story-design]--------------------> In Progress
In Progress --[all tasks Resolved]----------------> Resolved
Resolved    --[story-test passes, integration PR merged]--> Closed
```

| State | Meaning | Who transitions |
|---|---|---|
| Open | Not started | — |
| In Progress | Design, task creation, or implementation underway | `story-design` (on invocation) |
| Resolved | All tasks resolved, ready for Story-level validation | `task-test`, on the last task |
| Closed | Test plan passed and the integration PR merged | `story-test`, or the merge itself |
| Reopened | `story-test` failed, or issues found post-close | `story-test` or a human |

The Story closes **either** because `story-test` closed it explicitly,
**or** because the integration PR carrying `Closes #{story}` merged
into the default branch. Both paths are expected — check whether the
issue is already closed before trying to close it.

## Task Lifecycle

```
Open        --[task-implement]------------------> In Progress
In Progress --[task-test passes]-----------------> Resolved
Resolved    --[task PR merged into the story branch]--> Closed
```

| State | Meaning | Who transitions |
|---|---|---|
| Open | Not started, assigned | — |
| In Progress | Implementation underway, draft PR open | `task-implement` (on invocation) |
| Resolved | Code complete, unit tests pass, PR ready for review | `task-test` |
| Closed | PR merged | `task-test`, on a merged PR, or the integration PR merge |
| Reopened | Test regression or review rejection | a human |

**Task issues do not auto-close on their own PR merge** — see
`References/branch-and-pr-model.md` § Closing Task Issues.

## All Tasks Resolved Check

After a task resolves (`task-test` passes):

1. List the parent Story's sub-issues
   (`References/gh-operations.md` § Sub-issues).
2. Check whether **all** carry `status:resolved` or are closed. The
   "Execute test plan" task (created by `task-create`, resolved by
   `story-test`) is **excluded** from this count — including it would
   mean a Story could never reach "all resolved" from here.
3. If yes: transition the Story to Resolved and comment that it is
   ready for `story-test`.

## All Stories Closed Check

After a Story closes (`story-test` passes):

1. List Stories in the milestone
   (`gh issue list --milestone --label type:story --state all`).
2. If all are closed: resolve or create the epic tracker issue, label
   it `status:resolved`, and comment that the Epic is ready for
   handoff. **Leave the milestone open** — closing it is a human
   decision (or a future close-out step this port does not yet have —
   see `AGENT.md`).

## Parallel Engineer Detection

Before starting design on a Story:

1. Fetch it (`labels`, `assignees`, `state`).
2. If it carries `status:in-progress`, check `assignees`.
3. If the assignee differs from `{current_user}`, warn and ask before
   continuing.

Also check for an existing story branch — a stronger signal than the
label, since it means someone has actually started:

```bash
git ls-remote --heads origin "story/{n}-*"
```
