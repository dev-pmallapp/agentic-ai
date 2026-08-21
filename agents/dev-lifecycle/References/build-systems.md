# Build System Detection

Build targets are the unit of task creation: **one independently
buildable unit = one task**. A build target is a library, binary,
package, or crate defined by a build definition file.

The `## Build Targets` table in `ARCHITECTURE.md` is the preferred
source (see `References/context-discovery.md`). Filesystem discovery
described here is the **fallback** — and the input used to propose that
table in the first place, when a project has no table yet.

## Supported Build Definition Files

| Language | Build file | Target name source | Type detection |
|---|---|---|---|
| C/C++ | `module.mk` | `MODULE_TARGET` value | `.lib` -> library, `.bin` -> binary, `.dontuse` -> skip |
| C/C++ | `Makefile` | `TARGET` variable | context-dependent |
| C/C++ | `CMakeLists.txt` | `add_library()` / `add_executable()` arg | `add_library` -> library, `add_executable` -> binary |
| Go | `go.mod` | `module` path, last component | has `cmd/` or `main.go` -> binary, else library |
| Python | `pyproject.toml` | `[project] name` | has `[project.scripts]` -> binary, else library |
| Python | `setup.py` | `name=` in `setup()` | has `console_scripts` -> binary, else library |
| Python | `setup.cfg` | `[metadata] name` | has `[options.entry_points]` -> binary, else library |
| Rust | `Cargo.toml` | `[package] name` | `[lib]` or `src/lib.rs` -> library; `[[bin]]` or `src/main.rs` -> binary |

## Discovery Command

Search for every known build definition file at once, skipping `.git`:

```bash
find {relevant_source_dirs} -type d -name .git -prune -o \( \
     -name 'module.mk' -o \
     -name 'Makefile' -o \
     -name 'CMakeLists.txt' -o \
     -name 'go.mod' -o \
     -name 'pyproject.toml' -o \
     -name 'setup.py' -o \
     -name 'setup.cfg' -o \
     -name 'Cargo.toml' \) -print | sort
```

Only files relevant to the project's languages will be found — a C
project has no `go.mod`, and searching for it is harmless.

Exclude vendored and generated trees, which otherwise produce dozens of
phantom targets:

```bash
| grep -vE '/(vendor|node_modules|third_party|external|\.venv|build|target|dist)/'
```

## Parsing Details

### C/C++: `module.mk`

```makefile
MODULE_TARGET := libhft.lib
MODULE_SRCS   := $(wildcard *.cc)
```

- Target name: the `MODULE_TARGET` value **including its extension** —
  that full string is the canonical build target name. The extension
  gives the type: `.lib` = library, `.bin` = binary, `.dontuse` =
  disabled (skip).
- Source files: the `MODULE_SRCS` expansion.

### C/C++: `Makefile`

Look for `TARGET`, `OUTPUT`, or the first target rule:

```makefile
TARGET = myapp
```

Type is context-dependent — check whether it links as a shared library
(`-shared`) or produces an executable. A top-level `Makefile` that only
recurses into subdirectories is **not** a build target; treat it as a
driver and descend.

### C/C++: `CMakeLists.txt`

```cmake
add_library(mylib STATIC src/lib.cc)
add_executable(myapp src/main.cc)
```

- `add_library()` -> library; `add_executable()` -> binary. The first
  argument is the target name.
- One `CMakeLists.txt` may declare several targets — each is its own
  build target, and therefore its own task.
- Skip targets whose name starts with a generator expression or a
  variable (`${...}`): they cannot be resolved statically. Note them
  for the engineer instead of guessing.

### Go: `go.mod`

```
module github.com/org/repo/pkg/myservice
```

- **Package-level `go.mod`** (one package per module): target name is
  the last path component of the `module` line (`myservice`). Type is
  binary when the directory contains `main.go`, else library.
- **Repo-root `go.mod`** with `cmd/` subdirectories: each
  `cmd/<name>/main.go` is a separate binary target named `<name>`.
  Non-`cmd` packages under the same `go.mod` are libraries and do not
  get their own build target unless they have their own `go.mod`.
  Example: `cmd/server/main.go` + `cmd/cli/main.go` -> targets `server`
  and `cli`, both binaries.

### Python: `pyproject.toml`

```toml
[project]
name = "my-package"

[project.scripts]
my-cli = "my_package.cli:main"
```

- Target name: `[project] name`.
- Type: has `[project.scripts]` or `[project.gui-scripts]` -> binary;
  otherwise library.
- Also recognize `[tool.poetry] name` for Poetry-style projects.

### Python: `setup.py` / `setup.cfg`

```python
setup(
    name="my-package",
    entry_points={"console_scripts": ["my-cli=my_package.cli:main"]},
)
```

- Target name: the `name` parameter.
- Type: has `console_scripts` -> binary; otherwise library.
- A `setup.py` that only calls `setup()` with values read from
  `setup.cfg` -> parse `setup.cfg` instead.

### Rust: `Cargo.toml`

```toml
[package]
name = "my-crate"

[lib]
name = "my_lib"

[[bin]]
name = "my-tool"
path = "src/bin/tool.rs"
```

- Target name: `[package] name`, or the individual `[lib]` / `[[bin]]`
  names when declared.
- Type: `[lib]` or `src/lib.rs` -> library; `[[bin]]` or `src/main.rs`
  -> binary. A crate can be both — record it as a library with a
  binary; it is one task either way.
- A workspace `Cargo.toml` with `[workspace] members` is **not** itself
  a target; each member's `Cargo.toml` is.

## Priority When Multiple Files Exist

If one directory holds several build definition files — both a
`Makefile` and a `CMakeLists.txt`, say — prefer, in order:

1. The project-specific convention (`module.mk` in repos that use it).
2. The file that declares explicit named targets.
3. Ask the engineer, if still ambiguous.

A `Makefile` that just wraps `cmake --build` is a convenience driver,
not the source of target definitions.

## When There Is No Build File At All

Not every build target has a build definition. A documentation target,
a catalog of markdown, or a directory of workflow files is a real unit
of work with no `pyproject.toml` to find — filesystem discovery cannot
see it, and inventing a build file for it would be worse than not
having one.

This is exactly why the `## Build Targets` table takes priority over
discovery: the table can declare a target with `—` in its build-file
column, and the type falls back to `library` for sizing purposes. A
project whose targets are mostly content should write the table by hand
rather than expecting discovery to produce it.

## Extending to New Languages

To support Bazel, Meson, Gradle, or anything else: add a row to the
table above, add a parsing section, and add the filename to the `find`
command. The concept does not change — one independently buildable unit
is one task.
