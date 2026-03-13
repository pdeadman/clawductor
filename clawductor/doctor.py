from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click
import yaml

from clawductor.config import CONFIG_PATH


def _check(label: str, result: str, detail: str = "") -> tuple[str, str]:
    """Return (result, label) and print the line."""
    colour = {"PASS": "green", "FAIL": "red", "WARN": "yellow"}[result]
    line = f"  [{click.style(result, fg=colour)}] {label}"
    if detail:
        line += f" — {detail}"
    click.echo(line)
    return result, label


@click.command("doctor")
def doctor() -> None:
    """Run preflight checks and report on system readiness."""
    click.echo(click.style("Clawductor Doctor", bold=True))
    click.echo("─" * 40)

    results: list[str] = []

    # Python version >= 3.11
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) >= (3, 11):
        r, _ = _check("Python version >= 3.11", "PASS", f"{major}.{minor}")
    else:
        r, _ = _check("Python version >= 3.11", "FAIL", f"{major}.{minor} — upgrade required")
    results.append(r)

    # git
    if shutil.which("git"):
        r, _ = _check("git on PATH", "PASS")
    else:
        r, _ = _check("git on PATH", "FAIL", "install git")
    results.append(r)

    # tmux
    if shutil.which("tmux"):
        r, _ = _check("tmux on PATH", "PASS")
    else:
        r, _ = _check("tmux on PATH", "FAIL", "install tmux")
    results.append(r)

    # claude
    if shutil.which("claude"):
        r, _ = _check("claude (Claude Code CLI) on PATH", "PASS")
    else:
        r, _ = _check("claude (Claude Code CLI) on PATH", "FAIL", "install Claude Code CLI")
    results.append(r)

    # gh — WARN only
    if shutil.which("gh"):
        r, _ = _check("gh (GitHub CLI) on PATH", "PASS")
    else:
        r, _ = _check("gh (GitHub CLI) on PATH", "WARN", "optional — install gh for PR features")
    results.append(r)

    # config file exists and is valid YAML
    config_path = CONFIG_PATH
    if not config_path.exists():
        r, _ = _check("~/.clawductor/config.yaml exists", "FAIL", "run clawductor to create it")
        results.append(r)
    else:
        try:
            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}
            r, _ = _check("~/.clawductor/config.yaml exists and is valid YAML", "PASS")
            results.append(r)

            # config models are non-empty strings
            mc = config_data.get("model_config", {})
            model_fields = ["task", "admin", "plan", "init"]
            all_ok = all(isinstance(mc.get(k), str) and mc.get(k) for k in model_fields)
            if all_ok:
                r, _ = _check("Config model names are non-empty strings", "PASS")
            else:
                r, _ = _check("Config model names are non-empty strings", "FAIL", "check model_config in config.yaml")
            results.append(r)

        except yaml.YAMLError as e:
            r, _ = _check("~/.clawductor/config.yaml is valid YAML", "FAIL", str(e))
            results.append(r)

    click.echo("─" * 40)
    passed = results.count("PASS")
    warned = results.count("WARN")
    failed = results.count("FAIL")
    click.echo(
        f"{click.style(str(passed), fg='green')} checks passed, "
        f"{click.style(str(warned), fg='yellow')} warnings, "
        f"{click.style(str(failed), fg='red')} failures"
    )

    if failed:
        sys.exit(1)
