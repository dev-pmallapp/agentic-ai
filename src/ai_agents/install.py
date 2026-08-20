"""Copy an agent directory from one tier into another.

The semantics are LifeOS's ``copyMissing`` narrowed to a single named
agent: copy when absent, never overwrite when present. An agent already
installed at the destination may have been edited on purpose — clobbering
it would silently discard local work — so the only way to refresh a copy
is to remove it first.
"""

from __future__ import annotations

import shutil
from pathlib import Path

__all__ = ["copy_agent", "generate_harness_adapters"]


def copy_agent(name: str, src_root: Path, dst_root: Path) -> bool:
    """Copy ``src_root/agents/<name>`` to ``dst_root/agents/<name>``.

    Returns ``True`` if the agent was copied, ``False`` if it was already
    present at the destination and was therefore left untouched. Raises
    ``FileNotFoundError`` if the agent does not exist in the source tier.

    ``dirs_exist_ok=False`` is kept as a second line of defense behind the
    existence check — if the check is ever wrong, the copy fails loudly
    instead of merging two trees.
    """
    src = Path(src_root) / "agents" / name
    dst = Path(dst_root) / "agents" / name

    if not src.is_dir():
        raise FileNotFoundError(f"agent {name!r} not found in {src_root}")

    if dst.exists():
        return False

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=False)
    return True


def generate_harness_adapters(agent_name: str, tier_root: Path) -> None:
    """Write per-harness pointer files for an installed agent. STUB.

    The eventual contract, one file per harness, each a thin pointer at
    ``agents/<name>/AGENT.md`` and never a copy of its content:

    * claude-code — ``.claude/agents/<name>.md``
    * cline       — ``.clinerules/<name>.md``
    * gemini-cli  — ``GEMINI.md`` entry / ``gemini-extension.json``
    * qwen-code   — ``QWEN.md`` entry

    See ``harness-adapters/<harness>/README.md`` for each mechanism.
    """
    # TODO: implement per harness-adapters/<harness>/README.md contract; not
    # yet implemented (equal-skeleton scope for this pass)
    raise NotImplementedError(
        "harness adapter generation is not implemented yet; "
        "see harness-adapters/<harness>/README.md for the intended contract"
    )
