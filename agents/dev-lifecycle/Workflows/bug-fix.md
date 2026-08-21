# bug-fix

The bug track end to end: analyze, gate the diagnosis, implement the
fix with a verified regression test, gate the fix, and resolve the bug
with a PR that closes it on merge.

Composes `bug-analyze`, `task-implement`, `task-test-plan`, and
`task-test`. Two human gates.

## Purpose

Bugs enter from outside the milestone → Story → task hierarchy, so they
get their own track rather than being forced into one. What does not
change is the discipline: a fix follows a stated root cause, and a
regression test is verified to fail before the fix rather than merely
claimed to.

## Preconditions

- A `type:bug` issue.
- `gh` authenticated with write access.
- No milestone, Story, or design doc required.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{default_branch}`, `{commands}`,
`{design_doc_path}`.

Note whether `build` and `test` are configured. Gate 1 reports their
absence, because **a bug fix without a runnable regression test is
worth flagging before any code is written**, not after.

**2. Get a root-cause analysis.** Fetch the issue and type-check it;
not `type:bug` → stop and route.

Scan comments for `## dev-lifecycle-rca`. Found → report it and ask
whether to use the existing analysis or re-analyze. Not found → run
`bug-analyze`.

**3. Verify the RCA landed.** Do not trust the Skill's self-report —
re-read GitHub:

```bash
gh issue view {issue} --repo {repo} --json comments \
  --jq '[.comments[] | select(.body | startswith("## dev-lifecycle-rca"))] | length'
```

0 → the analysis did not complete. Report and **stop**. Do not write a
fix without an RCA: **a fix without a stated root cause is a guess that
happens to make the symptom go away**, and it will regress.

Read the RCA and extract the root cause, its confidence, the proposed
changes, the risk assessment, and the test plan.

### Gate 1 — fix approval

Present the classification, the root cause with its confidence, the
proposed file/change table, the risk, and the test plan's case count.

Two warnings that must be surfaced here rather than discovered later:

> "The root cause is a **hypothesis**, not confirmed. {What is
> missing}. Implementing a fix on an unconfirmed cause risks masking
> the symptom without fixing the defect."

> "No `test` command configured — the regression test cannot be run
> automatically."

Options: **approve**, **request changes** (feed them back through
`bug-analyze` and re-present, at most 3 rounds), **investigate
further** (stop here; the RCA stands as triage output), or **stop**.

**Do not skip this gate.** Do not print the analysis and start coding.
The engineer decides whether the diagnosis is right before any code
changes — that is the whole value of having produced a diagnosis.

**4. Implement.** Run `task-implement` in bug mode. It cuts
`bug/{issue}-{slug}` off the default branch, uses the RCA as design
context in place of a design doc, and opens a PR **targeting the
default branch** carrying `Closes #{issue}` — that keyword fires here,
unlike on a task PR, because this merge lands on the default branch
(`AGENT.md` § Gotchas).

**5. Generate the regression test** with `task-test-plan` in bug mode,
grounding on the RCA instead of a design doc and Story test plan.

**Then verify the first case actually fails against the unfixed
code** — do not assert it:

```bash
git stash                # or check out the parent commit
{test_command}           # the new test should FAIL
git stash pop
{test_command}           # it should now PASS
```

A regression test that passes before the fix tests nothing. Passing
both ways →

> "The regression test passes against the unfixed code — it does not
> reproduce the bug. Either the test is wrong or the root cause is not
> what the RCA says."

**This is a strong signal the diagnosis is wrong.** Surface it at
Gate 2 rather than proceeding quietly; it is the single most useful
thing this Workflow can catch.

**6. Run the tests** with `task-test` in bug mode — no parent-Story
lookup, no sibling roll-up, resolves the bug directly on a pass.
Collect the outcome: `RESOLVED`, `IMPLEMENTED` (tests could not run),
or `BLOCKED`.

### Gate 2 — fix review

Present the branch, the PR and its state, the files changed, the build
result, and the test counts — including **whether the regression test
was verified as failing pre-fix, or not verified**.

Summarize what actually changed **from the diff, not from the plan**.
The plan is what was intended; the diff is what happened, and Gate 2
exists to check the second.

Carry forward any warning from step 5.

Options: **approve**, **request changes** (re-enter implementation, at
most 3 rounds), or **stop** and leave the PR open for manual review.

**7. Close out.** Mark the PR ready if it is still a draft, post a
closure summary to the issue (root cause, fix, tests, PR link), and
resolve the bug:

```bash
gh issue edit {issue} --repo {repo} \
  --add-label status:resolved --remove-label status:in-progress
```

**Do not merge.** The PR carries `Closes #{issue}` and targets the
default branch, so merging closes the issue automatically — and
merging is a human decision, gated by review and CI.

> "PR #{pr} is ready for review. Merging it closes #{issue}."

This is stricter than the source material, which allows merging on an
explicit request. `AGENT.md` § Boundaries admits no exception, and one
here would be the worst place for it: a bug fix is exactly the change
most likely to be urgent, least likely to have been reviewed, and most
likely to be merged in a hurry.

**8. Summarize** — the root cause and confidence, the files changed and
the branch, the test counts and whether the regression test was
verified, the PR, and that the issue closes on merge.

Where the outcome was `IMPLEMENTED`, say plainly that **the fix is
unverified** because no test command was configured, and name what to
do about it. Where it was `BLOCKED`, report the reason and note that
the branch and PR are preserved for a re-run.

## Outputs

- An RCA document and its sentinel comment (via `bug-analyze`).
- A `bug/{issue}-{slug}` branch with the fix and its regression test.
- A PR against the default branch carrying `Closes #{issue}`.
- The bug moved to Resolved; it closes when a human merges.

## State Transitions

Bug: Open → In Progress (`bug-analyze`) → Resolved (step 7) → Closed,
by the merge, not by this Workflow.

## Errors

- **Not a bug:** stop and route.
- **RCA missing after `bug-analyze`:** stop. Never fix without one.
- **Root cause is a hypothesis:** allowed, but surfaced at Gate 1 as a
  warning. The engineer decides whether to fix on an unconfirmed
  diagnosis.
- **Regression test passes pre-fix:** report loudly at Gate 2 — the
  diagnosis is probably wrong.
- **No test command:** the fix lands as `IMPLEMENTED`, unverified, and
  the summary says so.
- **Implementation blocked:** preserve the branch and PR, report the
  reason.
- **Standard `gh` failures:** `References/gh-error-handling.md`.

Never merges, deletes, or force-pushes — see `AGENT.md` § Boundaries.
