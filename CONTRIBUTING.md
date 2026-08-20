# Contributing

## Add an agent

Create a directory under `agents/`:

```
agents/<name>/
  AGENT.md              required
  workflows/*.md        the procedures
  references/*.md       optional — shared contracts
  tools/*               optional — scripts the agent shells out to
```

`AGENT.md` needs frontmatter with `name`, `description`, and a
`workflows:` list, then a short persona section and a routing table
mapping each workflow to its trigger and file. Look at
`agents/stock-screening/AGENT.md` for the shape.

The catalog picks up the directory automatically — there is no registry
file to update. `ai-agents list` will show it once `AGENT.md` exists.

Keep the content harness-neutral. Nothing in an agent should mention
Claude Code, Cline, Gemini CLI, or Qwen Code; that is what
`harness-adapters/` is for.

## Add a workflow to an existing agent

Add `agents/<name>/workflows/<workflow>.md`, then add it to two places:
the `workflows:` list in that agent's `AGENT.md` frontmatter, and the
routing table in its body with the trigger that should select it.

The catalog cross-checks frontmatter against what is on disk, so a
workflow listed but missing (or present but unlisted) still appears —
but the routing table is what a harness actually reads, and only you
can write that.

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

`harness-adapters/<harness>/README.md` currently describes a contract
only; no adapter generates files yet, and
`install.generate_harness_adapters` raises `NotImplementedError`.
Build-out is tracked as future work. If you are adding a harness,
add its directory and README in the same shape as the existing four —
what the harness natively reads, what its pointer file will contain,
and a closing status line.
