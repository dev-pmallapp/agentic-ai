# Sizing Criteria

Relative sizing in four T-shirt sizes: **S**, **M**, **L**, **XL**,
computed across three dimensions — design, coding, and test effort —
then aggregated. **No time estimates**, deliberately: a size is a
comparison between pieces of work, and attaching hours to it invites
the number to be read as a commitment.

Used by the `size` Skill, and by `planner`, which sizes each Story
while its design is fresh. Documented here for team calibration
regardless of whether either is run.

## Task-Level Sizing (per build target)

Each task maps to one build target. The five signals come from the
design doc (`### Code Path:` sections for that target) and are
validated against the codebase when source files are accessible.

| Size | Code Paths | New Files | Modify Files | Interfaces | Dependencies |
|---|---|---|---|---|---|
| S | 1 | 0-1 | 0-2 | 0-2 | 0-1 |
| M | 2-3 | 1-3 | 2-5 | 3-5 | 2-3 |
| L | 4-6 | 3-6 | 5-10 | 6-8 | 4-5 |
| XL | 7+ | 6+ | 10+ | 9+ | 6+ |

### How to apply

1. Count each signal for the build target.
2. Map each signal to its row (S/M/L/XL).
3. Task size is the **median** of the five — median keeps one outlier
   from skewing the result. When two tie for the median position,
   round up.

**Example:** Code Paths = 2 (M), New Files = 0 (S), Modify Files = 3
(M), Interfaces = 2 (S), Dependencies = 1 (S) -> sorted S, S, S, M, M
-> median **S**.

### Signal definitions

| Signal | How to count |
|---|---|
| Code Paths | `### Code Path:` sections whose `**Build target:**` matches |
| New Files | Files in Implementation Notes not on disk, or described as "new" / "create" / "add" |
| Modify Files | Files in Implementation Notes that already exist on disk |
| Interfaces | Bullet items under `**Interfaces:**` across matching code paths |
| Dependencies | Items under `**Dependencies:**` across matching code paths, deduplicated |

When the codebase is not accessible, New and Modify Files are estimated
from Implementation Notes language ("add new", "modify existing",
"extend", "refactor").

## Story-Level Sizing (aggregate of tasks)

| Size | Tasks | Total est. files | Cross-target interfaces | Risk |
|---|---|---|---|---|
| S | 1 | 1-3 | 0 | Low |
| M | 2-3 | 4-10 | 1-2 | Low-Medium |
| L | 4-6 | 11-20 | 3-4 | Medium-High |
| XL | 7+ | 21+ | 5+ | High |

| Signal | How to count |
|---|---|
| Tasks | Rows in `## Build Targets`, or the existing sub-issue count |
| Total est. files | Sum of (New + Modify) across all tasks |
| Cross-target interfaces | Items in `## Cross-Target Interfaces` |
| Risk | Qualitative — see Risk Assessment |

## Dimensional Sizing (Story level)

### Design effort

| Size | Criteria |
|---|---|
| S | Well-understood patterns, no architectural decisions, no open questions |
| M | Some design decisions, moderate interface surface, clear precedents in the codebase |
| L | Significant design decisions, multiple new interfaces, limited precedents |
| XL | Novel architecture, cross-system design, no precedents, many open questions |

**Signals:** open-question count, cross-target interface count,
dependency graph depth, ratio of new to existing interfaces.

### Coding effort

| Size | Criteria |
|---|---|
| S | 1 build target, few files, mostly modifications |
| M | 2-3 build targets, moderate files, mix of new and modify |
| L | 4-6 build targets, many files, significant new code |
| XL | 7+ build targets, extensive files, mostly new code |

**Signals:** task count, total estimated files, new-to-modify ratio.

### Test effort

| Size | Criteria |
|---|---|
| S | Under 10 test cases, standard functional only |
| M | 10-25 cases, functional plus negative |
| L | 25-50 cases, functional, negative, and scale/performance |
| XL | 50+ cases, all categories plus new test infrastructure |

**Signals:** test case count from the test plan when one exists, and
the number of categories in the design doc's `## Testing Strategy`
table.

### Aggregation

1. Overall = max(design, coding, test).
2. **Two-below rule:** if the max is two levels above **both** other
   dimensions, round down one level.

| Dimensions | Max | Result |
|---|---|---|
| design=S, coding=S, test=L | L, both two below | **M** |
| design=M, coding=XL, test=M | XL, both one below | **XL** |
| design=S, coding=M, test=L | L, only one two below | **L** |

## Risk Assessment

Qualitative, not mechanical — this one resists a formula on purpose.

| Risk | Indicators |
|---|---|
| Low | Well-understood patterns, isolated changes, existing test infrastructure, no external dependencies |
| Low-Medium | Some new patterns, limited cross-target interaction, partial test coverage exists |
| Medium-High | New architectural patterns, significant cross-target interaction, new test infrastructure needed |
| High | Novel architecture, concurrent or distributed changes, no existing test patterns, external system dependencies, many open questions |

Reported per task and per Story. Epic risk is the highest Story risk.

## Epic-Level Sizing (milestone)

| Size | Stories | Designed stories | Total tasks (est.) |
|---|---|---|---|
| S | 1 | 1 | 1-3 |
| M | 2-3 | 2-3 | 4-10 |
| L | 4-6 | 3-6 | 11-25 |
| XL | 7+ | 5+ | 26+ |

Epic size is max(Story sizes) with the analogous rounding rule: if the
max is two levels above all others, round down one. Stories sized
S, S, S, L -> **M**.

## Data-Limited Estimates

Without a design doc, produce a "data-limited" estimate from GitHub
structure alone, and annotate **every** value with "(est.)". An
unmarked guess is worse than no estimate, because it gets quoted back
as though it were derived.

### Story without a design doc

1. List the Story's sub-issues.
2. If tasks exist, use the count as the task count and estimate files
   from task titles.
3. If no tasks, estimate from the issue body length:
   under 100 words -> S; 100-300 -> M; over 300 -> L.
4. Mark all dimensions "(est., no design doc)".
5. Recommend running `story-design` for accurate sizing.

### Milestone with mixed coverage

- Stories with design docs -> full sizing.
- Stories without -> data-limited.
- Show the coverage ratio: "Estimate based on 2/5 Stories with design
  docs."
- Annotate the overall: "Re-run after the remaining designs."

## Re-Sizing

Sizing runs at any stage; accuracy improves as artifacts accumulate.

| Stage | Available data | Accuracy |
|---|---|---|
| After `story-create` | Issue body only | Low (data-limited) |
| After `story-design` | Design doc with Build Targets, Code Paths | Medium-High |
| After `task-create` | Task sub-issues exist | High |
| After `task-implement` | Actual code and diffs on disk | Highest |

Estimates are preserved as separate issue comments (sentinel
`## dev-lifecycle-effort-estimate`, per
`References/artifact-resolution.md`) so the progression stays visible
rather than each estimate overwriting the last.
