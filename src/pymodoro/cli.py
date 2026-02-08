from __future__ import annotations

from pathlib import Path

import typer

from pymodoro.app import PomodoroApp
from pymodoro.config import DEFAULT_CONFIG_PATH, load_config

cli = typer.Typer(add_completion=False)


@cli.command()
def run(
    config_path: Path = typer.Option(
        DEFAULT_CONFIG_PATH,
        "--config",
        help="Path to config file.",
    ),
) -> None:
    config = load_config(config_path)
    app = PomodoroApp(config=config)
    app.launch()


def main() -> None:
    cli()


if __name__ == "__main__":
    raise SystemExit(main())
