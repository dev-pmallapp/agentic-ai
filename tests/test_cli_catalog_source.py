"""Where ``init`` finds a catalog to seed from.

Story #42 / task #45. The interesting cases are the two install shapes —
a wheel that bundles ``ai_agents/_catalog/`` and an editable install of a
checkout that does not — plus the case that used to fall through to
``Path.cwd()`` and now raises.

``cli._BUNDLED_CATALOG`` is a module-level constant computed from
``__file__``, so every test here monkeypatches it rather than creating
files inside the installed package. ``_checkout_catalog`` walks up from
the real ``__file__`` and would find this actual repo, so the tests that
need "no checkout either" patch that too.
"""

from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from ai_agents import cli


@pytest.fixture(autouse=True)
def fake_home(tmp_path, monkeypatch):
    """Point HOME at tmp_path so ``init`` never writes a real ``~/.ai-agents``."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _make_catalog(root: Path, agent_name: str = "Bundled") -> Path:
    """A minimal but real catalog: one agent directory with an AGENT.md."""
    agent_dir = root / agent_name
    agent_dir.mkdir(parents=True)
    (agent_dir / "AGENT.md").write_text(
        f"---\nname: {agent_name}\ndescription: seeded from a test\nskills: []\nworkflows: []\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return root


def test_bundled_catalog_is_used_when_present(tmp_path, monkeypatch):
    # The wheel shape: ai_agents/_catalog/ exists, so no checkout is needed.
    bundled = _make_catalog(tmp_path / "_catalog")
    monkeypatch.setattr(cli, "_BUNDLED_CATALOG", bundled)

    assert cli._catalog_source() == bundled


def test_bundled_catalog_wins_over_a_checkout(tmp_path, monkeypatch):
    # A developer with both installed and checked out gets the bundled copy,
    # not an answer that depends on how the interpreter resolved ai_agents.
    bundled = _make_catalog(tmp_path / "_catalog", "FromBundle")
    checkout = _make_catalog(tmp_path / "checkout" / "agents", "FromCheckout")
    monkeypatch.setattr(cli, "_BUNDLED_CATALOG", bundled)
    monkeypatch.setattr(cli, "_checkout_catalog", lambda: checkout)

    assert cli._catalog_source() == bundled


def test_checkout_is_the_fallback_when_nothing_is_bundled(tmp_path, monkeypatch):
    # The editable-install shape: force-include never ran, so _catalog is
    # absent and the checkout's agents/ tree is the catalog.
    checkout = _make_catalog(tmp_path / "checkout" / "agents")
    monkeypatch.setattr(cli, "_BUNDLED_CATALOG", tmp_path / "does-not-exist")
    monkeypatch.setattr(cli, "_checkout_catalog", lambda: checkout)

    assert cli._catalog_source() == checkout


def test_no_catalog_anywhere_raises_instead_of_falling_back_to_cwd(tmp_path, monkeypatch):
    # The regression this task exists to fix. Standing in a directory that
    # happens to hold agents/ must NOT make it the catalog.
    decoy = tmp_path / "somewhere-else"
    _make_catalog(decoy / "agents", "Decoy")
    monkeypatch.chdir(decoy)
    monkeypatch.setattr(cli, "_BUNDLED_CATALOG", tmp_path / "does-not-exist")
    monkeypatch.setattr(cli, "_checkout_catalog", lambda: None)

    with pytest.raises(click.ClickException) as excinfo:
        cli._catalog_source()

    message = str(excinfo.value)
    assert "--source" in message
    # The error names where it looked; it must not have silently used cwd.
    assert str(decoy) not in message


def test_checkout_catalog_finds_this_repos_agents_tree():
    # Not monkeypatched: the developer path resolving against the real
    # checkout these tests run inside is the behaviour being asserted.
    found = cli._checkout_catalog()

    assert found is not None
    assert found.name == "agents"
    assert (found / "stock-screening" / "AGENT.md").is_file()


def test_init_seeds_from_the_bundled_catalog_with_no_source_flag(tmp_path, monkeypatch, fake_home):
    # End to end on the wheel shape: `ai-agents init`, no arguments.
    bundled = _make_catalog(tmp_path / "_catalog", "Bundled")
    monkeypatch.setattr(cli, "_BUNDLED_CATALOG", bundled)

    result = CliRunner().invoke(cli.cli, ["init"])

    assert result.exit_code == 0, result.output
    assert (fake_home / ".ai-agents" / "agents" / "Bundled" / "AGENT.md").is_file()


def test_init_source_flag_still_takes_a_checkout_root(tmp_path, monkeypatch, fake_home):
    # --source keeps its old meaning: the repo root, not the agents/ dir.
    checkout = tmp_path / "checkout"
    _make_catalog(checkout / "agents", "FromSource")
    monkeypatch.setattr(cli, "_BUNDLED_CATALOG", tmp_path / "does-not-exist")

    result = CliRunner().invoke(cli.cli, ["init", "--source", str(checkout)])

    assert result.exit_code == 0, result.output
    assert (fake_home / ".ai-agents" / "agents" / "FromSource" / "AGENT.md").is_file()


def test_init_reports_the_missing_catalog_rather_than_seeding_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_BUNDLED_CATALOG", tmp_path / "does-not-exist")
    monkeypatch.setattr(cli, "_checkout_catalog", lambda: None)

    result = CliRunner().invoke(cli.cli, ["init"])

    assert result.exit_code != 0
    assert "no agent catalog found" in result.output
