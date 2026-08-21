# size

Estimates relative effort — S/M/L/XL across design, coding, and test —
for a milestone, a Story, or a task, and shows the signals the estimate
came from. Read-only apart from one optional informational comment.

## Purpose

Give a scope decision something better than intuition, early enough to
matter. Sizes are **relative**, calibrated against each other within a
project.

**No time estimates.** Hours do not survive contact with a different
codebase, a different engineer, or a different week; a size that
compares two Stories in the same repo does.

## Preconditions

- `gh` authenticated. Read access is enough unless the estimate is
  posted.
- Accessible source directories improve accuracy substantially — file
  existence turns "is this a new file?" from a guess into a fact.
- Nothing else. A missing design doc downgrades the estimate rather
  than blocking it.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{build_targets}`, `{design_doc_path}`,
`{test_plan_path}`.

**2. Detect the scope** and route:

| Target | Path |
|---|---|
| Milestone | Size every Story, then aggregate (step 6) |
| `type:story` | Steps 3-5 |
| `type:task` | Step 4 only |

A bare number is ambiguous between a milestone and an issue — check
both, and if both exist size the issue while noting the milestone.

**3. Gather signals.**

- **Resolve the design doc** via `References/artifact-resolution.md`
  § Resolution Chain — **optional** here. Stop at the local fallback; a
  missing design doc means a data-limited estimate (step 7), not a
  failure.
- **List the tasks**, if any exist. A real task count beats a predicted
  one.
- **Resolve the test plan** — also optional. A real case count is the
  best test-effort signal available.
- **Check the codebase.** For each file named in the design's
  implementation notes, `ls {file} 2>/dev/null`. This is what separates
  *new* files from *modified* ones — a distinction that moves a size by
  a whole level when the design says "add" and the file already exists.
- **Check for existing implementation** — `git -C {repo_root} log
  --oneline --all --grep="^#{task}:"`. Commits or merged PRs mean part
  of the work is already done.

**4. Size the tasks.** Per build target, extract the five signals and
take the median of their row values, per
`References/sizing-criteria.md` § Task-Level Sizing.

**Show the working, not just the answer:**

> | Build target | Paths | New | Mod | Ifaces | Deps | Size |
> |---|---|---|---|---|---|---|
> | libtelemetry | 2 (M) | 0 (S) | 3 (M) | 2 (S) | 1 (S) | **S** |
> | exporter-svc | 4 (L) | 3 (L) | 6 (L) | 7 (L) | 4 (L) | **L** |

A size with no visible signals is unarguable and therefore useless.
Showing the counts is what lets an engineer say "no, that interface
count is wrong" — which is the entire point of estimating out loud.

**5. Size the Story.** Aggregate the task data per
`References/sizing-criteria.md` § Story-Level Sizing, score design,
coding and test against § Dimensional Sizing, then take the overall as
the max of the three and apply that section's **two-below rule** — if
the max is two levels above *both* others, round down one. Assess risk
qualitatively against § Risk Assessment.

Present the three dimensions with a rationale each, the aggregate and
whether the two-below rule applied, the risk level, and the per-task
table.

**6. Size the milestone.** Size each Story, then aggregate per
`References/sizing-criteria.md` § Epic-Level Sizing with the analogous
rounding rule. Report coverage alongside the number — which Stories
have design docs and which are data-limited guesses — so the aggregate
is read with the right confidence.

**7. Data-limited estimates.** Without a design doc, estimate from
GitHub structure alone per `References/sizing-criteria.md` § Data-
Limited Estimates, and mark **every** value `(est.)`. Tasks exist →
use their count and estimate files from their titles. No tasks →
estimate from issue body length. Either way, recommend `story-design`
for a real estimate.

State the confidence plainly rather than burying it:

> "Data-limited estimate — no design doc. Based on issue body length
> and {n} existing tasks. Expect this to be wrong by a level in either
> direction."

An estimate presented without its confidence gets quoted back later as
a commitment. Say what it is.

**8. Present, and offer to post.** Show the estimate with its signals,
then ask whether to post it as an informational comment or display it
only. In an autonomous run, display only — an estimate is advice, and
posting it unasked puts a number on the record that nobody chose.

On post, use `References/artifact-resolution.md` § Upload Procedure
with sentinel `## dev-lifecycle-effort-estimate`, carrying the three
dimensions with rationales, the overall size and risk, the per-task
table, the signals table, and the confidence note if data-limited.

Each run posts a **new** comment rather than editing the last, so the
progression across pipeline stages stays visible — that is the
arrangement `References/sizing-criteria.md` § Re-Sizing describes.
Where earlier estimates exist, show the trajectory and what it implies:

> "Estimate history for #{issue}: M (after story-create) → L (after
> story-design) → L (now, after task-create). The growth between the
> first two suggests the initial read under-scoped the interface
> surface."

**9. Calibrate, where the work is finished.** Compare the estimate
against what actually happened — build targets, files, test cases,
commits — and say whether the estimate held:

> "Estimated M, actual signals map to **L**. Under-estimated — the
> interface count grew from 4 to 9 during implementation."

Say it **especially** when the estimate was wrong. Relative sizing only
improves if the misses are recorded; an estimate that is never checked
against reality is a number, not a measurement.

## Outputs

- An estimate with its signals, printed.
- Optionally, one `## dev-lifecycle-effort-estimate` comment.

## State Transitions

**None, by design.** This Skill applies no labels, closes nothing,
transitions nothing, creates no branch, and makes no commit. Its only
write is the optional informational comment, and only with consent.

## Errors

- **No design doc:** produce a data-limited estimate, annotated as one.
- **Design doc has no Build Targets table:** size from the code-path
  headings and warn that task-level sizing may not match what
  `task-create` will actually produce.
- **Source files not accessible:** estimate new-versus-modified from
  the implementation notes' language and mark those signals `(est.)`.
- **Milestone with no Stories:** nothing to size — route to
  `story-create` first.
- **Standard `gh` failures:** `References/gh-error-handling.md`.

Sizing bugs from a root-cause analysis is not part of this port — see
`AGENT.md` § What's Ported and What Isn't.
