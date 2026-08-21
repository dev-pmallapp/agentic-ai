"""Catalog reads this repo's own agents/ tree — it is the fixture."""

from pathlib import Path

from ai_agents import catalog

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_lists_the_scaffolded_agents():
    agents = catalog.list_agents(REPO_ROOT)
    names = [a["name"] for a in agents]

    assert "stock-screening" in names
    assert "dev-lifecycle" in names


def test_stock_screening_has_both_skills_and_no_workflows():
    # Post-migration shape: swing-trading and day-trading-shortlist live
    # under Skills/ (each is atomic and individually invocable), and
    # Workflows/ is empty by design — see agents/stock-screening/AGENT.md.
    agents = {a["name"]: a for a in catalog.list_agents(REPO_ROOT)}
    screening = agents["stock-screening"]

    assert set(screening["skills"]) == {"swing-trading", "day-trading-shortlist"}
    assert screening["workflows"] == []
    assert screening["description"]


def test_dev_lifecycle_has_the_ported_skills_and_workflow():
    # Story #9 replaced the placeholder with a port of six Skills and one
    # Workflow (autodev); story #23 (task #28) added the remaining ten —
    # the pipeline half (init, story-test-plan, task-test-plan) and the
    # utility set. See agents/dev-lifecycle/AGENT.md "What's Ported and
    # What Isn't" for what remains deferred.
    agents = {a["name"]: a for a in catalog.list_agents(REPO_ROOT)}
    dev_lifecycle = agents["dev-lifecycle"]

    assert set(dev_lifecycle["skills"]) == {
        # pipeline, in run order
        "init",
        "story-create",
        "story-design",
        "story-test-plan",
        "task-create",
        "task-implement",
        "task-test-plan",
        "task-test",
        "story-test",
        "enhance-debugger",
        # utility
        "status",
        "size",
        "replan",
        "story-test-replan",
        "checkpoint",
        "resume",
    }
    assert dev_lifecycle["workflows"] == ["autodev"]
    assert catalog.find_dangling_skill_refs(dev_lifecycle) == []


def test_missing_agents_dir_is_empty_not_an_error(tmp_path):
    assert catalog.list_agents(tmp_path) == []


def test_frontmatter_parsing_handles_lists_and_quotes():
    front, body = catalog.split_frontmatter(
        "---\nname: demo\ndescription: 'a thing'\nworkflows:\n  - one\n  - two\n---\n# Body\n"
    )
    meta = catalog.parse_frontmatter(front)

    assert meta["name"] == "demo"
    assert meta["description"] == "a thing"
    assert meta["workflows"] == ["one", "two"]
    assert "# Body" in body


def test_body_only_document_has_no_frontmatter():
    front, body = catalog.split_frontmatter("# Just a heading\n")

    assert front == ""
    assert body.startswith("# Just a heading")


def _write_agent_md(agent_dir: Path, *, skills=None, workflows=None) -> None:
    """Write a minimal AGENT.md into a synthetic agent directory.

    ``name`` is deliberately omitted from frontmatter so the entry's
    ``name`` falls back to the directory's own name — useful when a test
    builds several synthetic agents side by side and wants distinct keys.
    ``skills``/``workflows``, when given, become a declared frontmatter
    list; when omitted, the key is absent entirely (no declaration at all).
    """
    agent_dir.mkdir(parents=True, exist_ok=True)
    lines = ["---", "description: a synthetic test agent"]
    if skills is not None:
        lines.append("skills:")
        lines.extend(f"  - {s}" for s in skills)
    if workflows is not None:
        lines.append("workflows:")
        lines.extend(f"  - {w}" for w in workflows)
    lines += ["---", "# demo"]
    (agent_dir / "AGENT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_md(dir_path: Path, stem: str, body: str = "") -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / f"{stem}.md").write_text(body or f"# {stem}\n", encoding="utf-8")


# --- Skills/Workflows combinations -------------------------------------------


def test_agent_with_skills_only(tmp_path):
    agent_dir = tmp_path / "agents" / "demo"
    _write_agent_md(agent_dir)
    _write_md(agent_dir / "Skills", "one")

    entry = catalog.read_agent(agent_dir)

    assert entry["skills"] == ["one"]
    assert entry["workflows"] == []


def test_agent_with_workflows_only(tmp_path):
    agent_dir = tmp_path / "agents" / "demo"
    _write_agent_md(agent_dir)
    _write_md(agent_dir / "Workflows", "one")

    entry = catalog.read_agent(agent_dir)

    assert entry["skills"] == []
    assert entry["workflows"] == ["one"]


def test_agent_with_both_skills_and_workflows(tmp_path):
    agent_dir = tmp_path / "agents" / "demo"
    _write_agent_md(agent_dir)
    _write_md(agent_dir / "Skills", "s")
    _write_md(agent_dir / "Workflows", "w")

    entry = catalog.read_agent(agent_dir)

    assert entry["skills"] == ["s"]
    assert entry["workflows"] == ["w"]


def test_agent_with_neither_skills_nor_workflows(tmp_path):
    agent_dir = tmp_path / "agents" / "demo"
    _write_agent_md(agent_dir)

    entry = catalog.read_agent(agent_dir)

    assert entry["skills"] == []
    assert entry["workflows"] == []


def test_list_agents_keeps_skills_and_workflows_independent_per_agent(tmp_path):
    # Same four combinations as above, but exercised through list_agents
    # scanning a whole synthetic agents/ tree rather than read_agent on one
    # directory at a time.
    agents_dir = tmp_path / "agents"

    _write_agent_md(agents_dir / "skills-only")
    _write_md(agents_dir / "skills-only" / "Skills", "a")

    _write_agent_md(agents_dir / "workflows-only")
    _write_md(agents_dir / "workflows-only" / "Workflows", "b")

    _write_agent_md(agents_dir / "both")
    _write_md(agents_dir / "both" / "Skills", "c")
    _write_md(agents_dir / "both" / "Workflows", "d")

    _write_agent_md(agents_dir / "neither")

    agents = {a["name"]: a for a in catalog.list_agents(tmp_path)}

    assert agents["skills-only"]["skills"] == ["a"]
    assert agents["skills-only"]["workflows"] == []

    assert agents["workflows-only"]["skills"] == []
    assert agents["workflows-only"]["workflows"] == ["b"]

    assert agents["both"]["skills"] == ["c"]
    assert agents["both"]["workflows"] == ["d"]

    assert agents["neither"]["skills"] == []
    assert agents["neither"]["workflows"] == []


# --- Frontmatter/disk cross-check, mirrored for skills -----------------------


def test_declared_skill_missing_on_disk_is_kept_as_drift_signal(tmp_path):
    agent_dir = tmp_path / "agents" / "demo"
    _write_agent_md(agent_dir, skills=["ghost"])
    (agent_dir / "Skills").mkdir(parents=True)  # exists, but no ghost.md in it

    entry = catalog.read_agent(agent_dir)

    assert entry["skills"] == ["ghost"]


def test_on_disk_skill_missing_from_frontmatter_is_appended(tmp_path):
    agent_dir = tmp_path / "agents" / "demo"
    _write_agent_md(agent_dir, skills=["declared"])
    _write_md(agent_dir / "Skills", "declared")
    _write_md(agent_dir / "Skills", "undeclared")

    entry = catalog.read_agent(agent_dir)

    assert entry["skills"] == ["declared", "undeclared"]


# --- Lowercase-fallback (migration window) ------------------------------------


def test_lowercase_skills_and_workflows_dirs_still_resolve(tmp_path):
    # Migration-window scaffolding: `_agent_subdir` falls back to lowercase
    # `skills/`/`workflows/` when the capitalized directory is absent (see
    # its docstring in catalog.py). That fallback is meant to be deleted
    # once every agent tree is migrated to `Skills/`/`Workflows/` — delete
    # this test in the same change that removes the fallback.
    agent_dir = tmp_path / "agents" / "demo"
    _write_agent_md(agent_dir)
    _write_md(agent_dir / "skills", "legacy")
    _write_md(agent_dir / "workflows", "legacy-flow")

    entry = catalog.read_agent(agent_dir)

    assert entry["skills"] == ["legacy"]
    assert entry["workflows"] == ["legacy-flow"]


# --- find_dangling_skill_refs -------------------------------------------------


def test_find_dangling_skill_refs_flags_markdown_link_to_missing_skill(tmp_path):
    agent_dir = tmp_path / "agents" / "demo"
    _write_agent_md(agent_dir, skills=["real-skill", "missing-skill"])
    _write_md(agent_dir / "Skills", "real-skill")
    _write_md(
        agent_dir / "Workflows",
        "flow",
        "See [missing skill](../Skills/missing-skill.md) for the procedure.\n",
    )

    entry = catalog.read_agent(agent_dir)
    findings = catalog.find_dangling_skill_refs(entry)

    assert findings == [{"workflow": "flow", "skill": "missing-skill"}]


def test_find_dangling_skill_refs_does_not_flag_a_resolving_reference(tmp_path):
    agent_dir = tmp_path / "agents" / "demo"
    _write_agent_md(agent_dir, skills=["real-skill"])
    _write_md(agent_dir / "Skills", "real-skill")
    _write_md(agent_dir / "Workflows", "flow", "Run `real-skill` first.\n")

    entry = catalog.read_agent(agent_dir)
    findings = catalog.find_dangling_skill_refs(entry)

    assert findings == []


def test_find_dangling_skill_refs_ignores_bare_prose_mention(tmp_path):
    # missing-skill has no Skills/missing-skill.md, but the workflow only
    # mentions its name in running prose — not as a link target or an
    # inline-code span — so it must not be flagged.
    agent_dir = tmp_path / "agents" / "demo"
    _write_agent_md(agent_dir, skills=["missing-skill"])
    (agent_dir / "Skills").mkdir(parents=True)
    _write_md(
        agent_dir / "Workflows",
        "flow",
        "This workflow does not use missing-skill anywhere.\n",
    )

    entry = catalog.read_agent(agent_dir)
    findings = catalog.find_dangling_skill_refs(entry)

    assert findings == []
