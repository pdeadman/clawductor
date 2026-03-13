"""
Integration tests covering bugs found during manual testing:

  BUG 1 — Add Repo modal buttons were unreachable (cut off below visible area).
           Fixed by switching to ScrollableContainer + ctrl+s binding.
           Tests: verify the modal opens, confirm submits a repo, cancel does not.

  BUG 2 — Removing a repo that appeared twice removed all copies.
           Fixed by breaking after the first match in remove_repo.
           Tests: in test_state.py::test_remove_only_first_duplicate.
           The TUI-level test below confirms the dashboard row count is correct
           after removing one of two duplicate repos.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from clawductor.state import ClawductorState, RepoEntry
from clawductor.tui import AddRepoModal, ClawductorApp, TaskListModal, MOCK_TASKS
from textual.widgets import DataTable, Input


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(tmp_path, repos=None):
    state = ClawductorState(_path=tmp_path / "state.yaml")
    for r in repos or []:
        state.add_repo(r)
    return state


def _git_repo(tmp_path, name="repo"):
    p = tmp_path / name
    p.mkdir()
    (p / ".git").mkdir()
    return p


# ---------------------------------------------------------------------------
# BUG 1 — Add Repo modal is submittable via keyboard
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_add_repo_modal_opens(tmp_path):
    """Pressing 'a' opens the Add Repo modal."""
    state = _make_state(tmp_path)
    app = ClawductorApp(state=state)

    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, AddRepoModal)


@pytest.mark.anyio
async def test_add_repo_modal_cancel_adds_nothing(tmp_path):
    """Escape closes the modal without adding a repo."""
    state = _make_state(tmp_path)
    app = ClawductorApp(state=state)

    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    assert state.repos == []


@pytest.mark.anyio
async def test_add_repo_modal_invalid_path_shows_error(tmp_path):
    """Submitting an empty path keeps the modal open and shows an error."""
    state = _make_state(tmp_path)
    app = ClawductorApp(state=state)

    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        # modal still open — error kept it from closing
        assert isinstance(app.screen, AddRepoModal)

    assert state.repos == []


@pytest.mark.anyio
async def test_add_repo_modal_valid_path_adds_repo(tmp_path):
    """Submitting a valid git repo path adds it to state and closes the modal."""
    repo_path = _git_repo(tmp_path)
    state = _make_state(tmp_path)
    app = ClawductorApp(state=state)

    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#repo-path", Input).value = str(repo_path)
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert len(state.repos) == 1
    assert state.repos[0].path == str(repo_path)
    assert state.repos[0].status == "INITIALISING"


# ---------------------------------------------------------------------------
# Task list modal
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_task_list_modal_opens_with_datatable(tmp_path):
    """Pressing t on a repo with tasks opens TaskListModal containing a DataTable."""
    repo_path = _git_repo(tmp_path)
    repo = RepoEntry(
        path=str(repo_path),
        name=repo_path.name,
        status="READY",
        added_at=datetime(2026, 3, 13),
        tasks=list(MOCK_TASKS),
    )
    state = _make_state(tmp_path, repos=[repo])
    app = ClawductorApp(state=state)

    async with app.run_test() as pilot:
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, TaskListModal)
        table = app.screen.query_one(DataTable)
        assert table.row_count == len(MOCK_TASKS)


@pytest.mark.anyio
async def test_task_list_modal_empty_repo_shows_placeholder(tmp_path):
    """TaskListModal with no tasks shows a placeholder row."""
    repo_path = _git_repo(tmp_path)
    repo = RepoEntry(
        path=str(repo_path),
        name=repo_path.name,
        status="INITIALISING",
        added_at=datetime(2026, 3, 13),
    )
    state = _make_state(tmp_path, repos=[repo])
    app = ClawductorApp(state=state)

    async with app.run_test() as pilot:
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, TaskListModal)
        table = app.screen.query_one(DataTable)
        assert table.row_count == 1  # placeholder row


# ---------------------------------------------------------------------------
# Dashboard task count
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_task_count_shows_progress_format(tmp_path):
    """Tasks column shows in_progress/total (e.g. '1/4') not 'X pending'."""
    repo_path = _git_repo(tmp_path)
    repo = RepoEntry(
        path=str(repo_path),
        name=repo_path.name,
        status="READY",
        added_at=datetime(2026, 3, 13),
        tasks=list(MOCK_TASKS),
    )
    state = _make_state(tmp_path, repos=[repo])
    app = ClawductorApp(state=state)

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(DataTable)
        row = table.get_row_at(0)
        assert str(row[2]) == "1/4"


# ---------------------------------------------------------------------------
# BUG 2 — Removing one of two duplicate repos leaves one row
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_remove_duplicate_repo_leaves_one_row(tmp_path):
    """
    Regression: removing a repo that was added twice used to wipe both rows.
    After the fix, one row should remain in state.
    """
    repo_path = _git_repo(tmp_path)
    repo = RepoEntry(
        path=str(repo_path),
        name=repo_path.name,
        status="INITIALISING",
        added_at=datetime(2026, 3, 1),
    )
    state = _make_state(tmp_path, repos=[repo, repo])
    app = ClawductorApp(state=state)

    async with app.run_test() as pilot:
        await pilot.press("d")
        await pilot.pause()
        # tab to the Remove button and confirm
        await pilot.press("tab")
        await pilot.press("enter")
        await pilot.pause()

    assert len(state.repos) == 1
    assert state.repos[0].path == str(repo_path)
