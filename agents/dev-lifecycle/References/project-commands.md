# Project Commands

Project commands are the project-specific actions this pipeline needs
to build, test, lint, and run code. They bridge a generic workflow and
each project's toolchain.

They live in `CONTRIBUTING.md`, under `## Commands` — a location chosen
because they are useful to human contributors too, so the file has a
reason to stay current independently of any tooling that reads it.

## Where They Live

### Table form (preferred)

```markdown
## Commands

| Action | Command |
|---|---|
| build | make -j8 |
| test | ctest --output-on-failure |
| lint | make lint |
| run | ./build/exporter --config dev.yaml |
```

### Block form (for multi-line commands)

````markdown
## Commands

### build

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j8
```

### test

```bash
source .venv/bin/activate
pytest -q tests/
```
````

A `###` heading naming a well-known action, followed by a fenced block,
is equivalent to a table row. Mixing forms in one document is fine —
both are read, and **the block form wins** for an action defined twice.

## Well-Known Actions

| Action | Used by | Purpose |
|---|---|---|
| `build` | `task-implement` | Compile or build. Absent -> build verification is skipped with a warning |
| `test` | `task-test`, `story-test` | Run tests. Absent -> `task-test` cannot run |
| `lint` | `task-implement` (optional) | Style and static analysis |
| `run` | `story-test` manual execution | Start the thing, for manual verification |
| `load-image` | validation roles | Deploy built artifacts to a testbed |
| `debug` | implementation roles | Project-specific debugging entry point |

Any other action name is kept and available by name.
`deploy-staging`, `run-perf-tests`, and `setup-testbed` are all
legitimate rows.

## Scoping a Command to One Target

Commands may use placeholders, substituted before execution:

| Placeholder | Meaning |
|---|---|
| `{target}` | Build target name from the design doc |
| `{target_dir}` | That target's first source directory |
| `{repo_root}` | Repo root, absolute |
| `{issue}` | The issue number being worked |

```markdown
| Action | Command |
|---|---|
| build | cmake --build build --target {target} |
| test | ctest --output-on-failure -R "^{target}\." |
```

When a command has no placeholder it runs whole-project. That is
acceptable — running the full suite to validate one task is slower but
correct. Say so rather than letting it look scoped:

> "`test` is not target-scoped — running the full suite for #{issue}.
> Add `{target}` to the test command in CONTRIBUTING.md to scope it."

## Resolution Chain

```
1. CONTRIBUTING.md ## Commands table row       <- primary
2. CONTRIBUTING.md ### <action> fenced block   <- multi-line form
3. Ask the engineer                            <- interactive fallback
```

**Step 3 behaves differently depending on who is asking:**

- **Interactive run:** ask for the command and use the answer for this
  run. Then offer to record it:
  > "Add this to `## Commands` in CONTRIBUTING.md so it is available
  > next time?"
- **Orchestrated run** (a Workflow driving a worker role): **do not
  prompt.** Preflight already checked, so a missing command here is an
  error rather than a decision point. Stop with a clear message, or
  skip the step when it is optional (`build`).

There is deliberately **no auto-detection step**. Scanning for a
`Makefile` and guessing `make` misfires in containerized,
cross-compiled, and multi-stage toolchains, and a wrong build command
costs more time than one question. This is the same reasoning that puts
the `## Build Targets` table ahead of filesystem discovery in
`References/build-systems.md`: a declared answer beats an inferred one.

## Pass Criteria

By default a command passes on **exit code 0**. When that is not
enough, state it:

````markdown
### test

```bash
./run-tests.sh
```

Passes when: exit 0 **and** output contains `All tests passed`,
**and** no line matches `FAIL|ERROR`.
````

A `Passes when:` line directly after the block is parsed and applied.
Without one, the exit code alone decides.

This matters more than it looks. A test runner that reports failures on
stdout and still exits 0 will otherwise be read as a pass, and the
pipeline will resolve a task whose tests did not actually succeed.

## Environment Setup

If a command needs a container, a VM, a virtualenv, or a remote host,
put that in the block:

````markdown
### test

```bash
docker run --rm -v "$PWD:/src" -w /src build-env:latest \
  ctest --output-on-failure
```
````

**Exactly what is written is what runs.** Environments are never
entered on their own initiative, and `.venv` is never activated by
inference. If activation is needed, it belongs in the block.

## Table Shape Is Fixed

The `## Commands` table is parsed mechanically by header name, so its
column shape is a contract, not a style preference: `| Action |
Command |`, in that order. Add rows freely; renaming or reordering the
columns makes the table unparseable and the commands invisible.

The same applies to `## Build Targets` in `ARCHITECTURE.md` — see
`References/context-discovery.md`.

## Example `CONTRIBUTING.md` Section

````markdown
## Commands

| Action | Command |
|---|---|
| build | cmake --build build -j8 --target {target} |
| lint | clang-format --dry-run --Werror $(git ls-files '*.cc' '*.h') |

### test

```bash
cmake --build build -j8
ctest --test-dir build --output-on-failure -R "^{target}\."
```

Passes when: exit 0 and output contains `100% tests passed`.
````
