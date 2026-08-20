# task-create

Parses an approved design document and creates one task sub-issue per
build target. Detects duplicates when re-run on a Story that already
has some tasks.

## Purpose

Convert a Story's design doc into `type:task` sub-issues, one per
build target, so each task is self-contained, unit-testable, and
substantial enough to have meaningful tests — never a single file or a
trivial change (see `AGENT.md`'s granularity rules).

## Preconditions

- A Story issue with a completed design doc.
- `gh` authenticated with write access.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{build_targets}`, `{design_doc_path}`.

**2. Validate the input.** Fetch the Story:

```bash
gh issue view {issue} --repo {repo} --json \
  number,title,body,state,labels,assignees,milestone,comments
```

Record `assignees[0].login` as `{story_assignee}` (falls back to the
current user if unassigned). Not `type:story` → route to
`task-implement` or `story-create`. Not `status:in-progress` → warn but
continue — design may not have started.

**3. Detect duplicates.** List existing sub-issues
(`References/gh-operations.md` § Sub-issues). Normalize each existing
task's title (`"Implement {name} for #{story}"` → `{name}`, lowercased,
spaces to hyphens, punctuation stripped but dots preserved — build
target names contain them) and match against the design's build
targets. Exact match → existing, skip. No match → new, create. An
existing task matching no build target → orphaned, warn. Present the
delta and confirm before proceeding.

**4. Analyze the design.** Resolve it via
`References/artifact-resolution.md` (required — stop if truly absent,
suggesting `story-design {issue}`). Determine task boundaries:

   - **Primary:** parse the `## Build Targets` table; each row is one
     task. Aggregate every `### Code Path:` section whose
     `**Build target:**` field matches, for Responsibility, Interfaces,
     Implementation Notes, and Dependencies.
   - **Fallback (older design docs, no table):** parse `### Module:` /
     `### Code Path:` headings, then **merge by build target** —
     cross-reference each heading's source files against
     `{build_targets}` and combine everything mapping to the same
     target into one task automatically. Report the merge. Headings
     mapping to no target at all → one task per heading, with a
     warning that merging wasn't possible.

   **Granularity validation:** a task scoped to a single enum value or
   trivial change merges into a related target's task. Two tasks
   referencing the same source files in their Implementation Notes get
   flagged — sibling task branches touching the same file will
   conflict when merging into the story branch (see
   `References/branch-and-pr-model.md` § Rebasing and Conflicts).
   Present findings and let the engineer choose to merge, keep, or
   abort.

   **No task boundaries found at all:** discover build targets from
   the filesystem (`References/context-discovery.md` § Step 3b) and
   present them as proposed boundaries, or derive from the design's
   architecture sections. Never proceed silently with a guess.

**5. Create each new task:**

```bash
gh issue create --repo {repo} \
  --title "Implement {target_name} for #{issue}" \
  --body-file /tmp/dl-task-body.md \
  --label type:task --label dev-lifecycle \
  --milestone "{milestone_title}" \
  --assignee "{story_assignee}"
```

Body:

```markdown
Parent: #{issue}

{responsibility}

## Interfaces

{interfaces}

## Implementation Notes

{implementation notes from the design doc}

## Build Target

| Field | Value |
|---|---|
| Target | `{target_name}` |
| Type | {library / binary} |
| Build file | `{build_file}` |

---
**Design doc:** see the `## dev-lifecycle-design-doc` comment on
#{issue} (build target: `{target_name}`)
```

The `Parent: #{issue}` line is written even when native sub-issues are
available — it costs nothing and is what the fallback path reads.
Immediately link it as a sub-issue
(`References/gh-operations.md` § Sub-issues); if that API is
unavailable, switch to the body-link fallback for the whole run and
say so once, then add a `## Tasks` checklist to the Story body.

**6. Create the test-execution task**, one more sub-issue with no
build target and no PR of its own:

```markdown
Parent: #{issue}

Run the story-level test plan for #{issue} via story-test.

This task runs **after** all implementation tasks are resolved.
story-test resolves it.
```

This task is excluded from the "all tasks resolved" check — see
`References/workflow-states.md`.

**7. Dependency links.** GitHub has no first-class "blocks" relation.
For a task with declared dependencies, append `Blocked by: #{n}` to its
body and label it `status:blocked`. Link every implementation task to
the test-execution task the same way — it is blocked by all of them;
`story-test` clears the label when it runs.

**8. Summarize.** Comment on the Story with a table of created/existing
tasks, and report the same to the engineer with the next command
(`task-implement {first_task}`).

## Outputs

- One `type:task` sub-issue per build target, linked to the Story.
- One "Execute test plan" sub-issue, blocked on all the others.
- A summary comment on the Story issue.

## State Transitions

None on the Story or tasks directly (task state starts at Open;
`task-implement` moves it forward).

## Errors

- **Not a Story:** route to the right Skill.
- **Design doc not found:** suggest `story-design {issue}`.
- **No task boundaries found:** discovery, then a manual list, then
  abort — see step 4.
- **Sub-issue linking fails but issue creation succeeded:** nothing is
  lost — the task carries `Parent: #{issue}` in its body. Warn once
  and stay in fallback mode for the rest of the run.
