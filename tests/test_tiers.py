"""Tier resolution: project -> workspace -> user, closest wins."""

from pathlib import Path

from ai_agents import tiers


def test_resolve_returns_the_three_tiers():
    resolved = tiers.resolve(Path.cwd())

    assert set(resolved) == {"project", "workspace", "user"}
    assert resolved["user"].name == ".ai-agents"
    assert resolved["user"] == Path.home() / ".ai-agents"


def test_project_tier_is_the_git_root_even_with_no_ai_agents_dir(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    nested = repo / "src" / "deep"
    nested.mkdir(parents=True)

    resolved = tiers.resolve(nested)

    assert resolved["project"] == repo.resolve() / ".ai-agents"
    assert not resolved["project"].exists()


def test_no_project_tier_outside_a_git_repo(tmp_path):
    assert tiers.resolve(tmp_path)["project"] is None


def test_workspace_is_an_ancestor_above_the_project(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / ".ai-agents").mkdir(parents=True)
    repo = workspace / "repo"
    (repo / ".git").mkdir(parents=True)

    resolved = tiers.resolve(repo)

    assert resolved["workspace"] == workspace.resolve() / ".ai-agents"
    assert resolved["project"] == repo.resolve() / ".ai-agents"


def test_project_is_never_also_its_own_workspace(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".ai-agents").mkdir()

    resolved = tiers.resolve(repo)

    assert resolved["project"] == repo.resolve() / ".ai-agents"
    assert resolved["workspace"] is None
