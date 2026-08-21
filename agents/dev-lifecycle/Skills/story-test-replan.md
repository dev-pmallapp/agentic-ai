# story-test-replan

Updates an existing test plan against what was actually built. Grounds
on implementation commits and task PRs, then marks stale cases
not-applicable, flags changed ones outdated, and generates cases for
uncovered surfaces. Runs after implementation, before `story-test`.

## Purpose

The distinction from `story-test-plan`: that Skill **generates** a plan
from a design; this one **diffs** an existing plan against reality.
A plan written before the code was written describes intentions, and
intentions drift.

## Preconditions

- A `type:story` issue with an existing test plan.
- Implementation commits for at least some of its tasks.
- `gh` authenticated with write access.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{design_doc_path}`, `{test_plan_path}`.

**2. Load the plan and cases.**

- **Fetch the Story.** Not `type:story` → route and stop.
- **Resolve the existing test plan** via
  `References/artifact-resolution.md` § Resolution Chain, sentinel
  `## dev-lifecycle-test-plan` — **required**. Not found → stop; there
  is nothing to replan. Route to `story-test-plan`.
- **Inventory the case files** in
  `{test_plan_path}/test-cases/{issue}/`, recording number, slug,
  filename, category, priority, purpose, steps summary, and status.
  Files already carrying `status: not-applicable` are inventoried but
  **not re-classified** in this pass — exclude them from active
  coverage and from uncovered-surface counts.
- **Resolve the design doc** — needed to map build targets to cases.

**3. Ground on the implementation.** Unlike `story-test-plan`, where
grounding is optional, here it is the entire point: without
implementation data there is nothing to diff.

List the Story's tasks (`References/gh-operations.md` § Sub-issues).
Zero → stop; implementation has not started, and initial generation is
`story-test-plan`'s job.

```bash
git -C {repo_root} log --oneline --all --grep="^#{task}:"

gh pr list --repo {repo} --base "story/{issue}-*" --state all \
  --json number,headRefName,state,mergedAt,files
```

The PRs against the story branch are the authoritative view. In a
multi-repo project, run the git command in each declared repo path.

Nothing found anywhere → return **`NO_DELTA`** and stop. This is **not
a fatal error** — tasks exist but the code may pre-date this Story.
Callers treat it as "replan not applicable" and continue with the
existing plan.

Read the diffs (`gh pr diff {pr}`, `git show {sha}`) and build a
**surface inventory** — for each interface, API, error path, edge case,
config option or integration point discovered, record its name, source
task, source file, and type.

**4. Analyze the delta.** Map each active case to the surfaces it
covers, using build-target names as anchors, and classify:

| Class | Meaning |
|---|---|
| **VALID** | Covers a real, unchanged surface; steps and expectations still match the code |
| **NOT-APPLICABLE** | The surface it targeted no longer exists — API removed, target refactored away, approach fundamentally changed |
| **OUTDATED** | Right surface, wrong details — signature changed, error codes differ, new parameters |

**OUTDATED cases are flagged, never auto-rewritten.** Silently editing
a test's expectations to match the code destroys the test's value: if
the code changed the contract, a human decides whether the code or the
test is wrong. A test that always agrees with the implementation is not
a test.

Then identify uncovered surfaces and group them by the category a new
case would belong to — a new API or interface is Positive, a new error
path Negative, a new edge case Boundary, a new integration point
Integration, a new config option a config-matrix case.

Present the delta: existing case counts split VALID / OUTDATED /
NOT-APPLICABLE, surfaces covered versus uncovered, the proposed new
cases with category and priority, the cases to be marked
not-applicable with reasons, and the cases flagged outdated with what
changed.

Then ask: apply the whole delta; apply the new cases only, skipping the
not-applicable markings; review each classification individually; or
stop. In an autonomous run, apply and report what was applied.

**5. Apply the delta.**

- **Not-applicable cases:** edit the case file's frontmatter — `status:
  not-applicable`, a reason, and a date. **Do not delete the file.**
  The record of what was once planned, and why it stopped applying, is
  worth keeping.
- **Outdated cases:** add `status: outdated` and a reason to the
  frontmatter, plus a note at the top of the body. **Do not touch the
  steps or expected result.**
- **New cases:** generate files continuing the **global numbering from
  the highest existing number**. Never renumber existing cases —
  results files and issue comments reference them by number, and
  renumbering silently invalidates every one of those references.
- **The plan file:** add rows for new cases, annotate changed rows, and
  append a replan-history entry naming the date, how many commits
  across how many tasks it was grounded on, the classification counts,
  and the new case number range.

**6. Self-review** the new cases against the same checklist
`Skills/story-test-plan.md` step 7 applies — the structural scan across
every new file, and a full read of every new P0, verified from disk
rather than from memory of what was written. Then present for approval
in an interactive run; report and proceed in an autonomous one.

**7. Commit and upload.**

```bash
git add "{test_plan_path}/{issue}-test-plan.md" \
        "{test_plan_path}/test-cases/{issue}/"
git commit -m "#{issue}: Reground test plan on implementation"
git push
```

Post a **new** `## dev-lifecycle-test-plan` sentinel comment via
`References/artifact-resolution.md` § Upload Procedure — new, not an
edit of the old one, so the plan's evolution stays readable; consumers
take the most recent automatically. Carry the delta in the metadata:
total cases split active versus not-applicable, the delta counts, and
how many commits across how many tasks it was grounded on. Verify it
landed, per that section.

**8. Report** the classification counts, the new case count, and — when
any case is flagged outdated — say prominently that those were **not**
modified and need review before `story-test` runs.

## Return Contract

Callers parse the first line:

| First line | Meaning |
|---|---|
| `DELTA_APPLIED: +{n} new, {n} outdated, {n} n/a` | Plan updated |
| `NO_DELTA: {reason}` | Nothing to diff against; proceed with the existing plan |
| `NO_CHANGES: plan already matches implementation` | Grounded successfully, nothing to change |
| `BLOCKED: {reason}` | Could not run — no plan, or no tasks |

## Outputs

- Case files edited in place with status frontmatter; new case files
  added.
- An updated plan file with a replan-history entry.
- A new `## dev-lifecycle-test-plan` sentinel comment.

## State Transitions

None.

## Errors

- **No existing test plan:** stop, route to `story-test-plan`.
- **No tasks:** stop, same routing.
- **Tasks but no commits:** return `NO_DELTA` — not an error.
- **Design doc not found:** continue with reduced mapping accuracy;
  surfaces are still discoverable from the diffs. Warn.
- **Case files missing but the plan lists cases:** the plan and the
  files are out of sync. Report which numbers have no file and offer to
  generate them from the plan rows before diffing — do not treat the
  missing cases as uncovered surfaces.
- **Standard `gh` failures:** `References/gh-error-handling.md`.
