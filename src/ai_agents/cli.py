"""The ``ai-agents`` command line.

``init`` populates the user master tier, ``list`` shows what is in it,
``install`` copies one agent down into a project or workspace tier,
``update``/``diff``/``remove`` maintain an agent already installed there,
and ``doctor`` reports harness detection, tier contents, and drift across
all three tiers at once (see ``doctor.py``).

The CLI's whole job is moving agent directories between tiers. It does not
interpret an agent's content — that is the harness's job.

``update``, ``diff``, and ``remove`` share ``install``'s ``--project`` /
``--workspace`` destination flags and the same source: the user master
tier. That mirrors ``install_cmd`` exactly, on purpose — an agent is always
installed *from* the master, so refreshing or diffing it is a comparison
against that same master, not against whichever tier happens to be above
it in the resolution order.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from . import __version__, catalog, install, lifecycle, tiers
# Names, not the module: the `doctor` command below shadows a module
# import of the same name.
from .doctor import ERROR, INFO, OK, WARN, run_checks


def _tier_options(f):
    """Shared ``--project``/``--workspace`` destination flags.

    Factored out because ``install``, ``update``, ``diff``, and ``remove``
    all resolve their destination tier identically — one is default, the
    other opt-in, never both.
    """
    f = click.option(
        "--workspace", "tier", flag_value="workspace", help="Use the workspace tier."
    )(f)
    f = click.option(
        "--project", "tier", flag_value="project", default=True, help="Use the project tier (default)."
    )(f)
    return f


def _resolve_dst(tier: str) -> Path:
    """The destination tier root for ``update``/``diff``/``remove``/``install``.

    Raises ``click.ClickException`` with a tier-specific hint when the
    requested tier does not resolve here, matching ``install_cmd``'s
    existing error message exactly.
    """
    resolved = tiers.resolve(Path.cwd())
    dst_root = resolved[tier]
    if dst_root is None:
        hint = "not inside a git repo" if tier == "project" else "no ancestor declares a .ai-agents workspace"
        raise click.ClickException(f"no {tier} tier here ({hint})")
    return dst_root


#: The catalog as it lands inside an installed wheel. ``agents/`` is
#: force-included at build time (see ``pyproject.toml``), so on any
#: non-editable install this directory *is* the catalog — no checkout, no
#: network, no ``--source``.
_BUNDLED_CATALOG = Path(__file__).resolve().parent / "_catalog"


def _checkout_catalog() -> Path | None:
    """The ``agents/`` tree of a checkout of this repo, if we are in one.

    Walks up from this file looking for a directory holding both
    ``agents/`` and ``pyproject.toml``. This is the *developer* path: an
    editable install points at ``src/`` in the working tree, where the
    build-time force-include has not run and so no ``_catalog`` exists.
    Returns ``None`` when no such ancestor is found.
    """
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "agents").is_dir() and (candidate / "pyproject.toml").is_file():
            return candidate / "agents"
    return None


def _catalog_source() -> Path:
    """Where ``init`` seeds the user master from, absent ``--source``.

    Two places, in order: the catalog bundled into the installed package,
    then a checkout of this repo. The bundled copy wins so that a developer
    who *also* has the package installed gets a predictable answer rather
    than one that depends on where the interpreter resolved ``ai_agents``.

    Deliberately raises instead of falling back to ``Path.cwd()``. The old
    fallback meant ``init`` run from an arbitrary directory would either
    seed from whatever ``agents/`` happened to be underfoot or fail with a
    message pointing at a path the user never named — both worse than
    saying plainly that there is no catalog to seed from.
    """
    if _BUNDLED_CATALOG.is_dir():
        return _BUNDLED_CATALOG

    checkout = _checkout_catalog()
    if checkout is not None:
        return checkout

    raise click.ClickException(
        "no agent catalog found: this install bundles none and no checkout of "
        "the repo was found above "
        f"{Path(__file__).resolve().parent}. Reinstall the package, or pass "
        "`--source /path/to/checkout`."
    )


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """Cross-harness catalog of agents and their workflows."""


@cli.command(name="list")
def list_cmd() -> None:
    """List the agents in the user master tier."""
    root = tiers.user_root()
    agents = catalog.list_agents(root)

    if not agents:
        click.echo(f"No agents found in {root}. Run `ai-agents init` first.")
        return

    click.echo(f"{len(agents)} agent(s) in {root}:\n")
    for agent in agents:
        click.echo(f"  {agent['name']}")
        if agent["description"]:
            click.echo(f"    {agent['description']}")
        skills = agent["skills"]
        workflows = agent["workflows"]
        if not skills and not workflows:
            # Neither kind present: keep the old single-line "(none)"
            # signal rather than printing two empty "(none)" lines.
            click.echo("    workflows: (none)")
        else:
            # Skills and workflows each get their own line, but an empty one
            # is omitted entirely rather than printed as "(none)" — an agent
            # with only workflows (or only skills) should not show a
            # spurious empty line for the kind it doesn't have.
            if skills:
                click.echo(f"    skills: {', '.join(skills)}")
            if workflows:
                click.echo(f"    workflows: {', '.join(workflows)}")
        click.echo()


@cli.command()
@click.option(
    "--source",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Repo checkout to seed from (default: the catalog shipped with this install).",
)
def init(source: Path | None) -> None:
    """Populate the user master tier (~/.ai-agents) with the agent catalog.

    Needs no arguments: the catalog ships inside the package, so a plain
    ``ai-agents init`` works on an ordinary ``pipx``/``uv`` install with no
    checkout, no network, and no git. ``--source`` remains a developer
    convenience for seeding from a specific checkout instead — it takes the
    repo root, and the ``agents/`` directory beneath it is what gets copied.
    """
    src = (source / "agents") if source is not None else _catalog_source()
    dst = tiers.user_root() / "agents"

    if not src.is_dir():
        raise click.ClickException(f"no agents/ directory at {src}")

    if dst.exists():
        click.echo(f"Already initialized: {dst} (left untouched)")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=False)
    click.echo(f"Initialized {dst} from {src}")


def _echo_pointer_results(results: list[dict], *, empty_note: str = "no pointer files written") -> None:
    """Print a ``{"harness", "path", "action", "reason"}`` list the same way
    everywhere — ``install``, ``update``, and ``remove`` all end with one.

    ``empty_note`` exists because "no harness detected" means something
    different depending on the caller: nothing was written on install,
    nothing was there to clean up on remove.
    """
    if not results:
        click.echo(f"No supported harness detected here — {empty_note}.")
        return

    click.echo("\nHarness pointers:")
    for result in results:
        click.echo(f"  {result['harness']:<12} {result['action']:<10} {result['path']}")
        if result["reason"]:
            click.echo(f"    left alone: {result['reason']}")


@cli.command(name="install")
@click.argument("name")
@_tier_options
def install_cmd(name: str, tier: str) -> None:
    """Copy agent NAME from the user master down into a lower tier."""
    resolved = tiers.resolve(Path.cwd())
    dst_root = _resolve_dst(tier)

    try:
        copied = install.copy_agent(name, resolved["user"], dst_root)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    if copied:
        click.echo(f"Installed {name} -> {dst_root / 'agents' / name}")
    else:
        click.echo(f"{name} already present at {dst_root / 'agents' / name} (not overwritten)")

    # Pointers are regenerated even when the copy was a no-op: the agent may
    # be present from an earlier install whose harness had not been set up
    # yet, and regenerating an unchanged pointer costs nothing.
    results = install.generate_harness_adapters(name, dst_root, tier=tier)
    _echo_pointer_results(results)


@cli.command(name="update")
@click.argument("name")
@_tier_options
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite the installed copy even if it holds local edits.",
)
def update_cmd(name: str, tier: str, force: bool) -> None:
    """Refresh agent NAME at a lower tier from the user master copy.

    Picking up changes the master has made since install needs no flag —
    that is the ordinary case. ``--force`` is only required when the
    installed copy itself holds local edits (a changed or locally-added
    file), because refreshing would destroy them. Run ``ai-agents diff``
    first to see exactly what would be overwritten.
    """
    resolved = tiers.resolve(Path.cwd())
    dst_root = _resolve_dst(tier)

    try:
        diff = lifecycle.update_agent(name, resolved["user"], dst_root, force=force)
    except lifecycle.LocalDivergenceError as exc:
        raise click.ClickException(f"{exc} (see `ai-agents diff {name}`)") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Updated {name} -> {dst_root / 'agents' / name}")
    overwritten = lifecycle.local_evidence(diff)
    if overwritten:
        click.echo(f"  {len(overwritten)} file(s) of local edits were overwritten (--force)")
    if diff["master_only"]:
        click.echo(f"  picked up {len(diff['master_only'])} new file(s) from the master")

    results = install.generate_harness_adapters(name, dst_root, tier=tier)
    _echo_pointer_results(results)


@cli.command(name="diff")
@click.argument("name")
@_tier_options
def diff_cmd(name: str, tier: str) -> None:
    """Report drift between an installed agent and the user master copy.

    Purely read-only — nothing on disk changes, no matter how much drift
    is reported. See ``ai-agents update`` to actually refresh the copy.
    """
    resolved = tiers.resolve(Path.cwd())
    dst_root = _resolve_dst(tier)

    try:
        diff = lifecycle.diff_agent(name, resolved["user"], dst_root)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    if not diff["diverged"]:
        click.echo(f"{name} matches the user master copy — no drift.")
        return

    click.echo(f"{name} has diverged from the user master copy:\n")
    if diff["changed"]:
        click.echo("  changed (differs on both sides):")
        for rel in diff["changed"]:
            click.echo(f"    {rel}")
    if diff["master_only"]:
        click.echo("  missing locally (present in the master copy):")
        for rel in diff["master_only"]:
            click.echo(f"    {rel}")
    if diff["local_only"]:
        click.echo("  local-only (not in the master copy):")
        for rel in diff["local_only"]:
            click.echo(f"    {rel}")


@cli.command(name="remove")
@click.argument("name")
@_tier_options
def remove_cmd(name: str, tier: str) -> None:
    """Delete agent NAME from a tier, along with its generated pointers.

    A pointer a person hand-authored (no ``ai-agents``-generated marker) is
    never deleted, even if it sits at the exact path a pointer would occupy
    — see ``install.remove_harness_adapters``.
    """
    dst_root = _resolve_dst(tier)

    try:
        result = lifecycle.remove_agent(name, dst_root, tier=tier)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Removed {dst_root / 'agents' / name}")
    _echo_pointer_results(result["pointers"], empty_note="no pointer files to clean up")


#: Short tag printed ahead of every doctor finding. Kept to four characters
#: so every line lines up regardless of status; ``info`` prints as ``--``
#: rather than a word, since the whole point of that status is that it is
#: not something to alarm about — see ``doctor.py``'s module docstring for
#: the vocabulary this maps.
_DOCTOR_TAGS = {OK: "ok  ", INFO: "--  ", WARN: "warn", ERROR: "FAIL"}


def _doctor_tag(status: str) -> str:
    return _DOCTOR_TAGS[status]


def _echo_doctor_harnesses(findings: list[dict]) -> None:
    """Render ``doctor.run_checks()["harnesses"]``, grouped by tier.

    Absence is printed with exactly what was probed for it (the paths
    ``install.harness_probes`` reported) so "absent" is never a bare
    unsupported claim — see the honesty requirement in issue #15.
    """
    click.echo("Harnesses:")
    current_tier = None
    for f in findings:
        if f["tier"] != current_tier:
            current_tier = f["tier"]
            click.echo(f"  {current_tier}:")
        if f["detected"]:
            click.echo(f"    [{_doctor_tag(f['status'])}] {f['harness']:<12} detected at {f['matched']}")
        else:
            probed = ", ".join(str(p) for p in f["probed"])
            click.echo(f"    [{_doctor_tag(f['status'])}] {f['harness']:<12} absent (probed {probed})")


def _echo_doctor_tiers(findings: list[dict]) -> None:
    """Render ``doctor.run_checks()["tiers"]`` — one line per tier."""
    click.echo("\nTiers:")
    for f in findings:
        tag = _doctor_tag(f["status"])
        if f["root"] is None:
            click.echo(f"  [{tag}] {f['tier']:<10} {f['detail']}")
            continue
        if not f["exists"]:
            click.echo(f"  [{tag}] {f['tier']:<10} {f['root']} — {f['detail']}")
        else:
            click.echo(f"  [{tag}] {f['tier']:<10} {f['root']} ({f['agent_count']} agent(s))")
        if f["fix"]:
            click.echo(f"           fix: {f['fix']}")


def _echo_doctor_agents(findings: list[dict]) -> None:
    """Render ``doctor.run_checks()["agents"]`` — integrity, drift, and
    dangling-reference findings, one per line, with a fix line for anything
    reported as broken or drifted.
    """
    click.echo("\nAgents:")
    if not findings:
        click.echo("  (none installed below the user master tier)")
        return
    for f in findings:
        tag = _doctor_tag(f["status"])
        click.echo(f"  [{tag}] [{f['tier']}] {f['agent']:<24} {f['detail']}")
        if f["fix"]:
            click.echo(f"           fix: {f['fix']}")


@cli.command()
def doctor() -> None:
    """Report harness detection, tier contents, and drift.

    Purely read-only, like ``diff`` — nothing here writes to disk. Exits
    non-zero only when something is genuinely broken (see ``doctor.py``'s
    module docstring for exactly what qualifies); an absent optional
    harness, an empty tier, or a merely-diverged installed copy are all
    normal conditions and never affect the exit code.
    """
    report = run_checks(Path.cwd())

    _echo_doctor_harnesses(report["harnesses"])
    _echo_doctor_tiers(report["tiers"])
    _echo_doctor_agents(report["agents"])

    # All three lists, so the tally can never undercount against the exit
    # code doctor.run_checks computed from the same three.
    findings = (*report["tiers"], *report["harnesses"], *report["agents"])
    problems = [f for f in findings if f["status"] in (WARN, ERROR)]
    if report["has_errors"]:
        errors = sum(1 for f in problems if f["status"] == ERROR)
        warnings = sum(1 for f in problems if f["status"] == WARN)
        click.echo(f"\n{errors} error(s), {warnings} warning(s) — see fix lines above.")
        raise SystemExit(1)
    elif problems:
        click.echo(f"\n{len(problems)} warning(s) — nothing broken.")
    else:
        click.echo("\nAll checks passed.")


if __name__ == "__main__":  # pragma: no cover
    cli()
