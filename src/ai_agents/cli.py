"""The ``ai-agents`` command line.

``init`` populates the user master tier, ``list`` shows what is in it,
``install`` copies one agent down into a project or workspace tier,
``update``/``diff``/``remove`` maintain an agent already installed there,
and ``doctor`` is reserved for environment checks.

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


def _repo_root() -> Path:
    """Best-effort location of a checkout of this repo (for ``init``).

    Walks up from this file looking for a directory holding both
    ``agents/`` and ``pyproject.toml``. Works for an editable install of a
    checkout, which is how ``init`` is expected to be run; a non-editable
    install has no bundled ``agents/`` tree, so ``init`` there needs an
    explicit ``--source``.
    """
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "agents").is_dir() and (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd()


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
    help="Repo checkout to seed from (default: auto-detected).",
)
def init(source: Path | None) -> None:
    """Populate the user master tier (~/.ai-agents) from this repo."""
    src = (source or _repo_root()) / "agents"
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


@cli.command()
def doctor() -> None:
    """Check the environment. STUB."""
    click.echo("planned checks: harness detection, tier contents — not yet implemented")


if __name__ == "__main__":  # pragma: no cover
    cli()
