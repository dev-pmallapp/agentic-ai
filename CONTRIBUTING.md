# Contributing

## Add an agent

Create a directory under `agents/`:

```
agents/<Name>/
  AGENT.md              required
  Skills/*.md           optional — atomic, individually invocable
  Workflows/*.md        optional — cumulative, compose Skills
  References/*.md       optional — shared contracts, cited by both
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
