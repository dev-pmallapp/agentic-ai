"""Read the agent catalog off disk.

An agent is a directory: ``agents/<name>/AGENT.md`` plus an optional
``workflows/`` directory of markdown procedures. This module is the only
place that knows how to turn that layout into data.

Frontmatter is parsed by hand — first ``---``-delimited block, ``key: value``
lines, and ``- item`` list continuations — rather than pulling in a YAML
dependency. The subset of YAML an ``AGENT.md`` header uses is small and
fixed, and keeping the runtime dependency list to ``click`` alone matters
more here than covering every YAML corner case.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["list_agents", "read_agent", "split_frontmatter", "parse_frontmatter"]


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split ``text`` into (frontmatter, body).

    Returns ``("", text)`` when the document does not open with a ``---``
    fence, so a body-only ``AGENT.md`` degrades to "no metadata" rather
    than raising.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    # Unterminated fence — treat the whole thing as body.
    return "", text


def parse_frontmatter(block: str) -> dict:
    """Parse the tiny YAML subset used in agent frontmatter.

    Supports ``key: value`` scalars, ``key:`` followed by indented ``- item``
    lines (a list), and inline ``key: [a, b]`` lists. Values are stripped of
    matching surrounding quotes. Anything else is ignored.
    """
    data: dict = {}
    current_list_key: str | None = None

    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        stripped = line.lstrip()
        if stripped.startswith("- ") and current_list_key is not None:
            data[current_list_key].append(_scalar(stripped[2:]))
            continue

        if ":" not in stripped:
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        if not value:
            data[key] = []
            current_list_key = key
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [_scalar(p) for p in inner.split(",") if p.strip()] if inner else []
            current_list_key = None
        else:
            data[key] = _scalar(value)
            current_list_key = None

    return data


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def read_agent(agent_dir: Path) -> dict | None:
    """Read one ``agents/<name>/`` directory into a catalog entry.

    Returns ``None`` if the directory has no ``AGENT.md``. The returned dict
    is ``{"name", "description", "workflows", "path"}``.

    Workflows are the union of what the frontmatter declares and what
    ``workflows/*.md`` actually contains — declared-but-missing entries are
    kept (they show up as a drift signal rather than silently vanishing) and
    on-disk files absent from the frontmatter are added. The directory name
    is the fallback ``name`` when frontmatter omits it.
    """
    agent_file = agent_dir / "AGENT.md"
    if not agent_file.is_file():
        return None

    front, _body = split_frontmatter(agent_file.read_text(encoding="utf-8"))
    meta = parse_frontmatter(front)

    declared = meta.get("workflows", [])
    if isinstance(declared, str):
        declared = [declared]
    declared = [_stem(w) for w in declared if str(w).strip()]

    on_disk = sorted(p.stem for p in (agent_dir / "workflows").glob("*.md"))

    workflows = list(declared)
    workflows.extend(w for w in on_disk if w not in workflows)

    return {
        "name": str(meta.get("name") or agent_dir.name),
        "description": str(meta.get("description") or ""),
        "workflows": workflows,
        "path": agent_dir,
    }


def _stem(value: str) -> str:
    """Normalize a declared workflow to a bare stem (``a/b.md`` -> ``b``)."""
    return Path(str(value).strip()).stem


def list_agents(master_root: Path) -> list[dict]:
    """Scan ``master_root/agents/*/AGENT.md`` and return catalog entries.

    ``master_root`` is a tier root (this repo, ``~/.ai-agents``, a workspace
    or project ``.ai-agents``) — the directory that *contains* ``agents/``.
    Returns a list of ``{"name", "description", "workflows", "path"}`` dicts
    sorted by name; an absent or empty ``agents/`` yields ``[]`` rather than
    an error, since an empty project tier is the normal starting state.
    """
    master_root = Path(master_root)
    agents_dir = master_root / "agents"
    if not agents_dir.is_dir():
        return []

    entries = [read_agent(d) for d in sorted(agents_dir.iterdir()) if d.is_dir()]
    return sorted((e for e in entries if e is not None), key=lambda e: e["name"])
