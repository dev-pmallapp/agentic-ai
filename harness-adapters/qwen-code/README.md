# Qwen Code adapter

Qwen Code is a fork of Gemini CLI and keeps the same instruction
discovery shape: a hierarchically loaded context file, here named
`QWEN.md` (global under `~/.qwen/`, then project-level files merged),
and the same extension-manifest mechanism.

The adapter will therefore mirror the Gemini CLI adapter almost
exactly — one thin pointer per installed agent, written either into a
managed block in `QWEN.md` or into an extension directory, carrying the
agent name, description, and the path to `agents/<name>/AGENT.md` in
the resolved tier. No content is copied.

The two adapters are kept as separate directories rather than one
shared "gemini-family" adapter because the forks are free to diverge —
file names already differ, and defaults may follow. Sharing
implementation between them is an option once both are real; sharing
the contract description before either exists would only hide the
places they already differ.

Status: not yet implemented — this is a contract description only.
