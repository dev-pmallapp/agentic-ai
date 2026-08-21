# init

Bootstraps a project so the rest of this pipeline can discover it:
creates the label set and writes the missing standard root documents.
Run once per project, before `story-create`.

## Purpose

Every other Skill here derives what it needs from the git repo and the
documents in its root — there is no config file, and adding one would
be the wrong fix. This Skill finds what is missing, asks the questions
needed to fill the gaps, and writes **standard** documents.

The documents it writes are useful to human contributors whether or not
this pipeline ever runs again. That is the point: no proprietary
metadata, nothing that only a tool can read.

## Preconditions

- A git repository with a GitHub remote.
- `gh` authenticated with write access.
- **Missing documents are the expected input**, not a failure. Unlike
  every other Skill here, this one treats a gap as work to do rather
  than a stop condition.

Can be run whole, or narrowed to just the label set, just the build
targets table, or just the commands table.

## Procedure

**1. Discover, and report the gaps.** Run
`References/context-discovery.md` Steps 1-5, recording what is absent
instead of stopping at the first gap:

```
dev-lifecycle setup for {repo}

  Repo             {owner}/{name} (default branch: {default_branch})
  Issues enabled   yes
  Labels           3 of 9 exist
  README.md        present
  ARCHITECTURE.md  missing
  CONTRIBUTING.md  present (no ## Commands section)
  docs/            present, 4 markdown files

Will set up: labels, ARCHITECTURE.md, CONTRIBUTING.md ## Commands
```

Nothing missing → say so and stop, naming how to revisit the build
target table deliberately. Re-running on a configured project reports
"nothing to do" rather than churning files.

**2. Create the label set.** Check what exists first:

```bash
gh label list --repo {repo} --limit 200 --json name --jq '.[].name'
```

Then create only what is absent. **Leave an existing label alone even
if its colour differs** — the project may have chosen it deliberately,
and recolouring someone's labels is not this Skill's call.

| Label | Colour | Description |
|---|---|---|
| `type:epic` | `5319e7` | Epic tracker issue for a milestone |
| `type:story` | `0e8a16` | Story — one end-to-end deliverable feature |
| `type:task` | `1d76db` | Task — one build target's change |
| `type:bug` | `d73a4a` | Bug |
| `status:in-progress` | `fbca04` | Work actively underway |
| `status:resolved` | `0e8a16` | Work done, pending validation |
| `status:reopened` | `d93f0b` | Issue found post-resolution |
| `status:blocked` | `b60205` | Blocked by another issue |
| `dev-lifecycle` | `ededed` | Created or managed by this pipeline |

This is the canonical table — `References/gh-error-handling.md` § 7
sends single-label repairs here for the standard colour, and
`References/workflow-states.md` treats these labels as the source of
truth for state.

Creation fails with 403 → warn and continue; the documents are still
worth writing. Say plainly that state tracking needs the labels and
that a maintainer must create them.

**3. README.md.** Skip entirely if it exists and is non-trivial (more
than roughly ten non-blank lines). If it is missing or a stub, ask one
short round of questions rather than an interrogation: what the project
is in one sentence; who uses it (service, imported library, CLI,
firmware); and whether it is a multi-repo project, collecting the
sibling repos and their local paths if so.

Write a README with the title, that one-sentence summary, a Quick Start
derived from the commands collected in step 5, and a `## Repositories`
table where applicable.

**An existing README is never rewritten.** If the project is multi-repo
and has no `## Repositories` table, offer to append only that section.

**4. ARCHITECTURE.md — the Build Targets table.** This is the
highest-value part of setup: `task-create` creates one task per row, so
a wrong table produces wrong tasks all the way down the pipeline.

*Discover candidates* with the build-file search from
`References/build-systems.md`, excluding vendored trees:

```bash
find . -type d -name .git -prune -o \( \
     -name 'module.mk' -o -name 'Makefile' -o -name 'CMakeLists.txt' -o \
     -name 'go.mod' -o -name 'pyproject.toml' -o -name 'setup.py' -o \
     -name 'setup.cfg' -o -name 'Cargo.toml' \) -print \
  | grep -vE '/(vendor|node_modules|third_party|external|\.venv|build|target|dist)/' \
  | sort
```

Parse each per that reference to get a name and a type.

*Present them for correction* — do not silently accept discovery. Show
the table with the build file and source directories per row, flag the
rows you doubt and why, and ask the engineer to accept all, drop
specific rows, correct them in prose, or supply the list directly when
discovery was useless.

*Sanity-check granularity* before writing, and ask about anything that
looks wrong:

- More than roughly 15 targets → the table probably includes vendored
  or generated units.
- Exactly one target in a repo with many top-level source directories →
  probably under-decomposed.
- Two targets whose source directories overlap → their tasks will
  collide on the same files. The one-target-per-task rule depends on
  disjoint ownership, so this one matters more than it looks.

*Write.* Missing file → write it from `Templates/ARCHITECTURE.md`,
filling the Build Targets table and leaving the prose sections as
prompts. Existing file with no `## Build Targets` → **append only that
section**; an existing architecture document is never rewritten.

Ask the remaining template prompts only if the engineer wants to fill
them now. An ARCHITECTURE.md with a correct Build Targets table and
placeholder prose is fully functional for this pipeline.

**5. CONTRIBUTING.md — the Commands table.** Look for evidence before
asking, and propose what you find rather than asking cold: `Makefile`
targets, `package.json` scripts, `pyproject.toml` script and tox/nox
entries, the standard Cargo commands, and `.github/workflows/*.yml`.

CI workflows are the best source — the build and test steps a CI job
runs are usually exactly right.

Present what was inferred, then ask specifically about three things
that `References/project-commands.md` depends on and that inference
cannot settle:

1. **Can the test command be scoped to one build target?** If so,
   capture the placeholder form. An unscoped test command makes every
   task run the whole suite — correct, but slow, and this pipeline will
   say so on every run.
2. **Does anything need an environment first** — a container, a
   virtualenv, a remote host? If so, use the fenced-block form so the
   setup lines are carried too.
3. **Is exit code 0 sufficient for a pass?** If not, capture the pass
   criteria.

Missing file → write from `Templates/CONTRIBUTING.md`. Existing file
without `## Commands` → append only that section.

**6. Offer a conventions file, do not insist.** If the repo has no
agent-conventions file at its root, offer one: coding conventions
recorded there get loaded automatically during implementation, which
makes generated code match the codebase. If the engineer accepts, ask
for naming conventions, formatting rules, error-handling patterns, and
whatever a new contributor gets wrong on their first PR. Keep it short
— five real rules beat a page restating general good practice.

Where the repo already carries conventions for some other tool, offer
to adapt that content instead of asking the same questions again.

**7. Verify by re-discovering.** Run
`References/context-discovery.md` end to end, as a fresh Skill would,
and show what the pipeline now sees — repo, default branch, build
targets, commands and whether the test command is target-scoped,
knowledge files, artifact directories, and the label count.

Name every remaining gap together with the Skill it will block:

> "No `test` command — `task-test` will ask for one on each run. Add it
> to `## Commands` in CONTRIBUTING.md when you know it."

**8. Show the diff and ask before committing.** These are the
engineer's project documents, not this pipeline's:

```bash
git status --short
git diff
```

Offer to commit, to leave the changes uncommitted for the engineer to
review, or to revert the writes. On commit:

```bash
git add README.md ARCHITECTURE.md CONTRIBUTING.md
git commit -m "Add project docs for the dev-lifecycle workflow

Records build targets and commands so the pipeline can discover
project context without a config file."
```

No issue-number prefix here — setup precedes any issue, so the
`#{issue}: ` convention in `References/branch-and-pr-model.md` does not
apply.

## Idempotency

Every step checks before writing:

| Already present | Behaviour |
|---|---|
| Label exists | Skip — do not recolour |
| README.md non-trivial | Skip entirely |
| `## Build Targets` exists | Show it, ask whether to revisit |
| `## Commands` exists | Show it, ask whether to revisit |
| Conventions file exists | Skip |

## Outputs

- The nine labels this pipeline's state machine depends on.
- `README.md`, `ARCHITECTURE.md` (with a `## Build Targets` table), and
  `CONTRIBUTING.md` (with a `## Commands` table) — created or minimally
  appended to, never rewritten.
- Optionally a conventions file, and a commit if the engineer approves
  one.

## State Transitions

None. This Skill runs before any issue exists.

## Errors

- **Not a git repo:** stop. Never run `git init` — see `AGENT.md`
  § Boundaries.
- **No GitHub remote:** stop, and suggest adding one.
- **Issues disabled on the repo:** stop. This pipeline tracks all work
  as issues; there is no fallback.
- **Label creation 403:** warn, continue with the documents.
- **Build target discovery finds nothing:** the project may use a build
  system `References/build-systems.md` does not cover. Ask for the
  target list directly and note that the reference can be extended.
- **Engineer declines every question:** write nothing, and report which
  Skills are blocked as a result. Do **not** write a half-populated
  table with placeholder rows — a wrong Build Targets table is worse
  than no table at all, because discovery fallback at least reflects
  reality while a wrong table is trusted.
- **Standard `gh` failures:** `References/gh-error-handling.md`.

## Templates

`Templates/ARCHITECTURE.md` and `Templates/CONTRIBUTING.md` are cited
above by path and are **present**. Write a missing document from its
template rather than improvising a shape.

Both carry a fixed-shape section — `## Build Targets` and
`## Commands` respectively — found by exact heading text and read by
column name. **Keep the heading and the columns verbatim.** Everything
around them is the user's to rewrite freely; those two sections are
not. A renamed heading or a table turned into prose does not error, it
degrades silently: `context-discovery` falls back to guessing from the
filesystem, and nothing announces that it did.

Both templates state that contract inline, so a user editing the
document later sees it without reading this Skill. Preserve those HTML
comments when writing the file — they are the warning, not decoration.

`Templates/CONTRIBUTING.md` also carries the install instructions for
`Templates/git-commit-msg-hook.sh`, which enforces the commit prefix
this lifecycle depends on. Installing it is the user's action, never
this Skill's: `.git/hooks/` is per-clone and untracked, and writing
there would be a change to their repository that nobody asked for.
Point at the instructions; do not run them.
