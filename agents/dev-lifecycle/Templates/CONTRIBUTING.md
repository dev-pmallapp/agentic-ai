<!--
  Scaffold written by the `init` Skill when CONTRIBUTING.md is missing.
  Placeholders in {braces} are filled from the init interview.

  Exactly one section here is read mechanically: `## Commands`.
  Keep it accurate — it is how every Skill knows to build and test.
-->

# Contributing

{One paragraph: how to get from a fresh clone to a working
development setup.}

## Getting Started

```bash
git clone {clone-url}
cd {repo-name}
{setup command — install deps, configure, bootstrap}
```

## Commands

<!--
  FIXED SHAPE — do not rename this heading or its columns.

  `context-discovery` finds this section by the exact heading text
  `## Commands` and reads either the table below (by the column names
  `Action` and `Command`) or a `### <action>` subsection. Rename the
  heading, translate a column, or replace the table with prose, and
  every Skill that builds or tests this project loses its commands and
  has to ask. It will not warn you.

  Table form for one-liners; a `### <action>` heading with a fenced
  block for anything multi-line. Well-known actions: build, test,
  lint, run, load-image, debug. See `References/project-commands.md`.

  Placeholders substituted at run time: {target}, {target_dir},
  {repo_root}, {issue}.
-->

| Action | Command |
|---|---|
| build | {build command} |
| test | {test command} |
| lint | {lint command} |

<!-- Multi-line form, if you need it:

### test

```bash
{setup line}
{test command}
```

Passes when: exit 0 and output contains `{marker}`.
-->

## Branching

| Kind | Pattern | Base |
|---|---|---|
| Story | `story/<issue>-<slug>` | `{default-branch}` |
| Task | `task/<issue>-<slug>` | the story branch |
| Bug | `bug/<issue>-<slug>` | `{default-branch}` |

Task PRs target the story branch; one integration PR takes the story
branch to `{default-branch}`.

## Commits

Every commit references its issue:

```
#1234: short imperative summary

Optional body explaining why, not what.
```

Add a co-author trailer if your tooling or your project convention
calls for one; nothing here requires a particular attribution line.

**Enforce the prefix locally** with the `commit-msg` hook shipped
alongside this template. Copy it into your clone — git hooks are
per-clone and never travel with a push, so every contributor installs
it once:

```bash
cp ~/.ai-agents/agents/dev-lifecycle/Templates/git-commit-msg-hook.sh \
   .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
```

If the agent is installed at the project or workspace tier instead,
the source path is `.ai-agents/agents/dev-lifecycle/Templates/` under
that tier's root rather than under `~`.

To version the hook with the repo so a fresh clone gets it without a
manual copy, commit it to a tracked directory and point git at that
directory once:

```bash
mkdir -p .githooks
cp ~/.ai-agents/agents/dev-lifecycle/Templates/git-commit-msg-hook.sh \
   .githooks/commit-msg
chmod +x .githooks/commit-msg
git config core.hooksPath .githooks
```

`core.hooksPath` is still per-clone — it is a local config setting, so
each contributor runs that one `git config` line — but the hook itself
is then reviewed and updated like any other tracked file.

See `References/hook-contract.md` for what this hook guarantees, and
what the other lifecycle hooks do where a harness can run them.

## Code Style

{Naming, formatting, and structural conventions. If there is a
formatter, name it and how to run it — the `lint` command above should
enforce whatever is written here.}

- {convention}
- {convention}

## Tests

{Where tests live, how they are named, and what is expected of a
change. State the bar: does every new build target need unit tests?
What must a bug fix include?}

## Pull Requests

{What a reviewable PR looks like here: size expectations, required
checks, who reviews, how long to wait.}
