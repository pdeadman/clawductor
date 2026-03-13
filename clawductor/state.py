from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

STATE_PATH = Path.home() / ".clawductor" / "state.yaml"


def validate_repo_path(path_str: str) -> tuple[bool, str]:
    """Return (is_valid, error_message). Empty error string means valid."""
    if not path_str.strip():
        return False, "Repo path cannot be empty."
    p = Path(path_str)
    if not p.exists():
        return False, f"Path does not exist: {path_str}"
    if not p.is_dir():
        return False, f"Not a directory: {path_str}"
    if not (p / ".git").exists():
        return False, f"Not a git repository (no .git found): {path_str}"
    return True, ""


@dataclass
class RepoEntry:
    path: str
    name: str
    status: str
    added_at: datetime
    merge_strategy: str = "Open PR"
    default_branch: str = "main"
    num_agents: int = 1
    tasks: list = field(default_factory=list)


@dataclass
class SessionEntry:
    id: str
    repo_path: str
    task_id: str
    status: str
    started_at: datetime
    cost_usd: float = 0.0


@dataclass
class ClawductorState:
    repos: list[RepoEntry] = field(default_factory=list)
    sessions: list[SessionEntry] = field(default_factory=list)
    _path: Path = field(default=STATE_PATH, repr=False, compare=False)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "repos": [
                {
                    "path": r.path,
                    "name": r.name,
                    "status": r.status,
                    "added_at": r.added_at.isoformat(),
                    "merge_strategy": r.merge_strategy,
                    "default_branch": r.default_branch,
                    "num_agents": r.num_agents,
                    "tasks": r.tasks,
                }
                for r in self.repos
            ],
            "sessions": [
                {
                    "id": s.id,
                    "repo_path": s.repo_path,
                    "task_id": s.task_id,
                    "status": s.status,
                    "started_at": s.started_at.isoformat(),
                    "cost_usd": s.cost_usd,
                }
                for s in self.sessions
            ],
        }
        with open(self._path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def add_repo(self, repo: RepoEntry) -> None:
        self.repos.append(repo)
        self.save()

    def remove_repo(self, repo_path: str) -> None:
        for i, r in enumerate(self.repos):
            if r.path == repo_path:
                self.repos.pop(i)
                break
        self.save()

    def add_session(self, session: SessionEntry) -> None:
        self.sessions.append(session)
        self.save()

    def update_session_status(self, session_id: str, status: str) -> None:
        for s in self.sessions:
            if s.id == session_id:
                s.status = status
        self.save()


def load_state(path: Path = STATE_PATH) -> ClawductorState:
    if not path.exists():
        return ClawductorState(_path=path)

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return ClawductorState(_path=path)

    repos = [
        RepoEntry(
            path=r["path"],
            name=r["name"],
            status=r["status"],
            added_at=datetime.fromisoformat(r["added_at"]),
            merge_strategy=r.get("merge_strategy", "Open PR"),
            default_branch=r.get("default_branch", "main"),
            num_agents=r.get("num_agents", 1),
            tasks=r.get("tasks", []),
        )
        for r in data.get("repos", [])
    ]
    sessions = [
        SessionEntry(
            id=s["id"],
            repo_path=s["repo_path"],
            task_id=s["task_id"],
            status=s["status"],
            started_at=datetime.fromisoformat(s["started_at"]),
            cost_usd=s.get("cost_usd", 0.0),
        )
        for s in data.get("sessions", [])
    ]
    return ClawductorState(repos=repos, sessions=sessions, _path=path)
