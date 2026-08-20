# Claude Code adapter

Claude Code discovers instructions from a few conventional locations in
a project or in `~/.claude/`. The two that matter here are
`.claude/agents/*.md` — subagents, each a markdown file with `name`,
`description`, and `tools` frontmatter, dispatched when its description
matches the task — and `.claude/skills/*/SKILL.md`, directories loaded
on demand by name. A `.claude-plugin/plugin.json` manifest bundles a
set of these for distribution, which is why this repo carries one at
its root.

The adapter will generate one thin pointer file per installed agent —
`.claude/agents/<name>.md` — carrying the frontmatter Claude Code needs
for dispatch (name, description lifted from `AGENT.md`) and a body that
points at `agents/<name>/AGENT.md` in the resolved tier. The agent's
actual content is never copied into it. A copy would fork on the next
edit to the source, and the whole point of the tier cascade is that
there is exactly one authoritative copy of an agent's instructions per
tier.

Which tier the pointer resolves to is decided at generation time by
`ai_agents.tiers.resolve`, so a project that has installed its own copy
of an agent gets a pointer into `.ai-agents/`, and everything else
points at the user master.

Status: not yet implemented — this is a contract description only.
