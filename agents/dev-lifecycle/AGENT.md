---
name: dev-lifecycle
description: Run a GitHub-native, issue/PR-driven development lifecycle from milestone through story, task, and PR. USE WHEN bootstrapping a project's labels and root docs, turning a milestone's requirements into Story and Task issues, designing a Story, generating test plans, implementing or testing a task, validating a Story before merge, sizing work, reporting pipeline status, checkpointing or resuming a handoff, replanning after a requirement change, extracting milestone learnings, or running the whole pipeline end to end. NOT FOR merging PRs, deleting issues or branches, the bug-fix track, or any lifecycle that isn't GitHub issues plus PRs.
skills:
  - init
  - story-create
  - story-design
  - story-test-plan
  - task-create
  - task-implement
  - task-test-plan
  - task-test
  - story-test
  - story-test-replan
  - replan
  - size
  - status
  - checkpoint
  - resume
  - enhance-debugger
workflows:
  - autodev
  - planner
  - coder
  - validator
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

**The pipeline**, in the order a Story passes through it:

| Kind | Name | Trigger | File |
|---|---|---|---|
| Skill | **init** | A project has no labels or no `## Build Targets` / `## Commands` table yet — run once, before anything else | `Skills/init.md` |
| Skill | **story-create** | A milestone has requirements but no (or incomplete) Story issues yet | `Skills/story-create.md` |
| Skill | **story-design** | A Story exists and needs a design doc before tasks can be created | `Skills/story-design.md` |
| Skill | **story-test-plan** | A Story has an approved design doc and needs a test plan generated from it | `Skills/story-test-plan.md` |
| Skill | **task-create** | A Story has an approved design doc but no (or incomplete) task sub-issues | `Skills/task-create.md` |
| Skill | **task-implement** | A task (or a Story, expanded to its unresolved tasks) needs code written | `Skills/task-implement.md` |
| Skill | **task-test-plan** | A task has an implementation and needs unit test cases and test code written against it | `Skills/task-test-plan.md` |
| Skill | **task-test** | A task has a draft PR from `task-implement` and needs unit tests run and its PR marked ready | `Skills/task-test.md` |
| Skill | **story-test** | Every task on a Story is resolved and the Story needs end-to-end validation plus an integration PR | `Skills/story-test.md` |
| Skill | **enhance-debugger** | Every Story in a milestone is closed, and the milestone needs its learnings captured and itself closed | `Skills/enhance-debugger.md` |

**The utility set** — invoked when something changes or stalls, not on
a fixed position in the run:

| Kind | Name | Trigger | File |
|---|---|---|---|
| Skill | **status** | "Where are we, what's next" — for a project, a milestone, an issue, or a person | `Skills/status.md` |
| Skill | **size** | Relative effort (S/M/L/XL) is needed for a milestone, Story, or task before committing to scope | `Skills/size.md` |
| Skill | **replan** | A Story's requirements changed after its design was agreed | `Skills/replan.md` |
| Skill | **story-test-replan** | A test plan predates the implementation and needs regrounding on the code actually written | `Skills/story-test-replan.md` |
| Skill | **checkpoint** | Work is being handed off or paused, and the state that isn't in git needs recording | `Skills/checkpoint.md` |
| Skill | **resume** | Picking up an issue that has a checkpoint, whether someone else's or your own | `Skills/resume.md` |

**Orchestration** — cumulative runs that compose the Skills above:

| Kind | Name | Trigger | File |
|---|---|---|---|
| Workflow | **autodev** | Run the whole pipeline — or a whole Story's slice of it — with as few manual invocations as possible | `Workflows/autodev.md` |
| Workflow | **planner** | Take a milestone or Story from requirements to designed, sized, test-planned, and split into tasks | `Workflows/planner.md` |
| Workflow | **coder** | Take one task from Open to Resolved — implement, generate unit tests, run them, leave a PR ready | `Workflows/coder.md` |
| Workflow | **validator** | Every task on a Story is resolved and it needs its plan regrounded, run, and a verdict returned | `Workflows/validator.md` |

`planner`, `coder`, and `validator` are the three **worker roles**.
`autodev` composes them; each is also invocable directly when you want
one phase of the pipeline without the rest. They are Workflows rather
than harness agent definitions on purpose — a role can run in an
isolated subagent where the harness has one, or inline in the main
session where it does not, with no change to its steps or its output
contract. See `Workflows/autodev.md` § Running the Workers.

Sixteen Skills. The pipeline runs `init` once per project, then
`story-create` → `story-design` → `story-test-plan` → `task-create` →
`task-implement` → `task-test-plan` → `task-test` → `story-test`, with
`enhance-debugger` closing out the milestone once every Story in it is
closed.

Each is independently invocable — resuming a stalled Story means
finding which one its current label state maps to
(`References/workflow-states.md`), or asking `status`, and invoking
that directly rather than running `autodev` from the top.

Three of the pipeline Skills are **optional in practice**:
`story-test-plan` and `task-test-plan` generate plans that `story-test`
and `task-test` will otherwise resolve if present and run without if
absent (at reduced grounding, which those Skills report), and
`enhance-debugger` is worth running only on a milestone that produced
learnings worth keeping.

## What's Ported and What Isn't

This port covers the full lifecycle above: **16 Skills, 1 Workflow,
9 References** — a milestone from bootstrap through requirements,
design, test plans, implementation, validation, and close-out. It is
not a complete port of Forge, the source plugin (see `## Source`
below), which also carries a bug-fix track and three agent roles.

Story #9 ported the first 6 Skills and the Workflow; milestone-3 task
**#28** added the remaining 10 in two batches — the pipeline half
(`init`, `story-test-plan`, `task-test-plan`) and the utility set
(`replan`, `story-test-replan`, `status`, `size`, `checkpoint`,
`resume`, `enhance-debugger`).

Deliberately **not** ported, and tracked as milestone-3 tasks in this
repo:

- **The bug-fix track** (`bug-fix`, `bug-analyze`, the root-cause
  document and its sentinel, and the bug-mode branches inside Forge's
  `task-implement`, `task-test`, and `task-test-plan`) — this port
  covers the feature path only. `status` shows open bugs in its counts
  but has no bug view. Task **#29**.
- **Orchestration beyond `autodev`** (`autodev-mytasks`, and the
  planner/coder/validator agent roles Forge's skills branch on) — this
  port folds that branching into the autonomous-versus-interactive
  distinction each Skill states for itself. Task **#29**.
- **The scaffolding templates** (`Templates/`) — `init` and
  `enhance-debugger` cite `Templates/ARCHITECTURE.md`,
  `Templates/CONTRIBUTING.md` and `Templates/kb-article.md` by path,
  and degrade explicitly where they are absent. Task **#32**.
- **Wiring the new Skills into `autodev`** — the Workflow still
  sequences the original six. Sizing, test-plan generation, and
  mid-run checkpoints exist as Skills but are not yet steps in an
  autonomous run. See `Workflows/autodev.md` § Deferred Steps and task
  **#29**.
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
or edits. Anything repeated identically across two or more Skills
lives once in `References/` and is cited by path:

| Reference | Consolidates |
|---|---|
| `References/context-discovery.md` | Repo/build-target/command resolution — every Skill's step 1 |
| `References/gh-operations.md` | Issue fetch, search, milestone, sub-issue, label, and PR primitives |
| `References/gh-error-handling.md` | The twelve standard `gh` failure modes, and the verify-don't-assume rule for operations that exit 0 having done nothing |
| `References/branch-and-pr-model.md` | Stacked-branch naming, creation, the task-issue closing-keyword gotcha, rebasing, dirty-state handling |
| `References/workflow-states.md` | The `status:` label state machine and the resolved/closed roll-up checks |
| `References/artifact-resolution.md` | The sentinel-comment-plus-committed-file pattern shared by every artifact kind, its per-target narrowing, and the sync-upward modes |
| `References/build-systems.md` | Build-target detection per language, and why the declared table beats filesystem discovery |
| `References/project-commands.md` | Where build/test/lint commands live, their placeholders, and their pass criteria |
| `References/sizing-criteria.md` | T-shirt sizing at task, Story, and Epic level, and the data-limited estimate |

One contract deliberately lives in a Skill rather than a Reference: the
**label set** — names, colours, descriptions — is a table in
`Skills/init.md`, because `init` is the only thing that creates labels
and every other consumer needs just one row of it at a time.
`References/gh-error-handling.md` § 7 cites that table for single-label
repair, and `References/workflow-states.md` treats the labels as given.

### Source-to-reference mapping

The source material carries **13** reference files; this port has
**9**. Nothing is dropped — five of the source files describe one
contract each and collapse into two. The mapping, so the correspondence
is auditable rather than assumed:

| Source reference | Ported to |
|---|---|
| `gh-operations` | `gh-operations.md` |
| `gh-error-handling` | `gh-error-handling.md` |
| `context-discovery` | `context-discovery.md` |
| `workflow-states` | `workflow-states.md` |
| `branch-and-pr-model` | `branch-and-pr-model.md` |
| `build-systems` | `build-systems.md` |
| `project-commands` | `project-commands.md` |
| `sizing-criteria` | `sizing-criteria.md` |
| `gh-api` (artifact storage) | `artifact-resolution.md` § Upload Procedure |
| `artifact-gh-sync` | `artifact-resolution.md` § Syncing a Local Artifact Upward |
| `design-doc-resolution` | `artifact-resolution.md` § Resolution Chain + § Narrowing to One Build Target |
| `test-plan-resolution` | same, parameterized by sentinel and path |
| `unit-test-resolution` | same, plus § Step 3b (committed test files) |

The four artifact files are a 4-step resolution chain repeated with a
different sentinel and path each time, and `gh-api` is the writer side
of that same chain. Keeping them apart would mean four places to edit
when the chain changes — which is precisely the drift `References/`
exists to prevent. `unit-test-resolution`'s extra git-history step is
genuinely unique and survives as its own step rather than being flattened
away.

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
  `References/branch-and-pr-model.md` § Stale Branch Cleanup. Descoped
  work is closed as `not_planned` with a reason (`replan`), never
  deleted.
- **Closes exactly one thing on its own initiative: a milestone whose
  Stories are all closed**, and only through `enhance-debugger`, only
  after that Skill's mandatory review gate, and only once it has
  verified every Story is closed. Nothing else here closes an Epic —
  see `References/workflow-states.md` § Epic Lifecycle. Issues are
  closed only where a merged PR has already made it true (see
  `## Gotchas`).
- **Never force-pushes without `--force-with-lease`**, and only when a
  Skill's procedure explicitly calls for it (none of the sixteen Skills
  in this port currently do — they push new branches or fast-forward
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
