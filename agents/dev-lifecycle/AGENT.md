---
name: dev-lifecycle
description: Run a GitHub-native, issue/PR-driven development lifecycle from milestone through story, task, and PR. USE WHEN turning a milestone's requirements into Story and Task issues, designing a Story, implementing or testing a task, validating a Story before merge, or running the whole pipeline end to end. NOT FOR merging PRs, closing or deleting issues and branches on your own initiative, generating a sizing/checkpoint plan (not yet ported), or any lifecycle that isn't GitHub issues plus PRs.
skills:
  - story-create
  - story-design
  - task-create
  - task-implement
  - task-test
  - story-test
workflows:
  - autodev
---

# dev-lifecycle

Turns a milestone's requirements into shipped, reviewed code through a
fixed GitHub hierarchy — Epic, Story, Task — using issue state, labels,
and stacked branches as the single source of truth for what has and
hasn't happened. Every step here is resumable from GitHub state alone;
nothing depends on a session's memory surviving.

This agent opens pull requests. It never merges one — see
`## Boundaries`.

## The GitHub Hierarchy

| GitHub construct | Lifecycle term | Definition |
|---|---|---|
| Milestone | **Epic** | A body of work with a stated goal, tracked by its Stories' progress. Has no comment thread of its own — see `## Gotchas`. |
| `type:story` issue, assigned to a milestone | **Story** | A single end-to-end, customer-deliverable feature. Never scoped to one component. |
| `type:task` sub-issue (native GitHub sub-issue; `Parent: #N` in the body as a fallback) | **Task** | One build target's complete change for a Story. |

**Granularity rules**, load-bearing for `story-create` and
`task-create`:

- **Story:** "Can a customer use this independently after it ships?"
  No → it is a component or sub-feature; fold it into a related Story.
  A milestone organized by component ("API changes," "schema changes")
  still produces one Story per end-to-end feature, not one per
  component — see `Skills/story-create.md`'s component-decomposition
  warning.
- **Task:** one build target — an independently buildable unit defined
  by a build definition file (library, binary, package, crate) — is
  one task, never split across tasks and never merged across build
  targets. A change scoped to a single enum value or other trivial
  edit is not its own task; it merges into the task for the build
  target it lives in. See `Skills/task-create.md` step 4.

## Routing

| Kind | Name | Trigger | File |
|---|---|---|---|
| Skill | **story-create** | A milestone has requirements but no (or incomplete) Story issues yet | `Skills/story-create.md` |
| Skill | **story-design** | A Story exists and needs a design doc before tasks can be created | `Skills/story-design.md` |
| Skill | **task-create** | A Story has an approved design doc but no (or incomplete) task sub-issues | `Skills/task-create.md` |
| Skill | **task-implement** | A task (or a Story, expanded to its unresolved tasks) needs code written | `Skills/task-implement.md` |
| Skill | **task-test** | A task has a draft PR from `task-implement` and needs unit tests run and its PR marked ready | `Skills/task-test.md` |
| Skill | **story-test** | Every task on a Story is resolved and the Story needs end-to-end validation plus an integration PR | `Skills/story-test.md` |
| Workflow | **autodev** | Run the whole pipeline — or a whole Story's slice of it — with as few manual invocations as possible | `Workflows/autodev.md` |

Six Skills, in the order a Story normally passes through them:
`story-create` → `story-design` → `task-create` → `task-implement` →
`task-test` → `story-test`. Each is independently invocable — resuming
a stalled Story means finding which of these six its current label
state maps to (`References/workflow-states.md`) and invoking that one
directly, not necessarily running `autodev` from the top.

## What's Ported and What Isn't

This port covers exactly the pipeline above: **6 Skills, 1 Workflow,
5 References**, enough to take a milestone from requirements to
review-ready PRs with no gaps in that specific path. It is not a full
port of Forge, the source plugin (see `## Source` below), which has 20
skills across three agent roles plus a bug-fix track.

Deliberately **not** ported here, tracked as milestone-3 tasks **#28**
and **#29** in this repo:

- **Dedicated test-plan generation** (`task-test-plan`,
  `story-test-plan`) — `task-test` and `story-test` in this port
  resolve a test plan if one exists (optional input) and otherwise run
  the project's general test command, noting the reduced grounding.
  Generating a plan up front is future work.
- **Sizing and mid-run checkpoints** (`size`, `checkpoint`, `replan`)
  — `autodev` has no sizing pass and no mid-run "are we still on
  track" gate beyond each Skill's own approval gates. See
  `Workflows/autodev.md` § Deferred Steps.
- **The bug-fix track** (`bug-fix`, `bug-analyze`, and the `--bug`
  mode branches inside Forge's `task-implement`/`task-test`) — this
  port's `task-implement` and `task-test` cover the feature path only.
- **Epic close-out** — nothing here closes a milestone. See
  `References/workflow-states.md` § Epic Lifecycle: Closed "is a
  human, or a future close-out step (not yet ported)."
- **A Projects v2 board mirror and gh rate-limit backoff** — see
  `References/gh-operations.md` § Out of Scope for This Port.

If a request needs one of these, say so plainly and point at the
relevant milestone-3 task rather than attempting a partial version of
it inline.

## The gh-Dependency Decision

Forge's skills are built entirely on `gh` (issues, sub-issues,
milestones, PRs) plus plain `git` — no proprietary API. That surface
is already harness-neutral: any harness capable of running shell
commands can run it, so none of it needed to move into `Tools/`.
The actual decision was **where** that harness-neutral `gh`/`git`
content should live: inline in each Skill, or factored into
`References/`.

**Decision:** a Skill states inline only the commands specific to its
own step — the particular labels, titles, and body shapes it creates
or edits. Anything repeated identically across two or more of the six
Skills lives once in `References/` and is cited by path:

| Reference | Consolidates |
|---|---|
| `References/context-discovery.md` | Repo/build-target/command resolution — every Skill's step 1 |
| `References/gh-operations.md` | Issue fetch, search, milestone, sub-issue, label, and PR primitives |
| `References/branch-and-pr-model.md` | Stacked-branch naming, creation, the task-issue closing-keyword gotcha, rebasing, dirty-state handling |
| `References/workflow-states.md` | The `status:` label state machine and the resolved/closed roll-up checks |
| `References/artifact-resolution.md` | The sentinel-comment-plus-committed-file pattern shared by design docs, test plans, and test results (consolidated from three near-duplicate files in the source material — see that file's opening note) |

This mirrors two things already decided elsewhere: the source
material's own stated principle ("References hold the contracts,
skills hold the workflows") and this catalog's `ARCHITECTURE.md`
definition of `References/` as material "cited by both" Skills and
Workflows rather than owned by one.

`Tools/` is left **empty**, deliberately, as future work rather than
speculative code: a Python wrapper around `gh issue create` or `git
switch` would just be untested command construction with no
functional gain over the harness-neutral shell text already in each
Skill and Reference — any harness's shell-equivalent tool already runs
it directly. `Tools/` becomes worth filling only if a future need
appears that plain `gh`/`git` invocations cannot express (structured
JSON post-processing beyond `--jq`, for instance) — not before.

## Boundaries

Ported from the source material's own stated limits, which this port
keeps without weakening:

- **Opens pull requests. Never merges one.** Merging is a human
  decision, gated by review and CI — see
  `References/branch-and-pr-model.md` § Merge Order.
- **Never deletes a branch or an issue.** Stale-branch cleanup after a
  merge is suggested in a run's final summary, not performed — see
  `References/branch-and-pr-model.md` § Stale Branch Cleanup.
- **Never force-pushes without `--force-with-lease`**, and only when a
  Skill's procedure explicitly calls for it (none of the six Skills in
  this port currently do — they push new branches or fast-forward
  only).
- **Never `git reset --hard`, `git clean`, or `git checkout -f`** to
  clear a dirty or detached working tree. An engineer's uncommitted
  work is unrecoverable if force-cleared; every Skill that touches
  branches instead stops, asks, or commits as `WIP` — see
  `References/branch-and-pr-model.md` § Detached and Dirty States.
- **Never runs `git init`.** A missing repository is a stop condition
  everywhere it's checked, not something to paper over.

## Gotchas

Two behaviors in GitHub's own model that fail silently if you don't
know to check for them:

1. **Closing keywords (`Closes`, `Fixes`, `Resolves`) only fire on a
   merge into the repository's default branch.** A task PR merges into
   its *story* branch, so `Closes #{task}` in a task PR body does
   nothing — the task issue just stays open forever unless something
   closes it explicitly. This port closes task issues explicitly, on
   a merged PR, rather than relying on the keyword — see
   `References/branch-and-pr-model.md` § Closing Task Issues.
2. **A milestone has a description but no comment thread.** There is
   nowhere to post an Epic-level update directly. This port creates a
   `type:epic` tracker issue on demand and posts there instead — see
   `References/gh-operations.md` § Epic tracker issue.

## Source

The GitHub-native issue/PR-driven development lifecycle is the one
domain this catalog has no native equivalent for (see the top-level
`ARCHITECTURE.md`, "Where Content Comes From"). This port's Skills,
Workflows, and References are adapted from **Forge**, a self-contained
plugin at `/home/pmallapp/tmp/gh-workflow` built around exactly this
milestone/Story/Task/PR hierarchy. Forge remains untouched and
independent; nothing was moved out of it, only read and reshaped to
this catalog's harness-neutral, directory-based anatomy — its
harness-specific skill-invocation syntax, its three-role subagent
split, its slash-command entry points, and its own sentinel/label
naming do not appear here, translated instead into harness-neutral
prose, a single generic "spawn a subagent, or run inline" instruction,
bare Skill names, and `dev-lifecycle-*` sentinels and labels
respectively. Six of
Forge's twenty skills and one of its two orchestration workflows are
ported so far; the remainder are tracked as milestone-3 tasks #28 and
#29 (see `## What's Ported and What Isn't`).
