# Agents

Catalog of agents in this repo. Each `agents/<Name>/` directory follows
the anatomy described in `../ARCHITECTURE.md`: `AGENT.md` (persona,
routing, boundaries) plus `Skills/`, `Workflows/`, `References/`, and
`Tools/` as needed.

## Ported from LifeOS

`ExtractWisdom/`, `BiasCheck/`, `RootCauseAnalysis/`, and
`FirstPrinciples/` were ported from LifeOS's skill catalog
(`LifeOS/install/skills/` in the LifeOS repo) per
`../docs/porting-from-lifeos.md`.

**Why these four, first:** all four are self-contained reasoning and
analysis methods with no dependency on LifeOS's runtime services — no
coupling to its notification bus, its memory/context layers, its
goal-tracking system, or its skill-invocation subsystem. Each is a
standalone intellectual procedure (extract wisdom from text, check for
bias, investigate a root cause, decompose a problem to first
principles) that a person or agent can run start-to-finish using
nothing but the method itself.
That made them the lowest-risk, highest-confidence first batch to
port: nothing to rip out except LifeOS-specific packaging (voice
notifications, customization hooks, execution logging), and nothing
left behind that silently assumed a LifeOS service was running.

`SystemsThinking/` was deliberately left out of this batch — the
porting guide flags it as a case where the Skill/Workflow boundary is
genuinely ambiguous ("feeds"/"escalates to" language throughout looks
like wrapping language but isn't), and it's referenced by multiple of
the agents ported here as a forward pointer, so it's better ported
carefully in its own pass than rushed alongside this batch.

See each agent's `AGENT.md` for its own source-credit line and version
at time of port.
