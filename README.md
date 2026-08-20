# ai-agents

**A portable catalog of agents, each bundling its own workflows.**
Harness-neutral markdown plus a small Python CLI that installs it at
three levels — your machine, a workspace of related repos, or a single
project.

An agent is a directory. A workflow is a file inside it. Nothing in an
agent knows which coding harness will read it; the harnesses differ
only in how they *discover* instructions, and that difference is
handled at the edge by thin pointer files.

```
~/.ai-agents/agents/          master copy — every agent
  └─ workspace/.ai-agents/    curated subset for a group of repos
       └─ repo/.ai-agents/    only what this repo actually uses
```

Lookup runs project → workspace → user, closest wins — the same
cascade as `git config`.

---

## Quick start

```bash
pip install -e .

ai-agents init                          # seed ~/.ai-agents from this repo
ai-agents list                          # what's in the master catalog

cd ~/code/some-repo
ai-agents install stock-screening --project
```

`init` and `install` never overwrite. An agent already present is left
alone — refreshing means removing it first.

---

## Layout

| Path | Holds |
|---|---|
| `agents/<name>/AGENT.md` | Persona and a routing table to the agent's workflows |
| `agents/<name>/workflows/*.md` | The procedures themselves |
| `agents/<name>/references/`, `tools/` | Shared contracts; scripts the agent shells out to |
| `harness-adapters/<harness>/` | How one harness discovers instructions, and what its pointer files will look like |
| `src/ai_agents/` | The CLI — catalog, tier resolution, copying |
| `docs/design/` | Numbered design notes, one per pass |

Four harnesses are targeted: Claude Code, Cline, Gemini CLI, Qwen Code.

---

## Status

Scaffold. The Python package works — `list`, `init`, and `install` do
what they say. Everything else is deliberately a placeholder:

- No harness adapter generates anything yet.
- `stock-screening`'s two workflows are TODO outlines, not logic. No
  market-data source is wired.
- `dev-lifecycle` is a one-file reservation for a future port.

See `ARCHITECTURE.md` for the design and the full list of what this
scaffold does not do yet, and `CONTRIBUTING.md` for how to add an agent.
