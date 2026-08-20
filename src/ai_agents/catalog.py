"""Read the agent catalog off disk.

An agent is a directory: ``agents/<Name>/AGENT.md`` plus optional
``Skills/`` and ``Workflows/`` directories of markdown procedures — Skills
are atomic and individually invocable, Workflows are cumulative and compose
Skills (see ``ARCHITECTURE.md``, "Skills and Workflows"). This module is the
only place that knows how to turn that layout into data.

Subdirectory names are capitalized (``Skills/``, ``Workflows/``) to match
LifeOS, the source catalog most agents here are ported from. During the
migration off the older lowercase layout (``skills/``, ``workflows/``),
both spellings are tolerated on read — see ``_agent_subdir``.

Frontmatter is parsed by hand — first ``---``-delimited block, ``key: value``
lines, and ``- item`` list continuations — rather than pulling in a YAML
dependency. The subset of YAML an ``AGENT.md`` header uses is small and
fixed, and keeping the runtime dependency list to ``click`` alone matters
more here than covering every YAML corner case.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = [
    "list_agents",
    "read_agent",
    "split_frontmatter",
    "parse_frontmatter",
    "find_dangling_skill_refs",
]


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


def _agent_subdir(agent_dir: Path, capitalized_name: str) -> Path:
    """Resolve a Skills/Workflows/etc. subdirectory of an agent.

    Prefers the capitalized directory (``Skills/``, ``Workflows/``) that the
    current layout specifies. Falls back to the all-lowercase name
    (``skills/``, ``workflows/``) if the capitalized one is not present.

    This fallback exists only for the migration window: the anatomy was
    renamed from lowercase to capitalized subdirectory names, but not every
    agent tree has been migrated yet. It is scaffolding, not a permanent
    feature of the layout — safe to delete once the migration is done and
    only capitalized directories remain on disk.
    """
    capitalized_dir = agent_dir / capitalized_name
    if capitalized_dir.is_dir():
        return capitalized_dir
    return agent_dir / capitalized_name.lower()


def _declared_stems(meta: dict, key: str) -> list[str]:
    """Pull a declared list (``workflows:``/``skills:``) out of frontmatter.

    Normalizes a single scalar to a one-item list and reduces every entry to
    a bare stem (``a/b.md`` -> ``b``), matching how on-disk filenames are
    compared.
    """
    declared = meta.get(key, [])
    if isinstance(declared, str):
        declared = [declared]
    return [_stem(w) for w in declared if str(w).strip()]


def _merge_declared_and_disk(declared: list[str], on_disk: list[str]) -> list[str]:
    """Union declared frontmatter entries with what is actually on disk.

    Declared-but-missing entries are kept (a drift signal rather than a
    silent drop) and on-disk files absent from the frontmatter are appended.
    Order: declared entries first (in their declared order), then any
    on-disk-only additions.
    """
    merged = list(declared)
    merged.extend(name for name in on_disk if name not in merged)
    return merged


def _stem(value: str) -> str:
    """Normalize a declared workflow/skill to a bare stem (``a/b.md`` -> ``b``)."""
    return Path(str(value).strip()).stem


def read_agent(agent_dir: Path) -> dict | None:
    """Read one ``agents/<Name>/`` directory into a catalog entry.

    Returns ``None`` if the directory has no ``AGENT.md``. The returned dict
    is ``{"name", "description", "skills", "workflows", "path"}``.

    Skills and workflows are each the union of what the frontmatter declares
    (``skills:``/``workflows:``) and what ``Skills/*.md`` / ``Workflows/*.md``
    actually contains — declared-but-missing entries are kept (they show up
    as a drift signal rather than silently vanishing) and on-disk files
    absent from the frontmatter are added. See ``_merge_declared_and_disk``.
    The directory name is the fallback ``name`` when frontmatter omits it.

    Skills and workflows are returned as two separate lists, not merged into
    one — they are different kinds of procedure (atomic vs. cumulative; see
    ``ARCHITECTURE.md``) and a caller should not have to re-derive which is
    which.
    """
    agent_file = agent_dir / "AGENT.md"
    if not agent_file.is_file():
        return None

    front, _body = split_frontmatter(agent_file.read_text(encoding="utf-8"))
    meta = parse_frontmatter(front)

    declared_workflows = _declared_stems(meta, "workflows")
    on_disk_workflows = sorted(p.stem for p in _agent_subdir(agent_dir, "Workflows").glob("*.md"))
    workflows = _merge_declared_and_disk(declared_workflows, on_disk_workflows)

    declared_skills = _declared_stems(meta, "skills")
    on_disk_skills = sorted(p.stem for p in _agent_subdir(agent_dir, "Skills").glob("*.md"))
    skills = _merge_declared_and_disk(declared_skills, on_disk_skills)

    return {
        "name": str(meta.get("name") or agent_dir.name),
        "description": str(meta.get("description") or ""),
        "skills": skills,
        "workflows": workflows,
        "path": agent_dir,
    }


def list_agents(master_root: Path) -> list[dict]:
    """Scan ``master_root/agents/*/AGENT.md`` and return catalog entries.

    ``master_root`` is a tier root (this repo, ``~/.ai-agents``, a workspace
    or project ``.ai-agents``) — the directory that *contains* ``agents/``.
    Returns a list of ``{"name", "description", "skills", "workflows", "path"}``
    dicts sorted by name; an absent or empty ``agents/`` yields ``[]`` rather
    than an error, since an empty project tier is the normal starting state.
    """
    master_root = Path(master_root)
    agents_dir = master_root / "agents"
    if not agents_dir.is_dir():
        return []

    entries = [read_agent(d) for d in sorted(agents_dir.iterdir()) if d.is_dir()]
    return sorted((e for e in entries if e is not None), key=lambda e: e["name"])


_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


def find_dangling_skill_refs(agent: dict) -> list[dict]:
    """Find Workflow files that reference one of the agent's own Skills by
    name, where no matching file actually exists under ``Skills/``.

    This is the drift check the composition rule in ``ARCHITECTURE.md``
    implies: a Workflow may compose Skills, so a Workflow naming a Skill
    that isn't actually there is a broken composition, not a cosmetic
    mismatch. Takes an entry as returned by ``read_agent`` (needs its
    ``path`` and ``skills`` keys).

    Design decisions, recorded here per Story #33:

    * **What counts as a "reference".** Only a markdown link target
      (``[text](target)``) or an inline-code span (`` `target` ``) whose
      stem matches one of the agent's own skill names — i.e. a name already
      present in ``agent["skills"]``, the declared-or-on-disk union
      ``read_agent`` computes — counts as a reference. A bare mention of a
      skill's name in running prose does *not* count. This is deliberately
      narrow: matching free text would flag a workflow every time it talks
      *about* a skill without pointing at it, and a false positive here is
      worse than a miss — it teaches people to ignore the check. Restricting
      to link targets and code spans keeps matches to places an author
      clearly intended as a pointer to a file.
    * **What "does not exist" means.** A matched reference is dangling only
      if no ``<name>.md`` exists under the agent's ``Skills/`` (or, during
      the migration window, ``skills/``) directory — the same on-disk test
      ``read_agent`` uses, via ``_agent_subdir``.
    * **Where this check lives.** Deliberately *not* wired into
      ``read_agent``/``list_agents``: reading the catalog is meant to stay a
      cheap, non-judgmental scan of what's on disk, while this check does
      real cross-referencing work (open every workflow file, regex its
      body) that belongs on a validate/doctor path instead — e.g. a future
      ``ai-agents doctor`` check — not on the hot path every ``list`` call
      goes through.

    Returns a list of ``{"workflow", "skill"}`` dicts, one per dangling
    reference (a workflow can appear more than once if it references more
    than one missing skill). Empty list if the agent has no skill names at
    all, since there is nothing a reference could dangle against.
    """
    skill_names = set(agent.get("skills", []))
    if not skill_names:
        return []

    agent_dir = agent["path"]
    existing_skill_files = {p.stem for p in _agent_subdir(agent_dir, "Skills").glob("*.md")}
    workflows_dir = _agent_subdir(agent_dir, "Workflows")

    findings = []
    seen: set[tuple[str, str]] = set()
    for workflow_file in sorted(workflows_dir.glob("*.md")):
        _front, body = split_frontmatter(workflow_file.read_text(encoding="utf-8"))

        referenced = set()
        for pattern in (_MARKDOWN_LINK_RE, _INLINE_CODE_RE):
            for match in pattern.finditer(body):
                referenced.add(Path(match.group(1).strip()).stem)

        for skill_name in sorted(referenced & skill_names):
            if skill_name in existing_skill_files:
                continue
            key = (workflow_file.stem, skill_name)
            if key in seen:
                continue
            seen.add(key)
            findings.append({"workflow": workflow_file.stem, "skill": skill_name})

    return findings
