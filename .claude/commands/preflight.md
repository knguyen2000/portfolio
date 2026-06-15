# /preflight

Pre-commit and pre-deployment gate. All checks must pass before committing or pushing.

## Checks

Run all of these and report a pass/fail summary:

1. **Secrets** — Scan all tracked `.py` files for hardcoded API keys, tokens, or credentials. Verify `.streamlit/secrets.toml` is in `.gitignore`.

2. **Imports** — Run `python -c "import app"` (or attempt to import each top-level module) to catch broken imports. Flag any import that would fail on Streamlit Cloud (e.g., missing from `requirements.txt`).

3. **Requirements** — Cross-reference `import` statements across all `.py` files against `requirements.txt`. Flag any third-party package that is imported but not listed, or listed but never imported.

4. **Lint** — Run `ruff check .` and report the count. Zero errors = pass.

5. **Tests** — Run `pytest`. All tests must pass.

6. **Config** — Verify `config/app_config.py` constants are consistent: every mode in `AVAILABLE_MODES` has a corresponding agent, `DEFAULT_MODE_INDEX` is in range.

7. **Planning artifacts** — Flag `SPEC.md`, `TODO.md`, or any planning/scratch files in the project root that should not be committed. These must be deleted or gitignored before proceeding.

8. **Debug artifacts** — Check for tracked files matching `check_*.py`, `debug_*.py`, `verify_*.py`, `test_results.txt`. Check for stray `print(` debug statements, `breakpoint()`, `pdb`, `ipdb` in tracked `.py` files (exclude `scripts/debug/`).

9. **.gitignore gaps** — Check if these common patterns are covered: `.env`, `*.log`, `.DS_Store`, `Thumbs.db`, `*.bak`, `*.tmp`. Flag any tracked files that should be gitignored.

10. **Doc sync** — Identify ALL changed folders by combining `git diff --name-only` (staged + modified) AND `git ls-files --others --exclude-standard` (untracked new files). For every such folder that has a `README.md` or `DESIGN.md`, verify the docs reflect the current code. Compare the doc's descriptions against the actual files, classes, and public interfaces in the folder. Flag any doc that describes things that no longer exist, or misses newly added files/functions.

11. **Mode registration** — If any agent file was changed or added, verify the mode is registered in all three places: `config/app_config.py` (mode constant + `AVAILABLE_MODES`), `components/agent_dispatch.py` (routing branch), and `app.py` (mode selector UI). Flag if any registration point is missing.

## Output

End with a summary table:

| Check | Result |
|-------|--------|
| Secrets | Pass/Fail |
| Imports | Pass/Fail |
| Requirements | Pass/Fail |
| Lint | Pass/Fail (N errors) |
| Tests | Pass/Fail (N passed, N failed) |
| Config | Pass/Fail |
| Planning artifacts | Pass/Fail |
| Debug artifacts | Pass/Fail |
| .gitignore | Pass/Fail |
| Doc sync | Pass/Fail |
| Mode registration | Pass/Fail |

Then a one-line verdict: **Ready to commit** or **Fix N issues before committing**.
