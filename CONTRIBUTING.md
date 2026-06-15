# Contributing

## Getting Started

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Read these first (in order)

1. **`CLAUDE.md`** — architecture, conventions, git workflow, what not to do
2. **`config/app_config.py`** — all mode constants, model IDs, and thresholds in one file
3. **`state.py`** — session state API (small file, worth memorizing)
4. **`agents/rlm/DESIGN.md`** — best example of the documentation standard we follow
5. **`agents/*/BEHAVIOR.md`** — real execution traces showing how each agent actually behaves

### Key rules to internalize

- **Session state goes through `state.py`** — never access `st.session_state` directly. New variables must be initialized in `init_session_state()`.
- **No Streamlit in non-UI modules** — `config/`, `engines/`, `agents/` must not `import streamlit`.
- **Adding an agent mode requires three registrations** — `config/app_config.py`, `components/agent_dispatch.py`, `app.py`. Miss one and it fails silently at runtime.
- **`data/` is the CMS** — drop a markdown file in `data/projects/` and the app picks it up. No code changes needed.

## Working with Claude Code

This project uses [Claude Code](https://claude.ai/code) as the primary development tool. The workflow is designed so you describe what you want, Claude builds it, and you review before anything ships.

### Available commands

| Command | When to use |
|---------|-------------|
| `/kickoff` | Start work — paste tasks, get a SPEC, serial vs parallel recommendation |
| `/preflight` | Before every commit — 11-check quality gate |
| `/retest` | After fixing a bug found during manual testing |
| `/conform` | Check if your changes match codebase patterns |
| `/docsync` | Audit all folder-level docs for staleness |
| `/inspect` | Final browser-level check — pages, console, Lighthouse, perf |
| `/sweep` | Periodic cleanup — find dead code, stale files, .gitignore gaps |
| `/fix` | Auto-fix lint and format issues |
| `/add-agent` | Scaffold a new AI agent mode |

### Starting work: `/kickoff`

1. **Pick tasks from the backlog** — paste them (any format) into `TASKS.md` in the project root
2. **Run `/kickoff`** — Claude reads your tasks, asks clarifying questions (never assumes), and generates a proper `SPEC.md`
3. **Claude recommends serial or parallel** — based on file overlap and dependency analysis
4. **You approve** — Claude starts implementing

### Task sizing

| Size | Signal | What happens |
|------|--------|-------------|
| Small | <1 hour, <5 files | TDD → implement → commit. No ceremony. |
| Medium | 1-4 hours, 5-15 files | SPEC.md with stories → TDD → commit per story |
| Large | 4+ hours, 15+ files | SPEC.md with phases → scaffold → implement per phase → integrate |

### Serial vs parallel

**Serial (default)** — tasks are worked one at a time, each gets its own branch and PR. Use when tasks share files or have dependencies.

**Parallel** — tasks run in separate git worktrees simultaneously. Only when ALL of these are true:
- Each task takes >1 hour (otherwise serial is faster)
- Zero shared files between tasks
- Zero import dependencies between tasks
- Zero shared state (session_state keys, config values)

`/kickoff` runs this analysis automatically and recommends the right approach.

### Typical workflow (after kickoff)

1. **Claude writes tests first** (TDD) — failing tests that define the feature
2. **Claude implements** — code until tests pass
3. **You test manually** — run the app, try edge cases
4. **If bugs found** — tell Claude, then run `/retest` (appends new test cases, never modifies existing ones)
5. **When satisfied** — tell Claude to "commit" or "ship it"
6. **Claude runs the shipping checklist**: `/conform` → `/preflight` → `/inspect` → commit → branch → PR
7. **You review the PR** — approve and merge when ready

### What "done" means

A feature is done when all of these are true:

- [ ] Tests pass (`pytest`)
- [ ] `/conform` shows no issues
- [ ] `/preflight` passes (all 11 checks)
- [ ] `/inspect` passes (no console errors, Lighthouse scores above 70)
- [ ] Manual testing confirms the feature works as expected
- [ ] Folder-level docs (README.md, DESIGN.md) are updated
- [ ] PR is created with Summary, Changes, and Test Plan sections

## Git Conventions

### Commit messages

```
<type>(<scope>): <short summary>
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`, `perf`

**Scope:** the primary area — `rlm`, `vector`, `file-based`, `nla`, `trace`, `state`, `ui`, `config`, `deps`, `ci`

**Rules:** imperative mood, lowercase, under 60 chars, no period. Body explains *why*, not *what*.

### Branch naming

```
<type>/<short-slug>
```

Examples: `feat/availability-page`, `fix/trace-engine-overlap`

### Pull requests

Title follows commit format. Body uses:

```
## Summary
- what changed and why

## Changes
- notable file/module changes

## Test Plan
- [ ] how to verify

Closes #N
```

### Issues

Use the templates in `.github/ISSUE_TEMPLATE/` — GitHub shows them automatically when creating a new issue.

## Architecture at a Glance

```
Presentation    app.py, pages/, styles.py
Orchestration   components/agent_dispatch.py, chat_renderer.py
Reasoning       agents/file_based, vector, rlm, nla
Service         engines/, services/
Data            data/, config/
```

Each agent folder has `README.md`, `DESIGN.md`, and `BEHAVIOR.md`. Read them before modifying an agent.

## Things to know

- **Free-tier rate limits shape the architecture** — RLM's `max_steps=10` (not 30) and sequential sub-LLM calls are rate-limit driven, not performance choices. Don't "optimize" them into parallel calls.
- **NLA has no portfolio knowledge** — it explores model internals only. The trace engine doesn't apply to NLA responses. This is by design.
- **Trace engine is O(N*M)** — it scans response against corpus character-by-character. Fine for current scale, would need a suffix array for 10k+ docs.
- **SPEC.md is ephemeral** — it's a planning artifact used during development. It gets read for commit/PR context, then deleted. Never commit it.
