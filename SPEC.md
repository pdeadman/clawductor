# Clawductor — Master Specification
> Version: 1.0 | Author: PJ Deadman

---

## Table of Contents

1. [What Is Clawductor?](#1-what-is-clawductor)
2. [MVP Scope](#2-mvp-scope)
3. [Architecture](#3-architecture)
4. [Repo Initialisation Flow](#4-repo-initialisation-flow)
5. [Shared Memory Files](#5-shared-memory-files)
6. [Task Claiming Protocol & Ralph Loop](#6-task-claiming-protocol--ralph-loop)
7. [Git Management Protocol](#7-git-management-protocol)
8. [Security Model & Trust Boundaries](#8-security-model--trust-boundaries)
9. [Session State Model](#9-session-state-model)
10. [Attention Detection](#10-attention-detection)
11. [Hooks — Deterministic Quality Gates](#11-hooks--deterministic-quality-gates)
12. [Token Management](#12-token-management)
13. [Model Configuration](#13-model-configuration)
14. [Sandboxing](#14-sandboxing)
15. [TUI Dashboard](#15-tui-dashboard)
16. [Notification System](#16-notification-system)
17. [State Persistence](#17-state-persistence)
18. [CLI Interface](#18-cli-interface)
19. [Dependencies & System Requirements](#19-dependencies--system-requirements)
20. [Launch Checklist](#20-launch-checklist)
21. [Roadmap (Post-MVP)](#21-roadmap-post-mvp)
22. [What This Is NOT](#22-what-this-is-not)

---

## 1. What Is Clawductor?

Clawductor is a TUI-based orchestration runtime for Claude Code. You run it once and it becomes a persistent master process — a single pane of glass across all your Claude Code sessions, across all your repos. From inside the TUI you add repos, define tasks, spin up agents, and monitor everything in one place.

**Core philosophy:** Clawductor is an opinionated runtime, not a wrapper. You run `clawductor`, not `clawductor start some-config.yaml`. The TUI is the product.

**The mental model:**
- One `clawductor` process runs persistently in a terminal
- You add repos and tasks interactively from inside the TUI
- When a repo is added, an initialiser agent analyses the codebase and sets up the shared memory layer automatically
- Each task gets its own Claude Code session, its own git branch, and its own worktree — fully isolated
- One or more agents per repo run continuous Ralph loops: claim task → plan → implement → verify → complete → claim next task. Default is 1; configurable up to N.
- The dashboard shows state across all sessions and all repos simultaneously
- State is saved automatically — you never write config files manually

**Target user (v0.1):** Developers who are already using Claude Code and want to run multiple parallel sessions across one or more repos without the overhead of managing tmux, worktrees, branches, and context manually.

---

## 2. MVP Scope

### IN SCOPE

- Single entry point: `clawductor` launches TUI immediately
- Interactive repo and task creation from within TUI, including priority and blocked-by fields
- Task management view: reorder, block, delete tasks without leaving dashboard
- Repo initialisation: initialiser agent analyses codebase, generates shared memory files, asks user for anything it cannot infer via `CLAWDUCTOR_QUESTION`
- **Task list generation by Claude:** initialiser breaks high-level goals into properly sequenced, prioritised, independently-testable tasks — faster and more thoroughly than manual entry
- **Auto skills installation:** stack detected during init → curated SKILL.md files installed into `.clawductor/skills/` automatically — agents follow best practices from day one without manual CLAUDE.md maintenance
- Shared memory layer: `context.md`, `tasks.md`, `progress.md` per repo
- Ralph loop: single agent per repo, continuously claiming and completing tasks
- Atomic task claiming via git push to prevent race conditions
- Heartbeat system: orchestrator tracks stdout activity as heartbeat — agents never write heartbeat commits
- Stale task recovery: orchestrator resets timed-out tasks based on stdout silence, not git timestamps
- Spawn and manage named tmux sessions, each running a Claude Code CLI instance
- Monitor session stdout for attention states (WAITING, STALLED, ERROR, COMPLETED)
- TUI dashboard showing all session states, current tasks, and estimated cost across all repos
- Mac desktop notification (osascript) when a session needs attention
- TUI passthrough mode: press Enter on a session to attach directly
- Git worktree per task: isolated branch and working directory
- Branch naming: `clawductor/{task-id}/{slug}` — never touches main
- Three merge strategies: auto-merge, open PR (default), push branch only
- Automatic worktree cleanup on task completion
- Aggressive context clearing between tasks via `/clear`
- **Model configuration:** all model assignments (task, admin, plan, init) defined in a single `model_config` block in `~/.clawductor/config.yaml` — never hardcoded in source. Defaults to current Anthropic best-value models but fully overridable, including OpenAI-compatible endpoints for open-source models.
- Cost estimation displayed per session and as running total in dashboard
- Task integrity checksums: Clawductor verifies task descriptions haven't been tampered with before agents act on them
- Repo ownership verification on init
- Security boundaries: agents can only update task status fields, never task content
- State persistence: auto-saved to `~/.clawductor/state.yaml`, restored on relaunch
- `clawductor doctor` with full preflight: binaries, git auth, Claude Code version, estimated cost per task cycle
- Per-stack permission defaults: `.claude/settings.json` written per worktree at init — pre-approves safe operations so agents don't stop mid-task for routine commands
- Stuck loop detection: distinguishes agents retrying the same failing approach (STUCK) from agents producing no output (STALLED)
- Verification-before-completion: agents must run test suite and confirm pass before outputting "Task complete"
- **Hooks:** Clawductor generates `.claude/hooks.json` per worktree — PostToolUse auto-formats on every file edit, Stop hook enforces linter + test suite before session can end, PreToolUse hook blocks writes to protected paths
- **Plan Mode:** agents enter Plan Mode before implementing any task — read context, explore relevant files, write a brief plan to progress.md, then switch to implementation. Separates exploration from execution.
- **Sandboxing:** OS-level filesystem and network isolation per worktree using Claude Code's native sandbox — replaces advisory restrictions with enforced boundaries. Reduces permission prompts by ~84%.
- **Multi-agent support:** configurable number of Ralph loop agents per repo (default: 1, max: configurable). All agents share the same task claiming protocol — race conditions already handled by atomic git push design.
- **Voice mode compatibility:** Clawductor does not interfere with Claude Code's native voice mode. TUI passthrough mode preserves full Claude Code functionality including voice input.

### OUT OF SCOPE FOR v0.1

- Automated inter-agent coordination beyond shared task files (agents coordinate via tasks.md only)
- Full permission profiles (scoped permission defaults per stack are in scope — see init flow)
- Non-technical user UI
- Windows / Linux support (macOS only for MVP)
- Web dashboard or cloud connectivity
- SQLite or any database

---

## 3. Architecture

```
clawductor/
├── clawductor/
│   ├── __init__.py
│   ├── main.py              # Entry point — launches TUI
│   ├── orchestrator.py      # Session + task lifecycle management
│   ├── monitor.py           # tmux stdout reader, state detection
│   ├── tui.py               # Textual TUI dashboard
│   ├── notifier.py          # osascript Mac notifications
│   ├── worktree.py          # Git worktree + branch management
│   ├── initialiser.py       # Repo initialisation flow
│   ├── skills.py            # Skills registry, stack detection, installation
│   ├── task_protocol.py     # Task claiming, heartbeat, stale recovery
│   ├── hooks.py              # Hook file generation per worktree
│   ├── security.py          # Checksums, trust verification
│   ├── cost.py              # Token estimation, cost display
│   ├── config.py            # Application config (models, cost thresholds, notifications)
│   ├── state.py             # State persistence (session/repo state YAML)
│   └── session.py           # Session data model
├── skills_registry/         # Curated stack→skills mappings
│   ├── registry.yaml        # Stack detection rules and skill assignments
│   └── sources.yaml         # Pinned skill versions from community sources
├── pyproject.toml
├── README.md
└── tests/                   # Orchestrator test suite — required from day one
    ├── test_task_protocol.py  # Atomic claiming, stale recovery, orphan detection
    ├── test_worktree.py       # Worktree creation, cleanup, disk limits
    ├── test_monitor.py        # State detection, stuck loop, pattern matching
    ├── test_hooks.py          # Hook generation correctness per stack
    └── test_config.py         # Config loading, deep merge, model routing
```

**Testing note:** The orchestrator's reliability is foundational — if task claiming, stale recovery, or worktree cleanup have bugs, every agent session is affected. The `tests/` directory is not optional and should be built alongside the modules it covers, not after. Priority order for test coverage mirrors build order: `task_protocol.py` first, then `worktree.py`, then `monitor.py`.

**Per-repo structure (inside user's repos):**
```
my-project/
├── .git/
├── .clawductor/
│   ├── context.md           # Repo intelligence (committed)
│   ├── tasks.md             # Task list (committed)
│   ├── progress.md          # Progress log (committed)
│   ├── skills/              # Auto-installed SKILL.md files (committed)
│   │   ├── conventional-commits.md
│   │   ├── react-best-practices.md
│   │   └── test-first.md
│   ├── signals/             # Agent→orchestrator signals (gitignored)
│   └── worktrees/           # Active worktrees (gitignored)
│       ├── TASK-001-jwt-auth/
│       └── TASK-003-pw-reset/
└── src/
```

---

## 4. Repo Initialisation Flow

Runs once when a repo is first added in the TUI. No task agents start until initialisation is complete.

### Step 1: Prerequisites check

Before anything else, Clawductor verifies:

```python
def check_repo_prerequisites(repo_path):
    errors = []

    # Is it a git repo?
    result = subprocess.run(["git", "rev-parse", "--git-dir"],
                            cwd=repo_path, capture_output=True)
    if result.returncode != 0:
        errors.append("Not a git repository. Run 'git init' first.")

    # Does it have a remote?
    result = subprocess.run(["git", "remote", "-v"],
                            cwd=repo_path, capture_output=True, text=True)
    if not result.stdout.strip():
        errors.append("No git remote configured. Push to GitHub/GitLab first.")

    # Is working directory clean?
    result = subprocess.run(["git", "status", "--porcelain"],
                            cwd=repo_path, capture_output=True, text=True)
    if result.stdout.strip():
        errors.append("Uncommitted changes exist. Commit or stash before adding.")

    # Is gh CLI available? (needed for PR strategy)
    gh_available = subprocess.run(["gh", "auth", "status"],
                                  capture_output=True).returncode == 0

    return errors, gh_available
```

If errors exist, block repo addition and show them clearly in the TUI.

### Step 2: User configures repo (TUI modal)

```
┌─── Add Repo ────────────────────────────────────────────┐
│                                                          │
│  Repo path:      [/Users/pj/projects/myapp           ]  │
│  Merge strategy: [ ] Auto-merge  [●] Open PR  [ ] Push  │
│  Default branch: [main                               ]  │
│  Protected:      [main, develop, staging             ]  │
│  Agents:         [1        ] (parallel Ralph loops)     │
│                                                          │
│  Initial tasks (one per line):                          │
│  [Implement JWT authentication                       ]  │
│  [Add rate limiting to API endpoints                 ]  │
│  [Write e2e tests for checkout flow                  ]  │
│                                                          │
│              [Cancel]  [Initialise]                      │
└──────────────────────────────────────────────────────────┘
```

### Step 3: Initialiser agent runs

Clawductor creates `.clawductor/` directory, then spawns an initialiser Claude Code session with this prompt:

```
Analyse this repository thoroughly. Then:

1. Generate .clawductor/context.md — include: tech stack, key commands
   (dev server, test, build, lint), directory structure, coding conventions,
   commit style, and any files/directories that should NOT be modified.

2. Create .clawductor/tasks.md — using the goal provided below. Do not
   just copy the goal verbatim. Break it into a properly sequenced,
   prioritised task list. Each task should be independently completable,
   testable, and committable. Infer dependencies from the codebase.
   Add any tasks you think are missing that would be required to deliver
   the goal properly (e.g. tests, migrations, cleanup). Use your judgement.

3. Create .clawductor/progress.md — empty log file with just the header.

4. Commit all three files with message: "chore(clawductor): initialise"

If you cannot determine something critical, output on its own line:
CLAWDUCTOR_QUESTION: <your question here>
Then wait for the answer before continuing.

When fully complete, output exactly: "Initialisation complete"

Goal:
{user_task_list}
```

**Note on task generation:** One of Clawductor's core advantages is that the initialiser agent generates task lists faster and more thoroughly than a human would — correctly sequencing dependencies, identifying missing steps, and inferring priority from the codebase. This is a feature, not a risk. The checksum system (section 8) ensures the user sees and acknowledges what was generated before agents execute anything.

**Note on context.md length:** The initialiser must keep `context.md` under 200 lines. Rules that must always happen should go in hooks (enforced), not context.md (advisory). Skills files cover best practices — context.md should only contain what is genuinely non-obvious about this specific codebase: unusual patterns, protected files, non-standard commands. Instruct the initialiser: "Be concise. If it's obvious, omit it. If it must always happen, it belongs in a hook not here."

### Step 4: Skills installation

After generating `context.md`, Clawductor reads the identified stack and automatically installs a curated set of relevant SKILL.md files into `.clawductor/skills/`. These give every task agent specialised best-practice knowledge without the developer having to research, find, or configure anything manually. This directly eliminates the problem of maintaining CLAUDE.md best practices by hand.

**Stack → skills mapping (built into Clawductor):**

| Stack detected | Skills installed |
|----------------|-----------------|
| TypeScript / JavaScript | `conventional-commits`, `ts-best-practices`, `test-first` |
| React / Next.js | Above + `react-best-practices`, `accessibility` |
| Python | `conventional-commits`, `python-best-practices`, `test-first` |
| FastAPI / Flask | Above + `api-design-principles`, `openapi-docs` |
| Any | `conventional-commits`, `atomic-commits`, `security-review` |

Skills are sourced from the community skills ecosystem (e.g. skills.sh, lobehub) and pinned to a specific version in Clawductor's curated list. Skills are committed into `.clawductor/skills/` so they're part of the repo and visible in review.

The initialiser prompt is updated to reference installed skills:

```
Your available skills are in .clawductor/skills/ — read them before
starting any task. They define the standards this project must follow.
```

Users can add, remove, or override skills from the TUI task management view (`t` → `[k] skills`). Future: community can contribute stack mappings via PRs to Clawductor's skills registry.

### Step 4b: Permission defaults installation

The single biggest day-to-day complaint about Claude Code is agents stopping mid-task to ask permission for routine operations like `mkdir`, `npm install`, or `git status`. Clawductor solves this during init without requiring `--dangerously-skip-permissions`.

For each detected stack, Clawductor writes a `.claude/settings.json` into every worktree it creates, pre-approving safe, expected operations:

```python
STACK_PERMISSIONS = {
    "node": {
        "allow": [
            "Bash(npm install*)", "Bash(npm test*)", "Bash(npm run*)",
            "Bash(npx *)", "Bash(node *)", "Bash(tsc*)",
            "Bash(git add*)", "Bash(git commit*)", "Bash(git push*)",
            "Bash(git status)", "Bash(git diff*)", "Bash(git log*)",
            "Bash(mkdir *)", "Bash(rm -rf .clawductor/worktrees/*)",
        ]
    },
    "python": {
        "allow": [
            "Bash(pip install*)", "Bash(python *)", "Bash(pytest*)",
            "Bash(ruff *)", "Bash(black *)", "Bash(mypy *)",
            "Bash(git add*)", "Bash(git commit*)", "Bash(git push*)",
            "Bash(git status)", "Bash(git diff*)", "Bash(git log*)",
            "Bash(mkdir *)",
        ]
    },
    # extended for other stacks at launch
}
```

This is written per-worktree, not globally — permissions are scoped to the task's isolated directory. It does not use `--dangerously-skip-permissions`. Destructive commands (`rm -rf /`, `chmod 777`, etc.) are never pre-approved. Users can review and edit the generated settings via the TUI skills view.

### Step 5: Handle CLAWDUCTOR_QUESTION

Clawductor monitors stdout for `CLAWDUCTOR_QUESTION:` prefix. When detected:
1. Pause — do not send anything to the agent yet
2. Surface the question to user in a TUI modal
3. User types answer
4. Clawductor sends answer to agent via tmux send-keys
5. Agent continues

### Step 6: User reviews context.md and tasks.md

After `Initialisation complete` is detected:
1. Show `context.md` and `tasks.md` contents in a TUI review pane (tabbed)
2. User can confirm or edit inline
3. Any edits trigger a checksum update — Clawductor commits: `"chore(clawductor): review edits"`
4. Initialiser session is stopped and cleaned up

### Step 7: Task agents begin

Ralph loop agent(s) are spawned. Work begins.

---

## 5. Shared Memory Files

Three files live under `.clawductor/` in every managed repo. They are committed to git and serve as the shared memory layer across all agent sessions.

| File | Purpose | Written by |
|------|---------|------------|
| `context.md` | Repo intelligence — stack, conventions, structure | Initialiser (once) |
| `tasks.md` | Task list with status and ownership | Initialiser + agents |
| `progress.md` | Append-only log of agent activity | Agents |

### context.md

```markdown
# Project Context
> Generated by Clawductor initialiser | Last updated: 2025-03-11

## Stack
- Language: TypeScript
- Framework: Next.js 14 (App Router)
- Database: PostgreSQL via Prisma
- Testing: Jest + Playwright
- Package manager: pnpm

## Key Commands
- Dev server: `pnpm dev`
- Run tests: `pnpm test`
- Run e2e: `pnpm test:e2e`
- Build: `pnpm build`
- Lint: `pnpm lint`

## Structure
- `/src/app` — Next.js App Router pages and layouts
- `/src/components` — Shared React components
- `/src/lib` — Utilities and helpers
- `/prisma` — Database schema and migrations
- `/tests` — Jest unit tests

## Conventions
- Component files: PascalCase
- Utility files: camelCase
- Commits: conventional commits (feat:, fix:, chore:)
- All new features require unit tests

## Do Not Modify
- /src/lib/auth.ts — managed separately
- /.env — use .env.example as reference
```

### tasks.md

```markdown
# Task List
> Project: my-app | Last updated: 2025-03-11T20:14:32Z

## Pending

- [ ] **TASK-003** Implement password reset flow
  Priority: high
  Added: 2025-03-11T19:00:00Z
  Notes: Use SendGrid. See /src/lib/email.ts for existing setup.

- [ ] **TASK-004** Add rate limiting to API endpoints
  Priority: medium
  Added: 2025-03-11T19:00:00Z
  Notes: Use upstash/ratelimit. Endpoints: /api/auth/*, /api/user/*

## In Progress

- [~] **TASK-001** Implement JWT authentication
  Priority: high
  Agent: auth-agent
  Branch: clawductor/TASK-001/jwt-authentication
  Claimed: 2025-03-11T20:00:00Z
  Heartbeat: 2025-03-11T20:14:00Z

## Completed

- [x] **TASK-002** Set up Prisma schema
  Priority: high
  Agent: db-agent
  Completed: 2025-03-11T19:30:00Z
  Branch: clawductor/TASK-002/prisma-schema (merged)

## Blocked

- [!] **TASK-005** Deploy to staging
  Priority: high
  Blocked by: TASK-001, TASK-003
```

Task statuses:

| Symbol | Status | Meaning |
|--------|--------|---------|
| `[ ]` | Pending | Available to claim |
| `[~]` | In Progress | Claimed by an agent |
| `[x]` | Completed | Done |
| `[!]` | Blocked | Waiting on other tasks |

### progress.md

Append-only. Never truncated.

```markdown
# Progress Log
> Project: my-app

---

## 2025-03-11T20:00:00Z | auth-agent | STARTED | TASK-001
Reading codebase structure. Planning JWT implementation.

## 2025-03-11T20:14:00Z | orchestrator | ACTIVITY | TASK-001
[auth-agent stdout] JWT middleware created at src/middleware/auth.ts

## 2025-03-11T20:30:00Z | orchestrator | ACTIVITY | TASK-001
[auth-agent stdout] Login endpoint complete. Writing tests.

## 2025-03-11T20:45:00Z | auth-agent | COMPLETED | TASK-001
JWT auth complete. Tests passing (18/18). PR opened.
```

Entry types:
- `STARTED` — written by agent when claiming a task
- `ACTIVITY` — written by orchestrator from meaningful stdout lines
- `COMPLETED` — written by agent after tests pass and final commit made
- `FAILED` — written by agent on unrecoverable error
- `RECOVERED` — written by orchestrator when resetting a stale task

---

## 6. Task Claiming Protocol & Ralph Loop

### The Ralph Loop

One agent per repo runs this loop continuously:

```
START
  │
  ▼
Pull latest main → Read tasks.md
  │
  ├─ No pending tasks → Notify user "All tasks complete" → STOP
  │
  ├─ All pending are blocked → Notify user → Wait 60s → Loop
  │
  └─ Pending task found
       │
       ▼
     Claim task (atomic git push to main)
       │
       ├─ Push rejected → Go back to "Pull latest"
       │
       └─ Push succeeded → Own the task
            │
            ▼
          Read context.md + skills
          [PLAN MODE] Explore relevant files, write plan to progress.md
          [PLAN MODE] Output "Plan ready" → switch to implementation mode
          Work on task in worktree
          [Orchestrator monitors stdout for heartbeat + stuck loops]
            │
            ├─ Hooks confirm: tests pass, lint clean
            ├─ "Task complete" output
            │                → Update tasks.md [x] → Append progress.md
            │                → Push → /clear context → Loop
            │
            ├─ ERROR state → try /rewind → if unrecoverable: Reset task → STOP
            │
            └─ STUCK state → notify user → await intervention
```

The `/clear` between tasks is critical — it keeps context fresh and costs low.

### Claiming Protocol (race condition prevention)

**Step 1:** Always pull latest before reading tasks.md
```bash
git pull origin main
```

**Step 2:** Find highest priority `[ ]` task that is not blocked.

**Step 3:** Update task to `[~]`, add agent name, branch, claimed timestamp, heartbeat timestamp. Commit and push:
```bash
git add .clawductor/tasks.md
git commit -m "chore(clawductor): claim TASK-003 [agent-name]"
git push origin main
```

**Step 4:**
- Push succeeded → task is owned, proceed
- Push rejected → another agent got there first. Pull, re-read, pick next available task.

**Step 5 (during work — orchestrator responsibility, NOT the agent):**

The orchestrator already polls stdout every 2 seconds. Stdout activity IS the heartbeat signal. The orchestrator updates `tasks.md` and `progress.md` based on what it observes — the agent never writes heartbeats:

```python
def on_stdout_activity(session_name, task_id, output_line):
    now = datetime.utcnow().isoformat()
    # Orchestrator updates heartbeat timestamp in tasks.md
    update_task_heartbeat(repo_path, task_id, now)
    # Orchestrator appends meaningful output lines to progress.md
    if is_meaningful_output(output_line):
        append_progress(repo_path, session_name, task_id, "ACTIVITY", output_line)
```

Agents never write heartbeats. This eliminates the git lock race condition entirely — only the orchestrator touches `tasks.md` during active work. The agent only touches `tasks.md` twice: claim (start of task) and completion (end of task).

**`is_meaningful_output()` — what gets written to progress.md:**

Not every stdout line is worth recording. Spinner frames, blank lines, and progress bars create noise that makes `progress.md` unreadable. The filter is deliberately permissive — it's better to capture too much than to miss a meaningful step:

```python
import re

# Characters that indicate UI chrome rather than content
_SPINNER_CHARS = set("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏|/-\")
_ANSI_ESCAPE = re.compile(r"\[[0-9;]*m")

def is_meaningful_output(line: str) -> bool:
    """Return True if this stdout line is worth appending to progress.md."""
    # Strip ANSI colour codes before evaluating
    clean = _ANSI_ESCAPE.sub("", line).strip()

    if not clean:
        return False                          # blank line

    if len(clean) < 8:
        return False                          # too short to be informative

    if all(c in _SPINNER_CHARS for c in clean):
        return False                          # pure spinner frame

    if clean.startswith(("⠋", "⠙", "⠹", "⠸", "⠼", "⠴")):
        return False                          # leading spinner

    # Keep lines that look like actual agent output
    return True
```

This is intentionally simple. If `progress.md` becomes noisy in practice, tighten the minimum length threshold or add pattern-based exclusions — but start permissive.

**Step 6 (on completion):**
- Update task to `[x]`, add completed timestamp
- Append COMPLETED to `progress.md`
- Commit and push
- Send `/clear` to reset context
- Loop back to Step 1

**Step 7 (on error — try rewind first):**

On ERROR state, Clawductor attempts recovery before giving up:

1. Clawductor sends `/rewind` to the tmux session
2. Waits 10 seconds for the agent to recover to the last clean state
3. If stdout resumes → agent recovered, continue monitoring
4. If still ERROR after 30 seconds → proceed to full reset:
   - Reset task to `[ ]`, remove claim fields, add failure note
   - Append FAILED to `progress.md`
   - Commit and push
   - Write signal file: `.clawductor/signals/{agent-name}.signal`
   - Fire Mac notification: "TASK-001 failed after rewind attempt — manual review needed"
   - Kill session (see below)

This mirrors the community best practice: use `/rewind` before giving up rather than trying to fix in the same poisoned context.

**Step 8 (hard timeout):**

An agent can reach WAITING state and stay there indefinitely — blocked on a prompt Clawductor missed, or genuinely deadlocked. The spec handles STALLED (no output) but that resets after 2 minutes of silence. WAITING is different — the agent is actively prompting for input and will never self-resolve.

Hard timeout: any session that has been in WAITING state for more than **15 minutes** without a user response is killed and its task reset to `[ ]`.

**Session kill must terminate the entire process group, not just tmux:**

```python
import os
import signal

def kill_agent_session(session: Session) -> None:
    """
    Kill tmux session AND all child processes it spawned.
    Using tmux kill-session alone leaves zombie subprocesses running —
    any scripts, npm processes, or test runners the agent spawned persist
    as orphans consuming resources.
    """
    # Get the PID of the shell running inside the tmux session
    result = subprocess.run(
        ["tmux", "display-message", "-t", session.tmux_session,
         "-p", "#{pane_pid}"],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        pane_pid = int(result.stdout.strip())
        try:
            # Kill the entire process group — negative PID targets the group
            os.killpg(os.getpgid(pane_pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass  # Process already gone

    # Now kill the tmux session itself
    subprocess.run(["tmux", "kill-session", "-t", session.tmux_session],
                   capture_output=True)
```

This pattern — kill process group first, then tmux session — ensures no orphaned subprocesses remain after a session ends, regardless of whether the kill was triggered by timeout, ERROR recovery, or user action via `[s]top` in the TUI.

### Stale Task Recovery (orchestrator responsibility)

The orchestrator tracks `last_stdout_time` per session from its existing 2-second polling. No git commits required:

```python
HEARTBEAT_TIMEOUT = 120  # 2 minutes without any stdout = stale

for session in active_sessions:
    if (now - session.last_stdout_time).seconds > HEARTBEAT_TIMEOUT:
        # Orchestrator resets task in tasks.md
        # Orchestrator appends RECOVERED to progress.md
        # Orchestrator commits and pushes both (single atomic operation)
        # Fire Mac notification: "TASK-001 — agent went silent, task reset"
```

### Git Lock Recovery (orchestrator responsibility)

```python
lock_file = Path(repo_path) / ".git" / "index.lock"
if lock_file.exists() and (time.time() - lock_file.stat().st_mtime) > 30:
    lock_file.unlink()
    log.warning(f"Removed stale git lock in {repo_path}")
```

Only the orchestrator removes lock files — never agents.

---

## 7. Git Management Protocol

### Core Rules

1. **Agents never touch main directly.** Ever.
2. **One task = one branch = one worktree.** Always.
3. **Clawductor creates and cleans up worktrees.** Agents only work inside them.
4. **Merge strategy is set once per repo at init.**

### Branch Naming

```
clawductor/{TASK-ID}/{short-slug}
```

Examples:
```
clawductor/TASK-001/jwt-authentication
clawductor/TASK-003/password-reset-flow
```

Slug: task name, lowercase, hyphens, max 40 chars. Makes all Clawductor branches immediately identifiable in git log and GitHub.

### Worktree Lifecycle

**Creation (Clawductor, before agent starts):**
```python
def create_worktree(repo_path, task_id, task_slug):
    branch_name = f"clawductor/{task_id}/{task_slug}"
    worktree_path = f"{repo_path}/.clawductor/worktrees/{task_id}-{task_slug}"

    subprocess.run(["git", "fetch", "origin"], cwd=repo_path)
    subprocess.run(["git", "worktree", "add", "-b", branch_name,
                    worktree_path, "origin/main"], cwd=repo_path)

    # Write per-worktree settings (permissions) and hooks
    generate_settings(worktree_path, repo_config.stack)
    generate_hooks(worktree_path, repo_config)

    return worktree_path, branch_name
```

Always branch from freshly fetched `origin/main`.

**Worktree limits and disk protection:**

Real-world incidents have shown agents entering worktree creation loops, consuming hundreds of gigabytes. Clawductor enforces hard limits before creating any worktree:

```python
MAX_WORKTREES_PER_REPO = 10  # Hard ceiling — never exceeded regardless of agent_count
DISK_WARN_GB = 5.0           # Warn user if worktrees dir exceeds this
DISK_BLOCK_GB = 20.0         # Block new worktree creation above this

def check_worktree_limits(repo_path: str, repo_config) -> None:
    """Raises RuntimeError if limits exceeded. Call before create_worktree()."""
    worktree_dir = Path(repo_path) / ".clawductor" / "worktrees"

    # Count existing Clawductor worktrees
    existing = list_clawductor_worktrees(repo_path)
    if len(existing) >= MAX_WORKTREES_PER_REPO:
        raise RuntimeError(
            f"Worktree limit reached ({MAX_WORKTREES_PER_REPO}). "
            f"Clean up completed worktrees before starting new tasks."
        )

    # Check disk usage
    if worktree_dir.exists():
        usage_gb = get_dir_size_gb(worktree_dir)
        if usage_gb >= DISK_BLOCK_GB:
            raise RuntimeError(
                f"Worktree directory is using {usage_gb:.1f}GB. "
                f"Run 'clawductor cleanup' to remove orphaned worktrees."
            )
        if usage_gb >= DISK_WARN_GB:
            notify_user(f"Warning: worktrees using {usage_gb:.1f}GB disk space")
```

`clawductor doctor` also reports current worktree count and disk usage per repo. `clawductor cleanup` is a CLI command that prunes any orphaned worktrees (present on disk but not in `state.yaml`) — see section 18.

**Agent task prompt (generated per task, injected into every session):**

```
## Your Environment
- You are in a git worktree on branch: {branch_name}
- Worktree path: {worktree_path}
- Task: {task_id} — {task_description}

## Phase 1: Plan (DO THIS FIRST — do not write any code yet)
1. Read .clawductor/context.md to understand the project
2. Read .clawductor/skills/ — these define the standards you must follow
3. Search the web for current best practices and known pitfalls for what
   you are about to build. Use targeted queries like:
   "{task_topic} best practices 2026" and "{task_topic} security pitfalls".
   Incorporate any relevant findings into your plan.
4. Read the relevant source files for this task
5. Write a brief implementation plan (5-10 bullet points) as a STARTED entry
   in {repo_path}/.clawductor/progress.md
6. Output exactly: "Plan ready" — then begin implementation

## Phase 2: Implement
- Commit frequently using conventional commits: feat:, fix:, chore:
- Push after each commit: git push origin {branch_name}
- NEVER run: git checkout, git merge, git rebase, git push --force
- NEVER modify files outside your worktree directory
- NEVER push to main or any other branch

## Phase 3: Complete (MANDATORY — hooks will also enforce this)
Note: Stop hooks will automatically verify your work. Do not try to bypass them.
1. Run the test suite: {test_command}
   - If tests fail: fix the failures before proceeding
   - If there is no test command: output "CLAWDUCTOR_QUESTION: No test command found. How should I verify this task?"
2. Run the linter: {lint_command} (if applicable)
3. Make a final commit: "chore(clawductor): task complete [{task_id}]"
4. Push: git push origin {branch_name}
5. Output exactly: "Task complete"

Do NOT output "Task complete" if tests are failing.
```

The test and lint commands are injected from `context.md` at session start. Plan Mode is enforced by the prompt structure — the agent must output "Plan ready" before Clawductor sends the implementation signal. Note that even if the agent skips verification, the Stop hook will catch it.

**Shared memory files are in the MAIN repo, not the worktree:**
```
## Shared Memory (absolute paths — use these exactly)
- Context (read only): {repo_path}/.clawductor/context.md
- Tasks (read/write):  {repo_path}/.clawductor/tasks.md
- Progress (append):   {repo_path}/.clawductor/progress.md

When reading/writing these files, always pull/push from: {repo_path}
NOT from your worktree directory.
```

**Cleanup (Clawductor, after task complete):**
```python
def cleanup_worktree(repo_path, worktree_path, branch_name, merge_strategy):
    subprocess.run(["git", "worktree", "remove", worktree_path, "--force"],
                   cwd=repo_path)
    subprocess.run(["git", "worktree", "prune"], cwd=repo_path)
    subprocess.run(["git", "branch", "-d", branch_name], cwd=repo_path)
    if merge_strategy == "auto_merge":
        subprocess.run(["git", "push", "origin", "--delete", branch_name],
                       cwd=repo_path)
```

### Merge Strategies

Configured once per repo at init. Three options:

**A: Auto-merge to main** — Clawductor merges directly after task completion. No human review. For solo developers moving fast.
```python
subprocess.run(["git", "checkout", "main"], cwd=repo_path)
subprocess.run(["git", "merge", "--no-ff", branch_name,
                "-m", f"merge: {task_id} via clawductor"], cwd=repo_path)
subprocess.run(["git", "push", "origin", "main"], cwd=repo_path)
```
If merge conflict: notify user via Mac notification. Do not auto-resolve.

**B: Open PR (default)** — Clawductor opens a PR via `gh` CLI. PR body is auto-generated from `progress.md` entries for that task.
```python
subprocess.run(["gh", "pr", "create",
    "--title", f"[Clawductor] {task_id}: {task_name}",
    "--body", pr_body,
    "--base", "main",
    "--head", branch_name
], cwd=repo_path)
```

**C: Push branch only** — Branch pushed, nothing else. User handles PR manually. For teams with strict review processes.

If `gh` CLI is not available and user selects PR strategy, warn and fall back to option C.

### .gitignore additions

Clawductor appends on repo init:
```gitignore
# Clawductor — runtime files (do not commit)
.clawductor/worktrees/
.clawductor/signals/
.clawductor/*.log

# Per-worktree Claude Code config (hooks, settings — generated by Clawductor)
# This prevents hook scripts and permission files from leaking into project history
.claude/
```

`context.md`, `tasks.md`, `progress.md`, `.claudeignore`, and `.clawductor/skills/` are intentionally tracked — they are project config, not runtime state.

---

## 8. Security Model & Trust Boundaries

Recent vulnerabilities in Claude Code showed that configuration files committed to git can be used as attack vectors — malicious content executed automatically when a developer opens a project. Clawductor commits files that agents act on, which creates the same risk if not handled carefully.

### Agent permission tiers

Clawductor has two categories of agent with different trust levels:

**Initialiser agent (elevated permissions):** Runs once per repo during setup. Permitted to write all three shared memory files (`context.md`, `tasks.md`, `progress.md`) from scratch. Its output is shown to the user for review before any task agent runs. Checksums are stored after review, not before — so the reviewed state becomes the trusted baseline.

**Task-loop agents (restricted permissions):** Run continuously after init. These agents have strictly limited write access to shared files.

### Trust rules (task-loop agents only)

**Task content is immutable to task agents.** Task agents can update task *status* fields only (claimed, completed). They cannot add new tasks, modify task descriptions, or change task priorities. This is enforced in the agent prompt and validated by the orchestrator before acting on any `tasks.md` change.

**Task integrity checksums.** When Clawductor creates a task, it stores a SHA256 checksum of the task description in `~/.clawductor/state.yaml` (local, not committed). Before an agent starts work on a task, Clawductor verifies the checksum matches. A mismatch means the task description was modified in git — Clawductor blocks the task, notifies the user, and requires manual review:

```python
def verify_task_integrity(task_id, task_description, repo_path):
    stored_checksum = load_checksum(task_id)
    current_checksum = hashlib.sha256(task_description.encode()).hexdigest()
    if stored_checksum != current_checksum:
        notify_user(f"TASK {task_id} description changed in git — manual review required")
        block_task(task_id)
        return False
    return True
```

**Repo ownership verification.** On repo init, Clawductor checks the git remote URL matches the authenticated GitHub/GitLab user:

```python
def verify_repo_ownership(repo_path):
    remote_url = get_remote_url(repo_path)
    gh_user = subprocess.run(["gh", "api", "user", "--jq", ".login"],
                             capture_output=True, text=True).stdout.strip()
    if gh_user.lower() not in remote_url.lower():
        warn_user(f"Remote repo owner may not match authenticated user ({gh_user}). "
                  f"Only use Clawductor on repos you control.")
```

This is a warning, not a hard block — it accommodates org repos — but it surfaces the risk explicitly.

**Never run Clawductor on repos you don't control.** Document this prominently in the README. Clawductor is designed for personal and team repos you own, not for running against arbitrary open source repos where `tasks.md` could be tampered with.

**`.clawductor/` files are treated as executable instructions, not passive data.** The README must communicate this clearly. Treat a modified `tasks.md` from an unknown contributor the same way you'd treat a modified `Makefile`.

### What agents are permitted to write

| File | Initialiser can write | Task agent can write | Neither can write |
|------|----------------------|---------------------|-------------------|
| `tasks.md` | Everything (full creation) | Status fields only: `[~]`, `[x]`, claim timestamp | — |
| `progress.md` | Initial empty file | STARTED, COMPLETED, FAILED entries | Modify existing entries |
| `context.md` | Everything (full creation) | Nothing | — |
| `.clawductor/skills/` | Everything (install) | Nothing | — |
| Worktree files | Nothing | Everything within their worktree | Files outside worktree |

Orchestrator additionally writes: ACTIVITY and RECOVERED entries to `progress.md`, heartbeat timestamps to `tasks.md`.

---

## 9. Session State Model

```python
class SessionState(Enum):
    STARTING    = "starting"     # Spawning tmux session
    RUNNING     = "running"      # Active, producing output
    WAITING     = "waiting"      # Needs y/n or user input
    STALLED     = "stalled"      # No output for N seconds (no output at all)
    STUCK       = "stuck"        # Same output pattern repeating 3+ times
    ERROR       = "error"        # Hit an error pattern
    COMPLETED   = "completed"    # Task finished
    STOPPED     = "stopped"      # Manually stopped
```

---

## 10. Attention Detection

Poll each tmux session using `tmux capture-pane` every 2 seconds.

```python
WAITING_PATTERNS = [
    r"\(y/n\)", r"\[Y/n\]", r"\[y/N\]",
    r"Do you want to", r"Press Enter to continue",
    r"Would you like", r"\? ›",
]

ERROR_PATTERNS = [
    r"Error:", r"ERROR:", r"Failed to", r"Cannot ",
    r"Permission denied", r"fatal:", r"Traceback \(most recent",
]

COMPLETED_PATTERNS = [
    r"Task complete",       # Agent's required completion output
    r"Initialisation complete",  # Initialiser completion
    r"\$ $",               # Shell prompt returned
]
```

**Stall detection (STALLED state):**
- Track `last_output_time` per session
- If `now - last_output_time > stall_threshold` (default: 30s) and state is RUNNING → STALLED
- Reset timer on any new output

**Stuck loop detection (STUCK state):**

A distinct failure mode from stalling: the agent is producing output but repeating the same failing approach. Without detection, this can run for hours unnoticed.

```python
STUCK_WINDOW = 10        # lines to examine
STUCK_THRESHOLD = 3      # identical pattern appearances = stuck

def detect_stuck_loop(recent_output_lines: list[str]) -> bool:
    # Look for repeated identical error messages or commands
    if len(recent_output_lines) < STUCK_WINDOW:
        return False
    window = recent_output_lines[-STUCK_WINDOW:]
    # Count most frequent line in window
    from collections import Counter
    counts = Counter(line.strip() for line in window if line.strip())
    if counts and counts.most_common(1)[0][1] >= STUCK_THRESHOLD:
        return True
    return False
```

On STUCK detection: transition to STUCK state, fire Mac notification "Agent appears stuck in a loop", do NOT auto-kill — let user decide via TUI.

**Important:** COMPLETED detection via stdout triggers Clawductor's post-completion workflow (merge strategy, cleanup). The agent's required output string `"Task complete"` must be consistent and unambiguous.

---

## 11. Hooks — Deterministic Quality Gates

Hooks are shell commands that execute at specific lifecycle points in Claude Code. Unlike prompt instructions (advisory — Claude might forget or ignore them), hooks are **guaranteed** — they fire every time regardless of what the agent decides. This is the enforcement layer that makes Clawductor's quality guarantees real rather than aspirational.

Clawductor generates a `.claude/hooks.json` file and companion shell scripts into every worktree at creation time. Paths are worktree-relative: `.claude/hooks.json` and `.claude/hooks/*.sh`. Agents cannot modify these — they are written by Clawductor before the session starts and are outside the agent's permitted write scope.

### Hook architecture

```
Claude Code action cycle:
  ↓
PreToolUse hook  → can BLOCK the action (exit 2) or ALLOW it (exit 0)
  ↓
Tool executes (file edit, bash command, etc.)
  ↓
PostToolUse hook → runs after, cannot block but can trigger follow-up actions
  ↓
Stop hook        → runs when agent finishes responding — ideal for quality gates
```

### Hooks Clawductor generates per worktree

**1. PostToolUse — Auto-formatter**

Runs after every file edit. Ensures code style is consistent regardless of what the agent produces.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [{
          "type": "command",
          "command": ".claude/hooks/format.sh"
        }]
      }
    ]
  }
}
```

`format.sh` is stack-aware — runs `prettier` for TypeScript/JS, `black` for Python, etc., based on what Clawductor detected during init.

**2. Stop hook — Quality gate**

Runs every time the agent finishes a response. Enforces linting and testing before the session can proceed. Exit code 2 blocks the agent from continuing.

The hook detects task completion by scanning the agent's transcript for the literal string "Task complete". Claude Code passes the session transcript path to hooks via `$CLAUDE_TRANSCRIPT_PATH`.

**Important implementation note:** The transcript is a `.jsonl` file — each line is a JSON object. "Task complete" will appear as a value inside a JSON string, e.g. `{"role":"assistant","content":"Task complete"}`. A bare `grep` will match this correctly in practice, but the production implementation in `hooks.py` should parse JSONL properly using Python's `json` module when generating the hook, or use `jq` in the shell script, to avoid false positives from task descriptions or code comments that contain the substring "Task complete".

```bash
#!/bin/bash
# .claude/hooks/quality-gate.sh  (worktree-relative)
# Runs on Stop event. Exit 2 = block agent continuation.
# Env vars available: CLAWDUCTOR_TASK_ID, CLAWDUCTOR_REPO_PATH, CLAUDE_TRANSCRIPT_PATH

LINT_CMD="{lint_command}"
TEST_CMD="{test_command}"

# Run linter (always)
if [ -n "$LINT_CMD" ] && ! eval "$LINT_CMD" 2>/dev/null; then
  echo "Lint failed — fix errors before proceeding" >&2
  exit 2
fi

# Check if agent just declared task complete
# Parse JSONL: look for assistant content containing exactly "Task complete"
TASK_COMPLETE=false
if [ -f "$CLAUDE_TRANSCRIPT_PATH" ]; then
  if tail -30 "$CLAUDE_TRANSCRIPT_PATH" |      jq -r 'select(.role=="assistant") | .content' 2>/dev/null |      grep -qx "Task complete"; then
    TASK_COMPLETE=true
  fi
fi

# Run tests only on task completion signal
if [ "$TASK_COMPLETE" = "true" ] && [ -n "$TEST_CMD" ]; then
  if ! eval "$TEST_CMD" 2>/dev/null; then
    echo "Tests failed — cannot mark task complete. Fix failures first." >&2
    exit 2
  fi
fi

exit 0
```

`{lint_command}` and `{test_command}` are template variables injected by `generate_hooks()` from `context.md` at worktree creation time — they become literal command strings in the generated script. `jq` is added as a system requirement (see section 19).

**3. PreToolUse — Protected path guard**

Blocks any write to files in the protected list from `context.md`. Exit code 2 with a clear message back to the agent.

```bash
#!/bin/bash
# .claude/hooks/protect-paths.sh  (worktree-relative)
FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | jq -r '.file_path // empty')
PROTECTED=({protected_paths_from_context})

for PROTECTED_PATH in "${PROTECTED[@]}"; do
  if [[ "$FILE_PATH" == *"$PROTECTED_PATH"* ]]; then
    echo "Cannot modify $FILE_PATH — marked as protected in context.md" >&2
    exit 2
  fi
done
exit 0
```

**4. PreToolUse — Main branch guard**

Prevents any agent from pushing to main or any protected branch.

```bash
#!/bin/bash
# .claude/hooks/branch-guard.sh  (worktree-relative)
COMMAND=$(echo "$CLAUDE_TOOL_INPUT" | jq -r '.command // empty')

if echo "$COMMAND" | grep -qE "git push.*origin main|git push.*origin develop|git push.*origin staging"; then
  echo "Blocked: pushing to protected branch. Use your task branch only." >&2
  exit 2
fi
exit 0
```

### Key design principle

The Stop hook replaces the "trust the agent to run tests" approach from the task prompt. The task prompt still asks the agent to run tests — but the Stop hook *guarantees* they run. Two layers: advisory (prompt) + deterministic (hook). The hook wins.

Hooks are fast — kept under 2 seconds each. They run synchronously so slow hooks block the agent. Clawductor generates fast, focused hooks, not comprehensive test suites.

### What hooks Clawductor does NOT generate

- No hooks that run full test suites on every file edit (too slow)
- No hooks that make network calls (security risk)
- No hooks that modify the task files (orchestrator owns those)


---

## 12. Token Management

Token management is not a nice-to-have — it is the primary constraint on agent performance, cost, and reliability. As context fills, model performance degrades measurably before the window is exhausted. Clawductor manages this at every layer, not just at task boundaries.

### The constraint

Claude Code uses a 200K token context window. The practical ceiling before performance degrades is ~167K — a hardcoded 33K buffer is reserved for autocompaction. 80% of context is typically consumed by file reads and tool results, not conversation. A `package-lock.json` alone can consume 30K–80K tokens.

### Layer 1: `.claudeignore` — generated at init

Clawductor's initialiser generates a `.claudeignore` file per repo alongside `context.md`. This is enforced via a `PreToolUse` hook on all Read operations — not advisory, deterministic. Agents physically cannot read ignored files.

Stack-aware defaults written at init:

```
# .claudeignore — generated by Clawductor
# Node / JS
node_modules/
dist/
build/
.next/
*.lock
*.min.js
*.map
coverage/

# Python
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/

# General
.git/
*.log
tmp/
```

The initialiser agent reviews the repo and adds project-specific noise (e.g. large fixture files, generated protobufs, snapshot directories). The `.claudeignore` is committed to the repo and reviewed during the user's initialisation review step alongside `context.md`.

### Layer 2: MCP server scoping per worktree

Each MCP server adds tool definitions to the system prompt — consuming tokens before any conversation begins. Five servers can add ~55K tokens of overhead before a task starts.

Clawductor's `settings.json` generation per worktree only enables MCP servers relevant to the detected stack:

```python
MCP_STACK_MAP = {
    "typescript": ["github", "filesystem"],
    "python":     ["github", "filesystem"],
    "react":      ["github", "filesystem", "figma"],
    "database":   ["github", "filesystem", "postgres"],
}

def get_relevant_mcp_servers(stack: list[str], global_mcp: list[str]) -> list[str]:
    relevant = set()
    for layer in stack:
        relevant.update(MCP_STACK_MAP.get(layer, []))
    return [s for s in global_mcp if s in relevant]
```

A Python backend task won't load the Figma MCP. User can always override in the repo config.

### Layer 3: Autocompaction threshold

Clawductor sets `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=75` in the environment of every agent session. This triggers compaction at 75% capacity (~150K tokens) rather than the default ~83.5% (~167K). Earlier compaction means the agent compacts while it still has working memory to produce a good summary — not when it's already struggling.

```python
def launch_agent_session(worktree_path, task_id, branch_name, task_prompt, repo_config):
    env = os.environ.copy()
    # Context management
    env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] = str(
        load_config()["cost_config"]["autocompact_pct"]
    )
    # Inject task identity so hooks can reference it
    env["CLAWDUCTOR_TASK_ID"]    = task_id
    env["CLAWDUCTOR_BRANCH"]     = branch_name
    env["CLAWDUCTOR_REPO_PATH"]  = str(repo_config.path)
    env["CLAWDUCTOR_WORKTREE"]   = worktree_path
    # Model and endpoint config
    mc = load_config()["model_config"]
    if mc.get("base_url"):
        env["ANTHROPIC_BASE_URL"] = mc["base_url"]
    if mc.get("api_key_env"):
        env["ANTHROPIC_API_KEY"] = os.environ.get(mc["api_key_env"], "")
    # ... tmux session launch using env
```

All `CLAWDUCTOR_*` env vars are available to every hook script. The `PreCompact` hook uses `$CLAWDUCTOR_TASK_ID` and `$CLAWDUCTOR_BRANCH`; the quality gate hook uses `$CLAWDUCTOR_REPO_PATH` to locate `progress.md`.

### Layer 4: `PreCompact` hook — state preservation

Autocompaction is destructive — it replaces conversation history with a summary. Without intervention, an agent mid-task loses track of its branch, the files it has modified, and its current position in the task.

Clawductor generates a `PreCompact` hook per worktree that writes a recovery snapshot before every compaction (manual or auto):

```bash
#!/bin/bash
# .claude/hooks/pre-compact.sh  (worktree-relative)
# Runs before every compaction. Saves task state so agent can recover.

SNAPSHOT_FILE="${CLAWDUCTOR_REPO_PATH}/.clawductor/signals/compact-recovery.md"

{
  echo "# Compact Recovery Snapshot"
  echo "## Task"
  echo "Task ID: ${CLAWDUCTOR_TASK_ID}"
  echo "Branch: ${CLAWDUCTOR_BRANCH}"
  echo ""
  echo "## Modified files"
  git diff --name-only HEAD
  echo ""
  echo "## Test status"
  cat .clawductor/signals/last-test-result 2>/dev/null || echo "unknown"
  echo ""
  echo "## Last progress entry"
  tail -20 "${CLAWDUCTOR_REPO_PATH}/.clawductor/progress.md" 2>/dev/null
} > "$SNAPSHOT_FILE"

exit 0
```

A `SessionStart` hook (also generated per worktree) reads this snapshot when a session resumes after compaction and re-injects it into the agent's first message, restoring task continuity.

### Layer 5: Context % visibility in TUI

The spec already tracks `~COST`. It must also track context fill % — these are different signals. Cost tells you what you've spent; context % tells you whether the agent is about to degrade.

Claude Code emits context usage in its status line output. Clawductor's stdout monitor parses this alongside cost:

```python
import re

CONTEXT_RE = re.compile(r'(\d+)k?/(\d+)k?\s+tokens?\s*\((\d+)%\)')

def parse_stdout_line(line: str) -> dict:
    m = CONTEXT_RE.search(line)
    if m:
        return {"context_pct": int(m.group(3)), "context_used": int(m.group(1))}
    return {}
```

TUI dashboard updated to show CTX%:

```
┌─────────────────────────────────────────────────────────────────────┐
│ CLAWDUCTOR                                        [q]uit [?]help    │
├─────────────────────────────────────────────────────────────────────┤
│ SESSION         REPO    TASK      STATE    AGO    CTX%   ~COST      │
│ ────────────────────────────────────────────────────────────────    │
│ auth-agent      myapp   TASK-001  ● RUN    2s     38%    $0.23      │
│ frontend-agent  myapp   TASK-004  ● WAIT   12s    71%    $0.08  ⚠   │
│ api-agent       other   TASK-007  ◐ STALL  45s    19%    $0.41      │
├─────────────────────────────────────────────────────────────────────┤
│ Session total: $0.72  |  [n] new  [Enter] attach  [s] stop [↑↓]    │
└─────────────────────────────────────────────────────────────────────┘
```

The `⚠` appears when CTX% exceeds 65% — warning the user before the agent approaches the autocompaction threshold. At 75% the orchestrator logs it; the PreCompact hook handles the rest automatically.

### Layer 6: `/clear` between tasks as the primary cost lever

Already in the spec. Restated here for completeness: `/clear` between tasks reduces per-task cost by 60–80% by discarding the accumulated conversation history before starting fresh. This is the single highest-leverage action. All other token management strategies are secondary.

### Cost display

Cost estimated from token counts surfaced in Claude Code's output. Approximate — flagged as `~COST` in UI. Exact billing via Anthropic's dashboard.

Context clearing per task also directly reduces cost: a fresh context reads only `context.md` + current task rather than re-processing the entire session history.

---

## 13. Model Configuration

Model assignments are never hardcoded in source. They live in a single `model_config` block in `~/.clawductor/config.yaml` — the only file a user may edit. Clawductor writes defaults on first run; the user can change them freely.

### Design principle

Models change faster than the rest of this codebase. Anthropic ships new models regularly. Open-source models (Qwen, DeepSeek, Mistral) improve rapidly and often beat proprietary models on narrow coding tasks at a fraction of the cost. Clawductor must not require a code change to switch models. The config file is the single place to change.

### `~/.clawductor/config.yaml`

```yaml
# Clawductor configuration — edit freely
# Model identifiers follow Claude Code CLI conventions.
# For OpenAI-compatible endpoints, set base_url and use that model's identifier.

model_config:
  # Core task work — needs full coding capability
  task_model: claude-sonnet-4-6

  # Planning phase (Plan Mode) — analytical, less generative
  # Can be a cheaper model; Sonnet is fine, Haiku is not recommended
  plan_model: claude-sonnet-4-6

  # Repo initialisation — codebase reasoning, one-off
  init_model: claude-sonnet-4-6

  # Admin operations: status updates, PR body, CLAWDUCTOR_QUESTION
  # Simple, low-stakes, high-frequency — use cheapest capable model
  admin_model: claude-haiku-4-5-20251001

  # Optional: override base URL for OpenAI-compatible endpoints
  # Uncomment to route all model calls through a custom endpoint
  # base_url: https://api.openai.com/v1
  # api_key_env: OPENAI_API_KEY   # env var name, not the key itself

# Cost display preferences
cost_config:
  # Alert when session cost exceeds this threshold (USD)
  session_cost_alert: 5.00
  # Alert when context fill exceeds this percentage
  context_pct_warn: 65
  # Autocompaction threshold override (default: 75)
  autocompact_pct: 75

# Notification preferences
notifications:
  mac_desktop: true
  on_task_complete: true
  on_stalled: true
  on_stuck: true
  on_cost_alert: true
```

### How it's loaded

```python
# config.py
from pathlib import Path
import yaml
from dataclasses import dataclass

DEFAULT_CONFIG = {
    "model_config": {
        "task_model":  "claude-sonnet-4-6",
        "plan_model":  "claude-sonnet-4-6",
        "init_model":  "claude-sonnet-4-6",
        "admin_model": "claude-haiku-4-5-20251001",
        "base_url":    None,
        "api_key_env": None,
    },
    "cost_config": {
        "session_cost_alert": 5.00,
        "context_pct_warn":   65,
        "autocompact_pct":    75,
    },
    "notifications": {
        "mac_desktop":      True,
        "on_task_complete": True,
        "on_stalled":       True,
        "on_stuck":         True,
        "on_cost_alert":    True,
    }
}

CONFIG_PATH = Path.home() / ".clawductor" / "config.yaml"

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(yaml.dump(DEFAULT_CONFIG, default_flow_style=False))
        return DEFAULT_CONFIG
    with open(CONFIG_PATH) as f:
        user = yaml.safe_load(f) or {}
    # Deep merge: user values override defaults, missing keys fall back to defaults
    return deep_merge(DEFAULT_CONFIG, user)

def get_model(role: str) -> str:
    """role: 'task' | 'plan' | 'init' | 'admin'"""
    cfg = load_config()
    return cfg["model_config"][f"{role}_model"]
```

Every place in the codebase that needs a model calls `get_model("task")` or `get_model("admin")` — never a string literal. A grep for `claude-sonnet` or `claude-haiku` in source should return zero results after implementation.

### OpenAI-compatible endpoint support

If `base_url` is set in `model_config`, Clawductor passes it through to the Claude Code CLI via the `ANTHROPIC_BASE_URL` environment variable (which Claude Code respects). This allows routing through:

- Local models via Ollama or LM Studio exposing an OpenAI-compatible API
- Open-source models on Together.ai, Groq, Fireworks etc.
- Azure OpenAI or other enterprise endpoints
- A proxy/gateway for team cost management

```python
def build_session_env(config: dict) -> dict:
    env = os.environ.copy()
    mc = config["model_config"]
    if mc.get("base_url"):
        env["ANTHROPIC_BASE_URL"] = mc["base_url"]
    if mc.get("api_key_env"):
        # Read the actual key from the named env var
        env["ANTHROPIC_API_KEY"] = os.environ.get(mc["api_key_env"], "")
    env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] = str(
        config["cost_config"]["autocompact_pct"]
    )
    return env
```

### Practical guidance in defaults

The config file ships with comments explaining the trade-offs so users can make informed changes without reading the spec:

- `task_model`: swap to `claude-opus-4-6` for harder repos, at 5× cost
- `admin_model`: Haiku is the right choice here; don't upgrade without a reason
- `plan_model`: could be Haiku if costs matter and tasks are well-specified; Sonnet recommended
- Open-source: `qwen/qwen3-coder` or `deepseek/deepseek-coder-v3` via Together.ai are viable `task_model` substitutes for cost-sensitive workflows — test on your codebase before committing

### `clawductor doctor` checks models

```
$ clawductor doctor
...
✓ task_model:  claude-sonnet-4-6       (reachable)
✓ plan_model:  claude-sonnet-4-6       (reachable)  
✓ init_model:  claude-sonnet-4-6       (reachable)
✓ admin_model: claude-haiku-4-5        (reachable)
  base_url:    (not set — using Anthropic directly)
```

If a model identifier is wrong or unreachable, `doctor` fails with a clear error before any sessions start.

---

## 14. Sandboxing

Sandboxing is Claude Code's OS-level isolation feature that enforces hard boundaries on what an agent can access, regardless of what it's instructed to do. It operates at the operating system level — not the application level — so it constrains every subprocess, script, and tool the agent spawns, not just Claude Code itself.

### What it enforces

**Filesystem isolation:** The agent can only read and write within its worktree directory. Attempts to access files outside (including other worktrees, the home directory, or system files) are blocked at the OS level. Even if an agent gets prompt-injected and attempts `rm -rf ~`, the sandbox prevents it.

**Network isolation:** All outbound traffic routes through a controlled proxy. The agent can only reach domains on an allowlist. Sensitive data (SSH keys, API tokens) cannot be exfiltrated even if an agent is compromised.

This is built on macOS Seatbelt — no additional installs required on macOS. Anthropic's internal testing shows sandboxing reduces permission prompts by ~84% because Claude can work freely within defined boundaries rather than asking permission for every action.

### How Clawductor enables it

Sandboxing is enabled per worktree session via Claude Code's `--sandbox` flag. The canonical `launch_agent_session()` implementation is in section 12 (Token Management) — it owns all session environment setup including the autocompact threshold, `CLAWDUCTOR_*` env vars, and model/endpoint config. The sandbox flags are added there:

```python
# In launch_agent_session() — additions to the cmd list for sandboxing:
cmd = [
    "claude",
    "--sandbox",                                         # OS-level isolation
    "--allowedDomains", get_allowed_domains(repo_config), # Network allowlist
    "--model", get_model("task"),                        # From config.py
    "-p", task_prompt,
]
# Full env setup (CLAWDUCTOR_*, AUTOCOMPACT, model endpoint) is handled
# by build_session_env() called before this — see section 12.
```

**Allowed domains** are inferred from `context.md` during init — if the project uses npm, `registry.npmjs.org` is allowed; if Python, `pypi.org`; plus any project-specific APIs detected. User can extend the list from the TUI.

### Relationship to permission defaults

Sandboxing and `settings.json` permission allowlists are complementary:
- `settings.json` allowlists tell Claude Code which operations to auto-approve without prompting
- Sandboxing enforces at the OS level what operations are physically possible

Together they give the agent maximum autonomy within safe boundaries — no constant permission prompts, and no ability to escape the boundaries even if something goes wrong.

### Fallback

If sandboxing is unavailable (e.g. older Claude Code version), Clawductor falls back to `settings.json` allowlists only and logs a warning in the TUI. The `clawductor doctor` command checks for sandbox support.


---

## 15. TUI Dashboard

Built with **Textual**. If Textual proves problematic, fall back to a `curses` implementation — shipping matters more than aesthetics.

### Main dashboard

```
┌─────────────────────────────────────────────────────────────────────┐
│ CLAWDUCTOR                                        [q]uit [?]help    │
├─────────────────────────────────────────────────────────────────────┤
│ SESSION         REPO    TASK      STATE    AGO    CTX%   ~COST      │
│ ────────────────────────────────────────────────────────────────    │
│ auth-agent      myapp   TASK-001  ● WAIT   12s    38%    $0.23      │
│ frontend-agent  myapp   TASK-004  ● RUN    2s     71%    $0.08  ⚠   │
│ api-agent       other   TASK-007  ◐ STALL  45s    19%    $0.41      │
│ db-agent        other   TASK-002  ✓ DONE   3m     —      $0.31      │
├─────────────────────────────────────────────────────────────────────┤
│ Total: $1.03  [n]ew  [t]asks  [Enter]attach  [s]top  [↑↓]nav       │
└─────────────────────────────────────────────────────────────────────┘
```

CTX% shows `—` for completed/stopped sessions. The `⚠` symbol appears when CTX% exceeds the `context_pct_warn` threshold (default 65%) from `config.yaml`.

State colours: RUNNING=green, WAITING=yellow bold, STALLED=orange, ERROR=red bold, COMPLETED=dim green, STOPPED=grey.

### Task management view (`t`)

Pressing `t` opens the task list for the selected repo without leaving the dashboard:

```
┌─── Tasks: myapp ────────────────────────────────────────────────┐
│                                                        [+]add   │
│ [~] TASK-001  Implement JWT auth          HIGH   auth-agent     │
│ [ ] TASK-003  Password reset flow         HIGH   —              │
│ [ ] TASK-004  Rate limiting               MED    —              │
│ [ ] TASK-005  Playwright e2e tests        LOW    —              │
│ [!] TASK-006  Deploy to staging           HIGH   blocked        │
│ [x] TASK-002  Prisma schema               HIGH   done           │
├─────────────────────────────────────────────────────────────────┤
│ [+]add  [↑↓]move priority  [b]lock  [d]elete  [Esc]back        │
└─────────────────────────────────────────────────────────────────┘
```

From this view the user can add tasks, reorder pending tasks to change priority, mark tasks as blocked, and delete pending tasks. Cannot delete in-progress or completed tasks.

### Add task modal (`n` or `+`)

```
┌─── Add Task ─────────────────────────────────────────────────────┐
│                                                                   │
│  Repo:     [myapp (/Users/pj/projects/myapp)               ▼]   │
│                                                                   │
│  Task:     [Implement password reset using SendGrid.        ]    │
│            [Tests required. See /src/lib/email.ts.          ]    │
│                                                                   │
│  Priority: [ ] High  [●] Medium  [ ] Low                        │
│                                                                   │
│  Blocked by: [                                              ]    │
│              (optional — TASK-IDs comma separated)               │
│                                                                   │
│                    [Cancel]  [Add Task]                          │
└───────────────────────────────────────────────────────────────────┘
```

If repo has not been initialised: run initialisation flow first, then add task.
If repo is already initialised: add task to `tasks.md` directly. Agent picks it up on next loop.

### TUI Passthrough Mode

Passthrough mode drops the user directly into the Claude Code session for a specific agent. It's the escape hatch when you want to understand what's happening, intervene, or ask questions — without losing the dashboard or the agent's context.

**Entry flow:**

Press Enter on a selected session. Before attaching, Clawductor shows a contextual help overlay in the terminal for 4 seconds (dismissible with any key):

```
┌─────────────────────────────────────────────────────────────────────┐
│  Attaching to: auth-agent  │  Task: TASK-001 — JWT authentication   │
│  State: ● WAITING          │  CTX: 38%  │  Cost so far: $0.23       │
├─────────────────────────────────────────────────────────────────────┤
│  You are now inside the Claude Code session.                        │
│                                                                     │
│  /btw <question>  Ask a side question without interrupting the      │
│                   agent or adding noise to its context.             │
│                   E.g. /btw what files has it modified so far?      │
│                                                                     │
│  Type normally   Send a message directly to the agent               │
│                                                                     │
│  Ctrl+b d        Return to Clawductor dashboard                     │
│  (press any key to dismiss this and attach now)                     │
└─────────────────────────────────────────────────────────────────────┘
```

The overlay shows the current task name, state, CTX%, and cost — so the user is oriented before they type anything. It disappears automatically after 4 seconds or on any keypress.

**Implementation:**

```python
def attach_to_session(session: Session) -> None:
    overlay = build_attach_overlay(session)  # builds the string above
    # Print overlay to terminal
    print(overlay)
    # Wait up to 4 seconds for keypress, then attach regardless
    wait_for_keypress_or_timeout(seconds=4)
    # Clear overlay, attach to tmux session
    clear_terminal_line()
    os.execvp("tmux", ["tmux", "attach-session", "-t", session.tmux_session])
```

**While attached — what users can do:**

- **`/btw <question>`** — Ask a side question without interrupting the agent or polluting its context. The answer appears in a floating overlay, then vanishes. The agent keeps working. Use this to check what files have been modified, understand a decision the agent made, or look something up in context. Available even while the agent is mid-response.
- **Type normally** — Send a direct message to the agent. This does interrupt the current turn and adds to conversation history. Use when you want to redirect, correct, or add information.
- **`/rewind`** — Roll back to a previous checkpoint if something has gone wrong. Clawductor's error recovery attempts this automatically, but you can also trigger it manually.
- **Voice input** — Claude Code's native voice mode works as normal. Clawductor's tmux setup does not suppress audio input.

**Return to dashboard:**

`Ctrl+b d` detaches from the tmux session without stopping the agent. Clawductor dashboard resumes immediately, picks up monitoring where it left off.

**When to use passthrough vs. letting Clawductor handle it:**

| Situation | Do this |
|-----------|---------|
| WAITING — agent needs y/n or a quick answer | Let Clawductor's CLAWDUCTOR_QUESTION handler surface it in the TUI first. Only attach if the modal hasn't appeared. |
| STUCK — agent repeating itself | Attach and use `/btw` to understand what it's stuck on, then send a direct message to redirect. |
| STALLED — no output | Attach to check if it's genuinely blocked or just slow. Use `/btw what are you currently working on?` |
| Curious what it's doing | `/btw` from passthrough — no need to interrupt. |
| Want to redirect the task | Type directly to the agent. |

**Voice mode:** Clawductor does not interfere with Claude Code's native voice input. When in passthrough mode, voice works exactly as it would in a standalone Claude Code session. Clawductor's tmux setup must not suppress audio input — verified during testing on macOS.

---

## 16. Notification System

No external dependencies — uses macOS `osascript`:

```python
def notify(session_name: str, state: SessionState, detail: str = ""):
    messages = {
        SessionState.WAITING:   "Waiting for your input",
        SessionState.STALLED:   "No output — may be stuck",
        SessionState.ERROR:     "Hit an error",
        SessionState.COMPLETED: "Task complete",
    }
    message = messages.get(state, state.value)
    if detail:
        message = f"{message}: {detail}"

    script = f'display notification "{message}" with title "Clawductor" subtitle "{session_name}"'
    subprocess.run(["osascript", "-e", script])
```

Trigger on transitions to: WAITING, ERROR, COMPLETED, STALLED.
Do NOT notify repeatedly for the same state — only on transition.

---

## 17. State Persistence

Auto-saved to `~/.clawductor/state.yaml` after every change. Never edited by user. Restored on relaunch.

```yaml
# Auto-generated by Clawductor — do not edit
version: "1.0"
repos:
  - path: /Users/pj/projects/myapp
    name: myapp
    default_branch: main
    merge_strategy: open_pr
    protected_branches: [main, develop]
    agent_count: 1
    initialised: true
    sandbox_enabled: true
    allowed_domains: [registry.npmjs.org, github.com]
    # model overrides at repo level (optional — inherits from config.yaml if absent)
    # model_overrides:
    #   task_model: claude-opus-4-6

sessions:
  - id: "auth-agent-myapp-20250311"
    name: auth-agent
    repo_path: /Users/pj/projects/myapp
    current_task: TASK-001
    worktree_path: /Users/pj/projects/myapp/.clawductor/worktrees/TASK-001-jwt-auth
    branch: clawductor/TASK-001/jwt-authentication
    tmux_session: clawductor-auth-agent-myapp
    state: waiting
    created_at: "2025-03-11T20:00:00Z"
    last_output_at: "2025-03-11T20:12:00Z"
```

On relaunch: check if tmux session still exists. If yes, reconnect monitoring. If no, mark as STOPPED and let user decide whether to restart.

### Orchestrator crash recovery

The orchestrator is a single Python process. If it dies unexpectedly (SIGKILL, machine sleep, terminal close), in-flight tasks remain `[~]` in `tasks.md` with no process watching them. They will never go stale because no orchestrator is polling stdout. Left unrecovered, these tasks block the queue permanently — other agents see them as claimed and skip them.

**Recovery on relaunch:**

```python
def recover_orphaned_tasks(repo_config: RepoConfig) -> list[str]:
    """Called at startup for every initialised repo."""
    tasks = parse_tasks_md(repo_config.path)
    recovered = []

    for task in tasks:
        if task.status != "in_progress":
            continue

        # Check if the tmux session that claimed this task still exists
        session_name = task.claimed_by  # stored in tasks.md at claim time
        session_alive = tmux_session_exists(session_name)

        if not session_alive:
            # Orchestrator died — no session is working this task
            reset_task_to_pending(repo_config.path, task.id)
            append_progress(repo_config.path, "orchestrator", task.id,
                           "RECOVERED", "Orphaned after orchestrator restart")
            recovered.append(task.id)
            notify_user(f"{task.id} was orphaned — reset to pending")

    return recovered
```

This runs before any new sessions are spawned. The user sees a notification listing recovered tasks. They can review `progress.md` to understand what state the agent had reached before the crash.

**Prevention — PID file:**

Clawductor writes `~/.clawductor/orchestrator.pid` on startup and removes it on clean exit. On relaunch, if the PID file exists and the process is no longer running, that's an unclean exit — trigger orphan recovery immediately and log it clearly.

```python
PID_FILE = Path.home() / ".clawductor" / "orchestrator.pid"

def write_pid():
    PID_FILE.write_text(str(os.getpid()))

def check_unclean_exit() -> bool:
    if not PID_FILE.exists():
        return False
    old_pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(old_pid, 0)  # signal 0 = check existence only
        return False  # process still running (another instance?)
    except ProcessLookupError:
        return True  # PID gone = unclean exit
```

If a live process is found at the old PID, warn the user that another Clawductor instance may be running and refuse to start — prevents two orchestrators fighting over the same `tasks.md`.

---

## 18. CLI Interface

Primary interface is the TUI. CLI commands for scripting and quick ops:

```bash
# PRIMARY — launch TUI
clawductor

# Verify system requirements
clawductor doctor

# List sessions without TUI
clawductor list

# Stop a session
clawductor stop <session-name>
clawductor stop --all

# Attach to session (same as Enter in TUI)
clawductor attach <session-name>

# Remove orphaned worktrees not tracked in state.yaml
# Safe to run at any time — will not touch active sessions
clawductor cleanup

# Show worktree disk usage per repo
clawductor status
```

---

## 19. Dependencies & System Requirements

### Python dependencies

```toml
[project]
name = "clawductor"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    "textual>=0.47.0",
    "pyyaml>=6.0",
    "click>=8.0",
    "rich>=13.0",
]
```

### System requirements (verified by `clawductor doctor`)

| Requirement | Check | Error message |
|-------------|-------|---------------|
| macOS | `sys.platform == "darwin"` | "Clawductor v0.1 is macOS only" |
| tmux | `tmux -V` | "tmux not found. Install via Homebrew: brew install tmux" |
| Claude Code CLI | `claude --version` | "Claude Code not found. Install from code.claude.com" |
| git ≥ 2.5 | `git --version` | "git not found or too old" |
| gh CLI | `gh auth status` | "gh CLI not found (needed for PR strategy). brew install gh" |
| jq | `jq --version` | "jq not found. Install via Homebrew: brew install jq" |
| Disk space | available > 10GB | "Low disk space — worktrees may fail to create" |

`gh` is optional — warn but don't block if missing (PR strategy falls back to push-only). `jq` is required — used by hook scripts to parse Claude Code's JSONL transcripts.

---

## 20. Launch Checklist

- [ ] `pip install clawductor` works cleanly
- [ ] `clawductor doctor` verifies all requirements and shows estimated cost per task cycle
- [ ] `clawductor` launches TUI immediately with empty dashboard
- [ ] Pressing `n` opens add task modal with priority and blocked-by fields
- [ ] Pressing `t` opens task management view for selected repo
- [ ] Task reordering changes priority correctly in `tasks.md`
- [ ] Repo without `.clawductor/` triggers initialisation flow automatically
- [ ] Initialiser generates `context.md`, `tasks.md`, `progress.md` and commits them
- [ ] `CLAWDUCTOR_QUESTION` detected and surfaced in TUI modal correctly
- [ ] context.md review pane shown after initialisation, edits committed by Clawductor
- [ ] Task integrity checksums stored and verified before agent starts work
- [ ] Repo ownership warning shown when remote owner doesn't match authenticated user
- [ ] Agent session spawns in correct worktree on correct branch
- [ ] Agent never commits to main
- [ ] Per-stack `.claude/settings.json` written into each worktree — agent doesn't stop for npm install, pytest, git status etc
- [ ] Agent runs test suite before "Task complete" — failing tests block completion
- [ ] If no test command in context.md, CLAWDUCTOR_QUESTION fires asking user how to verify
- [ ] Task claiming via atomic git push works correctly
- [ ] Second agent (manual test) gets next available task, not the same one
- [ ] Orchestrator updates heartbeat timestamp from stdout activity — no git commits during active work
- [ ] Stale task recovery triggers after 2 minutes stdout silence
- [ ] STUCK state detected when same output pattern repeats 3+ times — notification fires
- [ ] STUCK does not auto-kill session — user decides via TUI
- [ ] `clawductor doctor` confirms all four models are reachable before first session
- [ ] No hardcoded model strings in source — all calls go through `get_model(role)`
- [ ] Config file written on first run with correct defaults and comments
- [ ] Model swap tested: change `task_model` in config.yaml, restart, confirm new model used
- [ ] Cost estimates appear in dashboard, update as sessions run
- [ ] Mac notification fires on WAITING, ERROR, COMPLETED, STALLED (transitions only)
- [ ] Enter in TUI attaches to session, `Ctrl+b d` returns to TUI
- [ ] `/clear` sent between tasks
- [ ] PR opened automatically on task completion (PR strategy) with auto-generated body from progress.md
- [ ] Auto-merge works and pushes to main (auto-merge strategy)
- [ ] Merge conflict detected and user notified — not auto-resolved
- [ ] Worktree and local branch cleaned up after completion
- [ ] Worktree creation blocked when limit (10) reached — error shown in TUI
- [ ] Disk usage warning fires when worktrees exceed 5GB
- [ ] `clawductor cleanup` removes orphaned worktrees correctly
- [ ] `kill_agent_session()` kills process group — verify no zombie processes after kill
- [ ] State restored correctly after TUI restart
- [ ] Multiple repos visible in same dashboard
- [ ] `.claudeignore` generated at init with stack-aware defaults, committed to repo
- [ ] PreToolUse hook on Read enforces `.claudeignore` — agent cannot read ignored files
- [ ] `PreCompact` hook generates recovery snapshot before every compaction
- [ ] `SessionStart` hook re-injects recovery snapshot after compaction
- [ ] `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=75` set in every session environment
- [ ] MCP servers scoped to stack — no irrelevant servers loaded per worktree
- [ ] CTX% shown in TUI dashboard, ⚠ appears above 65%
- [ ] Hooks generated per worktree: PostToolUse formatter, Stop quality gate, PreToolUse path guard, branch guard
- [ ] Stop hook blocks agent if tests fail — verified by intentionally breaking tests
- [ ] PostToolUse formatter runs automatically on every file edit
- [ ] Protected paths hook blocks writes to files listed in context.md "Do Not Modify"
- [ ] Plan Mode: agent outputs "Plan ready" before starting implementation
- [ ] Sandboxing enabled — agent cannot access files outside worktree
- [ ] Sandbox fallback warning shown in doctor if sandbox unavailable
- [ ] /rewind attempted on ERROR before full task reset
- [ ] Multi-agent: 2 agents configured, each claims different tasks, no conflicts
- [ ] Passthrough overlay appears on attach, shows task name/state/CTX%/cost
- [ ] Overlay auto-dismisses after 4 seconds or on any keypress
- [ ] /btw guidance visible in overlay
- [ ] Voice mode works when user attaches to session in passthrough mode
- [ ] context.md kept under 200 lines by initialiser
- [ ] README has demo GIF (record with asciinema)
- [ ] README prominently warns: only use on repos you control
- [ ] GitHub repo public with MIT licence
- [ ] Posted to: HackerNews Show HN, r/ClaudeAI, r/LocalLLaMA

---

## 21. Roadmap (Post-MVP)

In priority order, with reasoning:

1. **Task dependency resolution** — automatically unblock tasks when their dependencies complete, without user intervention. Users hit this almost immediately on any moderately complex project. The current design requires manual unblocking, which breaks the core "run autonomously and go do something else" promise. Highest friction item post-launch.

2. **Extended permission profiles** — the MVP covers Node and Python stacks; this expands to Go, Rust, Ruby, and others, adds user-defined profiles, and introduces a TUI for editing allowlists without touching JSON directly. Reduces onboarding friction for every new repo type.

3. **Hard cost controls** — the MVP has cost visibility (session totals, CTX% in dashboard) and a soft `session_cost_alert` threshold that fires a notification. What it lacks is a circuit breaker: an agent can run indefinitely with no hard cap. For solo developers this is an inconvenience; for anyone running Clawductor with a shared API key, on behalf of others, or simply unattended overnight, it is a real financial risk. This item adds: hard spend limits per session, per repo, and per day (configured in `config.yaml`); automatic session pause (not kill — pause, preserving state) when a limit is hit; a TUI prompt asking the user whether to resume or stop; and a daily/weekly cost summary. The pause-not-kill distinction matters — an abrupt kill mid-task loses work, whereas a pause lets the user make an informed decision and resume if they choose.

4. **Linux support** — macOS-only excludes a large share of developers and all server/CI infrastructure. Getting Clawductor working on Linux (where most of the multi-agent orchestration use cases live) unlocks a substantially larger audience and is a prerequisite for the cloud roadmap. Does not require full feature parity on day one — core Ralph loop and TUI first. The primary blocker is tmux behaviour differences and the macOS Seatbelt sandboxing dependency (Linux uses bubblewrap — Claude Code supports both, so sandboxing should carry over; the TUI and notification layers need testing).

5. **Windows / WSL2 support** — Windows is absent from the roadmap entirely, which is a silent gap given the developer population it represents. Native Windows support is unlikely near-term given the tmux dependency, but WSL2 makes this tractable: Clawductor running inside a WSL2 environment would work with minimal changes once Linux support exists. Not a standalone item — this follows directly from item 3 and should be tackled as a fast-follow once Linux is stable. Explicitly calling it out avoids it becoming a forgotten gap.

6. **Programmatic API** — a minimal interface for triggering Clawductor operations from scripts, CI pipelines, and external tools without launching the TUI. Even a thin CLI extension covers most cases: `clawductor task add --repo myapp --description "..."`, `clawductor task list --json`, `clawductor session status --json`. This opens up integrations — trigger a task from a GitHub Actions workflow, pipe task status into a dashboard, chain Clawductor into a larger automation — without needing to build a full web product. Sits naturally here: after platform reach is established but before the cloud roadmap.

7. **Non-technical user mode** — simplified UI that hides git/agent concepts entirely, shows task status in plain English with a "what's happening" summary. The biggest single growth lever: opens Clawductor to product managers, founders, and non-developer collaborators who want autonomous task execution without needing to understand worktrees or branch naming.

8. **Agent output quality evaluation** — a lightweight eval harness that scores task completion quality beyond binary pass/fail. Once non-technical users are running Clawductor (item 7), they cannot read the generated code to judge whether a task was actually done well — tests passing is necessary but not sufficient. This item adds: a post-task review step where a separate lightweight agent scores the output against the task description and a rubric; a quality score surfaced in the TUI and progress.md; and a threshold below which tasks are flagged for human review rather than auto-merged. Avoids the failure mode of Clawductor confidently completing low-quality work that users can't catch.

9. **Proactive mid-task compaction** — orchestrator-driven `/compact` when CTX% crosses a configurable mid-task threshold (e.g. 60%), with custom compaction instructions injected to preserve task state rather than relying on Claude's default summary. The MVP sets the autocompact threshold and generates PreCompact hooks; this adds active orchestrator intervention for long-running tasks. A reliability improvement for power users running complex or large-codebase tasks.

10. **Community skills registry** — open PRs to Clawductor's curated skills registry; crowdsourced stack mappings and skill recommendations. Seed with 20+ high-quality stacks at launch to give contributors something to build on. Value compounds over time as the registry grows, but not urgent in early days when the maintainer controls it directly.

11. **Automated inter-agent communication** — agents passing structured messages to each other beyond shared task files; reviewer/builder patterns where one agent reviews another's output before it's committed. Technically interesting but solves a coordination problem most users won't encounter until they're running Clawductor at scale across many concurrent agents. Worth building once the simpler cases are stable.

12. **Native Agent Teams integration** — Anthropic's experimental `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` feature (research preview, Feb 2026) enables built-in inter-agent coordination with shared task lists and direct messaging. Currently has known limitations around session resumption and shutdown. Worth integrating once stable as an alternative coordination layer to the git-based protocol.

13. **Alternative agent runtime support** — Clawductor v1.0 is hardwired to Claude Code's CLI as the underlying agent runtime, which is a deliberate dependency on Claude Code's specific feature set: hooks, sandboxing, skills, `/clear`, `/rewind`, `/btw`, and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`. These features are what make the architecture reliable rather than advisory. As the broader agent tooling ecosystem matures (OpenCode, Codex CLI, and others), a stable cross-runtime interface for hooks, sandboxing, and context management may emerge. When it does, abstracting the agent runtime layer — so Clawductor can orchestrate OpenCode or other agents with the same guarantees — becomes viable. Not worth building prematurely; the interface doesn't exist yet and the features would degrade. Track as a future architectural consideration once a standard emerges.

14. **Clawductor Cloud** — hosted dashboard, mobile push notifications if traction warrants. Needs an established user base first.

---

## 22. What This Is NOT

Do not build any of the following in v1.0:
- A web UI or API server
- Any cloud connectivity or telemetry
- A database (SQLite or otherwise)
- Anything requiring installs beyond `pip install clawductor`
- A YAML config file the user has to write manually

Note: Windows and Linux support are explicitly planned in the roadmap (items 4 and 5). They are out of scope for v1.0 only — not ruled out permanently.

**The test:** if a developer can go from `pip install clawductor` to a running agent on their first repo in under 5 minutes, the MVP is right. If they have to read more than the quickstart section of the README first, something is wrong.
