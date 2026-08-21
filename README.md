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

## Install

**The catalog ships inside the package.** `init` copies from the installed
package, not from a checkout — so it needs no clone, no network, and no
git, and the agents you get are exactly the ones the installed version's
parser was written to read. The trade is that a catalog edit reaches you in
a release rather than the moment it lands on `main`; see
[`docs/design/2-catalog-distribution.md`](docs/design/2-catalog-distribution.md)
for why that trade was taken, and `--source` below for the way around it.

```bash
pipx install ai-agents          # or: uv tool install ai-agents
```

> **Not on PyPI yet** — the first release is tracked by #44. Until it
> lands, install straight from the repo, which still needs no checkout:
>
> ```bash
> pipx install git+https://github.com/dev-pmallapp/agentic-ai
> ```

### Developer install

Only if you are working *on* this repo rather than using it:

```bash
git clone https://github.com/dev-pmallapp/agentic-ai
cd agentic-ai
pip install -e .
```

An editable install has no bundled catalog — the build step that embeds it
never runs — so `init` falls back to the `agents/` tree in your checkout.
That is deliberate: edit an agent, and `init` picks it up with no rebuild.
`ai-agents init --source /path/to/checkout` seeds from a named checkout
instead, which is also how you get a catalog newer than your installed
version without waiting for a release.

---

## Quick start

```bash
ai-agents init                          # seed ~/.ai-agents from the installed catalog
ai-agents list                          # what's in the master catalog

cd ~/code/some-repo
ai-agents install stock-screening --project

ai-agents diff stock-screening --project      # what would change on update?
ai-agents update stock-screening --project    # refresh from the master copy
ai-agents remove stock-screening --project    # drop it, and its pointers

ai-agents doctor                              # harnesses, tiers, drift — all at once
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
| `ai-agents update NAME [--project\|--workspace] [--force]` | Refreshes the installed copy from the master (delete, then recopy). | Refuses if the installed copy holds local edits, unless `--force` is given — those edits may have been made on purpose. Picking up what the master has added since install needs no flag. |
| `ai-agents remove NAME [--project\|--workspace]` | Deletes the agent directory from the tier, and the harness pointer files `install` generated for it. | Deletes. A pointer a person hand-authored (no `ai-agents`-generated marker in it) is left alone rather than deleted, even if it occupies the exact path a pointer would use. |

**What counts as drift, and what blocks an update.** Every file under the
installed agent directory and its master counterpart is compared
byte-for-byte by its relative path; mtimes and permissions are never
consulted. `diff` reports all of it, in both directions — that is what a
report is for. `update` asks a narrower question, and only two of the
three kinds answer it:

| Kind | `diff` shows it | Blocks `update`? |
|---|---|---|
| Changed on both sides | yes | **Yes.** Without a baseline recorded at install time there is no way to tell your edit from an upstream one, and guessing wrong destroys work. |
| Local-only (here, not in the master) | yes | **Yes.** A file that exists only here was almost certainly added here. |
| Master-only (in the master, not here) | yes | No. This is the master moving forward, not your copy being edited — picking it up is the ordinary case. |

If master-only additions blocked an update, every routine "pick up the
latest" would need `--force`, and a flag every ordinary command requires
is a flag nobody reads — leaving the genuinely destructive case
unguarded. The accepted cost: a file you deliberately deleted from your
copy is indistinguishable from one the master has since added, so an
update restores it. `diff` still lists it under master-only first.

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

## Checking the environment

`ai-agents doctor` walks all three tiers at once — read-only, like `diff` —
and reports:

- which of the four harnesses are detected at each tier, naming the exact
  path(s) probed to reach that answer;
- each tier's root, whether it exists, and how many agents it holds;
- any installed agent that has diverged from the user master copy (the
  same comparison `diff` makes);
- anything genuinely broken — an agent directory with no `AGENT.md`, or a
  generated harness pointer whose agent directory is gone — each with a
  concrete fix command.

An absent harness, an empty tier, or a project/workspace tier that simply
doesn't exist here are normal conditions, not defects — they're reported
(`--`) but never counted as problems. A diverged copy is a warning
(`warn`): `install.py`'s own rule is that a copy already installed may
have been edited on purpose, so drift is not automatically wrong. The
exit code is non-zero only when something is reported as broken (`FAIL`).

---

## Layout

| Path | Holds |
|---|---|
| `agents/<Name>/AGENT.md` | Persona and a routing table over the agent's skills and workflows |
| `agents/<Name>/Skills/*.md` | Atomic procedures, each individually invocable |
| `agents/<Name>/Workflows/*.md` | Cumulative procedures that compose Skills and own the gates between them |
| `agents/<Name>/References/`, `Tools/` | Shared contracts; scripts the agent shells out to |
| `harness-adapters/<harness>/` | How one harness discovers instructions, and what its pointer files will look like |
| `src/ai_agents/` | The CLI — catalog, tier resolution, copying |
| `docs/design/` | Numbered design notes, one per pass |

Four harnesses are targeted: Claude Code, Cline, Gemini CLI, Qwen Code.

---

## Status

Working, pre-release. The CLI does what it says — `list`, `init`,
`install`, `diff`, `update`, `remove`, `doctor` — and generates pointer
files for all four harnesses. Six agents are authored: four ported from
LifeOS, the Forge development lifecycle, and `stock-screening`.

Known limits:

- `stock-screening` covers **Indian equities only** (NSE and BSE) and is
  **end-of-day only** — there is no live or intraday path, so the
  day-trading screen reviews a completed session for a named date.
- Not published to a package index yet, so the `pipx install ai-agents`
  above does not resolve until the first release (#44). Installing from
  the repo URL works today and takes the same bundled catalog.

See `ARCHITECTURE.md` for the design and the full list of what this does
not do yet, and `CONTRIBUTING.md` for how to add an agent.
