"""External plugins: installed into a tier *alongside* the catalog.

An external plugin is a directory this repo did not author and does not
understand — Forge's Claude Code plugin, say. It is placed into a tier
**in its own native form**, recorded, and then left completely alone.
Nothing here parses it, reshapes it, or merges it into ``agents/``.

Why this exists is the governing rule of the gh-workflow milestone, and
it runs one way only: **the plugin bends to this catalog, never the
reverse.** Most of an adopted plugin does bend — references become
``References/``, skills become ``Skills/``, orchestration becomes
``Workflows/``. Some pieces cannot: a harness-specific hook registration
schema, a distribution manifest, anything keyed to a harness primitive
this catalog deliberately does not model. The wrong response to those is
to grow a hook registry or a manifest system here, because that is
bending the repo to fit the plugin. The right response is this module:
drop the leftover in as-is, write down what it was and why it could not
bend, and keep the catalog's anatomy exactly as it was.

Layout, at any tier root::

    .ai-agents/
      agents/            the catalog. Untouched by anything here.
      plugins/<name>/    one external plugin, verbatim.
      plugins.json       what is installed, where it came from, and why.

``plugins/`` is a sibling of ``agents/``, which is what makes the
"anatomy is unchanged" promise mechanical rather than a matter of
discipline: ``catalog.list_agents`` scans ``agents/`` and can no more
see a plugin than it can see a file outside the tier. A plugin that
happens to contain its own ``agents/foo/AGENT.md`` is still invisible to
it — there is a test to that effect, because that is the case where a
sloppier layout would leak.

**The directory is the unit of installation.** Removal deletes
``plugins/<name>/`` entire, so nothing else can be caught by it — and,
symmetrically, anything a user drops *inside* that directory is part of
the plugin as far as this module is concerned and goes with it. Keep
your own files somewhere else.

``reason`` is required, deliberately. See ``install_plugin``.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "PluginError",
    "PLUGINS_DIRNAME",
    "MANIFEST_NAME",
    "SCHEMA_VERSION",
    "plugins_dir",
    "manifest_path",
    "read_manifest",
    "list_plugins",
    "install_plugin",
    "remove_plugin",
]

PLUGINS_DIRNAME = "plugins"
MANIFEST_NAME = "plugins.json"
SCHEMA_VERSION = 1


class PluginError(Exception):
    """Raised for every failure in this module.

    One exception type rather than a hierarchy: every caller here is
    either the CLI (which turns it into a message and a non-zero exit) or
    ``doctor`` (which turns it into a finding). Neither branches on the
    kind of failure, so distinguishing them in the type system would be
    structure nobody reads.
    """


def plugins_dir(tier_root: Path) -> Path:
    """``<tier_root>/plugins`` — sibling of ``agents/``, never inside it."""
    return Path(tier_root) / PLUGINS_DIRNAME


def manifest_path(tier_root: Path) -> Path:
    """``<tier_root>/plugins.json``."""
    return Path(tier_root) / MANIFEST_NAME


def _validate_name(name: str) -> str:
    """Reject anything that is not a single, plain directory name.

    A plugin name becomes a path segment under ``plugins/``, so a value
    carrying a separator or a ``..`` would let an install or a removal
    reach outside the tier. Checked here rather than at each call site,
    because ``remove_plugin`` is the dangerous one and it takes the name
    straight from the command line.
    """
    if not name or name in (".", ".."):
        raise PluginError(f"invalid plugin name: {name!r}")
    if "/" in name or "\\" in name or Path(name).name != name:
        raise PluginError(
            f"invalid plugin name: {name!r} — must be a single directory name, "
            "not a path"
        )
    return name


def read_manifest(tier_root: Path) -> dict:
    """Read ``plugins.json``, or return an empty manifest if absent.

    Absent is normal — a tier with no external plugins has no manifest —
    so that is not an error. **Malformed is an error**, and is raised
    rather than swallowed.

    That asymmetry is deliberate, and it is the opposite of how
    ``catalog.py`` treats a broken ``AGENT.md``. There, degrading is
    right: markdown is written by hand, a missing ``---`` should not take
    down ``list``, and the damage is one agent with a blank description.
    Here, the manifest is machine-written JSON that nothing edits by
    hand, and silently returning ``{}`` for a corrupt file would make
    ``doctor`` report "no external plugins" while a ``plugins/`` tree sits
    on disk beside it — the report would be confidently wrong, which is
    worse than an error.
    """
    path = manifest_path(tier_root)
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "plugins": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PluginError(f"{path} is not readable JSON: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("plugins"), dict):
        raise PluginError(
            f"{path} is not a plugin manifest (expected an object with a "
            '"plugins" object)'
        )
    return data


def _write_manifest(tier_root: Path, data: dict) -> None:
    path = manifest_path(tier_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def list_plugins(tier_root: Path) -> list[dict]:
    """Every recorded plugin at this tier, sorted by name.

    Each entry is the manifest record plus ``name``, ``path``, and
    ``present`` — whether the directory the record names is actually
    there. Reports what is *recorded*; use ``plugins_dir`` directly to
    see what is on disk. ``doctor`` compares the two.
    """
    manifest = read_manifest(tier_root)
    out = []
    for name in sorted(manifest["plugins"]):
        record = dict(manifest["plugins"][name])
        path = plugins_dir(tier_root) / name
        record.update({"name": name, "path": path, "present": path.is_dir()})
        out.append(record)
    return out


def install_plugin(
    src: Path,
    tier_root: Path,
    *,
    reason: str,
    name: str | None = None,
    force: bool = False,
) -> dict:
    """Copy ``src`` into ``<tier_root>/plugins/<name>`` verbatim and record it.

    ``name`` defaults to the source directory's own name. ``force``
    replaces an existing install; without it, an existing directory is an
    error and nothing is touched — the same never-overwrite-by-accident
    rule ``install.copy_agent`` follows.

    ``reason`` is **required**, and it is the point of this function
    rather than a nicety. The story this implements warns that a
    local-install escape hatch, left unqualified, becomes an excuse to
    skip porting and leaves the catalog a thin wrapper around foreign
    plugins. A prose rule in ``ARCHITECTURE.md`` asking people to write
    down what could not bend is only as good as their discipline; making
    it an argument with no default means the record cannot be
    accidentally omitted. Refusing an empty one closes the obvious
    loophole.

    Returns the manifest record that was written.
    """
    src = Path(src).expanduser().resolve()
    if not src.is_dir():
        raise PluginError(f"not a directory: {src}")

    reason = (reason or "").strip()
    if not reason:
        raise PluginError(
            "a reason is required — state which pieces could not bend into "
            "the catalog's anatomy, and why"
        )

    # `is not None`, not `or`: an explicitly empty --name is a mistake and
    # should say so, rather than silently falling back to the source's name.
    name = _validate_name(name if name is not None else src.name)
    dst = plugins_dir(tier_root) / name

    if dst.exists():
        if not force:
            raise PluginError(
                f"plugin {name!r} is already installed at {dst} — "
                "pass force to replace it"
            )
        shutil.rmtree(dst)

    dst.parent.mkdir(parents=True, exist_ok=True)
    # Verbatim: no filtering, no rewriting, no reshaping. Whatever the
    # plugin is, that is what lands. `symlinks=True` so a plugin that
    # ships one keeps it rather than silently gaining a copy of its
    # target.
    shutil.copytree(src, dst, symlinks=True)

    record = {
        "source": str(src),
        "reason": reason,
        "installed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    manifest = read_manifest(tier_root)
    manifest["schema_version"] = SCHEMA_VERSION
    manifest["plugins"][name] = record
    _write_manifest(tier_root, manifest)

    return {**record, "name": name, "path": dst, "present": True}


def remove_plugin(name: str, tier_root: Path) -> dict:
    """Delete ``<tier_root>/plugins/<name>`` and drop its manifest entry.

    Removes **only** what was installed: the plugin's own directory and
    its one record. Other plugins, the manifest file itself, and
    everything under ``agents/`` are untouched. That guarantee is
    structural rather than bookkeeping — the plugin occupies exactly one
    directory, so there is no file list to get wrong.

    Raises ``PluginError`` when the plugin is neither recorded nor on
    disk. A plugin that is one but not the other is *repaired* rather
    than refused: a directory with no record is still removed, and a
    record with no directory still has its entry dropped, since in both
    cases the user asked for the same end state and reaching it is
    unambiguous.

    Returns ``{"name", "path", "removed_dir", "removed_record"}``.
    """
    name = _validate_name(name)
    dst = plugins_dir(tier_root) / name
    manifest = read_manifest(tier_root)

    had_dir = dst.is_dir()
    had_record = name in manifest["plugins"]

    if not had_dir and not had_record:
        raise PluginError(f"plugin {name!r} is not installed at {tier_root}")

    if had_dir:
        shutil.rmtree(dst)

    if had_record:
        del manifest["plugins"][name]
        _write_manifest(tier_root, manifest)

    return {
        "name": name,
        "path": dst,
        "removed_dir": had_dir,
        "removed_record": had_record,
    }
