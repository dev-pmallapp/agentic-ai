# GitHub Operations

The `gh` commands shared across more than one Skill in this pipeline —
issue fetch, search, milestone handling, issue creation, sub-issue
linking, label transitions, and comments. A Skill states only what is
specific to its own step; it cites this file by path for everything
else. See `AGENT.md`'s gh-dependency decision for why this split
exists.

Variables: `{repo}` (as `owner/name`), `{issue}`, `{story}`, `{task}`,
`{milestone_number}`. `gh` picks up `{repo}` from the current git
remote automatically; pass `--repo {repo}` explicitly anyway so
operations are correct when the working directory is a different
clone.

## Preflight

```bash
gh auth status
gh repo view --json nameWithOwner,defaultBranchRef,hasIssuesEnabled
```

`gh auth status` failing, or `hasIssuesEnabled: false`, is a hard stop
— see `AGENT.md`'s `gh`-dependency section.

## Fetch an Issue

```bash
gh issue view {issue} --repo {repo} --json \
  number,title,body,state,stateReason,labels,assignees,milestone,url,createdAt,updatedAt,comments
```

`--json comments` returns the full comment list in one call — this is
how sentinel-comment scanning works (see
`References/artifact-resolution.md`).

**Derive the type** from labels: `type:story` → Story, `type:task` →
Task. No `type:` label → untyped; warn and ask rather than guessing.

**Derive the state** from `state` + the `status:` label — see
`References/workflow-states.md`.

## Search Issues

Prefer `gh issue list` (repo-scoped, cheap) over `gh search issues`
(cross-repo, rate-limited).

```bash
# Stories in a milestone
gh issue list --repo {repo} --milestone "{milestone_title}" \
  --label type:story --state all --limit 200 \
  --json number,title,state,labels,assignees,milestone

# Tasks assigned to me, still open
gh issue list --repo {repo} --label type:task --assignee "@me" \
  --state open --json number,title,state,labels
```

Multiple `--label` flags are **AND**-ed. `--state all` is required to
see closed issues — the default is `open` and silently omits them.
`--limit` defaults to 30; pass `--limit 200` for completeness scans,
and treat exactly-200 as possibly truncated rather than complete.

## Milestones (Epics)

Milestones have no `gh` subcommand — use `gh api`.

```bash
# List
gh api repos/{repo}/milestones --jq \
  '.[] | {number, title, description, open_issues, closed_issues, state}'

# Fetch one (title + description = Epic requirements)
gh api repos/{repo}/milestones/{milestone_number}
```

**Resolving a milestone argument:** all-digits → a number; otherwise
match `title` case-insensitively. On multiple matches, ask.
`open_issues` / `closed_issues` give roll-up progress without listing
issues.

### Epic tracker issue

Milestones have a description but **no comment thread** — see
`AGENT.md` `## Gotchas`. When an Epic-level comment is needed, resolve
or create the tracker:

```bash
# Find it
gh issue list --repo {repo} --label type:epic \
  --milestone "{milestone_title}" --state all \
  --json number,title,body --limit 10

# Create it — only at the moment a comment must be posted, never ahead of need
gh issue create --repo {repo} --title "Epic: {milestone_title}" \
  --label type:epic --label dev-lifecycle \
  --milestone "{milestone_title}" \
  --body "Tracker issue for milestone **{milestone_title}**.

Milestone: {milestone_url}

Epic-level updates are posted here because milestones have no comment
thread. Requirements live in the milestone description."
```

## Create an Issue

```bash
# Story (in a milestone)
gh issue create --repo {repo} \
  --title "{feature_name}" \
  --body-file {path} \
  --label type:story --label dev-lifecycle \
  --milestone "{milestone_title}" \
  --assignee "{login}"

# Task (sub-issue of a Story — link separately, see § Sub-issues)
gh issue create --repo {repo} \
  --title "Implement {build_target} for #{story}" \
  --body-file {path} \
  --label type:task --label dev-lifecycle \
  --milestone "{milestone_title}" \
  --assignee "{login}"
```

`gh issue create` prints the new issue's URL; capture the number from
it:

```bash
url=$(gh issue create ...) && num="${url##*/}"
```

`--assignee` takes a login, not an email. If it cannot be resolved,
create the issue **unassigned** and warn — never fail creation over an
assignee.

## Sub-Issues (Parent-Child)

Sub-issues are GraphQL-only; both issues must already exist, and the
mutation needs their **node IDs**, not their numbers.

```bash
# Node ID for an issue number
gh api graphql -f query='
  query($owner:String!,$name:String!,$number:Int!){
    repository(owner:$owner,name:$name){ issue(number:$number){ id } }
  }' -F owner={owner} -F name={name} -F number={issue} --jq '.data.repository.issue.id'

# Attach child to parent
gh api graphql -f query='
  mutation($parent:ID!,$child:ID!){
    addSubIssue(input:{issueId:$parent, subIssueId:$child}){
      issue{ number } subIssue{ number }
    }
  }' -F parent={parent_node_id} -F child={child_node_id}

# List children of a Story
gh api graphql -f query='
  query($owner:String!,$name:String!,$number:Int!){
    repository(owner:$owner,name:$name){
      issue(number:$number){
        subIssues(first:100){ nodes{ number title state stateReason labels(first:20){nodes{name}} } }
      }
    }
  }' -F owner={owner} -F name={name} -F number={story} \
  --jq '.data.repository.issue.subIssues.nodes'
```

### Fallback when sub-issues are unavailable

Older GitHub Enterprise Server, or a token without the right scope,
returns an error naming `addSubIssue` / `subIssues` as an unknown
field. On that error, switch to a body-link fallback for the rest of
the run and say so once:

- Child body starts with `Parent: #{story}`.
- Parent body carries a task list: `- [ ] #{task} {title}`.
- "List children" becomes:
  `gh issue list --repo {repo} --label type:task --search "\"Parent: #{story}\" in:body" --state all --json number,title,state,labels`

Skills call the operations in this section rather than inlining
GraphQL directly, so the fallback applies uniformly wherever
sub-issues are used.

## Labels

See `References/workflow-states.md` for the state-transition commands.

```bash
gh label create "{name}" --repo {repo} --color "{hex}" \
  --description "{desc}" --force
```

`--force` updates an existing label instead of failing. This pipeline
assumes the labels it needs (`type:story`, `type:task`, `type:epic`,
`status:in-progress`, `status:resolved`, `status:reopened`,
`status:blocked`, `dev-lifecycle`) already exist in the repo; on a
"label not found" error from `gh issue edit`, create the one label
needed and retry once.

## Comments

```bash
# Post — always via --body-file for multi-line markdown, to avoid
# shell quoting damage to backticks, $, and newlines
gh issue comment {issue} --repo {repo} --body-file {path}
```

Never build a comment body inline in the shell. See
`References/artifact-resolution.md` for the sentinel-comment
convention and the 65,536-character body limit.

## Pull Requests

See `References/branch-and-pr-model.md` for when each of these is
used.

```bash
# Draft PR for a task, targeting the story branch
gh pr create --repo {repo} --draft \
  --base "story/{story}-{slug}" --head "task/{task}-{slug}" \
  --title "#{task}: Implement {build_target}" --body-file {path}

# Mark ready once tests pass
gh pr ready {pr_number} --repo {repo}

# Integration PR, story branch -> default branch
gh pr create --repo {repo} \
  --base "{default_branch}" --head "story/{story}-{slug}" \
  --title "#{story}: {story_title}" --body-file {path}

# Inspect
gh pr view {pr} --repo {repo} --json \
  number,state,isDraft,mergeable,mergeStateStatus,baseRefName,headRefName,url

# Find the PR for a branch
gh pr list --repo {repo} --head "task/{task}-{slug}" \
  --state all --json number,state,isDraft,url
```

## Out of Scope for This Port

A Projects v2 board mirror, and rate-limit backoff, are both part of
Forge's fuller `gh-operations.md` and are not carried into this port —
neither is needed by the six Skills and one Workflow authored here.
Labels remain the sole source of truth. See `AGENT.md` for what is
deferred and where.
