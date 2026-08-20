# story-create

Analyzes a milestone's requirements and creates one Story issue per
feature area. This is the upstream entry point of the pipeline, before
`story-design` — see the routing table in `AGENT.md`.

## Purpose

Turn a milestone description (the Epic) into `type:story` issues, each
an end-to-end, customer-deliverable feature. One row of a feature table
becomes one Story; a milestone describing a single feature — even
across many components — produces exactly one Story.

## Preconditions

- A milestone whose description (or `type:epic` tracker issue) holds
  requirements.
- `gh` authenticated with write access. If `gh` is unavailable or
  unauthenticated, stop immediately — creating Stories through any
  other means breaks traceability for everything downstream.
- `README.md` present at the repo root (see
  `References/context-discovery.md`). Missing → stop; there is nowhere
  to derive `{repo}` from that this pipeline trusts.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` Steps
1-2 (repo identity, root docs). Build targets and commands are not
needed here.

**2. Resolve and fetch the milestone:**

```bash
gh api repos/{repo}/milestones --jq \
  '.[] | {number, title, description, state, open_issues, closed_issues}'
gh api repos/{repo}/milestones/{milestone_number}
```

Accept a milestone number (all digits) or title (matched
case-insensitively; ask on multiple matches). A closed milestone gets a
warning and a confirmation before proceeding.

**3. Locate requirements**, in priority order: the milestone
description; the `type:epic` tracker issue body
(`References/gh-operations.md` § Epic tracker issue); any linked
`docs/*.md` path or GitHub blob URL mentioned in either. Combine
everything found and record which sources contributed — Story bodies
cite them. Nothing found anywhere → stop, and give the exact
`gh api -X PATCH` command to add a feature table to the milestone
description.

**4. Query existing Stories** (idempotency):

```bash
gh issue list --repo {repo} --milestone "{milestone_title}" \
  --label type:story --state all --limit 200 \
  --json number,title,state,labels,assignees
```

**5. Extract feature areas.** Prefer a markdown table
(`Feature | Description`) — each row is one Story, at the right
granularity already; do not decompose rows further by component.
Without a table, look for numbered lists, headings describing what a
user can do, or checklists, and group anything organized by component
("API changes", "schema changes") under the feature it serves — a
milestone organized by component still produces one Story per
end-to-end feature, not one per component.

**Granularity check**, for each proposed feature: "Can a customer use
this independently after it ships?" No → it's a component or
sub-feature; merge it into a related Story.

For each feature that passes, record: name, scope (1-2 sentences),
dependencies on other features in this milestone, and the verbatim
source text (exact requirement wording, for traceability).

**6. Deduplicate** against the existing Stories from step 4, by
semantic similarity of titles — an existing Story addressing the same
functional area counts as "already exists," even with different
wording. Present the plan (existing vs. to-create) before creating
anything.

**7. Create each net-new Story:**

```bash
gh issue create --repo {repo} \
  --title "{feature_name}" \
  --body-file /tmp/dl-story-body.md \
  --label type:story --label dev-lifecycle \
  --milestone "{milestone_title}" \
  --assignee "{default_assignee}"
```

Default assignee: the milestone's creator
(`gh api repos/{repo}/milestones/{n} --jq '.creator.login'`), else the
current user. Unresolvable assignee → create unassigned and warn;
never fail creation over it.

Body shape:

```markdown
{scope — 1-2 sentences on what the customer gets}

## Requirements

{requirements for this feature, from the milestone analysis}

## Acceptance Criteria

{extracted, or "TBD — to be refined during story-design"}

## Milestone Source

<!-- dev-lifecycle:milestone-source {milestone_number} -->
{verbatim source text}
<!-- /dev-lifecycle:milestone-source -->
```

Capture the new issue number from the printed URL. If creation fails
for one Story, continue with the rest and report partial results.

**8. Post a summary** to the epic tracker (resolve-or-create it — only
when new Stories were created) and to the engineer, listing each
feature, its action (Created/Existing), and its issue number. Point at
`story-design` as the next step for each new Story.

## Outputs

- One `type:story` issue per net-new feature area, in the milestone.
- A summary comment on the epic tracker (created if it did not exist).
- No milestone state change to make directly — see below.

## State Transitions

Creating Stories moves the Epic to "In Progress" implicitly (a
milestone with Stories is in progress by definition — see
`References/workflow-states.md` § Epic Lifecycle). There is no label
to set on a milestone itself.

## Errors

- **Milestone not found:** list existing milestones and stop.
- **Milestone has no requirements anywhere:** stop with the edit
  command from step 3.
- **Story creation partially fails:** report created + failed; suggest
  manual creation for the failures.
- **Assignee cannot be resolved:** create unassigned, warn, continue.
