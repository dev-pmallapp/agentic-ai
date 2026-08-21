<!--
  Shape for the design doc `story-design` writes, at the
  `design_doc_path` resolved by `context-discovery`.

  This template is the document's *shape*. The rules for filling it —
  which build targets to select, how code paths relate to them, how
  many approval rounds each section gets — live in
  `Skills/story-design.md` and are not repeated here. When the two
  disagree, the Skill wins: it is the procedure, this is the form.
-->
---
issue: {ISSUE}
repo: {OWNER}/{REPO}
story_title: >-
  {STORY_TITLE}
milestone: {MILESTONE_TITLE}
author: {AUTHOR}
status: draft
created: {DATE}
---

# Design: #{ISSUE} — {STORY_TITLE}

## Problem Statement

{Describe the problem this Story solves. Reference the milestone
context.}

## Solution Overview

{High-level approach. 2-3 paragraphs covering architecture decisions,
key trade-offs, and rationale.}

## Build Targets

<!--
  FIXED SHAPE — `task-create` reads this table to decide how many task
  sub-issues to create: one per row.

  Sourced from ARCHITECTURE.md's `## Build Targets`, narrowed to the
  targets this Story changes. Do not re-discover targets from the
  filesystem when that table exists — disagreement between the two
  produces wrong tasks later.

  Note the columns are narrower than ARCHITECTURE.md's: no source
  dirs, because the authoritative table already carries them and this
  one is a selection from it, not a second copy.
-->

| Build Target | Type | Build File |
|-------------|------|------------|
| {target_name} | library | {path/to/build-file} |
| {target_name} | binary | {path/to/build-file} |

## Code Path Design

<!-- Code paths are logical/functional sections of the design.
     They are NOT the unit of task creation — build targets are.
     Multiple code paths may belong to the same build target; a shared
     header with no owning target goes under the consuming target. -->

### Code Path: {code-path-1-name}

**Build target:** {target_name from the Build Targets table}

**Responsibility:** {What this code path does}

**Interfaces:**
- {API/CLI/data structure 1}
- {API/CLI/data structure 2}

**Dependencies:** {Other targets or external systems}

**Implementation Notes:**
{Key algorithms, data flows, design patterns, files to create/modify}

**Error Handling:**
{Failure modes, recovery strategies, error codes}

### Code Path: {code-path-2-name}

{Same structure as above}

## Cross-Target Interfaces

{How build targets communicate. Data formats, protocols, shared
state.}

## Testing Strategy

<!-- Categories here are the seed for the test plan `story-test-plan`
     generates. The full category list and what each one means is in
     that Skill; this table is the design-time sketch, not the plan. -->

| Category | What to Test |
|----------|-------------|
| Functional | {Happy path scenarios} |
| Negative | {Error conditions, edge cases} |
| Scale | {Load, concurrency} |
| Performance | {Latency, throughput targets} |

## Open Questions

- {Unresolved design decision 1}
- {Unresolved design decision 2}
