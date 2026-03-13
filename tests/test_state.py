from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from clawductor.state import ClawductorState, RepoEntry, SessionEntry, load_state


@pytest.fixture
def tmp_state(tmp_path) -> Path:
    return tmp_path / "state.yaml"


def test_empty_state_on_missing_file(tmp_state):
    assert not tmp_state.exists()
    state = load_state(tmp_state)
    assert state.repos == []
    assert state.sessions == []


def test_state_saves_and_loads_repos(tmp_state):
    state = ClawductorState(_path=tmp_state)
    repo = RepoEntry(
        path="/home/user/myrepo",
        name="myrepo",
        status="IDLE",
        added_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    state.add_repo(repo)

    loaded = load_state(tmp_state)
    assert len(loaded.repos) == 1
    assert loaded.repos[0].path == "/home/user/myrepo"
    assert loaded.repos[0].name == "myrepo"
    assert loaded.repos[0].status == "IDLE"
    assert loaded.repos[0].added_at == datetime(2026, 1, 1, 12, 0, 0)


def test_state_saves_and_loads_sessions(tmp_state):
    state = ClawductorState(_path=tmp_state)
    session = SessionEntry(
        id="sess-001",
        repo_path="/home/user/myrepo",
        task_id="task-1",
        status="RUNNING",
        started_at=datetime(2026, 1, 1, 12, 0, 0),
        cost_usd=0.42,
    )
    state.add_session(session)

    loaded = load_state(tmp_state)
    assert len(loaded.sessions) == 1
    s = loaded.sessions[0]
    assert s.id == "sess-001"
    assert s.status == "RUNNING"
    assert s.cost_usd == 0.42


def test_update_session_status(tmp_state):
    state = ClawductorState(_path=tmp_state)
    session = SessionEntry(
        id="sess-002",
        repo_path="/home/user/myrepo",
        task_id="task-2",
        status="IDLE",
        started_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    state.add_session(session)
    state.update_session_status("sess-002", "COMPLETED")

    loaded = load_state(tmp_state)
    assert loaded.sessions[0].status == "COMPLETED"


def test_auto_save_on_mutation(tmp_state):
    state = ClawductorState(_path=tmp_state)
    assert not tmp_state.exists()

    state.add_repo(RepoEntry(
        path="/repo",
        name="repo",
        status="IDLE",
        added_at=datetime(2026, 1, 1),
    ))
    assert tmp_state.exists()


def test_state_never_crashes_on_missing_file(tmp_state):
    # Calling load_state on a path that doesn't exist must not raise
    state = load_state(tmp_state)
    assert isinstance(state, ClawductorState)


def test_multiple_repos_and_sessions(tmp_state):
    state = ClawductorState(_path=tmp_state)
    for i in range(3):
        state.add_repo(RepoEntry(
            path=f"/repo/{i}",
            name=f"repo{i}",
            status="IDLE",
            added_at=datetime(2026, 1, i + 1),
        ))
    for i in range(2):
        state.add_session(SessionEntry(
            id=f"s{i}",
            repo_path=f"/repo/{i}",
            task_id=f"t{i}",
            status="RUNNING",
            started_at=datetime(2026, 1, i + 1),
        ))

    loaded = load_state(tmp_state)
    assert len(loaded.repos) == 3
    assert len(loaded.sessions) == 2


def test_add_repo_with_extra_fields(tmp_state):
    state = ClawductorState(_path=tmp_state)
    repo = RepoEntry(
        path="/home/user/proj",
        name="proj",
        status="INITIALISING",
        added_at=datetime(2026, 3, 1, 9, 0, 0),
        merge_strategy="Auto-merge",
        default_branch="develop",
        num_agents=3,
        tasks=["Set up CI", "Write tests"],
    )
    state.add_repo(repo)

    loaded = load_state(tmp_state)
    r = loaded.repos[0]
    assert r.merge_strategy == "Auto-merge"
    assert r.default_branch == "develop"
    assert r.num_agents == 3
    assert r.tasks == ["Set up CI", "Write tests"]


def test_add_repo_defaults_for_extra_fields(tmp_state):
    """Repos added without the new fields get sensible defaults on round-trip."""
    state = ClawductorState(_path=tmp_state)
    state.add_repo(RepoEntry(
        path="/repo/simple",
        name="simple",
        status="IDLE",
        added_at=datetime(2026, 3, 1),
    ))

    loaded = load_state(tmp_state)
    r = loaded.repos[0]
    assert r.merge_strategy == "Open PR"
    assert r.default_branch == "main"
    assert r.num_agents == 1
    assert r.tasks == []


def test_remove_repo(tmp_state):
    state = ClawductorState(_path=tmp_state)
    state.add_repo(RepoEntry(
        path="/repo/a",
        name="a",
        status="IDLE",
        added_at=datetime(2026, 3, 1),
    ))
    state.add_repo(RepoEntry(
        path="/repo/b",
        name="b",
        status="IDLE",
        added_at=datetime(2026, 3, 2),
    ))

    state.remove_repo("/repo/a")

    loaded = load_state(tmp_state)
    assert len(loaded.repos) == 1
    assert loaded.repos[0].path == "/repo/b"


def test_remove_nonexistent_repo_is_noop(tmp_state):
    state = ClawductorState(_path=tmp_state)
    state.add_repo(RepoEntry(
        path="/repo/x",
        name="x",
        status="IDLE",
        added_at=datetime(2026, 3, 1),
    ))
    state.remove_repo("/repo/does_not_exist")

    loaded = load_state(tmp_state)
    assert len(loaded.repos) == 1


def test_remove_all_repos(tmp_state):
    state = ClawductorState(_path=tmp_state)
    state.add_repo(RepoEntry(
        path="/repo/only",
        name="only",
        status="IDLE",
        added_at=datetime(2026, 3, 1),
    ))
    state.remove_repo("/repo/only")

    loaded = load_state(tmp_state)
    assert loaded.repos == []


def test_ctx_pct_saves_and_loads(tmp_state):
    state = ClawductorState(_path=tmp_state)
    session = SessionEntry(
        id="s1",
        repo_path="/repo",
        task_id="t1",
        status="RUNNING",
        started_at=datetime(2026, 3, 13),
        ctx_pct=42.5,
    )
    state.add_session(session)

    loaded = load_state(tmp_state)
    assert loaded.sessions[0].ctx_pct == 42.5


def test_ctx_pct_defaults_to_zero(tmp_state):
    """Sessions saved without ctx_pct load with 0.0."""
    state = ClawductorState(_path=tmp_state)
    state.add_session(SessionEntry(
        id="s1",
        repo_path="/repo",
        task_id="t1",
        status="RUNNING",
        started_at=datetime(2026, 3, 13),
    ))
    loaded = load_state(tmp_state)
    assert loaded.sessions[0].ctx_pct == 0.0


def test_complete_mock_init(tmp_state):
    state = ClawductorState(_path=tmp_state)
    state.add_repo(RepoEntry(
        path="/repo/a",
        name="a",
        status="INITIALISING",
        added_at=datetime(2026, 3, 13),
    ))
    tasks = [{"id": "TASK-001", "description": "Test", "status": "in_progress", "priority": "high"}]
    session = SessionEntry(
        id="agent-1",
        repo_path="/repo/a",
        task_id="TASK-001",
        status="RUNNING",
        started_at=datetime(2026, 3, 13),
        ctx_pct=34.0,
    )
    state.complete_mock_init("/repo/a", tasks, session)

    loaded = load_state(tmp_state)
    assert loaded.repos[0].status == "READY"
    assert loaded.repos[0].tasks == tasks
    assert len(loaded.sessions) == 1
    assert loaded.sessions[0].id == "agent-1"
    assert loaded.sessions[0].ctx_pct == 34.0


def test_complete_mock_init_unknown_path_is_noop(tmp_state):
    """complete_mock_init on a path not in repos still appends the session."""
    state = ClawductorState(_path=tmp_state)
    tasks = []
    session = SessionEntry(
        id="agent-1",
        repo_path="/repo/missing",
        task_id="TASK-001",
        status="RUNNING",
        started_at=datetime(2026, 3, 13),
    )
    state.complete_mock_init("/repo/missing", tasks, session)
    loaded = load_state(tmp_state)
    assert loaded.repos == []
    assert len(loaded.sessions) == 1


def test_remove_only_first_duplicate(tmp_state):
    """If the same path is added twice, remove_repo only removes the first entry."""
    state = ClawductorState(_path=tmp_state)
    for _ in range(2):
        state.add_repo(RepoEntry(
            path="/repo/dup",
            name="dup",
            status="IDLE",
            added_at=datetime(2026, 3, 1),
        ))
    state.remove_repo("/repo/dup")

    loaded = load_state(tmp_state)
    assert len(loaded.repos) == 1
    assert loaded.repos[0].path == "/repo/dup"
