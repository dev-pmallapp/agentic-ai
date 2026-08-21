# bug-analyze

Investigates a `type:bug` issue and produces a root-cause analysis
document: the specific defect, the trace to it, a proposed fix, and a
test plan whose first case fails against the current code.

## Purpose

Turn a bug report into something implementable. The output is a
committed RCA document plus a sentinel comment, which is what
`bug-fix` and `task-test-plan` consume — the bug track's equivalent of
what `story-design` produces for a feature.

## Preconditions

- A `type:bug` issue with a description.
- `gh` authenticated with write access.
- A bug needs **no milestone, no Story, and no Build Targets table**.
  Unlike everything else in this pipeline, those absences are not
  blocking here — bugs arrive from outside the planning hierarchy.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{build_targets}`, `{design_doc_path}`,
and the knowledge files.

**2. Validate the bug.** Fetch it (`number,title,body,state,labels,
assignees,milestone,url,createdAt,comments`).

Not `type:bug` → **hard stop** with routing: a Story goes to
`story-design`, a milestone to `autodev`, a task to `task-implement`.
No `type:` label at all → ask whether to treat it as a bug and label
it; on no, stop.

Then check information completeness:

| Field | Level | Check |
|---|---|---|
| Description | **Required** | Non-empty, and more than the title restated |
| Stack trace | **Required if a crash is reported** | See below |
| Version / build | Should have | Version strings, build numbers, commit SHAs |
| Reproduction steps | Should have | Commands, inputs, sequence |
| Observed vs expected | Should have | Both stated explicitly |
| Environment | Should have | OS, runtime, configuration |
| Attachments | Nice to have | Logs, dumps, screenshots |

Two hard stops, because proceeding past either produces a guess
dressed as an analysis:

- **No description** — stop and ask for the symptom, the environment,
  and what was expected.
- **A crash reported with no trace.** Scan body and comments for crash
  indicators (`segfault`, `panic`, `core dump`, `SIGSEGV`, `unhandled
  exception`) and for trace markers (`#0`, `at …:line`, `Traceback`,
  `goroutine`, `Stack trace`). Indicated but absent → stop, and say how
  to get one:

  > "#{issue} reports a crash but includes no stack trace. A trace
  > turns this from a guessing exercise into a five-minute read.
  > Attach one and re-run. For a core file: `gdb -batch -ex 'bt full'
  > -ex 'thread apply all bt' <binary> <core>`"

Present the full validation table. Should-have gaps are informational
warnings; only the required ones stop.

**3. Gather evidence.** GitHub stores attachments as asset URLs in the
body and comments. Extract and fetch them:

```bash
mkdir -p /tmp/dev-lifecycle-{issue}
curl -sfL -H "Authorization: token $(gh auth token)" \
  -o "/tmp/dev-lifecycle-{issue}/{filename}" "{asset_url}"
```

Validate each download — non-zero size, content type matching the
extension. A 404 usually means the asset is private to a different
org; note it and continue.

**Handle archives generically — do not hardcode extraction patterns**,
because layouts vary:

```bash
tar tzf {bundle} | head -30          # inspect before extracting
tar xzf {bundle} -C /tmp/dev-lifecycle-{issue}/
```

Handle nested archives, gzipped text, and plain logs, then find the
files carrying system state (names matching `version`, `config`,
`system`, `info`, `status`, `env`, `diag`).

**Evidence from a bundle takes priority over prose in the
description.** The description is what a human remembered; the bundle
is what the machine recorded.

Also follow linked context — issue and PR references in the body and
comments. **A referenced PR is often the change that introduced the
bug, which is the strongest lead available.**

**4. Check for existing analysis.** Scan comments for
`## dev-lifecycle-rca`. Found → ask whether to overwrite and
re-analyze, or stop and report the existing one. The analysis is never
silently redone.

Also scan for **prior investigation** by humans — hypotheses tried,
things ruled out. This is high-value input: incorporate it, credit it
in the RCA, and do not silently repeat work someone already did.

**5. Classify the symptom — before tracing any code.**

| Class | Examples | Investigate |
|---|---|---|
| Always wrong | "returns 0", "crashes every call" | Data flow, logic error |
| Intermittent | "sometimes fails", "flaky" | Races, thread safety, ordering |
| Delayed | "wrong at first, correct later" | Startup ordering, caching, timers |
| Regression | "worked in version X" | Version diff, recent commits |
| Conditional | "only with config Y" | Config-specific paths, feature flags |
| Environmental | "only on host Z" | Environment differences, resource limits |

**Classification steers everything downstream.** An intermittent bug
investigated as an always-wrong bug wastes hours reading correct code.
Ambiguous → say so and carry multiple hypotheses rather than
committing to one.

**6. Scope it before tracing.** Determine which component, build
target, and version the bug lives in **before reading any code**.

Take indicators in priority order: bundle evidence (authoritative), a
structured environment section, version and config strings, then the
stack trace's file paths (the most direct signal). None at all → record
"component-agnostic" and derive scope from the symptom.

Map to a build target and **verify rather than guess** — a file path in
a trace is evidence; a component name in prose is a hint. Genuinely
ambiguous → ask, listing the candidates, rather than picking one and
burning the investigation on the wrong subsystem.

Record the scope and filter all subsequent tracing by it.

**7. Investigate.** For a regression-class symptom where the issue
names a working version:

```bash
git -C {repo_root} log --oneline {good_ref}..{bad_ref} -- {scoped_paths}
```

A small suspect range is worth reading commit by commit; a large one
warrants an actual `git bisect` if the bug reproduces.

Otherwise work systematically — use a structured debugging aid if the
harness offers one, else follow the same shape by hand: read the error
carefully, reproduce, check recent changes, trace the data flow, form a
hypothesis, and test it with the smallest possible change. Then trace
backward from the symptom through the call path to where the invariant
first breaks.

**8. State the root cause precisely.** A root cause is a **specific
defect at a specific location**, not a category.

> "Race condition in the exporter" is a category.
> "`flush()` reads `buf.len` after releasing `buf.lock` at
> `exporter.c:214`, so a concurrent `append()` can grow the buffer
> between the read and the copy" is a root cause.

Where the evidence does not support that specificity, **say so**:
state the hypothesis, what is missing to confirm it, and the next
diagnostic step. A stated hypothesis with its confidence is honest and
useful; a confident-sounding guess is neither, and it sends whoever
implements the fix down the wrong path with false certainty.

**9. Write the RCA** to `{design_doc_path}/{issue}-rca.md`, with
frontmatter carrying `issue`, `repo`, `title`, `analyzed`, and
`confidence` (`confirmed` | `probable` | `hypothesis`), then:

- **Bug Summary** — what breaks, for whom, under what conditions.
- **Environment** — version, configuration, platform, and the
  **evidence source**, so a reader knows whether this rests on a bundle
  or on prose.
- **Symptom** — the classification, what was observed, what was
  expected.
- **Prior Investigation** — what was already tried, credited. "None
  recorded" if none.
- **Root Cause** — the confidence, the specific defect, a **Code Path**
  with file and line references, and the **Trigger Condition** (exactly
  what must be true for it to fire, which is what explains why it is
  intermittent or conditional).
- **Proposed Fix** — a file/change table, a risk assessment naming the
  build targets touched and whether a public interface changes, and any
  dependencies.
- **Test Plan** — numbered cases with what each verifies. **The first
  case must fail against the current code.** A fix without a test that
  would have caught it is a fix that will regress.

**10. Commit and post.**

```bash
git add "{design_doc_path}/{issue}-rca.md"
git commit -m "#{issue}: Add root-cause analysis"
git push
```

Committing on the default branch is acceptable — an RCA is
documentation, not a code change. Where the default branch is
protected, commit on `bug/{issue}-{slug}` instead and say so.

Post via `References/artifact-resolution.md` § Upload Procedure,
sentinel `## dev-lifecycle-rca`, and verify it landed per that section.

**11. Label the bug** `status:in-progress` — analysis is work underway
on it.

**12. Report** the classification, scope, root cause with its
confidence, proposed fix, risk, and the RCA permalink. Next is
`bug-fix`, or a human review of the RCA first.

## Outputs

- A committed `docs/design/{issue}-rca.md`.
- A `## dev-lifecycle-rca` sentinel comment on the bug.
- The bug moved to In Progress.

## State Transitions

Bug: Open → In Progress (step 11). Nothing else.

## Errors

- **Not a bug:** hard stop with routing.
- **No description:** hard stop.
- **Crash with no trace:** hard stop, with the command to produce one.
- **Attachment download fails:** note it and continue with what is
  available — and record in the RCA's Environment table which evidence
  was unavailable. An analysis resting on partial evidence should say
  so.
- **Root cause not determinable:** produce the RCA anyway with
  `confidence: hypothesis`, state what is missing, and name the next
  diagnostic step. **Do not invent a confident root cause.**
- **Not reproducible and no trace:** report what the evidence supports
  and what would be needed. Suggest adding diagnostics rather than
  guessing at a fix.
- **Standard `gh` failures:** `References/gh-error-handling.md`.

## Scope

This Skill is deliberately **self-contained** and does not reach into
any other agent in this catalog — an agent is a self-contained
directory (`ARCHITECTURE.md` § The Central Design Decision), and a path
into a sibling would dangle for anyone who installed `dev-lifecycle`
alone.

Where a bug needs more structure than the classification table above —
a genuine multi-cause incident rather than a single defect — the
catalog's `RootCauseAnalysis` agent carries the formal methods (Five
Whys, Fishbone, Fault Tree, Kepner-Tregoe) and a blameless postmortem
Workflow. It is a separate agent, installed separately; use it
alongside this Skill rather than expecting this one to reach it.
