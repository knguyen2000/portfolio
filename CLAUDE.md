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

1. If `SPEC.md` exists, read it — use its context to write the commit message body and PR description, then delete it (it's a planning artifact, not code)
2. Run `/conform` — verify changes match codebase patterns
3. Run `/preflight` — all 11 checks must pass before proceeding
4. Run `/inspect` — browser-level check (pages load, no console errors, Lighthouse, perf)
5. Stage relevant files (never `git add .` — be explicit)
6. Commit following the message format above
7. Create a branch if not already on a feature branch (never commit features directly to `main`)
8. Push the branch and create a PR using the template above
9. Report the PR URL — do NOT merge. The user reviews and approves.

Never force-push, never merge without user approval, never push directly to `main`.

## Don'ts

- Don't commit `.streamlit/secrets.toml` or any API keys
- Don't modify files in `env/` or `chroma_db/`
- Don't add dependencies to `requirements.txt` without checking Streamlit Cloud compatibility
- Don't import Streamlit (`st`) in non-UI modules (`config/`, `engines/`, `agents/`)
  — exception: agents may use `st.session_state` for logging via `state.py`
