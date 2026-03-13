from __future__ import annotations

import click

from clawductor.config import load_config
from clawductor.doctor import doctor
from clawductor.state import load_state
from clawductor.tui import ClawductorApp


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Clawductor — TUI orchestration runtime for Claude Code."""
    if ctx.invoked_subcommand is None:
        _launch_tui()


main.add_command(doctor)


def _launch_tui() -> None:
    load_config()  # ensures config file exists with defaults
    state = load_state()
    app = ClawductorApp(state=state)
    app.run()
