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

ai-agents diff stock-screening --project      # what would change on update?
ai-agents update stock-screening --project    # refresh from the master copy
ai-agents remove stock-screening --project    # drop it, and its pointers
```

`init` and `install` never overwrite. An agent already present is left
alone — refreshing means removing it first, which is exactly what `update`
does for you, with a safety check `install` doesn't need.

---

## Maintaining an installed agent

`install` is intentionally one-shot: copy when absent, never touch when
present. Once an agent is installed, three more commands manage it —
`update`, `diff`, and `remove` — each taking the same `--project` (default)
/ `--workspace` flag `install` does, and each always comparing against (or
refreshing from) the user master tier, the same source `install` copies
from.

| Command | Does | Mutates? |
|---|---|---|
| `ai-agents diff NAME [--project\|--workspace]` | Reports drift between the installed copy and the master: files changed, missing locally, or added locally. | Never. Read-only, always — safe to run before every `update`. |
| `ai-agents update NAME [--project\|--workspace] [--force]` | Refreshes the installed copy from the master (delete, then recopy). | Refuses if the installed copy has diverged from the master, unless `--force` is given — a diverged copy may hold edits made on purpose. |
| `ai-agents remove NAME [--project\|--workspace]` | Deletes the agent directory from the tier, and the harness pointer files `install` generated for it. | Deletes. A pointer a person hand-authored (no `ai-agents`-generated marker in it) is left alone rather than deleted, even if it occupies the exact path a pointer would use. |

**What counts as "diverged".** Every file under the installed agent
directory and its master counterpart is compared byte-for-byte by its
relative path — a file only one side has, or a file both sides have with
different content, both count. mtimes and permissions are never
consulted. This is a strict, symmetric definition on purpose: it is what
lets `update` refuse to silently delete a locally-added file, or silently
resurrect a locally-deleted one, not only to protect a file both sides
already share.

**What happens to a harness's shared context file on removal.** Claude
Code and Cline get one pointer file per agent, so removing an agent just
deletes its file outright (when `ai-agents` generated it). Gemini CLI and
Qwen Code instead share one managed block across every agent installed at
a tier — `GEMINI.md` / `QWEN.md` — so removing one agent re-renders that
block from whichever agents are left. When the removed agent was the last
one at that tier, the block is deleted in full (not left standing as an
empty "## AI Agents" heading with nothing under it), and if the file held
nothing but that block, the file itself is deleted too — a tier with
nothing installed looks the same whether or not it ever had anything
installed. Hand-written text elsewhere in the file is always left alone.

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
