# Contributing

## Add an agent

Create a directory under `agents/`:

```
agents/<Name>/
  AGENT.md              required
  Skills/*.md           optional — atomic, individually invocable
  Workflows/*.md        optional — cumulative, compose Skills
  References/*.md       optional — shared contracts, cited by both
  Templates/*           optional — shapes the agent writes into a
                                   user's project
  Tools/*               optional — scripts the agent shells out to
```

`AGENT.md` needs frontmatter with `name`, `description`, and a
`skills:` list and a `workflows:` list (either may be empty), then a
short persona section and a routing table mapping each skill and
workflow to its trigger and file. Look at
`agents/stock-screening/AGENT.md` for the shape.

The catalog picks up the directory automatically — there is no registry
file to update. `ai-agents list` will show it once `AGENT.md` exists.

Keep the content harness-neutral. Nothing in an agent should mention
Claude Code, Cline, Gemini CLI, or Qwen Code; that is what
`harness-adapters/` is for.

## Skill or workflow?

Rule of thumb: if it does one thing end to end and someone could
reasonably invoke it alone, it is a Skill. If its job is sequencing
other things and owning the gates between them, it is a Workflow.

When in doubt, write it as a Skill. A Workflow that later needs it
can call it; a Skill that turns out to depend on a Workflow has to
be pulled apart.

## Add a skill

Add `agents/<Name>/Skills/<skill>.md`, then add it in two places:
the `skills:` list in that agent's `AGENT.md` frontmatter, and the
routing table in its body, with the trigger that should select it.

A Skill does one thing end to end and should stand on its own — if
it needs another file to have run first, that sequencing belongs in
a Workflow, not folded into the Skill.

## Add a workflow

Add `agents/<Name>/Workflows/<workflow>.md`, then add it in two
places: the `workflows:` list in that agent's `AGENT.md`
frontmatter, and the routing table in its body, with the trigger
that should select it.

A Workflow sequences Skills and owns any human approval gates
between them. It should call a Skill rather than reimplement what
that Skill already does.

The catalog cross-checks frontmatter against what is on disk for
both lists, so a skill or workflow that's listed but missing (or
present but unlisted) still appears — but the routing table is what
a harness actually reads, and only you can write that.

## Cutting a release

### Where the version lives

**One place: `__version__` in `src/ai_agents/__init__.py`.**
`pyproject.toml` declares `dynamic = ["version"]` and hatchling reads
that attribute at build time, so the distribution version is derived,
never hand-synced. A bump edits one line.

### Catalog changes are releases too

This part is specific to this project, and follows directly from the
catalog shipping *inside* the wheel (see
[`docs/design/2-catalog-distribution.md`](docs/design/2-catalog-distribution.md)).
A user gets agents from `ai-agents init`, which copies out of the
installed package — so an agent edit that is merged but not released has
reached nobody.

**The catalog and the code share one version number.** There is no
separate catalog version, and adding one would be the wrong fix: the
whole reason the catalog ships as package data is that the hand-rolled
frontmatter parser in `catalog.py` and the content it parses are a
matched pair. Two numbers would let them drift apart on paper while the
wheel keeps them together in fact.

Since the user-facing surface is *both* the CLI and the agents, both
count toward the bump:

| Change | Bump |
|---|---|
| CLI behaviour breaks, or an agent is removed or renamed | **major** |
| A new agent, skill, or workflow; a new CLI command or flag | **minor** |
| An agent's wording, criteria, or thresholds edited in place; bug fix; docs | **patch** |

A content-only change is a real release, normally a patch one — but
judge it by what a user sees, not by which directory moved. Retuning a
screen's thresholds changes what `stock-screening` shortlists, and that
is a behaviour change even though no Python was touched.

### The sequence

In this order. The changelog is updated *as part of* the bump, in the
same commit — not written afterwards from the git log.

1. **Check the tree is releasable.** `pytest -q` and
   `python .github/scripts/check_catalog.py` both pass on `main`. CI runs
   both, plus a packaging job that installs the built wheel outside a
   checkout and seeds from it — that job is what proves `init` works for
   someone without a clone, so don't release on a red one.
2. **Bump `__version__`** in `src/ai_agents/__init__.py`. Nothing else;
   `pyproject.toml` follows on its own.
3. **Move `## [Unreleased]` into a dated `## [X.Y.Z]` section** in
   `CHANGELOG.md`, and open a fresh empty `Unreleased`. Update the two
   link definitions at the bottom. `tests/test_version_single_source.py`
   fails when the changelog has no section for the current version, so a
   forgotten entry is caught before it ships rather than noticed after.
4. **Commit** the bump and the changelog together: `release: vX.Y.Z`.
5. **Tag** with `git tag -a vX.Y.Z -m "vX.Y.Z"` and push using
   `git push --follow-tags`. Tags are `v`-prefixed; the version inside
   the package is not.
6. **Build** with `python -m build`, producing a wheel and an sdist.
7. **Verify the artifact, not just the build.** Install the wheel into a
   throwaway venv, `cd` somewhere that is neither a checkout nor a git
   repo, and run `ai-agents init && ai-agents list`. If the catalog does
   not appear, the force-include is broken and the release would ship a
   CLI with nothing to install.
8. **Publish** the wheel and sdist, and cut a GitHub release against the
   tag with that changelog section as its body.

## Commands

| Action | Command |
|---|---|
| build | pip install -e . |
| test | pytest -q |

Table shape is fixed — it is parsed mechanically by GitHub-workflow
tooling to resolve build and test commands. Add rows, keep the columns.

## Tests

The Python package is tested with `pytest`:

```bash
pip install -e .
pytest -q
```

The tests run against this repo's own `agents/` tree, so adding or
renaming an agent can change their expectations. That is intentional —
the catalog tests exist to catch a layout that no longer parses.

## Harness adapters

`harness-adapters/<harness>/README.md` states the contract for one
harness: what it natively reads, what its pointer file contains, and a
closing status line. `install.generate_harness_adapters` implements all
four — Claude Code and Cline get one pointer file per agent, while Gemini
CLI and Qwen Code share one managed block per tier that is re-rendered
when an agent is removed.

If you are adding a harness, add its directory and README in the same
shape as the existing four, then teach `install.py` to detect and render
it. A pointer file names an agent and gives the path to its `AGENT.md` —
it is never a copy of the agent's content, and that rule is what keeps
one authoritative copy per tier true.
