"""Resolve the three installation tiers for a working directory.

Three places an agent can live, closest wins:

===========  ====================================================
Tier         Physical location
===========  ====================================================
project      ``.ai-agents/`` at a git repo root. Starts empty and
             grows as agents are installed down into it.
workspace    ``.ai-agents/`` in an ancestor directory above the
             project — a folder holding several related repos.
             Optional; often absent.
user         ``~/.ai-agents/``. The master copy, always present
             after ``ai-agents init``. Source of truth.
===========  ====================================================

Lookup walks project -> workspace -> user and takes the first tier that
has the agent, so a project can pin its own copy of an agent while
everything it has not localized falls back upward. This is the same
cascading shape as ``git config`` (local -> global -> system) and Claude
Code's own settings layering (project ``.claude/`` -> user ``~/.claude/``),
chosen deliberately so the behavior is already familiar.

Two boundary rules keep the walk honest:

* The workspace search starts *above* the project root, so a project is
  never also reported as its own workspace.
* Both searches stop before ``Path.home()`` — the home directory is the
  user tier's own domain, and treating it as a workspace would make every
  repo on the machine share one accidental "workspace".
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["resolve", "user_root", "find_project_root", "find_workspace_root", "TIER_DIRNAME"]

TIER_DIRNAME = ".ai-agents"


def user_root() -> Path:
    """The user master tier. Always this path, whether or not it exists."""
    return Path.home() / TIER_DIRNAME


def find_project_root(start: Path) -> Path | None:
    """Nearest ancestor of ``start`` (inclusive) containing ``.git``.

    Deliberately keyed on ``.git`` alone, not on ``.git`` *and*
    ``.ai-agents``: the project tier path is computed for any repo even
    before anything is installed into it, so ``ai-agents install --project``
    has somewhere to create. Callers that need "does the project tier
    actually have content" should test the returned path for existence.
    """
    for candidate in _self_and_parents(start):
        if (candidate / ".git").exists():
            return candidate
    return None


def find_workspace_root(start: Path, *, below: Path | None = None) -> Path | None:
    """Nearest ancestor containing an existing ``.ai-agents/`` directory.

    Searching begins strictly above ``below`` when given (normally the
    project root) and stops before ``Path.home()``. Unlike the project
    tier, a workspace must already exist on disk to count — there is no
    way to guess which ancestor was meant to be one.
    """
    home = Path.home().resolve()
    begin = below.parent if below is not None else start

    for candidate in _self_and_parents(begin):
        if candidate.resolve() == home:
            break
        if (candidate / TIER_DIRNAME).is_dir():
            return candidate
    return None


def _self_and_parents(path: Path):
    path = Path(path).expanduser().resolve()
    yield path
    yield from path.parents


def resolve(cwd: str | Path | None = None) -> dict:
    """Resolve all three tiers for ``cwd`` (default: the current directory).

    Returns ``{"project": Path | None, "workspace": Path | None, "user": Path}``
    where each value is the *tier root* — the directory that contains
    ``agents/`` — i.e. ``<repo>/.ai-agents``, not ``<repo>``.

    ``project`` is ``None`` outside a git repo. ``workspace`` is ``None``
    when no ancestor declares one, which is the common case. ``user`` is
    never ``None``, though it may not exist until ``ai-agents init`` runs.
    Resolution order for a lookup is project -> workspace -> user; see the
    module docstring.
    """
    start = Path(cwd) if cwd is not None else Path.cwd()
    start = start.expanduser().resolve()

    project_repo = find_project_root(start)
    workspace_dir = find_workspace_root(start, below=project_repo)

    return {
        "project": (project_repo / TIER_DIRNAME) if project_repo else None,
        "workspace": (workspace_dir / TIER_DIRNAME) if workspace_dir else None,
        "user": user_root(),
    }
