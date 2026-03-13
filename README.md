# Clawductor

TUI orchestration runtime for Claude Code.

## Quick start

```bash
pip install -e .
clawductor          # launch TUI
clawductor doctor   # preflight checks
```

## Requirements

- Python >= 3.11
- tmux
- git
- [Claude Code CLI](https://docs.anthropic.com/claude-code)
- gh (optional, for PR features)

## Configuration

Config is auto-created at `~/.clawductor/config.yaml` on first run. Edit it to override model assignments, notification settings, or cost thresholds.
