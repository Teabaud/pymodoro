from __future__ import annotations

from pathlib import Path

import typer

from pymodoro.app import PomodoroApp
from pymodoro.settings import DEFAULT_SETTINGS_PATH, load_settings

cli = typer.Typer(add_completion=False)


@cli.command()
def run(
    settings_path: Path = typer.Option(
        DEFAULT_SETTINGS_PATH,
        "--settings",
        help="Path to settings file.",
    ),
) -> None:
    settings = load_settings(settings_path)
    app = PomodoroApp(settings=settings)
    app.launch()


def main() -> None:
    cli()


if __name__ == "__main__":
    raise SystemExit(main())
