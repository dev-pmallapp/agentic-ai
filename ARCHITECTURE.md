# Architecture

`ai-agents` is a catalog of markdown instruction files plus a small
Python CLI that moves them around. There is no runtime and no execution
engine of its own — the execution engine is whichever coding harness
reads the markdown.

That shapes everything below. The units are directories, the interface
between a directory and a harness is a generated pointer file, and the
CLI's entire job is copying and pointing.

## Layers

```
┌──────────────────────────────────────────────────────────┐
│ README / ARCHITECTURE / CONTRIBUTING                     │
│                    what this is, how it is shaped, how   │
│                    to add to it                          │
├──────────────────────────────────────────────────────────┤
│ agents/<name>/     the unit of distribution.             │
│   AGENT.md           persona + routing table             │
│   workflows/*.md     the actual procedures               │
│   references/*.md    shared contracts, loaded on demand  │
│   tools/*            scripts an agent shells out to      │
├──────────────────────────────────────────────────────────┤
│ harness-adapters/  one dir per harness. How that harness │
│                    discovers instructions, and what its  │
│                    pointer files will look like          │
├──────────────────────────────────────────────────────────┤
│ src/ai_agents/     the CLI. catalog (read), tiers        │
│                    (resolve), install (copy), cli (wire) │
├──────────────────────────────────────────────────────────┤
│ docs/design/       numbered design notes, one per pass   │
└──────────────────────────────────────────────────────────┘
```

## The Central Design Decision

**An agent is a self-contained directory. The CLI only copies it
between tiers and writes thin pointer files.**

Everything inside `agents/<name>/` is harness-neutral markdown. It says
nothing about Claude Code, Cline, Gemini CLI, or Qwen Code. The four
harnesses differ in *how they discover instructions* — not in what good
instructions say — so that difference is pushed entirely to the edge,
into per-harness pointer files that name an agent and give the path to
its `AGENT.md`.

The alternative — writing agent content into each harness's native
format — would mean four copies of every agent, drifting apart from the
first edit onward, and a new harness would be a full re-port rather
than one new adapter. Instead:

| Concern | Lives in |
|---|---|
| What an agent does | `agents/<name>/AGENT.md` and `workflows/*.md`, once |
| How a harness finds it | `harness-adapters/<harness>/`, one pointer generator |
| Which copy a project uses | `src/ai_agents/tiers.py`, one resolution order |

A pointer file is never a copy of an agent's content. That rule is what
keeps "one authoritative copy per tier" true.

## Multi-level Install

Three tiers, each a directory containing an `agents/` subdirectory.

| Tier | Physical location | Contents |
|---|---|---|
| **User (master)** | `~/.ai-agents/agents/` | The full catalog. Populated by `ai-agents init`. Source of truth. |
| **Workspace** | `<ancestor>/.ai-agents/agents/` | A curated subset for a folder holding several related project repos. Optional — most setups have none. |
| **Project** | `<repo-root>/.ai-agents/agents/` | Only what the repo actually uses. Starts empty; grows via `ai-agents install <agent> --project`. |

**Workspace discovery.** The nearest ancestor directory above a project
that contains an `.ai-agents/` folder, stopping before `$HOME`. The stop
is load-bearing: `$HOME` is the user tier's own directory, and treating
it as a workspace would silently make every repo on the machine share
one accidental workspace.

**Project discovery.** The nearest ancestor containing `.git`. The
`.ai-agents/` path is computed whether or not it exists yet, so
`install --project` has somewhere to create on a repo that has never
installed anything.

**Resolution order: project → workspace → user master.** Closest wins;
an agent missing from a tier falls back upward. A project can pin its
own edited copy of one agent while everything else it uses resolves to
the master.

This is deliberately the same cascade as `git config` (local → global →
system) and as Claude Code's own settings layering (project `.claude/`
→ user `~/.claude/`). The shape is not novel and is not trying to be —
it is chosen precisely because anyone who has overridden a git setting
already knows how this behaves.

Copies never overwrite. An agent already present at a destination may
have been edited on purpose; refreshing it means removing it first.
This mirrors LifeOS's `copyMissing` semantics, narrowed to one named
agent directory rather than a whole tree.

## Where Content Comes From

**LifeOS first; gh-workflow only where LifeOS doesn't suffice.**

Most future agents here will be ported from LifeOS's skill catalog
(`/home/pmallapp/tmp/LifeOS/LifeOS/install/skills/`, roughly fifty
skills). That catalog is the primary source, and the agent anatomy in
this repo is deliberately LifeOS's skill anatomy: one directory, a
top-level file carrying persona and a routing table, procedures in
subdirectory markdown files, shared contracts in a references
directory.

The vocabulary is renamed — `AGENT.md` rather than `SKILL.md`,
lowercase `workflows/` / `references/` / `tools/` rather than LifeOS's
capitalized `Workflows/` / `References/`. This is a stylistic choice,
not a technical one: it keeps a file open in an editor unambiguous
about which project it belongs to, and it keeps a future port honest
about being a port rather than a copy.

The one domain LifeOS has no equivalent for is a GitHub-native
issue/PR-driven development lifecycle. For that, and only that, the
Forge plugin at `/home/pmallapp/tmp/gh-workflow` is the reference —
specifically its agent split (`forge-planner` / `forge-coder` /
`forge-validator`) over a milestone → story → task → PR hierarchy.
`agents/dev-lifecycle/` is a placeholder marking that reservation.
Nothing has been ported; Forge is untouched and stays an independent
repo. A real port is future work.

## Layout

```
ai-agents/
  README.md
  ARCHITECTURE.md
  CONTRIBUTING.md
  .claude-plugin/plugin.json      Claude Code plugin manifest
  docs/design/1-scaffold.md       design note for this pass
  agents/
    stock-screening/
      AGENT.md
      workflows/swing-trading.md
      workflows/day-trading-shortlist.md
      references/                 (empty)
      tools/                      (empty)
    dev-lifecycle/
      AGENT.md                    placeholder only
  harness-adapters/
    claude-code/README.md
    cline/README.md
    gemini-cli/README.md
    qwen-code/README.md
  src/ai_agents/
    __init__.py  catalog.py  tiers.py  install.py  cli.py
  tests/
    test_catalog.py  test_tiers.py
  pyproject.toml
```

## What This Scaffold Does NOT Do Yet

Stated plainly so the scope is not overread:

- **No harness adapter is wired.** All four `harness-adapters/*/README.md`
  describe a contract; none generates anything.
  `install.generate_harness_adapters` raises `NotImplementedError`.
- **No agent workflow is authored.** Both `stock-screening` workflows
  are `## TODO` outlines naming what a real implementation needs. They
  contain no screening logic.
- **No market-data integration exists.** No API, no MCP server, no
  dataset, and no decision about which to use.
- **Nothing is ported from LifeOS or Forge.** `agents/dev-lifecycle/`
  is a one-file reservation.
- **`ai-agents doctor` is a stub** that prints its planned checks.

What does work: `catalog.list_agents`, `tiers.resolve`,
`install.copy_agent`, and the `list` / `init` / `install` CLI commands
over them.
