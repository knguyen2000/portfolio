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

### 3. Naming, style, and structural patterns
- Read 2-3 existing files in the same directory to learn the local patterns — not just naming, but structure
- **Naming:** snake_case functions/variables, PascalCase classes, UPPER_CASE constants. File naming matches neighbors (e.g., `engines/trace_engine.py` not `engines/traceEngine.py`)
- **Function signatures:** parameter ordering, default values, and return types should match the conventions of neighboring functions (e.g., if existing agent methods return `(text, tokens)`, new ones must too)
- **Logging patterns:** if neighboring files use `state.log_event()`, new code must do the same — not `print()` or `logging.info()`
- **Exception types:** if neighboring files raise `ValueError` for invalid input, new code should follow — not `Exception` or a custom type unless the pattern already uses one

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

### 8. Test coverage for new code
- For every new public function or class added, verify a corresponding test exists in `tests/`
- Check that tests follow the naming convention: `tests/test_<module>.py`
- If new behavior was added to an existing module, verify the test file for that module was updated (new test functions appended, not existing tests modified)
- **This is a hard gate.** New code without tests means TDD was skipped — fail and require tests before proceeding.

### 9. Extensibility and modification scope
- Check `git diff` for modified (not just added) lines in existing files
- For each modified function or class: is there an extend-only alternative? (new function, wrapper, config entry, subclass)
- If modification was necessary: are the changes minimal? Are all callers/dependents tested?
- Flag cases where a large block of existing code was rewritten when an additive approach was possible
- **This is a hard gate.** If existing code was modified without justification (no extend-only alternative), or modified code lacks test coverage for affected callers, this is a fail. The dev must either refactor to an extend-only approach or explicitly approve the modification with a reason.

## Output

Group findings by category. For each finding, show:
- File and line number
- What the code does vs what the convention expects
- A suggested fix

End with: **Conforms** or **N items to align**.
