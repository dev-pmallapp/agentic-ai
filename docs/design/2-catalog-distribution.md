---
pass: 2
title: How the catalog reaches an installed user
status: accepted
created: 2026-08-21
---

# Design: How the catalog reaches an installed user

Story #42, task #45. Records the ship-vs-fetch decision that issue asked
to be made and written down, and what it costs.

## The problem

`ai-agents` is a CLI whose entire job is copying an agent catalog
between tiers. Until now the only install path was `pip install -e .`
from a checkout, and `init` found the catalog by walking up from
`__file__` for a directory holding both `agents/` and `pyproject.toml`.
That resolves for an editable install of a clone and for nothing else.
On a published wheel there was no bundled `agents/` tree at all, so the
walk fell through to `Path.cwd()` — meaning `init` would silently seed
from whatever directory the user happened to be standing in, or fail
naming a path the user never mentioned.

So a user who has not cloned the repo cannot install the tool and get
the catalog. Two ways to fix that, and they are mutually exclusive.

## The decision

**The catalog ships as package data inside the wheel.**

`agents/` is force-included at build time and lands as
`ai_agents/_catalog/`; `cli._catalog_source()` reads it. A plain
`ai-agents init` on a `pipx`/`uv` install now works with no checkout, no
network, and no git.

## Why, against the alternative

The alternative was fetching the catalog at `init` time from GitHub.
Three things decided it:

**Version-locking is a correctness property here, not a nicety.**
`catalog.py` parses `AGENT.md` frontmatter with a hand-rolled YAML
subset — deliberately, to keep the runtime dependency list to `click`
alone. That parser and the catalog it reads are a matched pair. A
fetched catalog could move ahead of the installed parser and break
`ai-agents list` on a machine where nothing was upgraded. Shipping them
together makes that failure impossible by construction rather than by
discipline.

**Size does not argue for fetching.** The catalog is ~576 KB of
markdown across 38 files. The wheel is small either way, so the usual
reason to keep content out of a distribution does not apply.

**Offline and reproducible beats updatable.** `init` is a
first-five-minutes command. Making it depend on network reachability,
GitHub availability, and eventually some form of auth for a private
catalog trades a guarantee for a convenience. Fetching also needs
infrastructure this project does not otherwise have: a hosting location,
a cache, an integrity check, and a story for what happens when the fetch
half-fails.

## What it costs

**A catalog edit requires a release to reach users.** This is the real
price, and it is accepted. It also means a content change *is* a
release — which is why the release process (#48, `CONTRIBUTING.md`)
states the catalog-content-versus-package-version relationship
explicitly rather than leaving it to be inferred.

**Users can still get ahead of a release.** `--source` seeds from any
checkout, and the three-tier layout means a locally edited agent at the
project or workspace tier already wins over the master copy. So the
escape hatch for "I need a newer agent now" exists and does not run
through packaging at all.

## Resolution order, and the removed fallback

`_catalog_source()` looks in two places, in order:

1. `ai_agents/_catalog/` — the bundled catalog. Present on every
   non-editable install.
2. A checkout of this repo above `__file__` — the developer path. An
   editable install points at `src/` in the working tree, where the
   build-time force-include has not run, so nothing is bundled.

Bundled wins, so a developer who also has the package installed gets a
predictable answer rather than one depending on how the interpreter
resolved `ai_agents`.

If neither resolves, `init` **raises**. The old `Path.cwd()` fallback is
gone: seeding from an unrelated directory that happens to contain
`agents/` is a worse outcome than a clear error naming both places that
were checked and the `--source` flag that overrides them.
