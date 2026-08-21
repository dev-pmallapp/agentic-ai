<!--
  Scaffold written by the `init` Skill when ARCHITECTURE.md is missing.
  Placeholders in {braces} are filled from the init interview.

  Exactly one section here is read mechanically: `## Build Targets`.
  Everything else is for humans — write as much or as little as you
  like, but keep that table accurate, because it defines task
  boundaries for `task-create`.
-->

# Architecture

{One paragraph: what this system is and the shape of it. What are the
major pieces, and how does a request/event flow through them?}

## Components

{Prose or a diagram. One subsection per major component: what it owns,
what it talks to, and why it exists as a separate piece.}

### {Component}

{Responsibility. Key interfaces. Notable constraints.}

## Build Targets

<!--
  FIXED SHAPE — do not rename this heading or its columns.

  `context-discovery` finds this section by the exact heading text
  `## Build Targets` and reads the table under it by column name.
  Rename the heading, translate a column, or replace the table with
  prose or a bullet list, and discovery silently falls back to
  guessing from the filesystem. It will not warn you: a missing table
  and an unparseable one look identical from the outside.

  One row per independently buildable unit — a library, binary,
  package, or crate defined by its own build definition file.

  This is the single most important table in this document:
  `task-create` creates one task sub-issue per row that a Story
  touches.

  Granularity: NOT one row per file, NOT one row per feature. If two
  source files compile into the same library, they belong to the same
  row. See `References/build-systems.md`.
-->

| Target | Type | Build file | Source dirs |
|---|---|---|---|
| {target-name} | library | {path/to/CMakeLists.txt} | {src/thing} |
| {target-name} | binary | {path/to/go.mod} | {cmd/thing, internal/thing} |

**Type** is `library` or `binary`. **Source dirs** is comma-separated
and relative to the repo root; omit it and the build file's directory
is inferred.

A **wrong** table is worse than a missing one. Discovery falls back to
the filesystem when the table is absent, and the filesystem at least
reflects reality; a stale row is trusted and produces a task for a
target that no longer exists. Update this table in the same change
that adds or removes a build target.

## Data Model

{Key entities, their relationships, and where they are persisted.
Skip this section for stateless components.}

## Cross-Cutting Concerns

{Logging, configuration, error handling, authentication — whatever
every component has to participate in. New code is expected to follow
these.}

## Design Decisions

{Decisions a newcomer would otherwise re-litigate. One line of context
each: what was chosen, and what it was chosen over.}

| Decision | Rationale |
|---|---|
| {choice} | {why, and what was rejected} |
