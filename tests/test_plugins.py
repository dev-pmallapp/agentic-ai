"""External plugin install and removal — issue #39, the story in #38.

The whole point of ``plugins.py`` is a set of promises about what it does
*not* touch, so most of what follows asserts absence: the catalog cannot
see a plugin, removing one leaves everything else alone, and a plugin's
own contents come through unaltered.

Like ``test_install`` and ``test_lifecycle``, everything here writes
files, so each test builds tier roots under ``tmp_path`` and an autouse
fixture points ``HOME`` somewhere temporary — ``tiers.user_root`` goes
through ``Path.home()``, and a stray test must never be able to write
into a real ``~/.ai-agents``.
"""

import json
from pathlib import Path

import pytest

from ai_agents import catalog, doctor, plugins


@pytest.fixture(autouse=True)
def fake_home(tmp_path, monkeypatch):
    """Point HOME at tmp_path so the user tier never resolves to a real one."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def tier(tmp_path):
    """An empty tier root, with an ``agents/`` dir holding one real agent.

    The agent is here so every "plugins do not disturb the catalog" test
    has something concrete to be undisturbed.
    """
    root = tmp_path / "tier" / ".ai-agents"
    agent = root / "agents" / "keeper"
    agent.mkdir(parents=True)
    (agent / "AGENT.md").write_text(
        "---\nname: keeper\ndescription: A real catalog agent.\nskills: []\n"
        "workflows: []\n---\n\n# keeper\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def source(tmp_path):
    """A plugin source tree with nested dirs and a non-markdown file."""
    src = tmp_path / "src" / "forge"
    (src / "hooks").mkdir(parents=True)
    (src / ".claude-plugin").mkdir(parents=True)
    (src / "hooks" / "session-start.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    (src / "hooks" / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
    (src / ".claude-plugin" / "plugin.json").write_text('{"name": "forge"}\n', encoding="utf-8")
    (src / "README.md").write_text("# forge\n", encoding="utf-8")
    return src


REASON = "hooks.json is a Claude-Code-specific registration schema with no cross-harness equivalent"


def _install(source, tier, **kw):
    kw.setdefault("reason", REASON)
    return plugins.install_plugin(source, tier, **kw)


# --------------------------------------------------------------------------
# Native form
# --------------------------------------------------------------------------


def test_install_copies_the_tree_verbatim(source, tier):
    """Every file arrives with its path and bytes unchanged — no reshaping."""
    _install(source, tier)

    dst = plugins.plugins_dir(tier) / "forge"
    expected = {
        p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()
    }
    actual = {p.relative_to(dst): p.read_bytes() for p in dst.rglob("*") if p.is_file()}

    assert actual == expected
    # Named explicitly: these are the two files the story says cannot bend,
    # and they must survive in their native form rather than being dropped.
    assert (dst / "hooks" / "hooks.json").is_file()
    assert (dst / ".claude-plugin" / "plugin.json").is_file()


def test_install_lands_beside_agents_not_inside_them(source, tier):
    _install(source, tier)

    assert (tier / "plugins" / "forge").is_dir()
    assert not (tier / "agents" / "forge").exists()
    assert sorted(p.name for p in (tier / "agents").iterdir()) == ["keeper"]


def test_plugin_name_defaults_to_the_source_directory_name(source, tier):
    record = _install(source, tier)
    assert record["name"] == "forge"


def test_name_can_be_overridden(source, tier):
    record = _install(source, tier, name="forge-legacy")
    assert record["name"] == "forge-legacy"
    assert (plugins.plugins_dir(tier) / "forge-legacy").is_dir()
    assert not (plugins.plugins_dir(tier) / "forge").exists()


# --------------------------------------------------------------------------
# The catalog cannot see a plugin
# --------------------------------------------------------------------------


def test_list_agents_ignores_an_installed_plugin(source, tier):
    before = [a["name"] for a in catalog.list_agents(tier)]
    _install(source, tier)
    after = [a["name"] for a in catalog.list_agents(tier)]

    assert before == after == ["keeper"]


def test_list_agents_ignores_a_plugin_that_contains_its_own_agent(source, tier):
    """The case a sloppier layout would leak.

    A plugin is free to carry a directory called ``agents/`` with an
    ``AGENT.md`` in it — Forge-shaped plugins plausibly do. Because
    ``plugins/`` is a sibling of the tier's ``agents/`` rather than
    anything nested inside it, ``list_agents`` still cannot reach it.
    This is the test that would fail first if someone moved plugins under
    ``agents/`` for tidiness.
    """
    stowaway = source / "agents" / "impostor"
    stowaway.mkdir(parents=True)
    (stowaway / "AGENT.md").write_text(
        "---\nname: impostor\ndescription: Should never be listed.\n---\n",
        encoding="utf-8",
    )

    _install(source, tier)

    names = [a["name"] for a in catalog.list_agents(tier)]
    assert names == ["keeper"]
    # It really is on disk — the point is that the catalog does not reach it.
    assert (plugins.plugins_dir(tier) / "forge" / "agents" / "impostor" / "AGENT.md").is_file()


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------


def test_install_records_source_and_reason(source, tier):
    _install(source, tier)

    manifest = json.loads(plugins.manifest_path(tier).read_text(encoding="utf-8"))
    record = manifest["plugins"]["forge"]

    assert record["source"] == str(source.resolve())
    assert record["reason"] == REASON
    assert record["installed"]
    assert manifest["schema_version"] == plugins.SCHEMA_VERSION


def test_reason_is_required(source, tier):
    with pytest.raises(TypeError):
        plugins.install_plugin(source, tier)


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_blank_reason_is_refused(source, tier, blank):
    """The obvious way around a required argument, closed."""
    with pytest.raises(plugins.PluginError, match="reason is required"):
        plugins.install_plugin(source, tier, reason=blank)
    assert not plugins.plugins_dir(tier).exists()


def test_list_plugins_reports_records_with_presence(source, tier):
    _install(source, tier)
    (recorded,) = plugins.list_plugins(tier)

    assert recorded["name"] == "forge"
    assert recorded["present"] is True
    assert recorded["reason"] == REASON


def test_list_plugins_is_empty_for_a_tier_with_no_manifest(tier):
    assert plugins.list_plugins(tier) == []


def test_a_malformed_manifest_raises_rather_than_reading_as_empty(tier):
    """Deliberately the opposite of how ``catalog`` treats broken markdown.

    Returning ``{}`` here would make every caller confidently report "no
    external plugins" while a ``plugins/`` tree sat on disk beside it.
    """
    plugins.manifest_path(tier).parent.mkdir(parents=True, exist_ok=True)
    plugins.manifest_path(tier).write_text("{not json", encoding="utf-8")

    with pytest.raises(plugins.PluginError, match="not readable JSON"):
        plugins.read_manifest(tier)


def test_a_json_document_that_is_not_a_manifest_raises(tier):
    plugins.manifest_path(tier).parent.mkdir(parents=True, exist_ok=True)
    plugins.manifest_path(tier).write_text('["a", "list"]', encoding="utf-8")

    with pytest.raises(plugins.PluginError, match="not a plugin manifest"):
        plugins.read_manifest(tier)


# --------------------------------------------------------------------------
# Never overwrite without force
# --------------------------------------------------------------------------


def test_install_refuses_to_replace_an_existing_plugin(source, tier):
    _install(source, tier)
    (plugins.plugins_dir(tier) / "forge" / "LOCAL-EDIT.md").write_text("mine\n", encoding="utf-8")

    with pytest.raises(plugins.PluginError, match="already installed"):
        _install(source, tier)

    assert (plugins.plugins_dir(tier) / "forge" / "LOCAL-EDIT.md").is_file()


def test_force_replaces_the_plugin_entirely(source, tier):
    _install(source, tier)
    (plugins.plugins_dir(tier) / "forge" / "LOCAL-EDIT.md").write_text("mine\n", encoding="utf-8")

    _install(source, tier, force=True, reason="second pass")

    assert not (plugins.plugins_dir(tier) / "forge" / "LOCAL-EDIT.md").exists()
    assert (plugins.plugins_dir(tier) / "forge" / "README.md").is_file()
    assert plugins.list_plugins(tier)[0]["reason"] == "second pass"


@pytest.mark.parametrize("bad", ["../escape", "a/b", "", ".", "..", "x/"])
def test_a_name_that_is_a_path_is_refused(source, tier, bad):
    """A name becomes a path segment, so a separator would escape the tier."""
    with pytest.raises(plugins.PluginError, match="invalid plugin name"):
        _install(source, tier, name=bad)


def test_install_raises_when_the_source_is_not_a_directory(tmp_path, tier):
    missing = tmp_path / "nope"
    with pytest.raises(plugins.PluginError, match="not a directory"):
        _install(missing, tier)


# --------------------------------------------------------------------------
# Removal removes only what was installed
# --------------------------------------------------------------------------


def test_remove_deletes_the_plugin_and_its_record(source, tier):
    _install(source, tier)
    result = plugins.remove_plugin("forge", tier)

    assert result["removed_dir"] is True
    assert result["removed_record"] is True
    assert not (plugins.plugins_dir(tier) / "forge").exists()
    assert plugins.list_plugins(tier) == []


def test_remove_leaves_the_catalog_and_other_plugins_alone(source, tier, tmp_path):
    other = tmp_path / "src" / "other"
    other.mkdir(parents=True)
    (other / "keep.txt").write_text("keep\n", encoding="utf-8")

    _install(source, tier)
    _install(other, tier)

    plugins.remove_plugin("forge", tier)

    # The other plugin, its record, and the whole catalog survive.
    assert (plugins.plugins_dir(tier) / "other" / "keep.txt").is_file()
    assert [p["name"] for p in plugins.list_plugins(tier)] == ["other"]
    assert (tier / "agents" / "keeper" / "AGENT.md").is_file()
    assert [a["name"] for a in catalog.list_agents(tier)] == ["keeper"]
    # The manifest file itself is still there — only the one entry went.
    assert plugins.manifest_path(tier).is_file()


def test_remove_on_an_unknown_plugin_raises(tier):
    with pytest.raises(plugins.PluginError, match="not installed"):
        plugins.remove_plugin("ghost", tier)


def test_remove_repairs_a_record_with_no_directory(source, tier):
    """Half-installed states are reachable to the same end state, not refused."""
    _install(source, tier)
    import shutil

    shutil.rmtree(plugins.plugins_dir(tier) / "forge")

    result = plugins.remove_plugin("forge", tier)
    assert result["removed_dir"] is False
    assert result["removed_record"] is True
    assert plugins.list_plugins(tier) == []


def test_remove_repairs_a_directory_with_no_record(source, tier):
    orphan = plugins.plugins_dir(tier) / "stray"
    orphan.mkdir(parents=True)
    (orphan / "f.txt").write_text("x", encoding="utf-8")

    result = plugins.remove_plugin("stray", tier)
    assert result["removed_dir"] is True
    assert result["removed_record"] is False
    assert not orphan.exists()


@pytest.mark.parametrize("bad", ["../keeper", "a/b", ".."])
def test_remove_refuses_a_name_that_is_a_path(tier, bad):
    """Without this, ``remove ../agents`` would delete the catalog."""
    with pytest.raises(plugins.PluginError, match="invalid plugin name"):
        plugins.remove_plugin(bad, tier)
    assert (tier / "agents" / "keeper").is_dir()


# --------------------------------------------------------------------------
# doctor reports them
# --------------------------------------------------------------------------


def _project_tier(tmp_path):
    """A tier root inside a git repo, so ``tiers.resolve`` finds it as project.

    Also creates the user master tier. Without it ``_check_tier`` reports
    a missing user tier as an ERROR — correct, and documented in
    ``doctor.py`` — which would make every ``has_errors`` assertion below
    pass or fail for a reason that has nothing to do with plugins.
    """
    (Path.home() / ".ai-agents" / "agents").mkdir(parents=True, exist_ok=True)
    repo = tmp_path / "work" / "repo"
    (repo / ".git").mkdir(parents=True)
    root = repo / ".ai-agents"
    (root / "agents").mkdir(parents=True)
    return repo, root


def test_doctor_reports_an_installed_plugin(tmp_path, source):
    repo, root = _project_tier(tmp_path)
    _install(source, root)

    report = doctor.run_checks(repo)
    findings = [f for f in report["plugins"] if f["plugin"] == "forge"]

    assert len(findings) == 1
    assert findings[0]["status"] == doctor.OK
    assert findings[0]["reason"] == REASON
    assert report["has_errors"] is False


def test_doctor_flags_a_record_whose_directory_is_gone(tmp_path, source):
    repo, root = _project_tier(tmp_path)
    _install(source, root)
    import shutil

    shutil.rmtree(plugins.plugins_dir(root) / "forge")

    report = doctor.run_checks(repo)
    (finding,) = [f for f in report["plugins"] if f["plugin"] == "forge"]

    assert finding["status"] == doctor.ERROR
    assert report["has_errors"] is True


def test_doctor_warns_about_an_unrecorded_plugin_on_disk(tmp_path):
    repo, root = _project_tier(tmp_path)
    (plugins.plugins_dir(root) / "mystery").mkdir(parents=True)

    report = doctor.run_checks(repo)
    (finding,) = [f for f in report["plugins"] if f["plugin"] == "mystery"]

    assert finding["status"] == doctor.WARN
    # Provenance, not function, is what was lost — so not an error.
    assert report["has_errors"] is False


def test_doctor_reports_a_corrupt_manifest_once_without_crashing(tmp_path):
    repo, root = _project_tier(tmp_path)
    plugins.manifest_path(root).write_text("{broken", encoding="utf-8")

    report = doctor.run_checks(repo)
    findings = [f for f in report["plugins"] if f["tier"] == "project"]

    assert len(findings) == 1
    assert findings[0]["plugin"] is None
    assert findings[0]["status"] == doctor.ERROR
    assert report["has_errors"] is True


def test_doctor_reports_no_plugins_for_a_tier_that_has_none(tmp_path):
    repo, _ = _project_tier(tmp_path)
    report = doctor.run_checks(repo)
    assert report["plugins"] == []
