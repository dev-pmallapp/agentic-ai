# status

Shows pipeline progress, issue state, PR state, and the suggested next
action — as a project dashboard, a milestone or issue view, or a
per-person view. Read-only, and degrades to local state when GitHub is
unreachable.

## Purpose

Answer "where are we, and what happens next" from evidence rather than
recollection. Every check mark traces to a sentinel comment, a label, a
sub-issue, or a PR — never to an assumption.

## Preconditions

- `gh` authenticated, **optionally**. Without it this Skill degrades to
  local-only mode rather than stopping.
- No documents required. A missing `ARCHITECTURE.md` or
  `CONTRIBUTING.md` is reported as a setup gap, not a blocker — this is
  often the Skill someone runs *because* something is missing.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` Steps
1-2 — only `{repo}` and `{repo_root}` are needed. GitHub unreachable →
go to `## Local-Only Mode`.

**2. Pick the view.** No argument → the project dashboard. A milestone
number or title → the milestone view. An issue → the focused view,
auto-detecting Story, task, or epic tracker from its `type:` label. A
login → the person view; a login with an issue → that issue's view
filtered to them.

A bare number is ambiguous between a milestone and an issue. Check
both; if both exist, show the issue and note the milestone.

**3. Read local state.** Collect every `PROGRESS-*.md` in the working
directory (and a legacy `PROGRESS.md`), taking `issue`, `active_skill`,
`current_phase`, and `story_branch` from each.

## Project Dashboard

List open milestones, then per milestone its Stories, then per Story
count its sub-issues resolved-or-closed against total:

```bash
gh api repos/{repo}/milestones --jq \
  '.[] | {number, title, open_issues, closed_issues, due_on}'

gh issue list --repo {repo} --milestone "{title}" --label type:story \
  --state all --limit 200 --json number,title,state,labels,assignees
```

**Cap the fan-out.** More than 10 open milestones → show milestone-level
counts only, from `open_issues`/`closed_issues`, and say so. Making
hundreds of API calls to render a dashboard nobody asked to be
exhaustive is a bad trade, and a silent one is worse — state that the
Story breakdown was skipped and how to get it.

Then list open PRs and match them to issues by branch name
(`task/61-…` → #61), so the dashboard shows what is awaiting review:

```bash
gh pr list --repo {repo} --state open --limit 100 \
  --json number,title,isDraft,headRefName,baseRefName,reviewDecision
```

Present the local session summary, then a per-milestone table of Story,
title, state, tasks resolved over total, and PRs; then open bugs; then
the suggested next action.

## Milestone View

The milestone's Stories with their task counts and PRs, plus overall
tasks complete across Stories, issues closed and the percentage, the
epic tracker (or that it is created on demand), and the due date if set.

## Story View

A **pipeline checklist**, each item checked against real evidence:

- Design doc — a `## dev-lifecycle-design-doc` comment, with permalink
- Test plan — a `## dev-lifecycle-test-plan` comment, and case count
- Tasks created — how many
- All tasks resolved — resolved over total
- Validation — verdict, or not run
- Integration PR — number, or not opened
- Story closed

Check marks come from the sentinel comments, the sub-issue list and
their labels, the most recent results file, the PR list, and the issue
state — see `References/workflow-states.md` § All Tasks Resolved Check
for the roll-up rule.

Then the task table (task, build target, state, assignee, PR); the
**blocking chain** for any task carrying `status:blocked`, showing what
it waits on and whether that blocker is resolved; and the branch state:

```bash
git ls-remote --heads origin "story/{issue}-*"
git rev-list --count "origin/{default_branch}..origin/story/{issue}-{slug}"
```

## Task View

The task and its parent Story; its build-target context resolved from
the parent's design doc via `References/artifact-resolution.md`
§ Narrowing to One Build Target — responsibility, interfaces,
dependencies; its PR state (draft or ready, review decision, CI); and
its sibling tasks with the current one highlighted.

## Person View

Resolve the login — try it as-is, then search collaborators; not found
→ say so and ask for the GitHub login rather than a display name or
email. Then:

```bash
gh issue list --repo {repo} --assignee "{login}" --state open \
  --limit 200 --json number,title,labels,milestone,state
gh pr list --repo {repo} --author "{login}" --state open \
  --limit 100 --json number,title,isDraft,reviewDecision
```

Group by milestone, then Story. Present their issues and PRs, split
into PRs awaiting their action and PRs they opened awaiting review.

## Suggested Next Action

First match wins:

| Condition | Next |
|---|---|
| A progress file exists | Resume that Skill for that issue |
| Story In Progress, no design doc | `story-design` |
| Story has a design, no test plan | `story-test-plan` |
| Story In Progress, no tasks | `task-create` |
| Task Open | `task-implement` |
| Task In Progress with a draft PR | `task-test` |
| All of a Story's tasks resolved | `story-test` |
| All Stories in a milestone closed | `enhance-debugger` |
| Otherwise | No pending actions |

## Local-Only Mode

When GitHub is unreachable, say so with the error, then show what is
still derivable — progress files, current branch, uncommitted changes,
unpushed commits, and local artifacts:

```bash
git branch --show-current
git status --short
git log --oneline "origin/{default_branch}..HEAD"
git branch -a --list 'story/*' --list 'task/*'
```

**Do not claim any issue state in this mode.** The labels are on
GitHub, not on disk, and a cached guess presented as state is exactly
the kind of confident-but-wrong report this Skill exists to replace.

## Outputs

A presented report. No writes of any kind — no labels, no comments, no
commits.

## State Transitions

None.

## Errors

- **GitHub unreachable:** local-only mode, with the warning.
- **Ambiguous bare number:** show the issue, note the milestone.
- **Issue type indeterminate** (no `type:` label): show a generic issue
  view and suggest labelling it.
- **No open milestones:** say so and route to `story-create` after one
  is created.
- **No pipeline labels present:** no pipeline has been started here —
  route to `init`.
- **More than 10 open milestones:** milestone-level counts only, stated
  explicitly.
- **Standard `gh` failures:** `References/gh-error-handling.md`.

## Bug View

For a `type:bug` issue: whether an RCA exists
(`## dev-lifecycle-rca`) and its stated confidence, the classification
and scope it recorded, the `bug/{issue}-{slug}` branch and its PR, and
the test results.

Next action, first match wins: no RCA → `bug-analyze`; an RCA but no
PR → `bug-fix`; a PR open → review it.

Report the RCA's confidence rather than just its existence. An RCA
marked `hypothesis` is triage output, not a diagnosis, and a dashboard
that shows only "RCA: yes" hides exactly the distinction that decides
whether a fix should be written yet.
