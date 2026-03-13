from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    STALLED = "STALLED"
    ERROR = "ERROR"
    COMPLETED = "COMPLETED"


@dataclass
class Session:
    id: str
    repo_path: str
    task_id: str
    status: str
    started_at: datetime
    cost_usd: float = 0.0
