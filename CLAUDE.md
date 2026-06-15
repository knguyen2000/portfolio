# Portfolio — AI-Powered Interactive Portfolio

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Stack

Python 3.11+ / Streamlit / Google Gemini API (Gemma 4 31B) / ChromaDB

## Architecture

Five-layer structure:

| Layer | Location | Purpose |
|-------|----------|---------|
| Presentation | `app.py`, `pages/`, `styles.py` | Streamlit UI, page routing |
| Orchestration | `components/` | Agent dispatch, chat rendering, editor panel |
| Reasoning | `agents/` | Four pluggable AI agents |
| Service | `engines/`, `services/` | Trace engine, checkpoints, workflow intelligence |
| Data | `data/`, `config/` | Markdown content (headless CMS), app constants |

### Agent Modes

1. **File-Based Context** (`agents/file_based/`) — dumps all file summaries into prompt
2. **Vector RAG** (`agents/vector/`) — ChromaDB semantic search + sliding window
3. **RLM** (`agents/rlm/`) — recursive language model with sandboxed Python REPL
4. **NLA** (`agents/nla/`) — natural language autoencoder via Modal-hosted Qwen2.5-7B. Generic model exploration only — has no portfolio knowledge. Exclude NLA from all new features.

Each agent directory has its own `DESIGN.md` and `BEHAVIOR.md`.

## Key Files

- `app.py` — entry point, layout, agent mode selector
- `config/app_config.py` — models, tokens, modes, thresholds
- `components/agent_dispatch.py` — traffic controller for agent routing
- `state.py` — Streamlit session state abstraction
- `engines/trace_engine.py` — source verification and explainability

## Quality Tools

```bash
ruff check .           # lint
ruff format .          # format
ruff check --fix .     # auto-fix lint issues
pytest                 # run tests
pytest -x              # stop on first failure
```

## Conventions

- All new features use TDD: write failing tests first, then implement until they pass
- Session state managed centrally through `state.py`, not inline — never access `st.session_state` directly outside `state.py`; new state variables must be initialized in `init_session_state()`
- Data files in `data/` are the content source of truth (headless CMS pattern)
- API key stored in `.streamlit/secrets.toml` (gitignored, never commit)
- `scripts/debug/` contains throwaway debug scripts, excluded from linting
- `env/`, `chroma_db/`, `__pycache__/` are gitignored, never modify directly
- Adding an agent mode requires syncing three places: `config/app_config.py` (mode constant + `AVAILABLE_MODES`), `components/agent_dispatch.py` (routing branch), and `app.py` (mode description in UI). Missing any one causes a silent runtime failure.
- UI changes must work at mobile (375px), tablet (768px), and desktop (1440px) viewports. When adding or modifying any UI element, consider how it reflows at smaller widths — avoid fixed widths, use Streamlit's column/container layout, and ensure interactive elements remain tappable on touch devices.

### Extensibility and Modification Policy

Write code that can be extended without rewriting. Use patterns (hooks, registries, strategy/plugin, configuration-driven behavior) that let future features plug in rather than fork existing logic.

**Extend, don't modify.** When working on an existing codebase, default to extending existing code rather than modifying it. Add new functions, new branches, new modules — don't rewrite working lines unless there's no alternative.

**Before touching any existing file**, read the full function (and its callers if modifying a public interface) to understand the current behavior, contracts, and assumptions. Never modify code you haven't read.

**When modification is unavoidable**, follow this protocol:
1. **Justify** — confirm there is no extend-only path (new function, wrapper, decorator, subclass, config entry)
2. **Read** — read the full file (not just the target function) and at minimum 2-3 callers of the code being modified to understand the ripple effects
3. **Scope** — keep the change to the minimum lines necessary
4. **Impact analysis** — grep for all callers, importers, and dependents of the changed code
5. **Test all affected paths** — not just the new feature, but every feature that touches the modified lines. If existing tests don't cover a dependent path, add a regression test before making the change.
6. **Note in commit body** — explain why modification was necessary and what was verified

### Task Journal

Every task gets a journal file: `JOURNAL-<branch-name>.md` in the project root (gitignored). This serves two purposes: helps the dev understand how a feature was built without reading every diff, and enables session recovery when context runs out.

**Format:**
```markdown
# Journal: [task name]
Branch: feat/xxx
SPEC: [which section of SPEC.md this covers]

## Status
- [x] Story 1: description (commit sha)
- [ ] Story 2: description
- [ ] Story 3: description

## Current State
[What's working, what's in progress, what's blocked. Updated at each breakpoint.]

## Key Decisions
- [Decision]: [why, and what was the alternative]

## Log
### [timestamp]
**Done:** [what was completed]
**Next:** [what to do next]

### [timestamp]
**Done:** ...
**Problem:** [unexpected issue and how it was resolved]
**Next:** ...
```

**When to WRITE (append) — only at these breakpoints:**
- After completing a user story
- After making a non-obvious design decision (the "why" matters)
- After hitting and resolving an unexpected problem
- Before ending a session (handoff entry — update Status and Current State)

**When to READ:**
- At session start: if the journal exists, read Status and Current State sections to recover context. Do not re-read the full Log unless something is unclear.
- Never during normal work — you already have context from the current session.

**What NOT to write:**
- Every file edit ("edited line 42 of app.py") — that's the commit log's job
- Code snippets — reference `file:line` instead
- Mechanical summaries ("ran ruff, it passed") — only log things a future reader or session needs

**Context pressure:** If the conversation is getting long and you sense context may run out soon, write the handoff entry immediately — don't wait for the next natural breakpoint. Update Status (check off what's done) and Current State (where you are mid-story, what's left). A new session reading this should be able to continue without asking the dev what happened.

**Explicit handoff:** The dev can run `/resume` in a new session to recover context from the journal. When ending a session, proactively suggest: "Run `/resume` next session to pick up where we left off."

## How to Add Things

- **Add a project** → drop `data/projects/new.md`. Zero code.
- **Add a page** → create `pages/xyz.py`. Streamlit auto-discovers it; update `utils/sidebar.py` for a nav link.
- **Add an AI mode** → create `agents/<mode>/<mode>_agent.py` with `completion(query) -> (text, tokens)`; add a mode constant in `config/app_config.py`; add a branch in `components/agent_dispatch.py`.
- **Change embedding model** → update `EMBEDDING_MODEL_ID` in `config/app_config.py`. The corpus fingerprint triggers a full re-embed.
- **Swap LLM provider** → replace the Gemini client in `app.py`; adapt response-parsing in each agent's `completion`.

## Doc Sync (before committing)

After making code changes to any folder that contains a `README.md` (or `DESIGN.md` in agent folders), update those docs to reflect the current state before committing. This keeps folder-level docs accurate without a separate maintenance pass. Specifically:

- `agents/<mode>/README.md` and `DESIGN.md` — update if agent behavior, API, or architecture changed
- `engines/README.md`, `components/README.md`, `services/README.md`, `models/README.md` — update if files were added/removed/renamed or public interfaces changed
- `static/README.md` — update if assets were added or removed

Do not rewrite docs from scratch — make targeted edits to the sections affected by the code change. If a folder has no README.md, do not create one unless the user asks.

## Git Workflow

When the user says "commit", "ship it", "push", or similar — follow this convention exactly. Do not ask about formatting; just apply it.

### Commit Messages

Format: `<type>(<scope>): <short summary>`

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`, `perf`

Scope is the primary area affected: `rlm`, `vector`, `file-based`, `nla`, `trace`, `state`, `ui`, `config`, `deps`, `ci`, etc. Omit scope only if the change is truly cross-cutting.

Rules:
- Subject line under 60 characters, lowercase, no period
- Imperative mood ("add X", not "added X" or "adds X")
- Body (after blank line) explains **why**, not what — only if the subject isn't self-explanatory
- Reference issue numbers with `closes #N` or `refs #N` in the body, never the subject

Examples:
- `feat(ui): add availability page with Calendly integration`
- `fix(vector): recompute corpus fingerprint on embedding model change`
- `refactor(state): extract session init into dedicated helpers`
- `docs(rlm): update DESIGN.md for sandbox allowlist changes`

### Branch Naming

Format: `<type>/<short-slug>`

Use the same type prefixes as commits. Keep slugs to 2-4 words, hyphenated.

Examples: `feat/availability-page`, `fix/trace-engine-overlap`, `docs/update-readmes`

### Pull Requests

Title matches the primary commit message format: `<type>(<scope>): <summary>`

Body template (always use this structure):
```
## Summary
- <1-3 bullet points describing what changed and why>

## Changes
- <list of notable file/module changes>

## Test Plan
- [ ] <how to verify — tests, manual steps, or both>

Closes #N (if applicable)
```

### Issues

When creating issues, read the templates in `.github/ISSUE_TEMPLATE/` and follow them. GitHub auto-populates these for humans; Claude must match the same format.

### Workflow: Commit and PR

When the user asks to commit and/or create a PR:

1. If `SPEC.md` exists, read it — use its context to write the commit message body and PR description, then delete it (it's a planning artifact, not code). If the session dies before deletion, the next session should check whether SPEC.md belongs to the current branch or a previous task — if stale, delete it before proceeding.
2. **Verify** `/conform` and `/preflight` have already passed during the per-task cycle. If code changed since they last ran (e.g., doc sync fixes, last-minute tweaks), re-run only the affected checks with `/preflight recheck`. Do NOT re-run the full suite if nothing changed — it wastes context.
3. **Do NOT re-run `/inspect`** unless code changed since the last browser test. `/inspect` should have already run after implementation (see per-task cycle in `/kickoff`).
4. Stage relevant files (never `git add .` — be explicit)
5. Commit following the message format above
6. Create a branch if not already on a feature branch (never commit features directly to `main`)
7. Push the branch and create a PR using the template above
8. Report the PR URL — do NOT merge. The user reviews and approves.

Never force-push, never merge without user approval, never push directly to `main`.

## Don'ts

- Don't commit `.streamlit/secrets.toml` or any API keys
- Don't modify files in `env/` or `chroma_db/`
- Don't add dependencies to `requirements.txt` without checking Streamlit Cloud compatibility
- Don't import Streamlit (`st`) in non-UI modules (`config/`, `engines/`, `agents/`)
  — exception: agents may use `st.session_state` for logging via `state.py`
