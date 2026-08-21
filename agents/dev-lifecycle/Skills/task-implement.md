# task-implement

Implements task issues. Loads full design context, cuts a branch off
the story branch, enforces commit conventions, verifies the build,
runs code review, squashes, and opens a **draft PR** targeting the
story branch. `task-test` runs unit tests afterward and marks the PR
ready.

## Purpose

Turn one task sub-issue into a reviewed, buildable change on its own
branch — the unit of work this pipeline can hand to a reviewer
independent of the rest of the Story.

## Preconditions

- A task issue whose parent Story has a design doc, or a Story issue
  with tasks already created (expanded to its unresolved tasks — see
  below).
- `gh` authenticated with write access.

Accepts one or more task numbers, or a Story number (expanded to its
unresolved tasks, excluding the test-execution task). In an autonomous
run — this Skill invoked as a worker by `autodev` — a Story input is
unexpected and is a hard stop rather than an expansion, since the
orchestrator is supposed to supply task numbers directly.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{default_branch}`, `{build_targets}`,
`{commands}`, `{design_doc_path}`.

**2. Resolve inputs.** For each input issue, fetch it lightly
(`number,title,state,labels,assignees,milestone`) and route by type
label: `type:task` kept as-is; `type:story` expanded to its
unresolved, unblocked sub-issues (excluding the test-execution task) in
an interactive run — present the list and let the engineer pick some,
all, or none; anything else, warn and skip. A task carrying
`status:blocked` whose `Blocked by:` issue is not yet resolved is
skipped, in an autonomous run, or flagged for confirmation in an
interactive one.

**3. Load context, per task.** Fetch the task in full
(`number,title,body,state,labels,assignees,milestone,comments`), find
the parent Story (`References/gh-operations.md` § Sub-issues, falling
back to the `Parent: #N` body line), and transition it to In Progress:

```bash
gh issue edit {issue} --repo {repo} \
  --add-label status:in-progress --remove-label status:reopened
```

This is **mandatory before any implementation work**, even when the
code already exists — a task still lacking the label looks like a
failure to anything downstream that checks state.

Resolve the design doc (`References/artifact-resolution.md`, required)
and extract this build target's slice
(`References/context-discovery.md` describes build-target matching;
the design doc's `### Code Path:` sections carry the
`**Build target:**` field to match on). Resolve the test plan the same
way, but treat it as optional here — warn and continue if absent,
suggesting the test-plan Skill this port does not yet have (see
`AGENT.md`). Load only the knowledge files relevant to this build
target's source dirs.

Present the loaded context — responsibility, interfaces, dependencies,
relevant test cases — before writing any code.

**4. Detect pre-existing implementation** (idempotency — a prior run
may have already done this work). Extract source file paths from the
design's build-target section; if they exist on disk and a couple of
key interface names grep-match, this task is already implemented.
Skip straight to build verification and completion verification; no
new commits, no PR, and report that no changes were needed.

**5. Plan before coding.** If the harness offers a planning aid, use
it to produce an implementation plan (files, key functions, data flow,
sequence) and get it approved before writing code; in an autonomous
run, draft the plan inline and proceed without a separate approval
step. Always plan — do not start writing code from nothing.

**6. Branch and implement.** Enforce the project's coding conventions.
Set up the branch per
`References/branch-and-pr-model.md` (never `git checkout -f`,
`git reset --hard`, or `git clean` to clear a dirty tree — see
`AGENT.md` `## Boundaries`):

```bash
git fetch origin
git switch "story/{story}-{story_slug}" || \
  git switch --create "story/{story}-{story_slug}" "origin/{default_branch}"
git pull --ff-only
git switch --create "task/{issue}-{target_slug}"
```

Record `TASK_BASE_SHA=$(git rev-parse HEAD)` before writing anything —
this is the squash baseline in step 8. Never run `git init`; if
`git rev-parse` fails here, abort rather than initializing a repo.

Write the code, following the design's build-target context.

**7. Commit enforcement.** Stage specific files by path — never
`git add -A` or `git add .`, which sweep in build artifacts and
unrelated work. Every commit uses the issue prefix:

```
#{issue}: <descriptive message>
```

Include a `Co-Authored-By:` trailer naming the acting agent when the
commit was AI-assisted.

**8. Build verification.** Resolve `{build_command}` from
`{commands}`; not configured → skip with a logged warning (not every
project compiles) in an autonomous run, or ask in an interactive one.
On failure, use a systematic debugging approach if the harness offers
one — read the error, check recent changes, trace the data flow, form
a hypothesis, make the smallest fix — then re-run before proceeding.

**9. Code review.** If the harness offers a review aid, use it,
focused on correctness, edge cases, convention adherence, and
compliance with the design's interfaces; otherwise present a summary
of changes for manual review. Address findings **one at a time** —
read, verify against the codebase, fix or push back with reasoning,
then move to the next. Re-review after significant changes (max 2
iterations).

**10. Completion verification (mandatory — do not skip straight to a
PR).** Re-run the same build command fresh; confirm exit 0; verify the
design's requirements for this target are each backed by a named
file/function; check the branch diff for leftover `TODO`/`FIXME`
markers (must be empty); verify every public interface in the design
has a matching definition.

**11. Squash this task's implementation commits into one.** Guard: the
branch is not `{default_branch}` and not a story branch — rewriting
shared history is never safe. Skip if 0 or 1 commits since
`TASK_BASE_SHA`.

```bash
git reset --soft ${TASK_BASE_SHA}
git commit -m "#{issue}: Implement {target}"
```

Verify the result is exactly one commit and the diff against
`TASK_BASE_SHA` is non-empty. If `git commit` fails after the reset,
the staged changes are not lost — commit them as `#{issue}: WIP` and
report the squash failure rather than losing work.

**12. Push and open the draft PR** — see
`References/branch-and-pr-model.md` § Creating a Task Branch and Draft
PR. Reuse an existing PR for this branch rather than erroring; skip PR
creation (and say so) when there is nothing to push. Comment the
implementation summary on the task issue: build target, files changed,
build result, review outcome, branch, PR link.

**13. Report** the branch, PR, and build result, and name the next
Skill (`task-test`).

## Outputs

- A `task/{issue}-{target_slug}` branch with one squashed commit.
- A draft PR targeting the story branch (no `Closes` line — see
  `References/branch-and-pr-model.md`).
- An implementation-summary comment on the task issue.

## State Transitions

Task: Open → In Progress (step 3), on invocation.

## Errors

- **Story with no unresolved tasks:** skip, nothing to implement.
- **Design doc not found:** warn and continue with reduced grounding.
- **Story branch has diverged (`pull --ff-only` fails):** stop and
  report; do not merge or rebase unasked.
- **Task branch conflicts with the story branch:** report the
  conflicting files and the rebase command; do not auto-resolve.
- **`gh pr create` says "No commits between":** skip PR creation, note
  it, continue — the PR appears on the next run once commits exist.

Once every input issue is processed, stop. A suggested next Skill is
not authorization to run it.

## Bug Mode

Invoked by `Workflows/bug-fix.md` against a `type:bug` issue. Four
differences:

- `type:bug` is accepted in place of `type:task`.
- **The RCA is the design context** — resolve `## dev-lifecycle-rca`
  via `References/artifact-resolution.md` and implement its Proposed
  Fix section. There is no design doc and no parent Story to find.
- The branch is `bug/{issue}-{slug}`, cut off the **default branch**
  rather than off a story branch.
- The PR targets the **default branch** and carries `Closes #{issue}`.
  Unlike a task PR, that keyword fires here — the merge lands on the
  default branch, which is the condition GitHub requires (`AGENT.md`
  § Gotchas).

Build verification, review, and the squash step are unchanged.
