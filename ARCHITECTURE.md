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
│ agents/<Name>/     the unit of distribution.             │
│   AGENT.md           persona + routing table, both kinds │
│   Skills/*.md        atomic, individually invocable      │
│   Workflows/*.md     cumulative, compose Skills          │
│   References/*.md    shared contracts, cited by both     │
│   Templates/*        shapes an agent writes into a       │
│                      user's project (optional)           │
│   Tools/*            scripts an agent shells out to      │
├──────────────────────────────────────────────────────────┤
│ <tier>/plugins/    external plugins, installed verbatim  │
│                    beside the catalog — the fallback for │
│                    pieces that cannot bend into an agent │
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

Everything inside `agents/<Name>/` is harness-neutral markdown. It says
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
| What an agent does | `agents/<Name>/AGENT.md`, `Skills/*.md`, and `Workflows/*.md`, once |
| How a harness finds it | `harness-adapters/<harness>/`, one pointer generator |
| Which copy a project uses | `src/ai_agents/tiers.py`, one resolution order |

A pointer file is never a copy of an agent's content. That rule is what
keeps "one authoritative copy per tier" true.

## Skills and Workflows

`agents/<Name>/` holds two kinds of procedure, not one.

A **Skill** (`Skills/*.md`) does one thing end to end and is
individually invocable — a harness can run it on its own, with nothing
else loaded first. A **Workflow** (`Workflows/*.md`) is cumulative: it
sequences Skills toward a larger outcome and owns any human approval
gates along the way. `References/*.md`, `Templates/*`, and `Tools/*`
are shared by both kinds; neither owns them.

**References versus Templates**, since both are markdown an agent
cites by path and the distinction is easy to lose: a **Reference** is
a contract the agent *reads* to decide what to do — the `gh` error
taxonomy, the state machine, the sizing rules. A **Template** is a
shape the agent *writes into a user's project*, or a file the user
installs into their own repository. A Reference stays inside the
catalog; a Template's whole purpose is to leave it.

That distinction is what decides where a file goes when it could
plausibly be either. `dev-lifecycle`'s `commit-msg` git hook is a
Template rather than a `Tool`, because `Tools/` is code the agent
runs and the hook is a file the user copies into `.git/hooks/`. It is
also the one place the Python-first rule does not reach: it stays
bash, because it executes on every commit in someone else's
repository and must not add an interpreter dependency that repository
did not already have.

`Templates/` is **optional** — `stock-screening` has none, and an
agent that never writes into a user's project should not have the
directory at all. Nothing in the CLI requires it: `install` copies the
whole agent directory with `shutil.copytree`, so a `Templates/` tree
ships wherever it exists with no packaging or code change, and its
absence is not a special case.

The composition rule runs one direction only: a Workflow may compose
Skills, **and may compose other Workflows**; a Skill never depends on a
Workflow. `AGENT.md`'s routing table points to both kinds directly, but
nothing under `Skills/` is allowed to assume a `Workflows/` file already
ran.

Workflow-composes-Workflow is allowed because it does not touch the
guarantee below: the inner Workflow, like a Skill, stays directly
invocable on its own. Only the *upward* dependency is forbidden.
`dev-lifecycle` uses this — `autodev` composes the `planner`, `coder`,
and `validator` role Workflows, each of which composes Skills — and it
is what lets a role run either as an isolated subagent or inline in the
main session, unchanged, on harnesses that differ in whether they have
a subagent primitive at all.

That rule buys a specific guarantee: every step of a cumulative run
stays directly invocable on its own. If a workflow stalls partway
through — a gate rejected, a harness died, a human wants to re-run one
step by hand — the Skill it was on is still callable in isolation,
because the Skill was never written to depend on the workflow's state.

This is why the split is a directory, not a naming convention. One
`workflows/` directory holding both atomic and cumulative files would
still let an author write a "skill" that quietly reaches back into a
workflow's context, and nothing would catch it. Two directories make the
dependency direction structural: a file under `Skills/` importing
something from `Workflows/` is a visible layering violation, not a lapse
in discipline.

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
top-level file carrying persona and a routing table, atomic procedures
and cumulative ones each in their own subdirectory, shared contracts in
a references directory.

Subdirectory names now match LifeOS's exactly: `Skills/`, `Workflows/`,
`References/`, `Tools/`, capitalized the way LifeOS capitalizes them.
Porting a skill is meant to be close to mechanical — copy the directory,
strip what doesn't apply, done — and a renamed vocabulary turned every
port into a rename pass on top of that. An earlier version of this repo
lowercased these names on the reasoning that it kept a file unambiguous
about which project it came from; that reasoning is superseded now that
port fidelity has turned out to matter more than at-a-glance provenance.

`AGENT.md` is the one deliberate exception — it does not become
`SKILL.md`. A container that holds a `Skills/` directory cannot itself
be called a skill without reading as a skill nested inside a skill, so
the container keeps its own name.

Two things are dropped in the port, on every agent, not case by case.
LifeOS skills open with a `curl` to a local voice daemon on port 31337;
that call is stripped, so nothing here talks to a voice notifier. And
`Tools/` here is Python; LifeOS's equivalent is TypeScript.

The one domain LifeOS has no equivalent for is a GitHub-native
issue/PR-driven development lifecycle. For that, and only that, the
Forge plugin at `/home/pmallapp/tmp/gh-workflow` is the reference —
specifically its agent split (`forge-planner` / `forge-coder` /
`forge-validator`) over a milestone → story → task → PR hierarchy.
`agents/dev-lifecycle/` holds that port: seventeen Skills, six
Workflows, ten References, and seven Templates covering project
bootstrap, requirements, design, test plans, implementation,
validation, milestone close-out, the bug track, and orchestration. Forge itself is untouched and stays an independent
repo — content moves out of it in one direction only. What the port
deliberately leaves out is recorded in
`agents/dev-lifecycle/AGENT.md`.

## External Plugins

Adopting an outside plugin runs one way: **the plugin bends to this
catalog, never the catalog to the plugin.**

Most of one does bend. Forge's references became `References/`, its
skills became `Skills/`, its orchestration became `Workflows/`, its
scaffolds became `Templates/` — and where a piece had no direct home,
the answer was still to express it in this anatomy, as the hook
contract shows: six shell scripts and a Claude-Code-specific
`hooks.json` became `References/hook-contract.md`, a document stating
what each hook guarantees independent of any mechanism.

Some pieces genuinely cannot bend. A harness-specific registration
schema, a distribution manifest, anything keyed to a harness primitive
this catalog deliberately does not model. The tempting response is to
grow a hook registry or a plugin-manifest system here so the piece has
somewhere to live — and that is precisely bending the repo to fit the
plugin. Do that a few times and the anatomy is no longer a design, it
is an accumulation of accommodations.

So the fallback is: install the leftover into a tier **in its own
native form**, beside the catalog rather than inside it.

```
.ai-agents/
  agents/            the catalog. Untouched.
  plugins/<name>/    one external plugin, verbatim.
  plugins.json       what is installed, where it came from, and why.
```

`plugins/` is a sibling of `agents/`, which is what makes the promise
mechanical instead of a matter of discipline: `catalog.list_agents`
scans `agents/`, so it cannot see a plugin even when that plugin
carries an `agents/` directory of its own. Nothing here parses, loads,
or reshapes a plugin. See `src/ai_agents/plugins.py`.

**The decision rule, in order:**

1. Port the piece into `Skills/`, `Workflows/`, `References/`, or
   `Templates/`. This is the normal outcome.
2. If it has no direct equivalent, express *what it guarantees* in
   this anatomy — `hook-contract.md` over a copied `hooks.json`.
3. Only if neither works, install it locally as an external plugin —
   **and record which pieces those were and why.**

Step 3's second half is not paperwork. Without it the fallback becomes
an excuse to skip step 1, and the catalog degrades into a thin wrapper
around foreign plugins that nobody ever finished porting. That is why
`ai-agents plugin install` takes a **required `--reason`** with no
default, refuses a blank one, and writes it into `plugins.json` where
`ai-agents doctor` prints it back. A rule that lives only in this
document depends on the reader's discipline; an argument that cannot be
omitted does not.

Installing an external plugin is therefore a visible, justified
exception — never the quiet default.

## Layout

```
ai-agents/
  README.md
  ARCHITECTURE.md
  CONTRIBUTING.md
  .claude-plugin/plugin.json      Claude Code plugin manifest
  .claude-plugin/marketplace.json  local marketplace serving this repo
  docs/design/1-scaffold.md       design note for the scaffold pass
  docs/porting-from-lifeos.md     the porting guide
  agents/
    stock-screening/
      AGENT.md
      Skills/swing-trading.md
      Skills/day-trading-shortlist.md
      Skills/fundamental-gate.md
      Workflows/morning-shortlist.md  screen, then gate, then ten
      References/                 data contracts, universe, criteria
      Tools/bhavcopy.py           NSE/BSE fetch, cache, normalise
      Tools/screen.py             criteria application and ranking
      Tools/fundamentals.py       fundamentals across four providers
    dev-lifecycle/
      AGENT.md
      Skills/                     17 Skills ported from Forge
      Workflows/                  6, incl. autodev and the 3 worker roles
      References/                 10 contracts, incl. the hook contract
      Templates/                  7 scaffolds + the commit-msg git hook
      Tools/                      (empty by design)
    BiasCheck/  ExtractWisdom/  FirstPrinciples/  RootCauseAnalysis/
      AGENT.md + Skills/          ported from LifeOS
  harness-adapters/
    claude-code/README.md
    cline/README.md
    gemini-cli/README.md
    qwen-code/README.md
  src/ai_agents/
    __init__.py  catalog.py  tiers.py  install.py  lifecycle.py
    doctor.py  plugins.py  cli.py
  tests/
    test_catalog.py  test_tiers.py  test_install.py
    test_lifecycle.py  test_doctor.py  test_plugins.py
    test_stock_screening_tools.py  test_fundamentals.py  fixtures/
  pyproject.toml
```

## Build Targets

<!--
  This repo is mostly markdown with one small Python package. The rows
  below are the logical units a change lands in — what issue-tracker
  tooling needs to draw task boundaries. Type is `docs` for the
  markdown units; unknown types are treated as `library` for sizing.
-->

| Target | Type | Build file | Source dirs |
|---|---|---|---|
| ai_agents | library | pyproject.toml | src/ai_agents |
| tests | tests | pyproject.toml | tests |
| agents | docs | — | agents |
| harness-adapters | docs | — | harness-adapters |
| project-docs | docs | — | docs, README.md, ARCHITECTURE.md, CONTRIBUTING.md |
| ci | ci | — | .github |

One build target is one task. A change to the Python package and a
change to the agent catalog are separate tasks even when they ship the
same feature; a change touching three files inside `src/ai_agents` is
one.

`ci` owns `.github/`. It is a build target rather than unattributed
infrastructure because the workflow files fail, get fixed, and get
reviewed like anything else here.

## What CI Checks

Three jobs, in `.github/workflows/ci.yml`, kept separate because they
fail for different reasons:

| Job | Catches |
|---|---|
| `tests` | Broken Python. Matrixed over every version `requires-python` claims (3.10 through 3.14), so the claim has evidence rather than being a promise nothing runs on. |
| `catalog` | Broken *content*. Runs `.github/scripts/check_catalog.py`. |
| `package` | A distribution that builds but does not carry the catalog — installs the built wheel into a clean venv outside any checkout and seeds from it. |

The `catalog` job is not redundant with `tests`, and the reason is
specific to how this repo reads its own content. `catalog.py` parses
frontmatter with a hand-rolled YAML subset, and **nothing in it raises on
a malformed header**: `split_frontmatter` returns the whole document as
body when the fence is unterminated, and `parse_frontmatter` skips lines
it cannot read. A broken `AGENT.md` therefore yields an entry with an
empty description rather than an error — which breaks `ai-agents list`
while the unit suite passes straight through. That is not hypothetical:
removing one `---` from an agent header leaves all tests green and fails
the catalog check. So the check asserts on the *parsed result* — a
non-empty name and description, declared skills and workflows resolving
to real files, no dangling skill references — never on whether parsing
threw.

## What This Does NOT Do Yet

Stated plainly so the scope is not overread:

- **`stock-screening` is end-of-day only.** There is no live, intraday,
  or pre-market data path, so `day-trading-shortlist` screens a
  completed session for a named date rather than the one in progress,
  and `morning-shortlist` screens the previous session's close. Prices
  are unadjusted for corporate actions.
- **Three of the four fundamental providers are not contracts.**
  screener.in, tickertape.in and moneycontrol.com are commercial sites
  whose HTML and internal JSON are unversioned and can change without
  notice. Each provider fails loudly rather than half-parsing, and the
  exchange's own filings are kept as a credential-free floor beneath
  them — but a gate that depends on a page nobody promised will keep
  working is a standing liability, not a solved problem. Whether that
  access is appropriate is the operator's judgement, not something this
  repo settles.
- **Three gated fundamental fields have no provider.** `debt_equity`,
  `promoter_holding` and `promoter_pledge` are declared and are gated
  the moment a source supplies them, but nothing here parses a
  shareholding filing and screener.in publishes no leverage figure. The
  leverage and pledge filters are written and not yet biting.
- **Screening covers Indian equities only.** NSE and BSE, via public
  exchange bhavcopy files. The series codes, circuit rules and delivery
  data it relies on do not generalise to other markets.
- **Not published to a package index.** The catalog now ships as package
  data, so a wheel installs and seeds without a checkout — but no release
  has been cut, so `pipx install ai-agents` does not resolve yet.
  Installing from the repo URL does. Milestone 4 covers the rest.

What works: the catalog, tier resolution, `install` / `list` / `init`,
the lifecycle operations (`diff` / `update` / `remove`), `doctor`,
external plugin install/remove (`plugin install` / `list` / `remove`),
harness adapter generation for all four harnesses, the LifeOS and Forge
agent ports, all three stock screens, and the `morning-shortlist`
Workflow that composes two of them.
