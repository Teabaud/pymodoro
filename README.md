# Pymodoro

A lightweight system-tray Pomodoro timer with fullscreen breaks and quick notes.

## Features
- System tray timer with live countdown
- Fullscreen break prompt with note capture and snooze
- Pause until a specific time
- YAML-based configuration with sensible defaults

## Requirements
- Python 3.12 to 3.14
- A desktop session with system tray support

## Install
Using Poetry:

```bash
poetry install
```

## Run
```bash
poetry run pymodoro
```

## Configuration
On first run, `config.yaml` is created in the project root with defaults:

```yaml
timers:
  work_duration: 1500  # seconds (25 minutes)
  break_duration: 300  # seconds (5 minutes)
  snooze_duration: 60  # seconds (1 minute)

messages:
  work_end_question: "How do you feel rigth now?"
```

Update the values to fit your workflow. Changes are picked up on the next launch.

## Development
```bash
poetry run pytest
```
