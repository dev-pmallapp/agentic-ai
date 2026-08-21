"""Update, diff, and remove an already-installed agent.

Like ``test_install``, everything here writes files, so every test builds
a synthetic pair of tier roots (a "master" source and an "installed"
destination) under ``tmp_path``, and an autouse fixture points ``HOME`` at
a temporary directory too — ``install.tier_name_for`` and the user-tier
harness locations both go through ``Path.home()``, so without this fixture
a stray test could write into a real ``~/.claude``.

``lifecycle.diff_agent``/``update_agent``/``remove_agent`` are thin
wrappers around ``install.copy_agent`` and ``install.remove_harness_adapters``
— the interesting behavior to pin down here is not "does copytree work" but
the guarantees ``lifecycle``'s own docstrings promise on top of that: the
divergence definition is symmetric (added, deleted, and edited files must
each trip it independently), a refused update must leave nothing touched,
a diff must never write anything at all, and removal must respect the same
hand-authored-file rule installation does while re-rendering the shared
context block around whichever agents are left.
"""

from pathlib import Path

import pytest

from ai_agents import install, lifecycle

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
    """A git repo with no harness configured yet — the destination tier."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    return root


@pytest.fixture
def master(tmp_path):
    """A second tier root standing in for "the higher tier an agent came from"."""
    return tmp_path / "master"


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


def snapshot(*roots):
    """Every regular file under each root, keyed by absolute path, to its bytes.

    Used to assert an operation is non-mutating: a stronger check than "the
    agent directory still exists", since it also catches a stray write to a
    harness pointer, a context-file block, or anything else under the roots.
    """
    state = {}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file():
                state[p] = p.read_bytes()
    return state


# ---------------------------------------------------------------------------
# diff_agent
# ---------------------------------------------------------------------------


def test_diff_reports_no_divergence_for_an_identical_copy(master, repo):
    make_agent(master, "demo", skills=["alpha"])
    install.copy_agent("demo", master, repo / ".ai-agents")

    diff = lifecycle.diff_agent("demo", master, repo / ".ai-agents")

    assert diff == {"diverged": False, "master_only": [], "local_only": [], "changed": []}


def test_diff_flags_a_locally_added_file(master, repo):
    # A file only the local copy has — not present upstream — is exactly
    # the kind of on-purpose local edit the never-overwrite default exists
    # to protect, and diff's symmetric definition must catch it too.
    make_agent(master, "demo")
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    (dst_root / "agents" / "demo" / "Skills" / "mine.md").write_text("# mine\n", encoding="utf-8")

    diff = lifecycle.diff_agent("demo", master, dst_root)

    assert diff["diverged"] is True
    assert diff["local_only"] == ["Skills/mine.md"]
    assert diff["master_only"] == []
    assert diff["changed"] == []


def test_diff_flags_a_locally_deleted_file(master, repo):
    # The reverse case: a file the master still has that the local copy no
    # longer does. An update recopying from source would restore it, so
    # this must count as divergence just as much as an addition does.
    make_agent(master, "demo", skills=["alpha"])
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    (dst_root / "agents" / "demo" / "Skills" / "alpha.md").unlink()

    diff = lifecycle.diff_agent("demo", master, dst_root)

    assert diff["diverged"] is True
    assert diff["master_only"] == ["Skills/alpha.md"]
    assert diff["local_only"] == []
    assert diff["changed"] == []


def test_diff_flags_a_locally_edited_file(master, repo):
    # Same path on both sides, different bytes — the third independent way
    # to diverge, distinct from a pure add or a pure delete.
    make_agent(master, "demo")
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    agent_md = dst_root / "agents" / "demo" / "AGENT.md"
    agent_md.write_text(agent_md.read_text(encoding="utf-8") + "\nHand-edited addendum.\n", encoding="utf-8")

    diff = lifecycle.diff_agent("demo", master, dst_root)

    assert diff["diverged"] is True
    assert diff["changed"] == ["AGENT.md"]
    assert diff["master_only"] == []
    assert diff["local_only"] == []


def test_diff_is_non_mutating(master, repo):
    # The strongest form of this assertion: snapshot every file's bytes
    # under both roots, not just "the agent dir still exists" — diff is
    # meant to be safe to call from a CLI `diff` command with zero side
    # effects, including on harness pointers it never touches.
    make_agent(master, "demo", skills=["alpha"], workflows=["beta"])
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    configure(repo, "claude-code", "gemini-cli")
    install.generate_harness_adapters("demo", dst_root)
    (dst_root / "agents" / "demo" / "Skills" / "mine.md").write_text("# mine\n", encoding="utf-8")

    before = snapshot(master, repo)
    lifecycle.diff_agent("demo", master, dst_root)
    after = snapshot(master, repo)

    assert after == before


def test_diff_raises_when_missing_from_master(master, repo):
    make_agent(repo / ".ai-agents", "demo")

    with pytest.raises(FileNotFoundError):
        lifecycle.diff_agent("demo", master, repo / ".ai-agents")


def test_diff_raises_when_not_installed_locally(master, repo):
    make_agent(master, "demo")

    with pytest.raises(FileNotFoundError):
        lifecycle.diff_agent("demo", master, repo / ".ai-agents")


# ---------------------------------------------------------------------------
# update_agent
# ---------------------------------------------------------------------------


def test_update_refreshes_a_clean_install_from_master(master, repo):
    make_agent(master, "demo", skills=["alpha"])
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)

    diff = lifecycle.update_agent("demo", master, dst_root)

    assert diff["diverged"] is False
    assert (dst_root / "agents" / "demo" / "Skills" / "alpha.md").is_file()
    assert lifecycle.diff_agent("demo", master, dst_root)["diverged"] is False


def test_update_picks_up_a_master_only_addition_without_force(master, repo):
    # The whole point of update: master grew a skill since install, the
    # local copy was never touched, so there is nothing to protect and no
    # flag to reach for. Requiring --force here would make every routine
    # refresh need the same flag as "overwrite my edits", which is how a
    # safety flag stops being read at all. See lifecycle.local_evidence.
    make_agent(master, "demo")
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    (master / "agents" / "demo" / "Skills" / "gamma.md").write_text("# gamma\n", encoding="utf-8")

    diff = lifecycle.update_agent("demo", master, dst_root)

    assert diff["master_only"] == ["Skills/gamma.md"]
    assert (dst_root / "agents" / "demo" / "Skills" / "gamma.md").is_file()
    assert lifecycle.diff_agent("demo", master, dst_root)["diverged"] is False


def test_a_locally_deleted_file_is_restored_rather_than_blocking(master, repo):
    # The accepted cost of the rule above: a file deleted here looks exactly
    # like a file master has since added, so update restores it. That
    # resurrects something unwanted rather than destroying something wanted
    # — and diff still reports it under master_only beforehand.
    make_agent(master, "demo", skills=["alpha"])
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    (dst_root / "agents" / "demo" / "Skills" / "alpha.md").unlink()

    assert lifecycle.diff_agent("demo", master, dst_root)["master_only"] == ["Skills/alpha.md"]

    lifecycle.update_agent("demo", master, dst_root)

    assert (dst_root / "agents" / "demo" / "Skills" / "alpha.md").is_file()


def test_a_master_only_addition_does_not_excuse_a_local_edit(master, repo):
    # Both kinds of drift at once: the upstream addition is free, but the
    # local edit still blocks, so a busy master cannot smuggle an
    # overwrite past the guard.
    make_agent(master, "demo")
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    (master / "agents" / "demo" / "Skills" / "gamma.md").write_text("# gamma\n", encoding="utf-8")
    edited = dst_root / "agents" / "demo" / "AGENT.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "\nMy note.\n", encoding="utf-8")

    with pytest.raises(lifecycle.LocalDivergenceError):
        lifecycle.update_agent("demo", master, dst_root)

    assert "My note." in edited.read_text(encoding="utf-8")


def test_update_refuses_when_the_local_copy_has_diverged(master, repo):
    make_agent(master, "demo")
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    edited = dst_root / "agents" / "demo" / "AGENT.md"
    original_bytes = edited.read_bytes()
    edited.write_text(edited.read_text(encoding="utf-8") + "\nMy note.\n", encoding="utf-8")

    with pytest.raises(lifecycle.LocalDivergenceError) as excinfo:
        lifecycle.update_agent("demo", master, dst_root)

    assert excinfo.value.name == "demo"
    assert excinfo.value.diff["changed"] == ["AGENT.md"]
    # Refused update must leave the local copy exactly as it was — the
    # divergence check has to run in full before any deletion is even
    # considered.
    assert edited.read_bytes() != original_bytes  # still holds the hand edit
    assert "My note." in edited.read_text(encoding="utf-8")


def test_a_refused_update_touches_nothing(master, repo):
    # Stronger than the previous test: snapshot every file under both
    # roots, not just the one file we know we edited.
    make_agent(master, "demo", skills=["alpha"], workflows=["beta"])
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    (dst_root / "agents" / "demo" / "Skills" / "mine.md").write_text("# mine\n", encoding="utf-8")

    before = snapshot(master, repo)
    with pytest.raises(lifecycle.LocalDivergenceError):
        lifecycle.update_agent("demo", master, dst_root)
    after = snapshot(master, repo)

    assert after == before


def test_force_update_overwrites_a_diverged_local_copy(master, repo):
    make_agent(master, "demo", description="Original.", skills=["alpha"])
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    local_extra = dst_root / "agents" / "demo" / "Skills" / "mine.md"
    local_extra.write_text("# mine\n", encoding="utf-8")

    diff = lifecycle.update_agent("demo", master, dst_root, force=True)

    assert diff["diverged"] is True
    assert diff["local_only"] == ["Skills/mine.md"]
    # Force replaces wholesale: the locally-added file is gone, and the
    # copy now matches master exactly.
    assert not local_extra.exists()
    assert lifecycle.diff_agent("demo", master, dst_root)["diverged"] is False


def test_update_on_a_not_installed_agent_raises(master, repo):
    make_agent(master, "demo")

    with pytest.raises(FileNotFoundError):
        lifecycle.update_agent("demo", master, repo / ".ai-agents")


# ---------------------------------------------------------------------------
# remove_agent
# ---------------------------------------------------------------------------


def test_remove_deletes_the_agent_directory_and_its_pointers(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo", skills=["alpha"])
    configure(repo, "claude-code")
    install.generate_harness_adapters("demo", tier_root)
    pointer = repo / ".claude" / "agents" / "demo.md"
    assert pointer.is_file()

    result = lifecycle.remove_agent("demo", tier_root)

    assert result["removed_agent"] is True
    assert not (tier_root / "agents" / "demo").exists()
    assert not pointer.exists()


def test_remove_on_a_not_installed_agent_raises(repo):
    with pytest.raises(FileNotFoundError):
        lifecycle.remove_agent("demo", repo / ".ai-agents")


def test_remove_spares_a_hand_authored_pointer_at_the_same_path(repo):
    # A hand-written pointer sits exactly where a generated one for this
    # agent would — removal must recognize it lacks GENERATED_MARKER and
    # leave it alone, same as generation would refuse to overwrite it.
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "claude-code")
    pointer = repo / ".claude" / "agents" / "demo.md"
    pointer.parent.mkdir(parents=True)
    pointer.write_text("my own subagent, hand written\n", encoding="utf-8")

    result = lifecycle.remove_agent("demo", tier_root)

    assert not (tier_root / "agents" / "demo").exists()
    assert pointer.read_text(encoding="utf-8") == "my own subagent, hand written\n"
    pointer_result = next(r for r in result["pointers"] if r["harness"] == "claude-code")
    assert pointer_result["action"] == "skipped"


def test_removing_one_of_several_agents_re_renders_the_shared_block(repo):
    # The context-file harnesses share one block across every agent at the
    # tier: removing "alpha" must re-render the block around "zulu" rather
    # than deleting the file out from under it.
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "alpha")
    make_agent(tier_root, "zulu")
    configure(repo, "gemini-cli")
    install.generate_harness_adapters("alpha", tier_root)
    install.generate_harness_adapters("zulu", tier_root)
    context = repo / "GEMINI.md"
    assert "### alpha" in context.read_text(encoding="utf-8")
    assert "### zulu" in context.read_text(encoding="utf-8")

    lifecycle.remove_agent("alpha", tier_root)

    assert context.is_file()
    text = context.read_text(encoding="utf-8")
    assert "### alpha" not in text
    assert "### zulu" in text
    assert text.count(install.BLOCK_BEGIN) == 1


def test_removing_the_last_agent_drops_the_block_and_keeps_hand_written_prose(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "gemini-cli")
    context = repo / "GEMINI.md"
    context.write_text("# House rules\n\nAlways use tabs.\n", encoding="utf-8")
    install.generate_harness_adapters("demo", tier_root)
    assert install.BLOCK_BEGIN in context.read_text(encoding="utf-8")

    lifecycle.remove_agent("demo", tier_root)

    text = context.read_text(encoding="utf-8")
    assert install.BLOCK_BEGIN not in text
    assert "House rules" in text
    assert "Always use tabs." in text


def test_removing_the_last_agent_deletes_a_file_that_held_only_the_block(repo):
    # No hand-written content anywhere in the file: once the block is gone
    # there is nothing left to keep, so the file itself must be deleted —
    # a tier with its last agent just removed should look identical to a
    # tier that never had one installed.
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "gemini-cli")
    install.generate_harness_adapters("demo", tier_root)
    context = repo / "GEMINI.md"
    assert context.is_file()

    lifecycle.remove_agent("demo", tier_root)

    assert not context.exists()


def test_remove_reports_an_unterminated_block_instead_of_repairing_it(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "gemini-cli")
    context = repo / "GEMINI.md"
    # A BEGIN with no matching END: there is no safe way to guess where the
    # block was meant to stop, so removal must leave it untouched and just
    # report the problem, exactly as generation does.
    original = f"notes\n\n{install.BLOCK_BEGIN}\nhalf a block\n"
    context.write_text(original, encoding="utf-8")

    result = lifecycle.remove_agent("demo", tier_root)

    gemini_result = next(r for r in result["pointers"] if r["harness"] == "gemini-cli")
    assert gemini_result["action"] == "skipped"
    assert "unterminated" in gemini_result["reason"]
    assert context.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# install.copy_agent's never-overwrite default, unchanged by this module
# ---------------------------------------------------------------------------


def test_install_still_never_overwrites_an_existing_copy(master, repo):
    # This module exists specifically so update/force is the only path
    # that can refresh an installed copy — plain copy_agent must still
    # leave an existing destination alone, untouched by anything added
    # here.
    make_agent(master, "demo", description="Original.")
    dst_root = repo / ".ai-agents"
    install.copy_agent("demo", master, dst_root)
    local = dst_root / "agents" / "demo" / "AGENT.md"
    local.write_text(local.read_text(encoding="utf-8") + "\nLocal note.\n", encoding="utf-8")
    edited_bytes = local.read_bytes()

    copied = install.copy_agent("demo", master, dst_root)

    assert copied is False
    assert local.read_bytes() == edited_bytes
