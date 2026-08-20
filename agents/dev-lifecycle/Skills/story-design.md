# story-design

Guides an engineer through creating a design document for a Story
issue. Produces a markdown design doc committed to the story branch,
posted to the issue, and traceable from both.

## Purpose

Turn a Story issue's requirements into an approved design: build
targets, code paths within them, interfaces, error handling, and a
testing strategy — the artifact `task-create` later decomposes into
task sub-issues.

## Preconditions

- A Story issue (`type:story`).
- `gh` authenticated with write access. This Skill uploads the design
  doc; if `gh` is unavailable or unauthenticated, stop — a design doc
  that exists only locally is incomplete, since downstream Skills
  resolve it from the issue first (see
  `References/artifact-resolution.md`).

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{default_branch}`, `{build_targets}`,
`{design_doc_path}`.

**2. Fetch the issue and check for an existing design** (do not skip
any of this — workspace state does not carry over from earlier work;
verify actual state on disk and on GitHub):

```bash
gh issue view {issue} --repo {repo} --json \
  number,title,body,state,labels,assignees,milestone,url,comments
```

Not `type:story` → route: `type:task` to `task-implement`, anything
else warn and ask. Closed → warn and confirm before designing.

**Existing-design gate.** Check, in order: an issue comment starting
with `## dev-lifecycle-design-doc`; a committed
`docs/design/{issue}-*design*.md`; a local file at
`{design_doc_path}/{issue}-*design*.md` or `design.md`; a
`PROGRESS-{issue}.md` past the design phase. On GitHub already → stop,
point at `task-create`. Local-only → upload it first
(`References/artifact-resolution.md` § Upload Procedure), then stop.
Nothing anywhere → proceed.

**Parallel-engineer check** (warn only): `status:in-progress` with a
different assignee, or an existing `story/{issue}-*` branch that is
not yours — see `References/workflow-states.md` § Parallel Engineer
Detection.

**3. Transition to In Progress:**

```bash
gh issue edit {issue} --repo {repo} \
  --add-label status:in-progress --remove-label status:reopened
```

**4. Create or switch to the story branch** — see
`References/branch-and-pr-model.md` § Creating the Story Branch and §
Detached and Dirty States.

**5. Run the design session.** If the harness offers a structured
brainstorming aid, use it for "Design for #{issue}: {title}";
otherwise walk these sections directly, grounding each in the issue's
Requirements and Acceptance Criteria:

   a. **Requirements** — what must this Story deliver?
   b. **Architecture** — high-level approach, key trade-offs.
   c. **Build targets and code paths** — start from `{build_targets}`
      already resolved in step 1; select the subset this Story
      changes (do not re-discover from the filesystem when the table
      exists — disagreement between the two produces wrong tasks
      later). Record the selection in the design doc's
      `## Build Targets` table. Within those targets, identify the
      code paths this Story affects — each becomes a
      `### Code Path: {name}` section naming its
      `**Build target:** {name}`. Multiple code paths may share one
      build target; shared headers with no owning target go under the
      consuming target.
   d. **Interfaces** — APIs, data structures, cross-target contracts.
   e. **Error handling** — failure modes, recovery strategies.
   f. **Testing strategy** — what categories of tests are needed.

   After each section, write it to the local file and present it for
   approval — request changes and revise (up to 3 rounds) before
   moving to the next section. Do not write every section and present
   them all at the end; each is approved before the next is written.

**6. State management.** Write `PROGRESS-{issue}.md` (schema below)
and post a short progress comment to the issue — not the sentinel
comment, which comes at completion.

```yaml
---
schema_version: 1
issue: 57
repo: acme/telemetry
milestone: "Q3 Telemetry"
story_branch: story/57-live-flow-export
active_skill: story-design
current_phase: design-session
design_doc_path: docs/design/57-design.md
last_updated: 2026-08-20T10:00:00
---
```

**7. Review and final approval.** If the harness offers a code-review
aid, use it to check for gaps in error handling, unclear interfaces,
missing edge cases, and build-target boundary issues; otherwise
self-review against the same list. Iterate on findings (max 2
rounds), then present the complete design — build targets, code paths,
key decisions, review findings and how they were addressed, open
questions — and get explicit approval before committing anything.
Do not print a summary and stop short of asking; the engineer decides.

**8. Commit, push, and upload** (only after approval):

```bash
mkdir -p "{design_doc_path}"
git add "{design_doc_path}/{issue}-design.md" "PROGRESS-{issue}.md"
git commit -m "#{issue}: Add design for {slug}"
git push -u origin "story/{issue}-{slug}"
sha=$(git rev-parse HEAD)
```

The push must succeed before a permalink is usable. Never run
`git init`. Then follow
`References/artifact-resolution.md` § Upload Procedure with sentinel
`## dev-lifecycle-design-doc`, and its post-upload verification step —
do not skip it.

**9. Update `PROGRESS-{issue}.md`** to `current_phase: complete`, and
report the design doc's path, commit, build targets, and that
`task-create` is next.

## Multi-Session Resume

Look for `PROGRESS-{issue}.md`. A mismatched `issue` in its frontmatter
means treat it as a fresh start. Otherwise read `current_phase`,
re-fetch the issue to verify current state, and resume from that
phase.

## Outputs

- `docs/design/{issue}-design.md`, committed on `story/{issue}-{slug}`.
- A `## dev-lifecycle-design-doc` sentinel comment on the Story issue.
- `PROGRESS-{issue}.md` for multi-session resume.

## State Transitions

Story: Open → In Progress (step 3), on invocation.

## Errors

- **Not a Story:** route per step 2.
- **Design doc already exists:** handled by the existing-design gate —
  skip or sync, never silently overwrite.
- **Story branch exists with someone else's commits:** warn; do not
  force-switch or reset.
- **Push rejected (non-fast-forward):** someone advanced the story
  branch. Stop and report — do not merge or rebase unasked.
