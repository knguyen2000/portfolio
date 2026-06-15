# /add-agent

Scaffold a new agent mode for this portfolio app.

## Input

The user will provide a name and brief description of the new agent.

## Steps

1. Create `agents/<agent_name>/` directory with:
   - `<agent_name>_agent.py` — agent class following the interface in `agents/README.md`. Study an existing agent (e.g., `agents/vector/vector_agent.py`) for the expected constructor signature (`client`, `model_id`, `docs`, `log`) and `generate()` method pattern.
   - `DESIGN.md` — architecture and design decisions. **Must follow the same structure as `agents/rlm/DESIGN.md`** (the reference standard): sections for Overview, Architecture, Key Decisions, and Limitations at minimum.
   - `BEHAVIOR.md` — expected user-facing behavior with real execution traces showing input → output. Follow the format of existing `BEHAVIOR.md` files.
   - `README.md` — brief overview matching the structure of existing agent README files.
   - `tests/test_<agent_name>.py` — unit tests for the new agent. At minimum: test the constructor, test `completion()` returns the expected `(text, tokens)` tuple shape, test error handling.

2. Register the new mode in `config/app_config.py`:
   - Add a `MODE_<NAME>` constant
   - Add it to `AVAILABLE_MODES`

3. Wire it into `components/agent_dispatch.py`:
   - Import the new agent class
   - Add the mode branch in `generate_answer()`

4. Add the mode description/warning in `app.py` alongside the existing `if/elif` chain for agent modes.

5. Run `ruff check` and `pytest` to verify nothing broke.

## Constraints

- Match the existing code style exactly — no type hints, same logging pattern via `state.log_event`
- The agent must work without additional API keys beyond `GOOGLE_API_KEY` unless the user specifies otherwise
- Do not modify other agents
