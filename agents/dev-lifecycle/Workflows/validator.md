# validator

The validation role: regrounds a Story's test plan on the code that
was actually written, runs it, and returns a verdict. Composed by
`autodev`; independently invocable on its own.

## Purpose

One of three worker roles — `planner`, `coder`, `validator`. Scoped to
one Story, run once every task under it is resolved.

Its job is to produce a **verdict the orchestrator can act on**, not to
decide what happens next. It does not close the Story and does not roll
up the milestone.

## Preconditions

- A `type:story` issue whose implementation tasks are all resolved or
  closed.
- An existing test plan, ideally — absent one, `story-test` degrades
  explicitly and says so.
- `gh` authenticated with write access.

## Running This Role

As `Workflows/planner.md` § Running This Role. Validation reads test
output, results files, and diffs, so a separate worker keeps that
volume out of the orchestrator's context. Inline works identically.

## Procedure

**1. Preflight.** Run `References/context-discovery.md` in full. Fetch
the Story and confirm it is `type:story` and that its implementation
tasks are resolved or closed (`References/workflow-states.md` § All
Tasks Resolved Check). Tasks outstanding → return `BLOCKED` naming
them; validating a Story mid-implementation measures nothing.

**2. Reground the plan on what was built.** Run `story-test-replan`.
A plan written before implementation frequently tests interfaces that
changed, so this runs *before* anything executes.

Parse the first line of its return
(`Skills/story-test-replan.md` § Return Contract):

| Return | Action |
|---|---|
| `DELTA_APPLIED: …` | Use the updated plan; carry the delta into the report |
| `NO_DELTA: {reason}` | Not applicable — continue with the existing plan. **Not an error** |
| `NO_CHANGES: …` | Plan already matches. Continue |
| `BLOCKED: {reason}` | Note it and continue with the existing plan |

**Failure of this step is never fatal** — warn and continue with the
existing plan.

Where the replan flagged cases **OUTDATED**, carry that into the
verdict explicitly:

> "{n} test cases are flagged OUTDATED by the replan and were not
> updated. Their results are lower-confidence."

An OUTDATED case that "passes" may be passing for the wrong reason.
That is exactly why `story-test-replan` flags rather than rewrites —
see that Skill's step 4.

**3. Run the plan.** Run `story-test`.

In a worker there is no engineer at the keyboard, so prefer
non-interactive execution modes in this order: the project's automated
`test` command, then CI evidence, then existing recorded results. If
manual execution is the only option available, the verdict is
`TESTS_SKIPPED` — **not a hang**. A worker that waits for input nobody
can give has stalled, and stall prevention is the discipline this
whole orchestration layer is built on.

**4. Extract the verdict** — PASS / FAIL / PARTIAL / TESTS_SKIPPED —
along with total, passed, failed and skipped counts, the pass rate, the
results file path and permalink, the execution mode, and any
regressions or flaky tests.

**Verify the verdict against the results file**, re-read from disk,
rather than trusting the summary text. Where the two disagree, **report
what the counts say** and note the discrepancy. This is the same
verify-don't-assume rule that
`References/gh-error-handling.md` § 12 applies to writes, turned on
this role's own output — a worker is not exempt from it just because it
is the one reporting.

**5. Return the verdict.** Do not open anything further, transition the
milestone, or decide what happens next. That is the orchestrator's
closure gate.

## What This Role Does Not Withhold

Forge's validator runs its test step with closure suppressed, so that
closing the Story and opening the integration PR wait for the
orchestrator's approval gate.

**This port needs no such flag, because `story-test` here never closes
anything.** It opens the integration PR carrying `Closes #N` lines, and
those fire only when a human merges it onto the default branch — see
`Skills/story-test.md` step 10 and `AGENT.md` § Gotchas. Opening a PR
is explicitly inside this pipeline's boundaries; merging one is
explicitly outside them.

So the closure gate still exists and still gates the real decision — it
just gates the **merge** rather than the PR's creation. On a `FAIL`,
`story-test` stops at its failure path without reaching the integration
PR step at all, so a failing Story produces no PR to withhold.

## Output Contract

**The first line is parsed by the orchestrator.**

```
#{story}: PASS
Tests: {passed}/{total} ({rate}%), {skipped} skipped
Mode: {Automated | CI | Existing}
Replan: {delta summary | no delta}
Tasks: {resolved}/{total} resolved, {merged}/{total} PRs merged
Results: docs/test-results/{story}-{timestamp}.md ({permalink})
Story branch: story/{story}-{slug} — integration PR #{pr} open
```

```
#{story}: FAIL
Tests: {passed}/{total} ({rate}%), {failed} FAIL
Failures:
  - {case}: {reason}
Mode: {mode}
Regressions: {list | none}
Results: docs/test-results/{story}-{timestamp}.md ({permalink})
```

```
#{story}: PARTIAL
Tests: {passed}/{total} ({rate}%), {skipped} skipped
Skipped cases: {list with reasons}
Mode: {mode}
Results: docs/test-results/{story}-{timestamp}.md ({permalink})
```

```
#{story}: TESTS_SKIPPED
Reason: {no test command | no CI evidence | manual execution unavailable in a worker}
Tests: 0/{total} executed
Tasks: {resolved}/{total} resolved
Results: docs/test-results/{story}-{timestamp}.md (execution mode: none)
Resume: {what the engineer needs to do}
```

Append when they apply, on any verdict:

```
⚠ {n} cases flagged OUTDATED by the replan — lower-confidence results
⚠ Regressions: {list}
⚠ Flaky: {list}
```

## Outputs

A regrounded test plan (where a delta applied), a timestamped
test-results artifact with its sentinel comment, the test-execution
task resolved on a pass, and — on a pass — the integration PR that
`story-test` opens.

## Errors

- **Tasks not all resolved:** return `BLOCKED` naming them.
- **No test plan:** not fatal. `story-test` falls back to the project
  test command scoped to the Story's build targets, at reduced
  grounding, and says so.
- **`story-test-replan` fails:** warn, continue with the existing plan.
- **Only manual execution available:** `TESTS_SKIPPED`, never a wait.
- **Verdict disagrees with the results file:** report the counts and
  the discrepancy.

Never merges — see `AGENT.md` § Boundaries.
