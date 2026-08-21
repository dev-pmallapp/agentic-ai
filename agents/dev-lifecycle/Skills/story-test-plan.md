# story-test-plan

Generates a categorized, prioritized test plan for a Story from its
approved design doc, plus one standalone instruction file per test
case. Runs between `story-design` and `task-create`; its output is what
`story-test` later executes.

## Purpose

Turn a design document into an explicit, reviewable list of what must
be true before the Story ships — derived from the design's interfaces,
error conditions, and stated limits rather than from whatever the
implementation happens to do.

## Preconditions

- A `type:story` issue with a completed design doc.
- `gh` authenticated with write access. This is a **hard**
  precondition, not a soft one: the plan is uploaded to the issue, and
  every downstream consumer resolves it from there first. A plan that
  exists only on local disk is not a delivered plan — stop rather than
  producing one.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{design_doc_path}`, `{test_plan_path}`.

**2. Fetch the Story** (`number,title,body,state,labels,milestone,
comments`). Not `type:story` → route: `type:task` to `task-test-plan`,
anything else warn and ask.

**3. Resolve the design doc** via `References/artifact-resolution.md`
§ Resolution Chain, sentinel `## dev-lifecycle-design-doc`. **Required**
— follow the chain to the end. Work the steps in order and let the
first match win; the issue is the source of truth and a local path
written into an issue body is ignored (per-engineer paths go stale).

Parse out the feature scope: build targets and code paths, interfaces
and APIs, error conditions and failure modes, and any performance or
scale requirements.

**4. Ground the plan in the implementation, if any exists.** In the
normal pipeline order this Skill runs before `task-create`, so there is
usually nothing to ground on and this step skips. It earns its place
when the Story is being re-planned after work started.

List the Story's sub-issues (`References/gh-operations.md`
§ Sub-issues); zero → skip. Otherwise look for implementation commits
and merged task PRs:

```bash
git -C {repo_root} log --oneline --all --grep="^#{task}:"
gh pr list --repo {repo} --base "story/{issue}-*" --state all \
  --json number,headRefName,state,files
```

Read the diffs for real signatures, error paths actually implemented,
and edge cases handled in code but absent from the design. **Where the
design and the implementation disagree, the implementation wins** — and
the discrepancy is called out in the plan rather than quietly resolved.
This step is purely additive; skipped, the plan rests on the design
alone.

A full re-grounding pass over an already-implemented Story is
`story-test-replan`'s job, not this one.

**5. Generate the cases.** Number them **globally and sequentially**
across the whole plan — 1, 2, 3… continuing over category boundaries,
never restarting per category. Priority is P0 / P1 / P2.

| Category | Priority | Derived from |
|---|---|---|
| Positive | P0-P1 | Primary functionality and interfaces of each build target |
| Negative | P1 | Error conditions and invalid inputs |
| Boundary | P1 | Min/max, zero, empty, off-by-one for every bounded input |
| Error Recovery | P1-P2 | Each failure mode — does the system return to a usable state? |
| Concurrency | P1-P2 | Multi-caller interfaces — parallel access, races, shared state |
| Integration | P1-P2 | Cross-target interactions, and interaction with the existing system |
| Upgrade/Downgrade | P1 | Behaviour across version boundaries, where applicable |
| Scale | P2 | Load and resource limits from the design's scale considerations |
| Performance | P1-P2 | Latency and throughput targets from the design |
| Loop / Stability | P2 | Long-running, repeated-operation scenarios |

Three distinctions that are routinely collapsed and should not be:

- **Negative** is input rejection and error *reporting*. **Error
  Recovery** is system behaviour *after* the failure — can the
  operation be retried, is state corrupted, did cleanup run.
- **Boundary** cases are separate rows from Negative ones, even when
  they share an input.
- **Concurrency** may legitimately be empty if the design states the
  target is single-threaded — say so explicitly rather than omitting
  the category and leaving a reader to guess.

Absent stated performance or scale targets, write cases that establish
a baseline rather than inventing thresholds.

**6. Write one instruction file per case** — an instruction document,
not code — to `{test_plan_path}/test-cases/{issue}/{NN}-{slug}.md`,
zero-padded, slug in kebab-case (`01-basic-flow-export.md`).

Each file carries frontmatter with `topology` (from the design:
single-node for unit-level, back-to-back for datapath, switched for
multi-hop), `timeout` (estimated from complexity — simple 60-120s,
firmware/flash 300-600s, scale 600-1800s), `pass_criteria` (one line),
`stability` (default `stable`; `flaky` only where the design names
known intermittent behaviour, and then a linked issue is required), and
`validation_groups` (`[post-test]` for state-modifying tests, omitted
for read-only ones). Then `## Steps`, `## Expected Result`, and
`## Failure Indicators`.

Every step is a concrete command or action rather than a description,
tagged with the machine it runs on (`**[host]**`, `**[server]**`,
`**[client]**`), and ends with an `Expected:` line. Derive real commands
from the design's interface sections; where exact syntax is unknown,
use the design's command names with placeholder arguments.

P0 cases must have complete steps. P1 cases should have steps wherever
the commands are known. P2 cases may stay high-level and be refined at
execution time.

**7. Self-review, against the files on disk.** Verify from disk, not
from memory of what you just wrote — what landed may differ from what
was intended. Two passes, both required:

- **Structural, across every file:** frontmatter has `topology`,
  `timeout`, `pass_criteria`; a `## Steps` section exists; at least one
  `Expected:` line exists; `## Expected Result` and `## Failure
  Indicators` both exist.
- **Full content, P0 files only:** read each one. Every step has a
  concrete command (not "verify X works") and an `Expected:` line.
  Re-read the plan and confirm the row count matches the file count.

Then check coverage: every plan row has a file; Positive, Negative and
Integration each have at least one case; Boundary is present if the
design defines bounded inputs; at least two P0 cases exist; every build
target has a case; every error condition has a negative case; every
public interface has a positive case; Error Recovery is present if the
design lists failure modes; Concurrency is present if it lists
multi-caller interfaces. Fix what fails before continuing, and report
`{passed}/{total} checks passed, {fixed} fixed`.

**8. Engineer review gate.** Present the case count by category and
priority, the self-review results, two or three P0 files for
spot-check, and any coverage gap deliberately left unfilled with the
reason. Ask the engineer to approve, request changes (iterate, at most
three rounds), or stop (commit and upload nothing).

Do not skip this gate, and do not rationalize past it because the plan
looks complete. In an autonomous run it resolves as approve-and-note,
consistent with every other gate in this pipeline; in an interactive
one it is a real pause.

**9. Commit on the story branch** (`story/{issue}-{slug}`; create it
per `References/branch-and-pr-model.md` if absent):

```bash
mkdir -p "{test_plan_path}/test-cases/{issue}"
git add "{test_plan_path}/{issue}-test-plan.md" \
        "{test_plan_path}/test-cases/{issue}/"
git commit -m "#{issue}: Add test plan and test cases"
git push
```

**10. Upload** via `References/artifact-resolution.md` § Upload
Procedure, sentinel `## dev-lifecycle-test-plan`, path
`docs/test-plans/{issue}-test-plan.md`. The comment carries the
permalink, the commit SHA and branch, total cases split by priority,
the category list, and the case-file count — then the full plan below a
`---` separator when it fits. **Check the comment size rather than
assuming it fits**; a plan with many cases frequently exceeds the
limit, and the Upload Procedure's summary-plus-permalink fallback
handles it.

Verify the upload landed, per that same section — an operation that
exits 0 having done nothing is the failure mode this pipeline guards
against everywhere:

```bash
gh issue view {issue} --repo {repo} --json comments \
  --jq '[.comments[] | select(.body | startswith("## dev-lifecycle-test-plan"))] | length'
```

Still 0 after one retry → warn, do not block.

**11. Report** the case count by category and priority, the case-file
count, the commit, and that `task-create` is next.

## Re-running

Re-running regenerates the plan and posts a **new** sentinel comment.
Consumers take the most recent sentinel, so the newest wins with no
cleanup needed. Existing case files are overwritten; case files whose
rows no longer exist are **left in place and reported**, not deleted —
this pipeline does not delete an engineer's files on inference:

> "{n} stale case files no longer referenced by the plan: {list}.
> Delete them if those cases were intentionally dropped."

## Outputs

- A committed `docs/test-plans/{issue}-test-plan.md`.
- One instruction file per case in
  `docs/test-plans/test-cases/{issue}/`.
- A `## dev-lifecycle-test-plan` sentinel comment on the Story.

## State Transitions

None. This Skill produces an artifact; it does not move the Story
between states.

## Errors

- **Design doc not found:** report which sources were checked and route
  to `story-design` first. Do not generate a plan from the issue body
  alone — an ungrounded test plan is worse than none, because
  downstream Skills trust it.
- **Design doc has no interfaces or error conditions:** generate what
  is derivable and report the thin coverage explicitly rather than
  inventing requirements to fill the categories.
- **Comment exceeds the size limit:** handled by
  `References/artifact-resolution.md` — summary plus permalink.
- **`gh` unavailable or unauthenticated:** stop. See
  `## Preconditions`.
- **Standard `gh` failures:** `References/gh-error-handling.md`.

## Templates

Two templates back this Skill's outputs:

- `Templates/test-plan.md` — the plan document. Its `### <Category>`
  headings and the `#` / `Test Case` / `Description` / `Priority`
  columns are fixed: `story-test` matches its results rows back to
  these case numbers.
- `Templates/test-case.md` — one per case, for the instruction files
  under `docs/test-plans/test-cases/{issue}/`. Its frontmatter is read
  mechanically, `pass_criteria` above all.

The templates hold the *shape*. What each category means, the three
distinctions that are routinely collapsed, and the global-numbering
and priority rules are step 5 above, and are deliberately not repeated
in the templates — one place to edit when they change.

Leave the plan's `## Results` table empty. `story-test` writes results
to a separate file; a plan carrying its own results cannot be re-run
without editing it.
