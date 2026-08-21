<!--
  Shape for an individual test case document.

  One file per case, where a project keeps test cases as documents.
  The plan-level view is `Templates/test-plan.md`; this is the
  expansion of a single row of it. `task-test-plan` and `story-test`
  read the frontmatter mechanically — `pass_criteria`, `timeout`, and
  `stability` in particular — so keep the keys even where a value is
  obvious from the body.
-->
---
topology: <single-node | back-to-back | switched>
timeout: <max execution time in seconds>
pass_criteria: "<what success looks like, one line>"
stability: <stable | flaky>
retries: <0-3, default 0>
flaky_issue: "<#N, required when stability: flaky>"
validation_groups: [post-test]
---

# <Test Case Title>

## Purpose

<One sentence: what this test validates and why it matters.>

## Category

<one or more of: positive, negative, boundary, scale, performance,
stress, error-recovery, concurrency, upgrade-downgrade, integration,
security, fault-injection, config-matrix>

Supplementary tokens when applicable: `interoperability`,
`data-integrity`, `compliance`.

These names match the `### <Category>` headings in
`Templates/test-plan.md`, lowercased and hyphenated. Keep them
aligned — a case whose category has no corresponding plan section is
either a missing plan row or a typo, and both are worth catching.

## Prerequisites

- <condition that must be true before this test runs>
- <e.g. "service running", "two hosts with link up">

## Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| <name> | <default> | <min-max> | <what it controls> |

(Omit this section when the test case has no configurable parameters.)

## Steps

1. **[host]** <command or action>
   Expected: <what should happen>
2. **[host]** <command or action>
   Expected: <what should happen>
3. **[host]** <verification step>
   Expected: <pass criteria>

(Use **[host]** for single-node tests, **[server]** / **[client]** for
multi-host, **[switch]** for switched topology. The tag must match the
`topology` in the frontmatter.)

## Expected Result

<Detailed description of success, including specific output patterns,
values, or behaviours to verify.>

This section is the long form of the frontmatter's `pass_criteria`,
not a second opinion. Where they disagree, `pass_criteria` is what
gets read mechanically — fix the frontmatter rather than relying on a
reader to prefer the prose.

## Failure Indicators

- <symptom that indicates failure>
- <e.g. "connection refused", "throughput below target">
- <e.g. "core dump generated", "non-zero error counters">

## Cleanup

- <cleanup action>
- <cleanup action>
