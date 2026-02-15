# Pymodoro

A lightweight system-tray Pomodoro timer with fullscreen check-ins and quick notes.

## Features
- System tray timer with live countdown
- Fullscreen check-in prompt with note capture and snooze
- Pause until a specific time
- YAML-based settings with sensible defaults

## Requirements
- Python 3.12 to 3.14
- A desktop session with system tray support

## Install
Direct install using pipx (or pip, although not recomended to keep separate environment)
```bash
pipx install git+https://github.com/Teabaud/pymodoro
```

Manual install using Poetry:

```bash
poetry install
```

## Run
With pipx install
```bash
pymodoro
```

With Poetry install

```bash
poetry run pymodoro
```

## Settings
On first run, `settings.yaml` is created in the project root with defaults:

```yaml
timers:
  work_duration: 1500  # seconds (25 minutes)
  break_duration: 300  # seconds (5 minutes)
  snooze_duration: 60  # seconds (1 minute)

check_in:
  prompts:
    - "How present are you in what you do?"
    - "What do you want to focus on next?"
    - "What is your goal for the day?"
```

Update the values to fit your workflow. Changes are picked up on the next launch.

## Development
```bash
poetry run pytest
```
