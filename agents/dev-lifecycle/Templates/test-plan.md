<!--
  Shape for the test plan `story-test-plan` writes.

  This template is the document's *shape*. The rules for filling it —
  what each category means, how the three routinely-collapsed
  distinctions differ, which categories may legitimately be empty, and
  the global-numbering and priority rules — live in
  `Skills/story-test-plan.md` and are not repeated here. Read that
  Skill before generating cases; this file only says where they go.
-->
---
issue: {ISSUE}
repo: {OWNER}/{REPO}
story_title: >-
  {STORY_TITLE}
milestone: {MILESTONE_TITLE}
design_doc: {PERMALINK_TO_DESIGN_DOC}
created: {DATE}
---

# Test Plan: #{ISSUE} — {STORY_TITLE}

## Source

| Field | Value |
|-------|-------|
| Story | #{ISSUE} |
| Milestone | {MILESTONE_TITLE} |
| Design doc | {PERMALINK} |
| Build | {build identifier, if applicable} |
| Testbed | {testbed identifier, if applicable} |
| Date | {DATE} |

## Feature Summary

{One paragraph, from the design doc's Solution Overview.}

## Handoff Checklist

- [ ] Feature spec reviewed against the design doc
- [ ] CLIs / APIs documented in the design doc's Interfaces sections
- [ ] Test environment requirements identified
- [ ] Every build target has at least one test case

## Test Cases

<!-- FIXED SHAPE — one `### <Category>` heading per category, each
     followed by a table with the columns `#`, `Test Case`,
     `Description`, `Priority`.

     Numbering is global and sequential across all categories — 1, 2,
     3… continuing across category boundaries, NOT restarting per
     category. `story-test` matches its results rows to these numbers,
     so a restart makes two rows claim the same case.

     Priority: P0 (must pass), P1 (should), P2 (nice).

     A category with no applicable cases keeps its heading and says
     why it is empty. Deleting the heading is indistinguishable from
     forgetting the category. -->

### Positive

| # | Test Case | Description | Priority |
|---|-----------|-------------|----------|
| 1 | {name} | {what it verifies} | P0 |

### Negative

| # | Test Case | Description | Priority |
|---|-----------|-------------|----------|
| 2 | {name} | {invalid input → expected rejection} | P1 |

### Boundary

| # | Test Case | Description | Priority |
|---|-----------|-------------|----------|
| 3 | {name} | {min/max/empty/off-by-one} | P1 |

### Error Recovery

| # | Test Case | Description | Priority |
|---|-----------|-------------|----------|
| 4 | {name} | {failure → system returns to a usable state} | P1 |

### Concurrency

| # | Test Case | Description | Priority |
|---|-----------|-------------|----------|
| 5 | {name} | {parallel access, races, shared state} | P1 |

### Integration

| # | Test Case | Description | Priority |
|---|-----------|-------------|----------|
| 6 | {name} | {cross-target interaction} | P1 |

### Upgrade / Downgrade

| # | Test Case | Description | Priority |
|---|-----------|-------------|----------|
| 7 | {name} | {behaviour across version boundaries} | P1 |

### Scale

| # | Test Case | Description | Priority |
|---|-----------|-------------|----------|
| 8 | {name} | {load, resource limits} | P2 |

### Performance

| # | Test Case | Description | Priority |
|---|-----------|-------------|----------|
| 9 | {name} | {latency, throughput targets} | P1 |

### Loop / Stability

| # | Test Case | Description | Priority |
|---|-----------|-------------|----------|
| 10 | {name} | {long-running, repeated operation} | P2 |

## Results

<!-- Filled in by `story-test` into a separate results file under the
     test-results path, NOT here. This table stays empty in the plan
     itself — the plan is the plan, not the record. A plan carrying
     results cannot be re-run without editing it, which is why the two
     are kept in different files. -->

| # | Category | Test Case | Result | Notes |
|---|----------|-----------|--------|-------|
| 1 | Positive | {name} | | |

## Verdict

{PASS / FAIL / PARTIAL / TESTS_SKIPPED} — {summary}
