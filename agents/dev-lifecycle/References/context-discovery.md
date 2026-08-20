# Context Discovery

There is no configuration file for this agent. Every value a Skill or
Workflow needs is derived from the git repo and the documents in its
root. Run this at the start of any Skill invocation, before any GitHub
call. Discovery does not carry over between invocations — re-run it
every time. The repo may have changed branches, docs, or state since
the last run.

## What Gets Resolved

| Value | Source |
|---|---|
| `{repo_root}` | `git rev-parse --show-toplevel` |
| `{repo}` (`owner/name`) | `gh repo view --json nameWithOwner` |
| `{default_branch}` | `gh repo view --json defaultBranchRef` |
| `{current_user}` | `gh api user --jq .login` |
| `{build_targets}` | `ARCHITECTURE.md` `## Build Targets`, else filesystem discovery |
| `{commands}` | `CONTRIBUTING.md` `## Commands` |
| `{design_doc_path}` | `{repo_root}/docs/design` |
| `{test_plan_path}` | `{repo_root}/docs/test-plans` |
| `{test_results_path}` | `{repo_root}/docs/test-results` |

## Step 1: Repo Identity

```bash
git rev-parse --show-toplevel
gh repo view --json nameWithOwner,defaultBranchRef,hasIssuesEnabled
gh api user --jq .login
```

- Not a git repo → stop: this pipeline needs a git repository to
  operate in.
- No GitHub remote / `gh repo view` fails → stop; the repo is not on
  GitHub or `gh` cannot see it.
- `hasIssuesEnabled: false` → stop; there is nowhere to create the
  issues this pipeline depends on.

Record `{default_branch}` from `defaultBranchRef.name` — never assume
`main`. `master`, `develop`, and `trunk` are all real, and a hardcoded
`main` produces PRs against a branch that does not exist.

## Step 2: Locate Root Docs

Search `{repo_root}`, not the current working directory — a Skill may
be invoked from a subdirectory.

| Doc | Needed for |
|---|---|
| `README.md` | everything (project summary; multi-repo `## Repositories` table) |
| `ARCHITECTURE.md` | `task-create` (`## Build Targets`) |
| `CONTRIBUTING.md` | `task-implement`, `task-test`, `story-test` (`## Commands`) |
| `CLAUDE.md` / `AGENTS.md` | coding conventions (optional) |

Record which exist. Do not fail yet — a Skill only needs the docs that
feed the values it actually uses.

## Step 3: Build Targets

Build targets define task boundaries. One build target is one task
sub-issue.

**Primary — `ARCHITECTURE.md`:** find `## Build Targets` and parse the
table beneath it by header name (`Target`, `Type`, `Build file`,
`Source dirs`), not by column position. `Type` is `library` or
`binary`; anything else is recorded as-is and treated as `library` for
sizing. `Source dirs` is comma-separated, relative to `{repo_root}`.

**Fallback — filesystem discovery:** when no table exists, look for
build definition files (`Makefile`, `CMakeLists.txt`, `go.mod`,
`pyproject.toml`, `Cargo.toml`, and similar) and treat each as one
build target. Tell the user the table is missing and that discovery is
a fallback, not a replacement — two Skills discovering independently
can disagree, producing duplicate or missing tasks. Parsing the
build-definition files themselves (per-language conventions) is future
work; today's fallback is "one target per build file found," which is
enough to unblock `task-create` but not to size or type the targets
precisely.

**Cross-check:** verify each target's build file still exists on disk
regardless of which path produced the list. A build file that is gone
means the table is stale — warn, don't stop.

## Step 4: Commands

```markdown
## Commands

| Action | Command |
|---|---|
| build | make -j8 |
| test  | ctest --output-on-failure |
```

Heading matches `## Commands`; the first table beneath it, columns
`Action` and `Command` by name. A `###` heading naming the action
followed by a fenced code block is equivalent to a table row, for
multi-line commands.

**Resolution chain, in order:** the `## Commands` table row, then a
matching fenced block, then ask the engineer. There is no
auto-detection step — scanning for a `Makefile` and guessing `make` is
unreliable across containerized or multi-stage toolchains, and a wrong
build command wastes more time than asking once.

**When an action is missing:**
- `build` missing → skip build verification with a logged warning.
  Not every project compiles.
- `test` missing → `task-test` and `story-test` cannot run. In an
  autonomous run this is a hard stop; in an interactive run, ask for
  the command and use the answer for this run only (offer to record it
  in `CONTRIBUTING.md`).

## Step 5: Gaps

| Missing | Affects | Behavior |
|---|---|---|
| `README.md` | everything | stop; there is no project context to discover |
| `## Build Targets` | `task-create` | warn, fall back to filesystem discovery |
| `## Commands` → `test` | `task-test`, `story-test` | autonomous: stop. interactive: ask |
| `## Commands` → `build` | `task-implement` | warn, skip build verification |

Never write an agent-specific config file to fill a gap. The values
above are read from docs that are useful to a human reading the repo
regardless of whether this agent is in play.

## Step 6: Artifact Directories

```
{repo_root}/docs/design/                          design docs
{repo_root}/docs/test-plans/                      test plans
{repo_root}/docs/test-plans/test-cases/{issue}/   individual test cases
{repo_root}/docs/test-results/                    timestamped run results
```

Created with `mkdir -p` on first write. `docs/test-results/`
accumulates; a project that does not want run results in version
control can gitignore it — `git check-ignore -q docs/test-results`
detects that and skips committing results while still posting them as
comments.

## Multi-Repo Projects

A feature spanning several repos declares them in `README.md` under a
`## Repositories` table (`Repo`, `Path`, `Role` columns). Issues live
in the primary repo (`Path: .`) even when the code spans several;
commits in secondary repos use the qualified form
`{owner}/{repo}#{issue}: message` so GitHub still cross-links. No
`## Repositories` table means the project is single-repo.
