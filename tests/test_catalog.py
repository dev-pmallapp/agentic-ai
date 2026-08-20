"""Catalog reads this repo's own agents/ tree — it is the fixture."""

from pathlib import Path

from ai_agents import catalog

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_lists_the_scaffolded_agents():
    agents = catalog.list_agents(REPO_ROOT)
    names = [a["name"] for a in agents]

    assert "stock-screening" in names
    assert "dev-lifecycle" in names


def test_stock_screening_has_both_workflows():
    agents = {a["name"]: a for a in catalog.list_agents(REPO_ROOT)}
    screening = agents["stock-screening"]

    assert set(screening["workflows"]) == {"swing-trading", "day-trading-shortlist"}
    assert screening["description"]


def test_dev_lifecycle_is_a_placeholder_with_no_workflows():
    agents = {a["name"]: a for a in catalog.list_agents(REPO_ROOT)}

    assert agents["dev-lifecycle"]["workflows"] == []


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
