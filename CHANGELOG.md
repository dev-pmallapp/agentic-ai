# Changelog

All notable changes to this project — both the Python package and the
agent catalog it ships. The two travel together in one version number;
see [CONTRIBUTING.md](CONTRIBUTING.md#cutting-a-release) for why, and for
what a catalog-only change means for the number.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning is [semantic](https://semver.org/), with the catalog folded in
as described in the release process.

## [Unreleased]

Nothing yet.

## [0.1.0] — unreleased

First version. Not yet published to a package index, so the whole of it
is still pending a release — this entry describes what 0.1.0 will be when
cut.

### Added

**The CLI.** `init`, `list`, `install`, `diff`, `update`, `remove`, and
`doctor`. Three install tiers — project, workspace, user master —
resolved closest-wins, the same cascade as `git config`. Copies never
overwrite: an agent already present may have been edited on purpose.

**The catalog**, six agents. Four ported from LifeOS (`BiasCheck`,
`ExtractWisdom`, `FirstPrinciples`, `RootCauseAnalysis`), the Forge
development lifecycle (`dev-lifecycle`), and `stock-screening`. Ports
drop voice notifications and all TypeScript; `Tools/` is Python.

**Two-level agent anatomy.** `Skills/` are atomic and individually
invocable; `Workflows/` are cumulative, compose Skills, and own the
gates. The composition rule runs one direction only. Subdirectories are
LifeOS-cased for port fidelity.

**Harness adapters** for Claude Code, Cline, Gemini CLI, and Qwen Code —
thin pointer files, never copies of agent content. Gemini and Qwen share
one managed block per tier, re-rendered on removal.

**`stock-screening` for Indian equities**, NSE and BSE, from public
end-of-day bhavcopy files with no API key. Both exchanges publish the
same 34-column UDiFF schema carrying ISIN, so one parser serves both and
ISIN is the join key rather than the ticker. Screening criteria live in
`References/` as parameter tables read at run time, so a threshold is
edited in a readable document rather than in code.

**The catalog ships as package data.** `agents/` is force-included into
the wheel, so `ai-agents init` works on a non-editable install with no
checkout, no network, and no git. Reasoning in
[`docs/design/2-catalog-distribution.md`](docs/design/2-catalog-distribution.md).

**CI.** Tests across Python 3.10–3.14, a catalog-parse check that runs
independently of them, and a packaging job that installs the built wheel
outside any checkout and seeds from it.

**External plugins.** `ai-agents plugin install / list / remove` places a
plugin this repo did not author into a tier verbatim, beside `agents/`
rather than inside it, and records where it came from. The governing rule
is one-way — bend the plugin into an agent's anatomy first, and install
locally only the pieces that genuinely cannot bend. `--reason` is
required with no default, so an unported piece stays visible rather than
settling in quietly. `doctor` reports what a tier carries.

### Known limits

- Not published to a package index; `pipx install ai-agents` does not
  resolve yet. Installing from the repo URL does.
- `stock-screening` is Indian equities only and end-of-day only — there
  is no live or intraday path.

[Unreleased]: https://github.com/dev-pmallapp/agentic-ai/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dev-pmallapp/agentic-ai/releases/tag/v0.1.0
