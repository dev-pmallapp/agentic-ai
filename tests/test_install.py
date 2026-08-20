"""Harness detection and pointer generation.

Unlike ``test_catalog``, which reads this repo's own ``agents/`` tree as a
fixture, everything here writes files — so every test builds a synthetic
tier root under ``tmp_path``, and an autouse fixture points ``HOME`` at a
temporary directory too. Between them, nothing in this module can touch a
real checkout or a real ``~/.claude``.
"""

from pathlib import Path

import pytest

from ai_agents import install

# A sentence that appears only in an agent's body, never in its
# frontmatter — the probe for "no agent content is duplicated into a
# generated file".
BODY_SENTENCE = "This paragraph belongs to the agent body alone."


@pytest.fixture(autouse=True)
def fake_home(tmp_path, monkeypatch):
    """Point HOME at tmp_path so the user tier never resolves to a real one.

    ``Path.home()`` reads HOME on POSIX, and both ``tiers.user_root`` and
    the user-tier harness locations go through it.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def repo(tmp_path):
    """A git repo with no harness configured yet."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    return root


def make_agent(tier_root, name, description="Does a thing.", skills=(), workflows=()):
    """Write a minimal agent into ``tier_root/agents/<name>/``."""
    agent_dir = tier_root / "agents" / name
    (agent_dir / "Skills").mkdir(parents=True)
    (agent_dir / "Workflows").mkdir(parents=True)
    (agent_dir / "AGENT.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{BODY_SENTENCE}\n",
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


def actions(results):
    return {r["harness"]: r["action"] for r in results}


def paths(results):
    return {r["harness"]: r["path"] for r in results}


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_nothing_is_detected_in_a_bare_repo(repo):
    assert install.detect_harnesses(repo / ".ai-agents", "project") == []


@pytest.mark.parametrize("harness", install.HARNESSES)
def test_each_harness_is_detected_on_its_own(repo, harness):
    configure(repo, harness)

    assert install.detect_harnesses(repo / ".ai-agents", "project") == [harness]


def test_all_four_are_detected_in_declared_order(repo):
    configure(repo, "qwen-code", "cline", "claude-code", "gemini-cli")

    assert install.detect_harnesses(repo / ".ai-agents", "project") == list(install.HARNESSES)


def test_a_bare_context_file_is_enough_to_detect_a_context_harness(repo):
    # Someone can hand-write GEMINI.md without ever creating .gemini/, and
    # that is exactly the case where a pointer is wanted.
    (repo / "GEMINI.md").write_text("# notes\n", encoding="utf-8")
    (repo / "QWEN.md").write_text("# notes\n", encoding="utf-8")

    assert install.detect_harnesses(repo / ".ai-agents", "project") == ["gemini-cli", "qwen-code"]


def test_detection_creates_nothing(repo):
    before = sorted(p.name for p in repo.iterdir())

    install.detect_harnesses(repo / ".ai-agents", "project")

    assert sorted(p.name for p in repo.iterdir()) == before


def test_user_tier_harnesses_are_detected_under_home(fake_home):
    (fake_home / ".claude").mkdir()
    (fake_home / ".gemini").mkdir()

    detected = install.detect_harnesses(fake_home / ".ai-agents", "user")

    assert detected == ["claude-code", "gemini-cli"]


# ---------------------------------------------------------------------------
# Pointer locations
# ---------------------------------------------------------------------------


def test_project_tier_pointer_locations(repo):
    tier_root = repo / ".ai-agents"
    located = {h: install.harness_pointer_path(h, tier_root, "project", "demo") for h in install.HARNESSES}

    assert located["claude-code"] == repo / ".claude" / "agents" / "demo.md"
    assert located["cline"] == repo / ".clinerules" / "demo.md"
    assert located["gemini-cli"] == repo / "GEMINI.md"
    assert located["qwen-code"] == repo / "QWEN.md"


def test_user_tier_pointer_locations(fake_home):
    tier_root = fake_home / ".ai-agents"
    located = {h: install.harness_pointer_path(h, tier_root, "user", "demo") for h in install.HARNESSES}

    # The context harnesses keep their global context file inside their own
    # config directory, not loose in the home directory.
    assert located["claude-code"] == fake_home / ".claude" / "agents" / "demo.md"
    assert located["gemini-cli"] == fake_home / ".gemini" / "GEMINI.md"
    assert located["qwen-code"] == fake_home / ".qwen" / "QWEN.md"


def test_an_unknown_harness_is_rejected(repo):
    with pytest.raises(ValueError, match="unknown harness"):
        install.harness_pointer_path("emacs", repo / ".ai-agents", "project", "demo")


# ---------------------------------------------------------------------------
# Tier naming
# ---------------------------------------------------------------------------


def test_tier_name_for_the_three_tiers(tmp_path, fake_home, repo):
    workspace = tmp_path / "workspace"
    (workspace / ".ai-agents").mkdir(parents=True)

    assert install.tier_name_for(repo / ".ai-agents") == "project"
    assert install.tier_name_for(workspace / ".ai-agents") == "workspace"
    assert install.tier_name_for(fake_home / ".ai-agents") == "user"


def test_tier_name_refuses_to_guess(tmp_path):
    stray = tmp_path / "not-a-tier" / "somewhere"
    stray.mkdir(parents=True)

    # The tier name is written into every generated pointer, so guessing
    # would put a lie on disk.
    with pytest.raises(ValueError, match="not a recognized tier root"):
        install.tier_name_for(stray)


# ---------------------------------------------------------------------------
# Generation, per harness
# ---------------------------------------------------------------------------


def test_claude_code_pointer_shape(repo):
    tier_root = repo / ".ai-agents"
    agent_dir = make_agent(tier_root, "demo", description="Screens things.", skills=["alpha"], workflows=["beta"])
    configure(repo, "claude-code")

    results = install.generate_harness_adapters("demo", tier_root)
    text = paths(results)["claude-code"].read_text(encoding="utf-8")

    assert text.startswith("---\nname: demo\ndescription: Screens things.\n---\n")
    assert "Skills: alpha" in text
    assert "Workflows: beta" in text
    assert str((agent_dir / "AGENT.md").resolve()) in text
    assert "Resolved tier: project." in text


def test_cline_pointer_shape(repo):
    tier_root = repo / ".ai-agents"
    agent_dir = make_agent(tier_root, "demo", description="Screens things.", skills=["alpha"])
    configure(repo, "cline")

    results = install.generate_harness_adapters("demo", tier_root)
    text = paths(results)["cline"].read_text(encoding="utf-8")

    # No frontmatter: Cline has no dispatch mechanism to feed.
    assert not text.startswith("---")
    assert "# demo" in text
    assert "Screens things." in text
    assert "Skills: alpha" in text
    assert f"Full instructions: {(agent_dir / 'AGENT.md').resolve()}" in text
    assert "Tier: project" in text


@pytest.mark.parametrize(
    ("harness", "filename"),
    [("gemini-cli", "GEMINI.md"), ("qwen-code", "QWEN.md")],
)
def test_context_harness_block_shape(repo, harness, filename):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo", description="Screens things.", skills=["alpha"], workflows=["beta"])
    configure(repo, harness)

    results = install.generate_harness_adapters("demo", tier_root)
    path = paths(results)[harness]
    text = path.read_text(encoding="utf-8")

    assert path == repo / filename
    assert text.startswith(install.BLOCK_BEGIN)
    assert text.rstrip("\n").endswith(install.BLOCK_END)
    assert "## AI Agents" in text
    assert "### demo" in text
    assert "- Skills: alpha" in text
    assert "- Workflows: beta" in text
    assert "- Tier: project" in text


def test_an_empty_kind_gets_no_line_at_all(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "skills-only", skills=["alpha"])
    configure(repo, "claude-code", "cline", "gemini-cli")

    results = install.generate_harness_adapters("skills-only", tier_root)

    for harness, path in paths(results).items():
        text = path.read_text(encoding="utf-8")
        assert "Skills: alpha" in text, harness
        # Dropped outright rather than kept as a dangling label.
        assert "Workflows:" not in text, harness
        assert "(none)" not in text, harness


def test_an_agent_with_neither_kind_falls_back_to_one_none_line(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "empty")
    configure(repo, "claude-code", "gemini-cli")

    results = install.generate_harness_adapters("empty", tier_root)
    located = paths(results)

    claude_text = located["claude-code"].read_text(encoding="utf-8")
    gemini_text = located["gemini-cli"].read_text(encoding="utf-8")

    assert claude_text.count("(none)") == 1
    assert "Skills:" not in claude_text
    assert gemini_text.count("- (none)") == 1


def test_no_agent_content_is_duplicated_into_a_pointer(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo", skills=["alpha"])
    configure(repo, *install.HARNESSES)

    results = install.generate_harness_adapters("demo", tier_root)

    for harness, path in paths(results).items():
        assert BODY_SENTENCE not in path.read_text(encoding="utf-8"), harness


def test_every_detected_harness_gets_a_pointer(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo", skills=["alpha"])
    configure(repo, *install.HARNESSES)

    results = install.generate_harness_adapters("demo", tier_root)

    assert [r["harness"] for r in results] == list(install.HARNESSES)
    assert set(actions(results).values()) == {"created"}
    assert all(path.is_file() for path in paths(results).values())


def test_no_harness_means_no_files(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")

    assert install.generate_harness_adapters("demo", tier_root) == []
    # An unconfigured repo is left exactly as it was: generation never
    # creates a harness's config directory for it.
    assert sorted(p.name for p in repo.iterdir()) == [".ai-agents", ".git"]


def test_generating_for_an_uninstalled_agent_raises(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "claude-code")

    with pytest.raises(FileNotFoundError, match="not installed"):
        install.generate_harness_adapters("absent", tier_root)


def test_user_tier_pointers_land_under_home(fake_home):
    tier_root = fake_home / ".ai-agents"
    make_agent(tier_root, "demo", skills=["alpha"])
    (fake_home / ".claude").mkdir()
    (fake_home / ".gemini").mkdir()

    results = install.generate_harness_adapters("demo", tier_root)
    located = paths(results)

    assert located["claude-code"] == fake_home / ".claude" / "agents" / "demo.md"
    assert located["gemini-cli"] == fake_home / ".gemini" / "GEMINI.md"
    assert "Resolved tier: user." in located["claude-code"].read_text(encoding="utf-8")
    assert "- Tier: user" in located["gemini-cli"].read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Multi-agent behavior
# ---------------------------------------------------------------------------


def test_per_agent_harnesses_get_one_file_each(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "zulu")
    make_agent(tier_root, "alpha")
    configure(repo, "claude-code")

    install.generate_harness_adapters("zulu", tier_root)
    install.generate_harness_adapters("alpha", tier_root)

    written = sorted(p.name for p in (repo / ".claude" / "agents").iterdir())
    assert written == ["alpha.md", "zulu.md"]


def test_the_context_block_lists_every_installed_agent_alphabetically(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "zulu")
    make_agent(tier_root, "alpha")
    configure(repo, "gemini-cli")

    # Installing either one regenerates the whole block, so the block is
    # correct no matter which agent triggered it.
    install.generate_harness_adapters("zulu", tier_root)
    text = (repo / "GEMINI.md").read_text(encoding="utf-8")

    assert text.index("### alpha") < text.index("### zulu")
    assert text.count(install.BLOCK_BEGIN) == 1
    assert text.count(install.BLOCK_END) == 1


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_a_second_run_changes_nothing(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo", skills=["alpha"], workflows=["beta"])
    configure(repo, *install.HARNESSES)

    first = install.generate_harness_adapters("demo", tier_root)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths(first).values()}

    second = install.generate_harness_adapters("demo", tier_root)

    assert set(actions(second).values()) == {"unchanged"}
    for path, (content, mtime) in before.items():
        assert path.read_bytes() == content
        # Unchanged content is not rewritten at all, so even mtime holds.
        assert path.stat().st_mtime_ns == mtime


def test_repeated_runs_do_not_accumulate_blocks_or_blank_lines(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "gemini-cli")

    install.generate_harness_adapters("demo", tier_root)
    once = (repo / "GEMINI.md").read_text(encoding="utf-8")
    for _ in range(3):
        install.generate_harness_adapters("demo", tier_root)

    assert (repo / "GEMINI.md").read_text(encoding="utf-8") == once


def test_a_changed_agent_updates_its_pointer(repo):
    tier_root = repo / ".ai-agents"
    agent_dir = make_agent(tier_root, "demo", skills=["alpha"])
    configure(repo, "claude-code")
    install.generate_harness_adapters("demo", tier_root)

    (agent_dir / "Skills" / "gamma.md").write_text("# gamma\n", encoding="utf-8")
    results = install.generate_harness_adapters("demo", tier_root)

    assert actions(results)["claude-code"] == "updated"
    assert "Skills: alpha, gamma" in paths(results)["claude-code"].read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Never clobber what a person wrote
# ---------------------------------------------------------------------------


def test_a_hand_authored_pointer_file_is_preserved_and_reported(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "claude-code", "cline")
    mine = repo / ".claude" / "agents" / "demo.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("my own subagent, hand written\n", encoding="utf-8")

    results = install.generate_harness_adapters("demo", tier_root)

    assert actions(results)["claude-code"] == "skipped"
    assert "not generated by ai-agents" in dict((r["harness"], r["reason"]) for r in results)["claude-code"]
    assert mine.read_text(encoding="utf-8") == "my own subagent, hand written\n"
    # The other harness is unaffected by one being skipped.
    assert actions(results)["cline"] == "created"


def test_text_around_a_managed_block_is_left_alone(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "gemini-cli")
    context = repo / "GEMINI.md"
    context.write_text("# House rules\n\nAlways use tabs.\n", encoding="utf-8")

    install.generate_harness_adapters("demo", tier_root)
    text = context.read_text(encoding="utf-8")

    assert text.startswith("# House rules\n\nAlways use tabs.\n")
    assert install.BLOCK_BEGIN in text


def test_a_managed_block_is_replaced_without_touching_its_neighbors(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "gemini-cli")
    context = repo / "GEMINI.md"
    context.write_text(
        f"before\n\n{install.BLOCK_BEGIN}\nstale contents\n{install.BLOCK_END}\n\nafter\n",
        encoding="utf-8",
    )

    install.generate_harness_adapters("demo", tier_root)
    text = context.read_text(encoding="utf-8")

    assert "stale contents" not in text
    assert text.startswith("before\n\n")
    assert text.rstrip("\n").endswith("after")
    assert text.count(install.BLOCK_BEGIN) == 1


def test_an_unterminated_block_is_reported_not_repaired(repo):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, "gemini-cli")
    context = repo / "GEMINI.md"
    # A BEGIN with no END: there is no safe way to guess where the block
    # was meant to stop, so nothing is rewritten.
    original = f"notes\n\n{install.BLOCK_BEGIN}\nhalf a block\n"
    context.write_text(original, encoding="utf-8")

    results = install.generate_harness_adapters("demo", tier_root)

    assert actions(results)["gemini-cli"] == "skipped"
    assert "unterminated" in dict((r["harness"], r["reason"]) for r in results)["gemini-cli"]
    assert context.read_text(encoding="utf-8") == original


def test_generation_writes_only_inside_the_tier_and_its_harness_dirs(repo, tmp_path):
    tier_root = repo / ".ai-agents"
    make_agent(tier_root, "demo")
    configure(repo, *install.HARNESSES)

    results = install.generate_harness_adapters("demo", tier_root)

    for path in paths(results).values():
        assert Path(tmp_path) in path.parents
