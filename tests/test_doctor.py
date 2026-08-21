"""Doctor checks — issue #16, the test coverage half of the story in #6.

``doctor.run_checks`` is the whole implementation (``cli.doctor`` only
renders what it returns — see both modules' docstrings), so nearly every
test here calls ``run_checks`` directly against a synthetic tree built
under ``tmp_path`` and asserts on the returned dicts, the same shape
``test_install``/``test_lifecycle`` already exercise for their own modules.
A handful of tests go through ``click.testing.CliRunner`` instead, because
the exit code — the one piece of behavior ``run_checks`` itself does not
decide — only exists on the CLI side (``cli.doctor`` turns ``has_errors``
into ``raise SystemExit(1)``).

The point of this story is *honest* reporting: an absent harness is not a
defect, a diverged copy is not a defect, but a directory nothing can read
or a pointer aimed at nothing are. So the tests below are organized around
that vocabulary (see ``doctor.py``'s module docstring) rather than around
"call the function, check the dict" — each one pins a specific claim the
docstring makes about why a condition gets the status it gets.

Like ``test_install``/``test_lifecycle``, every test builds its own tier
roots under ``tmp_path`` and the autouse ``fake_home`` fixture points
``HOME`` there too — ``run_checks`` always walks the user tier as well as
project/workspace, and the user tier resolves through ``Path.home()``, so
without this fixture a stray test could read or report on a real
``~/.ai-agents``.
"""

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_agents import doctor, install
from ai_agents.cli import cli

BODY_SENTENCE = "This paragraph belongs to the agent body alone."


@pytest.fixture(autouse=True)
def fake_home(tmp_path, monkeypatch):
    """Point HOME at tmp_path so the user tier never resolves to a real one."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def repo(tmp_path):
    """A git repo with no harness configured yet — the project tier."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    return root


def make_agent(tier_root, name, description="Does a thing.", skills=(), workflows=(), body=BODY_SENTENCE):
    """Write a minimal agent into ``tier_root/agents/<name>/``."""
    agent_dir = tier_root / "agents" / name
    (agent_dir / "Skills").mkdir(parents=True)
    (agent_dir / "Workflows").mkdir(parents=True)
    (agent_dir / "AGENT.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    for skill in skills:
        (agent_dir / "Skills" / f"{skill}.md").write_text(f"# {skill}\n", encoding="utf-8")
    for workflow in workflows:
        (agent_dir / "Workflows" / f"{workflow}.md").write_text(f"# {workflow}\n", encoding="utf-8")
    return agent_dir


def configure(root, *harnesses):
    """Create the configuration each harness is detected by."""
    for harness in harnesses:
        if harness == "claude-code":
            (root / ".claude").mkdir(exist_ok=True)
        elif harness == "cline":
            (root / ".clinerules").mkdir(exist_ok=True)
        elif harness == "gemini-cli":
            (root / ".gemini").mkdir(exist_ok=True)
        elif harness == "qwen-code":
            (root / ".qwen").mkdir(exist_ok=True)
        else:  # pragma: no cover - guards the test helper itself
            raise ValueError(harness)


def init_user_tier(home):
    """Create ``~/.ai-agents`` with nothing in it — the state right after
    ``ai-agents init``, and the precondition for every scenario below that
    is not specifically testing the missing-user-tier ERROR itself."""
    user_root = home / ".ai-agents"
    user_root.mkdir()
    return user_root


def snapshot(*roots):
    """Every path under each root — files keyed to their bytes, directories
    to ``None`` — so a non-mutation claim also catches a stray ``mkdir()``
    that creates nothing but an empty directory, not just a changed file.
    """
    state = {}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        state[root] = None
        for p in root.rglob("*"):
            state[p] = p.read_bytes() if p.is_file() else None
    return state


def find(findings, **fields):
    """The single finding matching every keyword filter, or ``None``."""
    matches = [f for f in findings if all(f.get(k) == v for k, v in fields.items())]
    assert len(matches) <= 1, f"expected at most one match for {fields}, got {matches}"
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# Tiers: resolution, existence, population
# ---------------------------------------------------------------------------


def test_a_tier_with_no_ancestor_is_info_never_error(tmp_path):
    # Not inside a git repo and no ancestor declares a workspace: both are
    # normal, unremarkable conditions per the module docstring, so both must
    # be INFO — the user tier (missing here too, since fake_home only makes
    # the home directory, not ~/.ai-agents) is the one exception, and it is
    # ERROR, which is the whole point of drawing the line where doctor.py
    # says it does.
    outside = tmp_path / "nowhere"
    outside.mkdir()

    report = doctor.run_checks(outside)
    by_tier = {f["tier"]: f for f in report["tiers"]}

    assert by_tier["project"]["root"] is None
    assert by_tier["project"]["status"] == doctor.INFO
    assert by_tier["workspace"]["root"] is None
    assert by_tier["workspace"]["status"] == doctor.INFO
    assert by_tier["user"]["status"] == doctor.ERROR


def test_missing_user_tier_is_the_one_error_among_the_three(repo):
    # Project tier resolves (we're in a repo) but has nothing installed yet:
    # INFO, not ERROR, per tiers.py describing an empty project tier as the
    # normal starting state.
    report = doctor.run_checks(repo)
    by_tier = {f["tier"]: f for f in report["tiers"]}

    project = by_tier["project"]
    assert project["root"] == repo / ".ai-agents"
    assert project["exists"] is False
    assert project["status"] == doctor.INFO
    assert project["fix"] is None

    user = by_tier["user"]
    assert user["status"] == doctor.ERROR
    assert user["detail"] == "user master tier has not been initialized"
    assert user["fix"] == "ai-agents init"
    assert report["has_errors"] is True


def test_a_populated_user_tier_is_ok_not_info_even_when_empty(repo, fake_home):
    # Once ai-agents init has run, an empty user tier is fully normal — OK,
    # not INFO — unlike an empty project/workspace tier. INFO is reserved
    # for a tier that doesn't even resolve or hasn't been installed into;
    # the user tier resolving-and-existing-and-empty is just "nothing to
    # report yet", which is what OK with agent_count == 0 already says.
    init_user_tier(fake_home)

    report = doctor.run_checks(repo)
    user = next(f for f in report["tiers"] if f["tier"] == "user")

    assert user["status"] == doctor.OK
    assert user["exists"] is True
    assert user["agent_count"] == 0
    assert user["fix"] is None


def test_a_populated_project_tier_reports_its_agent_count(repo, fake_home):
    init_user_tier(fake_home)
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "alpha")
    make_agent(tier_root, "zulu")

    report = doctor.run_checks(repo)
    project = next(f for f in report["tiers"] if f["tier"] == "project")

    assert project["status"] == doctor.OK
    assert project["agent_count"] == 2


def test_a_workspace_tier_is_reported_by_name_and_counted(tmp_path, fake_home):
    # The workspace tier is resolved from an ancestor directory above the
    # project, not the project itself — exercise that indirection too,
    # since _TIER_NAMES walks all three the same way.
    init_user_tier(fake_home)
    workspace_root = tmp_path / "workspace"
    (workspace_root / ".ai-agents" / "agents").mkdir(parents=True)
    make_agent(workspace_root / ".ai-agents", "shared")
    project = workspace_root / "repo"
    (project / ".git").mkdir(parents=True)

    report = doctor.run_checks(project)
    workspace = next(f for f in report["tiers"] if f["tier"] == "workspace")

    assert workspace["root"] == workspace_root / ".ai-agents"
    assert workspace["status"] == doctor.OK
    assert workspace["agent_count"] == 1


# ---------------------------------------------------------------------------
# Harnesses: absence is normal, presence is named, shape is checked
# ---------------------------------------------------------------------------


def test_absent_harnesses_are_info_and_name_every_probed_path(repo, fake_home):
    # The single most important guarantee in this story: an absent optional
    # harness is INFO, and it says exactly what was probed (from
    # install.harness_probes, not a second-guessed copy of it) rather than
    # a bare "not found".
    init_user_tier(fake_home)

    report = doctor.run_checks(repo)
    project_harnesses = [f for f in report["harnesses"] if f["tier"] == "project"]

    assert len(project_harnesses) == len(install.HARNESSES)
    for f in project_harnesses:
        assert f["detected"] is False
        assert f["status"] == doctor.INFO
        assert f["matched"] is None
        expected_probed = [p.path for p in install.harness_probes(f["harness"], repo / ".ai-agents", "project")]
        assert f["probed"] == expected_probed
        assert f["probed"]  # never an empty list to name


def test_an_absent_harness_never_flips_the_exit_code(repo, fake_home, monkeypatch):
    # Same guarantee, from the CLI's side: several harnesses absent, tiers
    # otherwise healthy, exit code must be zero.
    init_user_tier(fake_home)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "0 error(s)" not in result.output  # the all-clear line, not an error tally
    assert "All checks passed." in result.output


def test_a_detected_harness_is_ok_and_names_what_matched(repo, fake_home):
    init_user_tier(fake_home)
    configure(repo, "claude-code")

    report = doctor.run_checks(repo)
    finding = find(report["harnesses"], tier="project", harness="claude-code")

    assert finding["detected"] is True
    assert finding["status"] == doctor.OK
    assert finding["matched"] == repo / ".claude"


def test_a_regular_file_named_dot_claude_reports_absent_not_detected(repo, fake_home):
    # Probe shape matters: a file, not a directory, named .claude must not
    # register as Claude Code in use — see install.Probe's own docstring on
    # why bare existence is not enough.
    init_user_tier(fake_home)
    (repo / ".claude").write_text("oops, not a directory\n", encoding="utf-8")

    report = doctor.run_checks(repo)
    finding = find(report["harnesses"], tier="project", harness="claude-code")

    assert finding["detected"] is False
    assert finding["status"] == doctor.INFO
    assert finding["matched"] is None


def test_gemini_detected_via_bare_context_file_names_the_file_not_the_dir(repo, fake_home):
    # A context-file harness can be detected by either its config directory
    # or a bare context file. Here only the file exists, so "matched" must
    # name the file (probed[1]) — naming probed[0] unconditionally (the
    # .gemini/ directory, which does not exist) would be a lie.
    init_user_tier(fake_home)
    (repo / "GEMINI.md").write_text("# notes\n", encoding="utf-8")

    report = doctor.run_checks(repo)
    finding = find(report["harnesses"], tier="project", harness="gemini-cli")

    assert finding["detected"] is True
    expected_probes = [p.path for p in install.harness_probes("gemini-cli", repo / ".ai-agents", "project")]
    assert finding["probed"] == expected_probes
    assert finding["matched"] == expected_probes[1]
    assert finding["matched"] != expected_probes[0]
    assert not (repo / ".gemini").exists()


def test_gemini_detected_via_config_dir_names_the_dir(repo, fake_home):
    # The mirror image of the previous test: only the directory exists, so
    # matched must be probed[0] this time — confirming "matched" tracks
    # whichever probe actually hit rather than always picking one index.
    init_user_tier(fake_home)
    configure(repo, "gemini-cli")

    report = doctor.run_checks(repo)
    finding = find(report["harnesses"], tier="project", harness="gemini-cli")

    expected_probes = [p.path for p in install.harness_probes("gemini-cli", repo / ".ai-agents", "project")]
    assert finding["matched"] == expected_probes[0]


# ---------------------------------------------------------------------------
# Agents: integrity (no AGENT.md)
# ---------------------------------------------------------------------------


def test_an_agent_directory_with_no_agent_md_is_error_with_a_fix(repo, fake_home):
    init_user_tier(fake_home)
    tier_root = repo / ".ai-agents"
    broken_dir = tier_root / "agents" / "broken"
    broken_dir.mkdir(parents=True)  # no AGENT.md written

    report = doctor.run_checks(repo)
    finding = find(report["agents"], tier="project", agent="broken")

    assert finding["status"] == doctor.ERROR
    assert "no AGENT.md" in finding["detail"]
    assert finding["fix"] == "ai-agents remove broken --project, then ai-agents install broken --project"
    assert report["has_errors"] is True


def test_a_broken_agent_at_the_user_tier_has_no_cli_mutation_fix(fake_home):
    # The user tier has no CLI command that edits it directly, so its fix
    # message must say so instead of naming a remove/install incantation
    # that does not exist for that tier.
    user_root = init_user_tier(fake_home)
    (user_root / "agents" / "broken").mkdir(parents=True)

    report = doctor.run_checks(fake_home)
    finding = find(report["agents"], tier="user", agent="broken")

    assert finding["status"] == doctor.ERROR
    assert "no CLI command that edits the user tier directly" in finding["fix"]


def test_a_directory_with_an_agent_md_is_not_flagged(repo, fake_home):
    init_user_tier(fake_home)
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "fine")

    report = doctor.run_checks(repo)

    assert find(report["agents"], tier="project", agent="fine", status=doctor.ERROR) is None


# ---------------------------------------------------------------------------
# Agents: stale per-agent pointers
# ---------------------------------------------------------------------------


def test_a_generated_pointer_with_no_agent_directory_is_error(repo, fake_home):
    init_user_tier(fake_home)
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "ghost")
    configure(repo, "claude-code")
    install.generate_harness_adapters("ghost", tier_root)
    pointer = repo / ".claude" / "agents" / "ghost.md"
    assert pointer.is_file()

    # The agent directory disappears (by hand, or via a bug elsewhere) but
    # the pointer it generated is left behind, aimed at nothing.
    shutil.rmtree(tier_root / "agents" / "ghost")

    report = doctor.run_checks(repo)
    finding = find(report["agents"], tier="project", agent="ghost")

    assert finding["status"] == doctor.ERROR
    assert "claude-code pointer" in finding["detail"]
    assert "AGENT.md is gone" in finding["detail"]
    assert finding["fix"] == f"rm '{pointer}'"


def test_a_hand_authored_pointer_with_no_matching_agent_is_not_flagged(repo, fake_home):
    # No GENERATED_MARKER in this file: it was never ours to judge, even
    # though it looks exactly like a stale pointer from the outside (no
    # agent directory of that name exists either).
    init_user_tier(fake_home)
    tier_root = repo / ".ai-agents"
    # The tier itself must exist and be scanned (an agent's presence isn't
    # required — the pointer check runs over tier_root/agents regardless of
    # whether *this* agent name is among them) or _check_agents never runs
    # at all and the assertion below would pass for the wrong reason.
    (tier_root / "agents").mkdir(parents=True)
    pointer_dir = repo / ".claude" / "agents"
    pointer_dir.mkdir(parents=True)
    (pointer_dir / "someones-notes.md").write_text("my own subagent, hand written\n", encoding="utf-8")

    report = doctor.run_checks(repo)

    assert find(report["agents"], tier="project", agent="someones-notes") is None
    assert report["has_errors"] is False


def test_a_current_generated_pointer_is_not_flagged(repo, fake_home):
    # The positive control for the previous two tests: a generated pointer
    # whose agent directory still exists must not appear in the report at
    # all.
    init_user_tier(fake_home)
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "claude-code")
    install.generate_harness_adapters("demo", tier_root)

    report = doctor.run_checks(repo)

    assert find(report["agents"], tier="project", agent="demo", status=doctor.ERROR) is None


# ---------------------------------------------------------------------------
# Agents: drift
# ---------------------------------------------------------------------------


def test_drift_is_warn_and_never_flips_the_exit_code(repo, fake_home, monkeypatch):
    user_root = init_user_tier(fake_home)
    make_agent(user_root, "demo", skills=["alpha"])
    tier_root = repo / ".ai-agents"
    install.copy_agent("demo", user_root, tier_root)
    (tier_root / "agents" / "demo" / "Skills" / "mine.md").write_text("# mine\n", encoding="utf-8")

    report = doctor.run_checks(repo)
    finding = find(report["agents"], tier="project", agent="demo")

    assert finding["status"] == doctor.WARN
    assert "diverged from the user master copy" in finding["detail"]
    assert "ai-agents diff demo --project" in finding["fix"]
    # Drift is the one condition the module docstring names as possibly
    # intentional, so it must not contribute to has_errors...
    assert report["has_errors"] is False

    # ...nor to the CLI exit code.
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(cli, ["doctor"])
    assert result.exit_code == 0
    assert "1 warning(s) — nothing broken." in result.output


def test_an_undiverged_copy_is_ok(repo, fake_home):
    user_root = init_user_tier(fake_home)
    make_agent(user_root, "demo", skills=["alpha"])
    tier_root = repo / ".ai-agents"
    install.copy_agent("demo", user_root, tier_root)

    report = doctor.run_checks(repo)
    finding = find(report["agents"], tier="project", agent="demo")

    assert finding["status"] == doctor.OK
    assert finding["detail"] == "matches the user master copy"
    assert finding["fix"] is None


def test_an_agent_absent_from_the_master_is_info_not_a_defect(repo, fake_home):
    # A project-only agent nobody ever installed from the catalog: nothing
    # requires it to trace back to the master, so there is nothing to diff
    # and nothing to warn about.
    init_user_tier(fake_home)
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "local-only")

    report = doctor.run_checks(repo)
    finding = find(report["agents"], tier="project", agent="local-only")

    assert finding["status"] == doctor.INFO
    assert "not present in the user master copy" in finding["detail"]
    assert finding["fix"] is None


def test_the_user_tier_itself_is_never_diffed_against_itself(fake_home):
    # _check_agents skips the drift finding entirely at the user tier — it
    # is the master, so there is nothing above it to compare against.
    user_root = init_user_tier(fake_home)
    make_agent(user_root, "demo")

    report = doctor.run_checks(fake_home)
    user_agent_findings = [f for f in report["agents"] if f["tier"] == "user"]

    assert user_agent_findings == []


# ---------------------------------------------------------------------------
# General properties over the whole report
# ---------------------------------------------------------------------------


def test_every_error_carries_a_fix(repo, fake_home):
    # A combined-breakage scenario exercising three independent ERROR
    # conditions at once (missing user tier, an unreadable agent directory,
    # a stale generated pointer), asserted as one property over the whole
    # report rather than three separate spot checks — the point being that
    # this must hold no matter *which* ERROR conditions are present, not
    # just the ones this test happens to construct.
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "fine")
    (tier_root / "agents" / "broken").mkdir(parents=True)
    configure(repo, "claude-code")
    make_agent(tier_root, "ghost")
    install.generate_harness_adapters("ghost", tier_root)
    shutil.rmtree(tier_root / "agents" / "ghost")
    # fake_home's ~/.ai-agents is deliberately left uninitialized here too.

    report = doctor.run_checks(repo)
    all_findings = (*report["tiers"], *report["harnesses"], *report["agents"])
    errors = [f for f in all_findings if f["status"] == doctor.ERROR]

    assert len(errors) >= 3
    assert all(f["fix"] for f in errors)
    assert report["has_errors"] is True


def test_run_checks_is_non_mutating(repo, fake_home):
    # The strongest form of "purely reads": snapshot every path under both
    # the project repo and the fake home directory, not just "the agent
    # still exists" — this must catch even a stray mkdir() with nothing put
    # in it. Exercises a rich mix: absent and present harnesses, a
    # diverged agent, a broken agent directory, and a stale pointer, all at
    # once, so there is plenty for a hidden write to land on.
    user_root = init_user_tier(fake_home)
    make_agent(user_root, "demo", skills=["alpha"], workflows=["beta"])
    tier_root = repo / ".ai-agents"
    install.copy_agent("demo", user_root, tier_root)
    (tier_root / "agents" / "demo" / "Skills" / "mine.md").write_text("# mine\n", encoding="utf-8")
    (tier_root / "agents" / "broken").mkdir(parents=True)
    configure(repo, "claude-code", "gemini-cli")
    install.generate_harness_adapters("demo", tier_root)
    make_agent(tier_root, "ghost")
    install.generate_harness_adapters("ghost", tier_root)
    shutil.rmtree(tier_root / "agents" / "ghost")

    before = snapshot(repo, fake_home)
    doctor.run_checks(repo)
    after = snapshot(repo, fake_home)

    assert after == before


def test_exit_code_nonzero_on_genuine_breakage(repo, fake_home, monkeypatch):
    init_user_tier(fake_home)
    tier_root = repo / ".ai-agents"
    (tier_root / "agents" / "broken").mkdir(parents=True)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(cli, ["doctor"])

    assert result.exit_code == 1
    assert "error(s)" in result.output
