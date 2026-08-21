"""The version lives in exactly one place.

Task #48. `__init__.py` carried `__version__` and `pyproject.toml` carried
`version`, which is two places for one number and drift waiting to happen.
`pyproject.toml` now declares `dynamic = ["version"]` and hatchling reads
the package attribute at build time.

These are structural assertions on the *files*, not on installed metadata.
`importlib.metadata.version("ai-agents")` would be the more direct check,
but it reports whatever was recorded when the package was last installed —
so bumping `__version__` without reinstalling would fail the test for a
reason that has nothing to do with the property being protected. What
actually needs guarding is that nobody reintroduces a second literal.
"""

from __future__ import annotations

import re
from pathlib import Path

from ai_agents import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def _project_table() -> str:
    """The `[project]` table's body, up to the next top-level table."""
    match = re.search(r"(?ms)^\[project\]\s*$(.*?)(?=^\[)", PYPROJECT)
    assert match, "pyproject.toml has no [project] table"
    return match.group(1)


def test_pyproject_declares_the_version_dynamic():
    assert re.search(r'(?m)^dynamic\s*=\s*\[\s*"version"\s*\]', _project_table()), (
        "[project] must declare dynamic = [\"version\"] so the build derives "
        "it from the package"
    )


def test_pyproject_carries_no_literal_version():
    # The regression this test exists for. A commented-out or re-added
    # `version = "..."` line under [project] is the duplication coming back.
    literal = re.search(r'(?m)^version\s*=\s*["\']', _project_table())
    assert literal is None, (
        "[project] carries a literal version again — it must be derived from "
        "ai_agents.__version__, not hand-synced"
    )


def test_hatch_reads_the_version_from_the_package():
    assert re.search(
        r'(?ms)^\[tool\.hatch\.version\]\s*$.*?^path\s*=\s*"src/ai_agents/__init__\.py"',
        PYPROJECT,
    ), "[tool.hatch.version] must point at src/ai_agents/__init__.py"


def test_package_version_is_a_plain_release_string():
    # Guards the bump itself: hatchling's regex reader wants a literal, so a
    # computed or malformed value would fail the build rather than the test.
    # Asserting the shape here makes the failure legible at bump time.
    assert re.fullmatch(r"\d+\.\d+\.\d+([.-]?(a|b|rc|dev|post)\d+)?", __version__), (
        f"__version__ = {__version__!r} is not a recognisable release version"
    )


def test_changelog_has_an_entry_for_the_current_version():
    # The release sequence in CONTRIBUTING.md says the changelog is updated
    # as part of the bump, not after. This is what makes that checkable.
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"(?m)^##\s*\[?{re.escape(__version__)}\]?", changelog), (
        f"CHANGELOG.md has no `## {__version__}` section — bump and changelog "
        "entry are meant to land together"
    )
