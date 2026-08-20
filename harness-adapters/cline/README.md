# Cline adapter

Cline reads custom instructions from a `.clinerules/` directory at the
project root — every markdown file in it is loaded as project rules,
which lets a project split its instructions across several files rather
than maintaining one monolith. There is no per-agent dispatch mechanism
of Claude Code's kind; the files are context, and Cline decides what is
relevant from their content.

The adapter will generate one thin pointer file per installed agent —
`.clinerules/<name>.md` — naming the agent, restating its one-line
description, and pointing at `agents/<name>/AGENT.md` in the resolved
tier for the full instructions and its workflow list. Never a copy of
the content.

Because Cline loads every rules file into context rather than
dispatching on demand, these pointers should stay short: the point is
that the agent exists and where to read it, not what it says.

Status: not yet implemented — this is a contract description only.
