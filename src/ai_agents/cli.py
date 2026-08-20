"""The ``ai-agents`` command line.

Four commands: ``init`` populates the user master tier, ``list`` shows what
is in it, ``install`` copies one agent down into a project or workspace
tier, and ``doctor`` is reserved for environment checks.

The CLI's whole job is moving agent directories between tiers. It does not
interpret an agent's content — that is the harness's job.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from . import __version__, catalog, install, tiers


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


@cli.command(name="install")
@click.argument("name")
@click.option("--project", "tier", flag_value="project", default=True, help="Install into the project tier (default).")
@click.option("--workspace", "tier", flag_value="workspace", help="Install into the workspace tier.")
def install_cmd(name: str, tier: str) -> None:
    """Copy agent NAME from the user master down into a lower tier."""
    resolved = tiers.resolve(Path.cwd())
    dst_root = resolved[tier]

    if dst_root is None:
        hint = "not inside a git repo" if tier == "project" else "no ancestor declares a .ai-agents workspace"
        raise click.ClickException(f"no {tier} tier here ({hint})")

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

    if not results:
        click.echo("No supported harness detected here — no pointer files written.")
        return

    click.echo("\nHarness pointers:")
    for result in results:
        click.echo(f"  {result['harness']:<12} {result['action']:<10} {result['path']}")
        if result["reason"]:
            click.echo(f"    left alone: {result['reason']}")


@cli.command()
def doctor() -> None:
    """Check the environment. STUB."""
    click.echo("planned checks: harness detection, tier contents — not yet implemented")


if __name__ == "__main__":  # pragma: no cover
    cli()
