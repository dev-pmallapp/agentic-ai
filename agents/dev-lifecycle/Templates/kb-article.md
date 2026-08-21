---
# KB article template — written by the `enhance-debugger` Skill.
#
# One file per extracted learning. The frontmatter is what makes an
# article findable six months later; the body is what makes it
# useful. Fill both.
#
# The confidence rules and what counts as a learning worth keeping are
# in `Skills/enhance-debugger.md`; this file is the shape.

entry_type: issue          # issue | solution | command | fact
subsystem: {subsystem}     # the build target or component area
title: "{one line — the symptom, not the cause}"
severity: medium           # critical | high | medium | low | info
confidence: high           # high | medium | low — see below
category:
  - {tag}
symptoms:
  # What someone actually observes. Verbatim where possible.
  - "{observable symptom}"
error_patterns:
  # Exact strings. These are what a future search matches on —
  # paraphrasing destroys their value.
  - "{exact error text}"
solutions:
  - "{what fixed it}"
related_commands:
  # Commands that diagnose or confirm this. The highest-value field.
  - "{command}"
source_type: github
source_repo: "{owner}/{repo}"
source_refs:
  # Every claim cites its origin, so it can be verified later.
  - "#{issue}"
  - "{commit_sha}"
  - "PR #{pr}"
milestone: "{milestone title}"
extracted: {DATE}
tags:
  - {tag}
---

## Symptom

{What is observed, concretely. The error message, the failing test,
the wrong output. Write it so someone searching the symptom finds
this — use their words, not the diagnosis.}

## What It Actually Means

{The real cause. This is the value of the article: the gap between
what it looks like and what it is.}

## How to Confirm

{The specific check that distinguishes this from things that look the
same. A command, a log line, a state to inspect.}

```
{command}
```

Expected when this is the cause: {what you see}

## Fix

{What resolves it. Concrete steps or a code change.}

```
{command or diff}
```

## Why It Happens

{The mechanism, if known. Skip this section rather than speculate —
a wrong mechanism is worse than none, because it sends the next
person down the wrong path.}

## Confidence

{high} — {root-caused, fixed, and verified by a test}
{medium} — {consistent evidence, no definitive confirmation}
{low} — {observed once; recorded as a hypothesis to confirm later}

Keep this in step with the frontmatter's `confidence`. An RCA marked
as a hypothesis maps to **low**, however well-written it reads.

## Source

Found during {milestone title}, {date}.

- {#issue} — {what happened there}
- {commit or PR} — {the fix}
