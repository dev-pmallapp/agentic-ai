# Gemini CLI adapter

Gemini CLI loads a `GEMINI.md` context file, discovered hierarchically —
a global one under `~/.gemini/`, then any found from the project root
down toward the working directory, concatenated. It also supports
extensions: a directory carrying a `gemini-extension.json` manifest,
which can declare its own context file and MCP servers.

The adapter will generate a thin pointer per installed agent, in one of
two shapes depending on how the tier is being consumed — either a
section appended to a managed block in `GEMINI.md`, or an extension
directory with a `gemini-extension.json` manifest whose context file
lists the installed agents. Both forms carry the agent name, its
one-line description, and the path to `agents/<name>/AGENT.md` in the
resolved tier. Neither inlines the agent's content.

The managed-block boundary matters here: `GEMINI.md` is a file humans
also edit, so generated content needs explicit start/end markers and
must never rewrite anything outside them.

Status: not yet implemented — this is a contract description only.
