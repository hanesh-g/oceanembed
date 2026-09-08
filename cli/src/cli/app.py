"""oe — root Typer application and entry point for OceanEmbed.

Mounts in-tree command sub-apps and discovers third-party plugins.
The shipped console script (``[project.scripts] oe``) targets
``app`` directly.
"""

from __future__ import annotations

import typer

from . import plugins as _plugins
from .commands import zarr as _zarr_cmd
from .commands import argo as _argo_cmd
from .commands import pipeline as _pipeline_cmd

app = typer.Typer(
    name="oe",
    help="OceanEmbed command-line tool.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

# In-tree commands. Mounted before plugin discovery so a plugin can't
# silently shadow a built-in by registering the same name.
app.add_typer(_zarr_cmd.app, name="zarr", help="Manage Zarr test datasets and pointer swaps.")
app.add_typer(_argo_cmd.app, name="argo", help="Manage PostGIS and In-Situ Data.")
app.add_typer(_pipeline_cmd.app, name="pipeline", help="Inference Pipeline (Worker Integration).")

def _mount_command_plugins() -> None:
    """Mount external Typer sub-apps registered under ``oe.commands``."""
    builtin_names = {"zarr", "argo", "pipeline"}
    for name, sub_app in _plugins.discover_command_plugins().items():
        if name in builtin_names:
            typer.secho(
                f"warning: plugin command '{name}' shadows a built-in; ignoring.",
                fg=typer.colors.YELLOW,
                err=True,
            )
            continue
        app.add_typer(sub_app, name=name)


_mount_command_plugins()


@app.callback()
def _root() -> None:
    """oe — OceanEmbed command-line tool."""
    # Typer uses this docstring as the root help text. The body is
    # intentionally empty: the callback exists so options like
    # ``--install-completion`` work without arguments.


if __name__ == "__main__":  # pragma: no cover
    app()
