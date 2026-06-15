# /conform

Check whether staged or recent changes follow the conventions and patterns established in this codebase.

## What to check

Run `git diff --cached` (staged) or `git diff HEAD~1` (last commit) to identify changed files. Then verify each item below against the actual codebase patterns, not just CLAUDE.md rules.

### 1. Architecture conformance
- New files are in the correct layer (`agents/`, `engines/`, `components/`, `pages/`, `config/`, `data/`)
- No Streamlit (`st`) imports in non-UI modules (`config/`, `engines/`, `agents/`) — exception: `st.session_state` via `state.py`
- Session state access goes through `state.py`, not inline `st.session_state` manipulation
- Data files live in `data/`, not hardcoded in Python

### 2. Agent interface
- Any new or modified agent exposes `completion(query) -> (text, tokens)` matching the existing contract
- Agent is registered in `config/app_config.py` modes and dispatched in `components/agent_dispatch.py`
- Agent folder has `README.md` and `DESIGN.md`

### 3. Naming and style
- Read 2-3 existing files in the same directory to learn the local naming patterns (function names, variable names, class names)
- New code should match: snake_case functions/variables, PascalCase classes, UPPER_CASE constants
- File naming matches neighbors (e.g., `engines/trace_engine.py` not `engines/traceEngine.py`)

### 4. Import patterns
- Compare import style with existing files in the same directory (relative vs absolute, ordering, grouping)
- No unused imports (ruff F401 catches this, but verify)

### 5. Error handling patterns
- Compare with how neighboring files handle errors — does this code match?
- No bare `except:` clauses
- No swallowed exceptions (catch-and-pass with no logging)

### 6. Config and constants
- New thresholds, model IDs, or magic numbers belong in `config/app_config.py`, not inline
- New profile/about data belongs in `config/profile.py` or `config/about_data.py`

### 7. Commit message format
- If checking a committed change, verify the commit message follows: `<type>(<scope>): <summary>`
- Imperative mood, under 60 chars, lowercase, no period

## Output

Group findings by category. For each finding, show:
- File and line number
- What the code does vs what the convention expects
- A suggested fix

End with: **Conforms** or **N items to align**.
