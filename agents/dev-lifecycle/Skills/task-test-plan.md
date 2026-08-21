# task-test-plan

Generates focused unit test cases for one task's build target, and
writes the test code, using the design doc's build-target slice, the
Story test plan, and the diff that was actually written. Runs between
`task-implement` and `task-test` — the tests it commits are what
`task-test` executes.

## Purpose

Produce unit coverage that targets the code as implemented rather than
the code as designed, scoped to a single build target so it lands in
the same PR as the change it tests.

## Preconditions

- A `type:task` issue whose parent Story has a design doc.
- `gh` authenticated with write access.
- Accepts several task numbers at once. Steps 2-9 run independently per
  task; step 1 runs once for the whole invocation.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{design_doc_path}`, `{test_plan_path}`,
`{build_targets}`.

**2. Fetch the task** (`number,title,body,state,labels,milestone,
comments`) and find its parent Story — a native sub-issue link
(`References/gh-operations.md` § Sub-issues), or the `Parent: #N` body
line as fallback. Not `type:task` → warn and route: `type:story` to
`story-test-plan`, anything else ask.

**3. Resolve the parent Story's design doc** via
`References/artifact-resolution.md` § Resolution Chain, sentinel
`## dev-lifecycle-design-doc`. First match wins, worked in order; a
local path written into an issue body is ignored.

Then narrow it to this task's slice per that reference's § Narrowing to
One Build Target — normalize the task title, find the target in
`## Build Targets`, and aggregate every code-path section whose build
target matches. Extract interfaces, dependencies, and error-handling
notes.

**4. Resolve the Story test plan** via the same reference, sentinel
`## dev-lifecycle-test-plan`, then filter to the cases touching this
build target. **Optional** — stop after the local-file fallback rather
than prompting; not found means Story-level mapping is skipped, not
that the Skill stops.

**5. Read the implementation.** This is the step that makes the tests
real rather than aspirational:

```bash
git -C {repo_root} log --oneline --all --grep="^#{issue}:"

pr=$(gh pr list --repo {repo} --head "task/{issue}-*" --state all \
      --json number --jq '.[0].number')
[ -n "$pr" ] && gh pr diff "$pr" --repo {repo}
```

From the diff take the actual function signatures and public APIs, the
error paths implemented, the edge cases handled — or conspicuously not
handled — and the dependencies used and how they are called.

**Where the design describes an interface and the code implements it
differently, target the code** and note the discrepancy in the
generated plan. Neither is silently preferred: the tests must run
against what exists, and the mismatch is a fact the reviewer needs.

No commits and no PR → implementation has not started. Generate from
design context alone and state plainly that the cases are unverified
against real signatures.

**6. Generate the cases** across these categories:

- **Interface contract** — per public function: valid input to
  expected output, return-type verification, and side effects (state
  changes, calls into dependencies).
- **Error condition** — per error condition in the design or in the
  code: invalid input to expected error, resource unavailable handled
  gracefully, timeout and retry behaviour.
- **Boundary value** — empty inputs, null values, maximum-size inputs,
  unicode and special characters, off-by-one on every numeric
  parameter.
- **Dependency mocks** — per dependency: mock the interface, mock
  success, mock failure, and verify the dependency was called with the
  right parameters.
- **Concurrency and thread safety** — per concurrently-callable
  function: parallel invocation without data races, correct locking or
  serialization, concurrent read and write on shared state. Explicitly
  single-threaded target → skip the category and say so.
- **Error recovery** — per multi-step function: mock an intermediate
  failure and check partial state is cleaned up, the caller can retry,
  and nothing leaks on the failure path (handles, memory, locks).

Map each case back to the Story-level case number it supports, where
one applies.

**7. Draft, then gate.** Infer language and framework conventions from
the existing test files in the repo; where no tests exist for this
area, use the project's dominant framework, and where there are none at
all, generate a standalone harness in the primary language.

In an interactive run, present the drafted cases and the framework
choice, and wait for the engineer to approve, adjust, add, or remove
cases before anything is written. In an autonomous run, select from the
existing patterns and proceed without pausing, recording the choice in
the summary.

**8. Write and commit.** The plan goes to
`{test_plan_path}/{issue}-unit-tests.md`; the test code goes wherever
the project already puts tests — mirroring the source tree, a `tests/`
directory, beside the source, whatever the existing convention is.

```bash
git add "{test_plan_path}/{issue}-unit-tests.md" {test_files}
git commit -m "#{issue}: Add unit tests for {build_target}"
```

Commit on the task branch (`task/{issue}-{slug}`) when it exists — the
tests belong in the same PR as the code they cover. No task branch →
warn and commit on the current branch. **Never run `git init`** (see
`AGENT.md` § Boundaries).

**9. Upload** via `References/artifact-resolution.md` § Upload
Procedure, sentinel `## dev-lifecycle-unit-tests`, path
`docs/test-plans/{issue}-unit-tests.md`. The comment carries the
permalink, the committed test-file paths, the commit SHA and branch,
the total case count, the per-category breakdown, and how many cases
map to the Story's test plan.

Verify it landed, per that section:

```bash
gh issue view {issue} --repo {repo} --json comments \
  --jq '[.comments[] | select(.body | startswith("## dev-lifecycle-unit-tests"))] | length'
```

Still 0 after one retry → warn, do not block; the plan is on disk
either way.

Then comment a **short** summary — counts and categories, not the full
plan — on the task PR where one exists, so reviewers see the coverage
without leaving the PR.

**10. Report.** For a single task, the case count by category and the
commit. For several, a summary table:

| # | Issue | Build target | Test cases | Posted |
|---|---|---|---|---|
| 1 | #61 | libtelemetry | 30 | yes |
| 2 | #62 | exporter-svc | 25 | yes |

Then note that `task-test` is next.

## Outputs

- A committed `docs/test-plans/{issue}-unit-tests.md` per task.
- Executable test code committed on the task branch.
- A `## dev-lifecycle-unit-tests` sentinel comment per task issue, plus
  a short summary comment on the task PR.

## State Transitions

None. Running tests and resolving the task is `task-test`'s job.

## Errors

- **Not a task:** warn and route to `story-test-plan` for Story-level
  plans.
- **Design doc not found:** warn but continue — generate from the issue
  body and the implementation diff, and report the reduced grounding.
- **Build-target section not found in the design doc:** generate from
  the task title, body, and diff; warn about reduced coverage.
- **Story test plan not found:** skip Story-level mapping and continue.
- **No implementation found:** generate from design context and state
  that the cases are unverified against real signatures.
- **Existing tests already cover this target:** do not duplicate them.
  Report what exists, generate only the gaps, and name the categories
  that were already covered.
- **Standard `gh` failures:** `References/gh-error-handling.md`.

## Bug Mode

Invoked by `Workflows/bug-fix.md` against a `type:bug` issue rather
than a task. Three differences, and nothing else changes:

- `type:bug` is accepted in place of `type:task`.
- **The RCA replaces both the design doc and the Story test plan** —
  resolve `## dev-lifecycle-rca` via
  `References/artifact-resolution.md` and take the proposed fix and
  test plan from it. Do not follow the normal design-doc chain.
- Parent-Story lookup is skipped; a bug has none, and Story-level case
  mapping does not apply.

The RCA's test plan states that **its first case must fail against the
unfixed code**. Generate that case first. `bug-fix` step 5 then
verifies the claim by running it against the pre-fix tree — this Skill
writes the test, it does not get to assert that the test works.
