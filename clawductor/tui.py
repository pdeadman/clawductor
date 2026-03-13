from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
    TextArea,
)

from clawductor.state import ClawductorState, RepoEntry, SessionEntry, validate_repo_path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MERGE_STRATEGIES = ["Auto-merge", "Open PR", "Push branch"]

STATUS_STYLES: dict[str, str] = {
    "INITIALISING": "bold yellow",
    "READY": "bold green",
    "ERROR": "bold red",
    "IDLE": "dim",
}

TASK_STATUS_STYLES: dict[str, str] = {
    "pending": "white",
    "in_progress": "yellow",
    "completed": "green",
    "blocked": "red",
}

# TODO: replace with real initialiser
MOCK_TASKS = [
    {"id": "TASK-001", "description": "Implement JWT authentication", "status": "in_progress", "priority": "high"},
    {"id": "TASK-002", "description": "Add rate limiting to API endpoints", "status": "pending", "priority": "medium"},
    {"id": "TASK-003", "description": "Write e2e tests for checkout flow", "status": "pending", "priority": "medium"},
    {"id": "TASK-004", "description": "Set up CI/CD pipeline", "status": "pending", "priority": "low"},
]

HELP_TEXT = """\
  a    Add repo
  t    View tasks  (on selected repo)
  d    Remove repo  (on selected repo)
  r    Refresh
  ?    This help
  q    Quit\
"""


def _status_text(status: str) -> Text:
    return Text(status, style=STATUS_STYLES.get(status, "white"))


# ---------------------------------------------------------------------------
# StatusBar
# ---------------------------------------------------------------------------


class StatusBar(Static):
    """One-line stats bar docked to the bottom."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $primary-darken-3;
        color: $text-muted;
        padding: 0 1;
        dock: bottom;
    }
    """

    def __init__(self, state: ClawductorState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state

    def on_mount(self) -> None:
        self.set_interval(5, self.refresh_stats)
        self.refresh_stats()

    def refresh_stats(self) -> None:
        count = len(self._state.repos)
        now = datetime.now().strftime("%H:%M:%S")
        self.update(
            f"Repos: {count}  |  Cost today: $0.00  |  Updated: {now}"
        )


# ---------------------------------------------------------------------------
# Help modal
# ---------------------------------------------------------------------------


class HelpModal(ModalScreen):
    """Keybinding reference."""

    BINDINGS = [Binding("escape,question_mark", "dismiss", "Close")]

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    HelpModal > Vertical {
        background: $surface;
        border: tall $primary;
        padding: 1 3;
        width: 50%;
        max-width: 50;
        height: auto;
    }
    HelpModal #help-title {
        text-style: bold;
        color: $success;
        margin-bottom: 1;
    }
    HelpModal #help-close {
        margin-top: 1;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Keybindings", id="help-title")
            yield Static(HELP_TEXT)
            yield Button("Close (Esc)", id="help-close", variant="default")

    def on_mount(self) -> None:
        self.query_one("#help-close").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


# ---------------------------------------------------------------------------
# Add Repo modal
# ---------------------------------------------------------------------------


class AddRepoModal(ModalScreen):
    """Form to add a new repository."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "confirm", "Confirm"),
    ]

    DEFAULT_CSS = """
    AddRepoModal {
        align: center middle;
    }
    AddRepoModal > ScrollableContainer {
        background: $surface;
        border: tall $primary;
        padding: 1 2;
        width: 80%;
        max-width: 100;
        height: auto;
        max-height: 80%;
    }
    AddRepoModal #modal-title {
        text-style: bold;
        color: $success;
        margin-bottom: 1;
    }
    AddRepoModal .field-label {
        color: $text-muted;
        margin-top: 1;
    }
    AddRepoModal Input {
        width: 100%;
    }
    AddRepoModal RadioSet {
        height: auto;
        border: none;
        padding: 0;
    }
    AddRepoModal #row-branch-agents {
        height: auto;
        margin: 0;
        padding: 0;
    }
    AddRepoModal #row-branch-agents > Vertical {
        height: auto;
        padding: 0;
        margin: 0;
    }
    AddRepoModal #branch-input {
        width: 2fr;
    }
    AddRepoModal #agents-input {
        width: 1fr;
        margin-left: 1;
    }
    AddRepoModal TextArea {
        height: 4;
        margin-top: 0;
    }
    AddRepoModal #error-label {
        color: $error;
        height: 1;
        margin-top: 1;
    }
    AddRepoModal #button-row {
        height: 3;
        margin-top: 1;
        align: right middle;
    }
    AddRepoModal #btn-cancel {
        margin-left: 1;
    }
"""

    def compose(self) -> ComposeResult:
        with ScrollableContainer():
            yield Label("Add Repository", id="modal-title")

            yield Label("Repo path:", classes="field-label")
            yield Input(
                placeholder="/path/to/repo",
                id="repo-path",
            )

            yield Label("Merge strategy:", classes="field-label")
            with RadioSet(id="merge-strategy"):
                yield RadioButton("Auto-merge")
                yield RadioButton("Open PR", value=True)
                yield RadioButton("Push branch")

            with Horizontal(id="row-branch-agents"):
                with Vertical():
                    yield Label("Default branch:", classes="field-label")
                    yield Input(value="main", id="branch-input")
                with Vertical():
                    yield Label("Agents (1–5):", classes="field-label")
                    yield Input(value="1", id="agents-input")

            yield Label("Initial tasks (one per line, optional):", classes="field-label")
            yield TextArea(id="tasks-area", tab_behavior="focus")

            yield Label("", id="error-label")

            with Horizontal(id="button-row"):
                yield Button("Confirm (Ctrl+S)", id="btn-confirm", variant="primary")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#repo-path", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_confirm(self) -> None:
        self._validate_and_submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-confirm":
            self._validate_and_submit()

    def _validate_and_submit(self) -> None:
        path_str = self.query_one("#repo-path", Input).value.strip()
        is_valid, error = validate_repo_path(path_str)
        if not is_valid:
            self._show_error(error)
            return

        agents_str = self.query_one("#agents-input", Input).value.strip()
        try:
            num_agents = int(agents_str)
            if not (1 <= num_agents <= 5):
                raise ValueError
        except ValueError:
            self._show_error("Number of agents must be an integer from 1 to 5.")
            return

        radio_set = self.query_one("#merge-strategy", RadioSet)
        strategy = MERGE_STRATEGIES[radio_set.pressed_index]

        default_branch = self.query_one("#branch-input", Input).value.strip() or "main"

        tasks_raw = self.query_one("#tasks-area", TextArea).text
        tasks = [t.strip() for t in tasks_raw.splitlines() if t.strip()]

        self.dismiss(
            {
                "path": path_str,
                "merge_strategy": strategy,
                "default_branch": default_branch,
                "num_agents": num_agents,
                "tasks": tasks,
            }
        )

    def _show_error(self, message: str) -> None:
        self.query_one("#error-label", Label).update(f"[red]{message}[/red]")


# ---------------------------------------------------------------------------
# Task list modal
# ---------------------------------------------------------------------------


class TaskListModal(ModalScreen):
    """Shows the task list for a repo."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    TaskListModal {
        align: center middle;
    }
    TaskListModal > Vertical {
        background: $surface;
        border: tall $primary;
        padding: 1 2;
        width: 90%;
        height: auto;
        max-height: 80%;
    }
    TaskListModal #task-title {
        text-style: bold;
        color: $success;
        margin-bottom: 1;
    }
    TaskListModal #task-table {
        height: 10;
    }
    TaskListModal #button-row {
        height: 3;
        margin-top: 1;
        align: right middle;
    }
    """

    def __init__(self, repo: RepoEntry, **kwargs) -> None:
        super().__init__(**kwargs)
        self._repo = repo

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Tasks — {self._repo.name}", id="task-title")
            yield DataTable(id="task-table")
            with Horizontal(id="button-row"):
                yield Button("Close (Esc)", id="task-close")

    def on_mount(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.add_columns("ID", "Description", "Status", "Priority")
        if self._repo.tasks:
            for task in self._repo.tasks:
                if isinstance(task, dict):
                    status = task.get("status", "pending")
                    status_text = Text(status, style=TASK_STATUS_STYLES.get(status, "white"))
                    table.add_row(
                        task.get("id", ""),
                        task.get("description", ""),
                        status_text,
                        task.get("priority", ""),
                    )
                else:
                    table.add_row("", str(task), Text("pending", style="white"), "")
        else:
            table.add_row("", "No tasks yet. Tasks will be generated during initialisation.", Text("", style="white"), "")
        self.query_one("#task-table").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


# ---------------------------------------------------------------------------
# Remove confirmation modal
# ---------------------------------------------------------------------------


class RemoveConfirmModal(ModalScreen[bool]):
    """Confirm before removing a repo from state."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    RemoveConfirmModal {
        align: center middle;
    }
    RemoveConfirmModal > Vertical {
        background: $surface;
        border: tall $error;
        padding: 1 2;
        width: 60%;
        max-width: 60;
        height: auto;
    }
    RemoveConfirmModal #confirm-title {
        text-style: bold;
        margin-bottom: 1;
    }
    RemoveConfirmModal #confirm-note {
        color: $text-muted;
        margin-bottom: 1;
    }
    RemoveConfirmModal #confirm-buttons {
        height: 3;
        align: right middle;
    }
    RemoveConfirmModal #btn-remove {
        margin-left: 1;
    }
    """

    def __init__(self, repo_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._repo_name = repo_name

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                f"Remove [bold]{self._repo_name}[/bold] from Clawductor?",
                id="confirm-title",
            )
            yield Label("This will not delete any files.", id="confirm-note")
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancel", id="btn-keep")
                yield Button("Remove", id="btn-remove", variant="error")

    def on_mount(self) -> None:
        self.query_one("#btn-keep").focus()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-remove")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


class ClawductorApp(App):
    """Clawductor TUI — dashboard."""

    TITLE = "Clawductor v0.1"

    CSS = """
    Screen {
        background: $background;
    }

    Header {
        background: $primary-darken-3;
        color: $success;
    }

    DataTable {
        height: 1fr;
        border: tall $primary-darken-2;
    }

    DataTable > .datatable--header {
        color: $success;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: $primary-darken-2;
        color: $success;
    }
    """

    BINDINGS = [
        Binding("a", "add_repo", "Add Repo"),
        Binding("t", "view_tasks", "Tasks"),
        Binding("d", "remove_repo", "Remove"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, state: ClawductorState | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="sessions-table")
        yield StatusBar(state=self._state, id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Repo", "Status", "Tasks", "Cost", "CTX%")
        self._populate_table(table)

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------

    def _populate_table(self, table: DataTable) -> None:
        if self._state is None:
            return
        for repo in self._state.repos:
            total = len(repo.tasks)
            in_progress = sum(
                1 for t in repo.tasks
                if isinstance(t, dict) and t.get("status") == "in_progress"
            )
            active_session = next(
                (s for s in self._state.sessions
                 if s.repo_path == repo.path and s.status == "RUNNING"),
                None,
            )
            ctx_cell = f"{int(active_session.ctx_pct)}%" if active_session else "—"
            table.add_row(
                repo.name,
                _status_text(repo.status),
                f"{in_progress}/{total}" if total else "0",
                "$0.00",
                ctx_cell,
            )

    def _refresh_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._populate_table(table)
        self.query_one(StatusBar).refresh_stats()

    def _get_selected_repo(self) -> RepoEntry | None:
        if self._state is None or not self._state.repos:
            return None
        table = self.query_one(DataTable)
        if table.row_count == 0:
            return None
        idx = table.cursor_row
        if idx < 0 or idx >= len(self._state.repos):
            return None
        return self._state.repos[idx]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_refresh(self) -> None:
        self._refresh_table()

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_add_repo(self) -> None:
        def on_result(result: dict | None) -> None:
            if result is None:
                return
            repo = RepoEntry(
                path=result["path"],
                name=Path(result["path"]).name,
                status="INITIALISING",
                added_at=datetime.now(),
                merge_strategy=result["merge_strategy"],
                default_branch=result["default_branch"],
                num_agents=result["num_agents"],
                tasks=result["tasks"],
            )
            self._state.add_repo(repo)
            self._refresh_table()
            self.notify("Repo added — initialising…")
            self.set_timer(3, lambda: self._complete_mock_init(repo.path))

        self.push_screen(AddRepoModal(), on_result)

    def _complete_mock_init(self, repo_path: str) -> None:
        # TODO: replace with real initialiser
        mock_session = SessionEntry(
            id="agent-1",
            repo_path=repo_path,
            task_id="TASK-001",
            status="RUNNING",
            started_at=datetime.now(),
            ctx_pct=34.0,
        )
        self._state.complete_mock_init(repo_path, list(MOCK_TASKS), mock_session)
        self._refresh_table()
        self.notify("Repo ready — mock tasks loaded.")

    def action_view_tasks(self) -> None:
        repo = self._get_selected_repo()
        if repo is None:
            self.notify("No repo selected.", severity="warning")
            return
        self.push_screen(TaskListModal(repo=repo))

    def action_remove_repo(self) -> None:
        repo = self._get_selected_repo()
        if repo is None:
            self.notify("No repo selected.", severity="warning")
            return

        def on_result(confirmed: bool) -> None:
            if confirmed:
                self._state.remove_repo(repo.path)
                self._refresh_table()
                self.notify(f"Removed {repo.name}.")

        self.push_screen(RemoveConfirmModal(repo_name=repo.name), on_result)
