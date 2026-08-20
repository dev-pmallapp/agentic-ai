---
pass: 1
title: Repository scaffold
status: accepted
created: 2026-08-20
---

# Design: Repository scaffold

Format precedent: `gh-workflow/docs/design/1-design.md`. This note is
deliberately much shorter — it documents a scaffolding decision, not a
feature.

## Why this structure

An agent is a directory containing its own workflows, because the
directory is what gets copied between installation tiers. If workflows
lived in a shared top-level tree, installing one agent into a project
would mean resolving a dependency graph to work out which workflow
files to bring along. Bundling makes the copy a `copytree` of one path.

The anatomy — a top-level file with persona and routing, procedures in
a subdirectory, contracts in `references/` — is LifeOS's skill anatomy,
which already works over roughly fifty skills. Renaming it (`AGENT.md`,
lowercase `workflows/`) is stylistic: it keeps an open editor buffer
unambiguous about which project it belongs to.

## Why Python

The tooling is a file-copier and a markdown-frontmatter reader. Python
has both in its standard library, is present on every machine this will
run on, and does not require a Node toolchain on a repo whose content
is otherwise pure markdown. The installer pattern is borrowed from
LifeOS's `DeployComponents.ts` — never overwrite, skip what exists —
but reimplemented rather than transliterated.

`click` is the single runtime dependency, for argument parsing only.

## Why three tiers

The three correspond to three real scopes that already exist in
practice: everything you have, the subset a group of related repos
uses, and the few things one repo actually needs. A project tier that
starts empty and grows by copying down keeps a repo's checked-in
surface honest — what is there is what was used.

Resolution order copies `git config`'s cascade on purpose. This is not
a place to be inventive; matching a mechanism everyone already
understands costs nothing and removes a category of surprise.

## Why only two example agents

The purpose of this pass is to show what goes where. One fully shaped
agent (`stock-screening`, with two workflows and empty `references/`
and `tools/`) demonstrates the anatomy; one bare placeholder
(`dev-lifecycle`) demonstrates a reservation without content. A
directory per anticipated future agent would be a guess about a
catalog that will actually be driven by the LifeOS port, and empty
guesses are harder to delete than to add.

## Deliberately deferred

Harness adapters are described but not built — all four at equal
depth, so no harness accidentally becomes the reference implementation
the others get compared against. Agent workflows are TODO outlines; no
market-data source is chosen. See ARCHITECTURE.md's closing section
for the full list.
