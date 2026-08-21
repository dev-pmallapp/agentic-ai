#!/usr/bin/env python3
"""Fail if the agent catalog does not parse.

Task #47. This runs in CI *separately from the unit tests*, and the
separation is the point. `catalog.parse_frontmatter` is a hand-rolled YAML
subset — deliberately, so `click` stays the only runtime dependency — which
means a malformed `AGENT.md` header breaks `ai-agents list` without touching
a line of Python. A content-only pull request can do that, and a green test
run would not necessarily say otherwise.

The trap this check is written around: **nothing in `catalog.py` raises on
malformed frontmatter.** `split_frontmatter` returns `("", text)` for an
unterminated or absent fence, and `parse_frontmatter` skips any line it does
not understand. So a broken header does not blow up — it silently yields an
entry with an empty `name`/`description` and no declared lists. Checking
"did it throw?" would therefore pass on exactly the input this exists to
catch. Every check below asserts on the *parsed result* instead.

Exits 0 with a one-line summary when the catalog is sound, or 1 with one
`path: problem` line per failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_agents import catalog  # noqa: E402  (needs the sys.path line above)


def _declared(agent_dir: Path, key: str) -> list[str]:
    """Re-read just the frontmatter's declared list for one agent.

    `read_agent` returns the *union* of declared and on-disk entries, which
    is right for display and useless here: a declared-but-missing workflow
    is indistinguishable from a present one once merged. The check needs the
    raw declaration, so it re-parses.
    """
    front, _ = catalog.split_frontmatter((agent_dir / "AGENT.md").read_text(encoding="utf-8"))
    meta = catalog.parse_frontmatter(front)
    declared = meta.get(key, [])
    if isinstance(declared, str):
        declared = [declared]
    return [Path(str(d).strip()).stem for d in declared if str(d).strip()]


def _subdir(agent_dir: Path, name: str) -> Path:
    """Capitalized subdirectory, falling back to lowercase — as `catalog` does."""
    capitalized = agent_dir / name
    return capitalized if capitalized.is_dir() else agent_dir / name.lower()


def check(repo_root: Path) -> list[str]:
    """Return a list of human-readable problems; empty means the catalog is sound."""
    problems: list[str] = []
    agents_dir = repo_root / "agents"

    if not agents_dir.is_dir():
        return [f"{agents_dir}: no agents/ directory"]

    agents = catalog.list_agents(repo_root)

    # A catalog-wide parse failure shows up as an empty list, not an error.
    # Without this, deleting or breaking every agent would pass silently.
    if not agents:
        return [f"{agents_dir}: parsed zero agents — the catalog is empty or unreadable"]

    # Every directory holding an AGENT.md must have been picked up. Catches a
    # directory that list_agents skipped for a reason the loop below cannot see.
    on_disk = {d.name for d in sorted(agents_dir.iterdir()) if d.is_dir() and (d / "AGENT.md").is_file()}
    parsed = {a["path"].name for a in agents}
    for missing in sorted(on_disk - parsed):
        problems.append(f"agents/{missing}/AGENT.md: has an AGENT.md but did not parse into an entry")

    for agent in agents:
        agent_dir = agent["path"]
        rel = f"agents/{agent_dir.name}"

        # The malformed-frontmatter signal. `name` falls back to the directory
        # name, so an empty description is the reliable tell that the header
        # did not parse — as is a `name` that never made it out of the block.
        if not agent["description"]:
            problems.append(
                f"{rel}/AGENT.md: frontmatter parsed to an empty description "
                "(missing key, or a header the parser could not read)"
            )

        front, body = catalog.split_frontmatter((agent_dir / "AGENT.md").read_text(encoding="utf-8"))
        if not front.strip():
            problems.append(
                f"{rel}/AGENT.md: no frontmatter block found "
                "(missing, or an unterminated --- fence)"
            )
            continue
        if not body.strip():
            problems.append(f"{rel}/AGENT.md: frontmatter present but the body is empty")

        meta = catalog.parse_frontmatter(front)
        for key in ("name", "description"):
            if not str(meta.get(key, "")).strip():
                problems.append(f"{rel}/AGENT.md: frontmatter is missing a non-empty `{key}`")

        # Declared skills and workflows must resolve to real files. The merge
        # in read_agent keeps declared-but-missing entries on purpose (drift is
        # visible rather than silently dropped) — CI is where that becomes an
        # error instead of a signal.
        for kind in ("Skills", "Workflows"):
            key = kind.lower()
            target_dir = _subdir(agent_dir, kind)
            for name in _declared(agent_dir, key):
                if not (target_dir / f"{name}.md").is_file():
                    problems.append(
                        f"{rel}/AGENT.md: declares {key[:-1]} `{name}` but "
                        f"{target_dir.name}/{name}.md does not exist"
                    )

        # A Workflow pointing at a Skill that is not there is a broken
        # composition, per the one-direction rule in ARCHITECTURE.md.
        for dangling in catalog.find_dangling_skill_refs(agent):
            problems.append(
                f"{rel}/Workflows/{dangling['workflow']}.md: references skill "
                f"`{dangling['skill']}`, which has no file under Skills/"
            )

    return problems


def main() -> int:
    problems = check(REPO_ROOT)

    if problems:
        print(f"Catalog check FAILED — {len(problems)} problem(s):\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    agents = catalog.list_agents(REPO_ROOT)
    skills = sum(len(a["skills"]) for a in agents)
    workflows = sum(len(a["workflows"]) for a in agents)
    print(f"Catalog OK — {len(agents)} agent(s), {skills} skill(s), {workflows} workflow(s).")
    for agent in agents:
        print(f"  {agent['name']:<24} {len(agent['skills'])} skill(s), {len(agent['workflows'])} workflow(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
