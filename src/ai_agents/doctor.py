"""Environment diagnostics — issue #15, the story in #6.

``run_checks`` is the whole implementation; ``cli.doctor`` only renders
what it returns. That split exists so the checks are a plain function
returning data — testable without shelling out to the CLI or scraping
stdout, which is exactly what issue #16 needs — and so the printing lives
in exactly one place, next to every other command's rendering, in
``cli.py``.

Every check is reused from the module that already owns the underlying
logic — ``tiers.resolve`` for tier roots, ``catalog.list_agents`` and
``catalog.find_dangling_skill_refs`` for tier contents and content
integrity, ``install.detect_harnesses``/``harness_probes`` for
harness presence, ``lifecycle.diff_agent`` for drift. Nothing here
re-derives a definition any of those modules already own; a second copy
of "what counts as diverged" or "what counts as detected" is exactly the
kind of thing that quietly drifts from the original and makes this
command lie.

**Status vocabulary.** Every finding carries one of four statuses:

* ``OK`` — checked, and in the expected state.
* ``INFO`` — a normal, unremarkable condition that still seems worth
  naming (an optional harness that simply is not installed, a workspace
  tier that does not exist, a project tier that has not had anything
  installed into it yet). Never affects the exit code, and is not phrased
  as a problem.
* ``WARN`` — worth a person's attention but not something ``doctor``
  itself can call broken: an installed copy that has diverged from its
  master may hold edits made on purpose (``install.py``'s own words), and
  a dangling Skill reference is an authoring mistake in content, not a
  failure of anything this tool did. Does not affect the exit code.
* ``ERROR`` — the tool's own invariants are violated: a copy on disk that
  nothing can act on correctly. This is the only status that flips the
  exit code, so it is kept to conditions with a genuine, nameable cause
  and a concrete fix — never to "a harness is not configured here".

**What counts as ERROR, and why.**

* The user master tier does not exist. Every other tier is optional by
  design (see ``tiers.py``); the user tier is not — it is described as
  "always present after `ai-agents init`" and every lower-tier install,
  update, and diff sources from it. Nothing else in this report can be
  trusted once it is missing. Fix: ``ai-agents init``.
* An agent directory with no ``AGENT.md``. ``catalog.list_agents`` already
  filters these out silently, which is correct for ``list`` — but it
  means a directory in this state is invisible everywhere except here.
  Nothing can read it, diff it, or point a harness at it. Fix: remove and
  reinstall it (project/workspace), or repair it by hand (user tier,
  which has no CLI mutation path of its own).
* A generated per-agent harness pointer (Claude Code, Cline) whose agent
  directory is gone. Its target ``AGENT.md`` cannot exist if the
  directory that would hold it does not, so the harness reading this
  pointer is being pointed at nothing. Detected without parsing the
  pointer's rendered content — which would duplicate ``install.py``'s
  rendering format — by comparing the pointer's filename stem (the agent
  name) against the directory names actually present, using the already
  public ``harness_pointer_path``. Hand-authored files (no
  ``GENERATED_MARKER``) are never flagged; they were never ours to judge.
  Fix: delete the stale pointer.

  The context-file harnesses (Gemini CLI, Qwen Code) share one managed
  block across every agent at a tier, so a name going stale there would
  require parsing the rendered block to find out which entries it lists —
  the same duplication problem, at a harder spot. That check is left out
  on purpose rather than built on a second copy of the block format; see
  ``install._render_context_block``. Re-running any ``install``/``update``/
  ``remove`` at that tier already regenerates the block in full, which is
  the practical fix regardless.
* An unreadable ``plugins.json``, or an external plugin recorded in it
  that is not on disk. Unlike an agent, nothing here *loads* a plugin —
  but the manifest is the only record of where one came from and what
  could not bend, so a corrupt or lying record is a failure of the one
  job this file has. See ``plugins.read_manifest`` for why malformed is
  raised rather than degraded, which is the opposite of how ``catalog``
  treats a broken ``AGENT.md``.

**What counts as WARN, and why not ERROR.** Drift (``lifecycle.diff_agent``
reports ``diverged``) is exactly the situation ``install.copy_agent``'s own
docstring names as "may have been edited on purpose" — the never-overwrite
guarantee exists *because* a diverged copy can be intentional. Calling
that broken would make ``doctor`` cry wolf on the tool's own normal
operating mode. A dangling Skill reference (``catalog.find_dangling_skill_refs``)
is a content-authoring mistake, not a failure of anything this tool
manages — the agent still installs, copies, and points fine. An external
plugin present on disk but absent from ``plugins.json`` is the same
shape: it still works, since nothing here loads it, but its provenance is
gone.
"""

from __future__ import annotations

from pathlib import Path

from . import catalog, install, lifecycle, plugins, tiers

__all__ = ["run_checks", "OK", "INFO", "WARN", "ERROR"]

OK = "ok"
INFO = "info"
WARN = "warn"
ERROR = "error"

#: Tiers to walk, in report order. Matches the resolution order documented
#: in ``tiers.py`` (closest wins on lookup; here we simply visit all three).
_TIER_NAMES = ("project", "workspace", "user")

#: Harnesses whose pointer is one file per agent, and therefore nameable
#: back to a single agent directory — see the module docstring's ERROR
#: list for why the context-file harnesses are not checked the same way.
_PER_AGENT_HARNESSES = ("claude-code", "cline")


def run_checks(cwd: str | Path | None = None) -> dict:
    """Run every doctor check for ``cwd`` (default: the current directory).

    Returns ``{"tiers": [...], "harnesses": [...], "agents": [...],
    "plugins": [...], "has_errors": bool}``. Each list holds one finding
    dict per check; see ``_check_tier``, ``_check_harnesses``,
    ``_check_agents``, and ``_check_plugins`` for their exact shapes.
    ``has_errors`` is ``True`` iff any finding anywhere in the report
    carries ``status == ERROR`` — the only thing ``cli.doctor`` needs to
    decide its exit code, so it is precomputed here rather than asking
    the caller to re-scan four lists.

    Purely reads: nothing on disk is created, written, or deleted, no
    matter what is found.
    """
    resolved = tiers.resolve(cwd)
    user_root = resolved["user"]

    tier_findings = []
    harness_findings = []
    agent_findings = []
    plugin_findings = []

    for tier_name in _TIER_NAMES:
        tier_root = resolved[tier_name]
        tier_findings.append(_check_tier(tier_name, tier_root))

        if tier_root is None:
            # No project (not in a git repo) / no ancestor workspace: there
            # is no harness root to probe and no agents/ to scan either.
            continue

        harness_findings.extend(_check_harnesses(tier_name, tier_root))

        if tier_root.is_dir():
            agent_findings.extend(_check_agents(tier_name, tier_root, user_root))
            plugin_findings.extend(_check_plugins(tier_name, tier_root))

    # Every list, including harnesses — no harness check produces an ERROR
    # today, but scanning only the ones that currently can would quietly
    # break the promise above the moment one did.
    has_errors = any(
        f["status"] == ERROR
        for f in (*tier_findings, *harness_findings, *agent_findings, *plugin_findings)
    )

    return {
        "tiers": tier_findings,
        "harnesses": harness_findings,
        "agents": agent_findings,
        "plugins": plugin_findings,
        "has_errors": has_errors,
    }


# --------------------------------------------------------------------------
# Tiers
# --------------------------------------------------------------------------


def _check_tier(tier_name: str, tier_root: Path | None) -> dict:
    """One finding for a tier root: does it resolve, does it exist, how big.

    Returns ``{"tier", "root", "exists", "agent_count", "status", "detail",
    "fix"}``. ``root`` is ``None`` exactly when ``tiers.resolve`` returned
    ``None`` for this tier (project: not in a git repo; workspace: no
    ancestor declares one) — normal, so ``INFO``, never ``ERROR``.

    A tier root that resolves to a path but has nothing on disk yet is
    also normal for project/workspace — ``tiers.py`` describes the project
    tier as starting empty — so that is ``INFO`` too. The one exception is
    the user tier: it is documented as always present after ``ai-agents
    init``, every install/update/diff sources from it, and nothing else in
    this report means anything once it is missing — so that combination
    alone is ``ERROR``.
    """
    if tier_root is None:
        hint = (
            "not inside a git repo"
            if tier_name == "project"
            else "no ancestor declares an .ai-agents workspace"
        )
        return {
            "tier": tier_name,
            "root": None,
            "exists": False,
            "agent_count": 0,
            "status": INFO,
            "detail": hint,
            "fix": None,
        }

    exists = tier_root.is_dir()
    if not exists:
        if tier_name == "user":
            return {
                "tier": tier_name,
                "root": tier_root,
                "exists": False,
                "agent_count": 0,
                "status": ERROR,
                "detail": "user master tier has not been initialized",
                "fix": "ai-agents init",
            }
        return {
            "tier": tier_name,
            "root": tier_root,
            "exists": False,
            "agent_count": 0,
            "status": INFO,
            "detail": "no agents installed here yet",
            "fix": None,
        }

    count = len(catalog.list_agents(tier_root))
    return {
        "tier": tier_name,
        "root": tier_root,
        "exists": True,
        "agent_count": count,
        "status": OK,
        "detail": None,
        "fix": None,
    }


# --------------------------------------------------------------------------
# Harnesses
# --------------------------------------------------------------------------


def _check_harnesses(tier_name: str, tier_root: Path) -> list[dict]:
    """One finding per harness in ``install.HARNESSES`` order, for this tier.

    Reuses ``install.detect_harnesses`` for the yes/no answer and
    ``install.harness_probes`` for *what was checked to reach it* — the
    honesty requirement at the heart of this issue: a harness reported
    absent must say what was probed for it, using the exact same probes
    ``detect_harnesses`` itself tested, not a second guess at them. That
    extends to the hit test: ``Probe.hit`` decides what matched here, so
    this cannot quietly disagree with detection about what counts (a
    regular file named ``.claude`` is not Claude Code being in use).

    Returns ``{"tier", "harness", "detected", "status", "probed", "matched"}``.
    ``probed`` is every path ``detect_harnesses`` tested, in the order it
    tested them; ``matched`` is whichever one actually hit (``None`` when
    absent) — a context-file harness can be detected by either its config
    directory or a bare context file, and reporting ``probed[0]``
    unconditionally would sometimes name the wrong one. Absence is always
    ``INFO``, never ``WARN``/``ERROR`` — an optional harness someone has
    not set up is not a defect.
    """
    detected = set(install.detect_harnesses(tier_root, tier_name))
    findings = []
    for harness in install.HARNESSES:
        is_detected = harness in detected
        probes = install.harness_probes(harness, tier_root, tier_name)
        probed = [p.path for p in probes]
        matched = next((p.path for p in probes if p.hit()), None) if is_detected else None
        findings.append(
            {
                "tier": tier_name,
                "harness": harness,
                "detected": is_detected,
                "status": OK if is_detected else INFO,
                "probed": probed,
                "matched": matched,
            }
        )
    return findings


# --------------------------------------------------------------------------
# Agents: integrity, drift, stale pointers
# --------------------------------------------------------------------------


def _agent_dirs(tier_root: Path) -> list[Path]:
    """Every directory under ``tier_root/agents``, regardless of content.

    Deliberately not ``catalog.list_agents`` — that already filters out a
    directory with no ``AGENT.md``, which is precisely the breakage this
    module needs to see in order to report it.
    """
    agents_dir = tier_root / "agents"
    if not agents_dir.is_dir():
        return []
    return sorted(p for p in agents_dir.iterdir() if p.is_dir())


def _remove_hint(tier_name: str, name: str) -> str:
    """The CLI incantation that would repair agent ``name`` at this tier.

    The user tier has no CLI command that mutates it directly — ``remove``/
    ``update``/``install`` all take a project/workspace *destination* and
    always source from the user tier (see ``cli.py``'s own comments) — so
    a broken agent there can only be named for manual repair.
    """
    if tier_name == "user":
        return (
            f"repair or delete ~/.ai-agents/agents/{name} by hand — "
            "there is no CLI command that edits the user tier directly"
        )
    flag = "--workspace" if tier_name == "workspace" else "--project"
    return f"ai-agents remove {name} {flag}, then ai-agents install {name} {flag}"


def _drift_finding(tier_name: str, name: str, user_root: Path, tier_root: Path) -> dict:
    """Compare one installed agent against the user master copy.

    Always diffs against ``user_root``, never against "whichever tier is
    immediately above" — the same choice ``cli.diff_cmd``/``update_cmd``
    already make deliberately (see their docstrings), so drift reported
    here means exactly what ``ai-agents diff`` would report if run by
    hand.

    An agent present locally but absent from the user master entirely
    (nothing there to diff against — e.g. a project-only agent nobody ever
    installed from the master) is ``INFO``, not a defect: nothing requires
    every agent at a lower tier to trace back to the catalog.
    """
    try:
        diff = lifecycle.diff_agent(name, user_root, tier_root)
    except FileNotFoundError:
        return {
            "tier": tier_name,
            "agent": name,
            "status": INFO,
            "detail": "not present in the user master copy — nothing to compare against",
            "fix": None,
        }

    flag = "--workspace" if tier_name == "workspace" else "--project"
    if diff["diverged"]:
        total = len(diff["changed"]) + len(diff["master_only"]) + len(diff["local_only"])
        return {
            "tier": tier_name,
            "agent": name,
            "status": WARN,
            "detail": f"diverged from the user master copy ({total} file(s) differ)",
            "fix": f"ai-agents diff {name} {flag}   (then ai-agents update {name} {flag} [--force] to overwrite)",
        }
    return {
        "tier": tier_name,
        "agent": name,
        "status": OK,
        "detail": "matches the user master copy",
        "fix": None,
    }


def _stale_pointer_findings(tier_name: str, tier_root: Path, agent_names: set[str]) -> list[dict]:
    """Generated per-agent pointers whose agent directory no longer exists.

    Only the per-agent harnesses (Claude Code, Cline) are checked — see the
    module docstring for why the context-file harnesses' shared block is
    left out. A pointer's filename stem is the agent name it was generated
    for (``install.harness_pointer_path``'s own convention); if no directory
    of that name remains under ``tier_root/agents``, its ``AGENT.md`` target
    cannot exist either. A hand-authored file (no ``GENERATED_MARKER``) is
    never flagged, matching every other rule in ``install.py`` about files
    this tool did not write.
    """
    findings = []
    for harness in _PER_AGENT_HARNESSES:
        # "_probe_" is never a real agent name; only its parent directory
        # (where every pointer for this harness/tier lives) matters here.
        pointer_dir = install.harness_pointer_path(harness, tier_root, tier_name, "_probe_").parent
        if not pointer_dir.is_dir():
            continue

        for pointer_file in sorted(pointer_dir.glob("*.md")):
            name = pointer_file.stem
            if name in agent_names:
                continue

            content = pointer_file.read_text(encoding="utf-8")
            if install.GENERATED_MARKER not in content:
                continue

            findings.append(
                {
                    "tier": tier_name,
                    "agent": name,
                    "status": ERROR,
                    "detail": f"{harness} pointer at {pointer_file} has no matching agent — its AGENT.md is gone",
                    "fix": f"rm '{pointer_file}'",
                }
            )
    return findings


def _check_agents(tier_name: str, tier_root: Path, user_root: Path) -> list[dict]:
    """Every agent-level finding for one existing tier: integrity, drift,
    dangling Skill references, and stale pointers.

    Returns a flat list of ``{"tier", "agent", "status", "detail", "fix"}``
    dicts — zero or more per agent directory, since an agent can trigger
    more than one kind of finding (e.g. both diverged *and* holding a
    dangling reference).
    """
    findings = []
    agent_dirs = _agent_dirs(tier_root)
    agent_names = {d.name for d in agent_dirs}

    for agent_dir in agent_dirs:
        name = agent_dir.name
        entry = catalog.read_agent(agent_dir)

        if entry is None:
            findings.append(
                {
                    "tier": tier_name,
                    "agent": name,
                    "status": ERROR,
                    "detail": f"{agent_dir} has no AGENT.md",
                    "fix": _remove_hint(tier_name, name),
                }
            )
            continue

        for dangling in catalog.find_dangling_skill_refs(entry):
            findings.append(
                {
                    "tier": tier_name,
                    "agent": name,
                    "status": WARN,
                    "detail": (
                        f"workflow {dangling['workflow']!r} references "
                        f"missing skill {dangling['skill']!r}"
                    ),
                    "fix": (
                        f"add Skills/{dangling['skill']}.md under {agent_dir}, "
                        f"or fix the reference in Workflows/{dangling['workflow']}.md"
                    ),
                }
            )

        # The user tier *is* the master; nothing to diff it against.
        if tier_name != "user":
            findings.append(_drift_finding(tier_name, name, user_root, tier_root))

    findings.extend(_stale_pointer_findings(tier_name, tier_root, agent_names))
    return findings


# --------------------------------------------------------------------------
# External plugins
# --------------------------------------------------------------------------


def _check_plugins(tier_name: str, tier_root: Path) -> list[dict]:
    """Findings for the external plugins installed at this tier.

    Returns a list of ``{"tier", "plugin", "source", "reason", "status",
    "detail", "fix"}``. Empty when the tier has neither a manifest nor a
    ``plugins/`` directory, which is the normal case — external plugins
    are the exception, not the usual way to adopt something.

    Three things can be wrong, and they are graded by what a reader can
    still trust:

    * **Manifest unreadable** -> ERROR, reported once for the tier with
      ``plugin`` set to ``None``. Nothing else here can be believed if
      the record is corrupt, so this short-circuits rather than guessing
      from directory names.
    * **Recorded but missing from disk** -> ERROR. The record claims
      something is installed that is not there; anything relying on it is
      broken now.
    * **On disk but unrecorded** -> WARN, not ERROR. The plugin still
      works — nothing here loads it — but its provenance is gone: no
      source, and no statement of what could not bend. That is a
      bookkeeping failure, and grading it as broken would be crying wolf
      in exactly the way this module's docstring warns against.
    """
    try:
        recorded = plugins.list_plugins(tier_root)
    except plugins.PluginError as exc:
        return [
            {
                "tier": tier_name,
                "plugin": None,
                "source": None,
                "reason": None,
                "status": ERROR,
                "detail": str(exc),
                "fix": (
                    f"repair or delete {plugins.manifest_path(tier_root)} — "
                    "it is machine-written JSON and nothing edits it by hand"
                ),
            }
        ]

    findings = []
    for record in recorded:
        if record["present"]:
            findings.append(
                {
                    "tier": tier_name,
                    "plugin": record["name"],
                    "source": record.get("source"),
                    "reason": record.get("reason"),
                    "status": OK,
                    "detail": f"installed from {record.get('source', 'an unrecorded source')}",
                    "fix": "",
                }
            )
        else:
            findings.append(
                {
                    "tier": tier_name,
                    "plugin": record["name"],
                    "source": record.get("source"),
                    "reason": record.get("reason"),
                    "status": ERROR,
                    "detail": f"recorded but missing from disk ({record['path']})",
                    "fix": (
                        f"ai-agents plugin remove {record['name']} --{tier_name} "
                        "to drop the stale record, then reinstall if it is still wanted"
                    ),
                }
            )

    known = {r["name"] for r in recorded}
    plugins_root = plugins.plugins_dir(tier_root)
    if plugins_root.is_dir():
        for path in sorted(p for p in plugins_root.iterdir() if p.is_dir()):
            if path.name in known:
                continue
            findings.append(
                {
                    "tier": tier_name,
                    "plugin": path.name,
                    "source": None,
                    "reason": None,
                    "status": WARN,
                    "detail": "present on disk but not recorded — provenance unknown",
                    "fix": (
                        f"reinstall it with ai-agents plugin install <source> "
                        f"--name {path.name} --reason '<what could not bend>' --force, "
                        "or delete it by hand"
                    ),
                }
            )

    return findings
