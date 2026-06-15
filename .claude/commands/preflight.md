# /preflight

Pre-commit and pre-deployment gate. All checks must pass before committing or pushing.

## Usage

- `/preflight` — run all 11 checks
- `/preflight recheck` — re-run only checks that failed in the previous run this session (skips already-passed checks to save context)

## Checks

Run all of these and report a pass/fail summary:

1. **Secrets** — Scan all tracked `.py` files for hardcoded API keys, tokens, or credentials. Verify `.streamlit/secrets.toml` is in `.gitignore`.

2. **Imports** — Run `python -c "import app"` (or attempt to import each top-level module) to catch broken imports. Flag any import that would fail on Streamlit Cloud (e.g., missing from `requirements.txt`).

3. **Requirements** — Cross-reference `import` statements across all `.py` files against `requirements.txt`. Flag any third-party package that is imported but not listed, or listed but never imported.

4. **Lint and format** — Run `ruff check .` and `ruff format --check .`. Both must report zero issues. (Skip if `/fix` already ran with zero remaining issues this session.) If format issues exist, run `ruff format .` to fix them automatically, then re-check.

5. **Tests** — Run `pytest`. All tests must pass.

6. **Config** — Verify `config/app_config.py` constants are consistent: every mode in `AVAILABLE_MODES` has a corresponding agent, `DEFAULT_MODE_INDEX` is in range.

7. **Planning artifacts** — Flag `SPEC.md`, `TODO.md`, or any planning/scratch files in the project root that should not be committed. These must be deleted or gitignored before proceeding.

8. **Debug artifacts** — Check for tracked files matching `check_*.py`, `debug_*.py`, `verify_*.py`, `test_results.txt`. Check for stray `print(` debug statements, `breakpoint()`, `pdb`, `ipdb` in tracked `.py` files (exclude `scripts/debug/`).

9. **.gitignore gaps** — Check if these common patterns are covered: `.env`, `*.log`, `.DS_Store`, `Thumbs.db`, `*.bak`, `*.tmp`. Flag any tracked files that should be gitignored.

10. **Doc sync** — Identify ALL changed folders by combining `git diff --name-only` (staged + modified) AND `git ls-files --others --exclude-standard` (untracked new files). For every such folder that has a `README.md` or `DESIGN.md`, verify the docs reflect the current code. Compare the doc's descriptions against the actual files, classes, and public interfaces in the folder. Flag any doc that describes things that no longer exist, or misses newly added files/functions. (Skip if `/docsync` already ran and all findings were resolved this session.)

11. **Mode registration** — If any agent file was changed or added, verify the mode is registered in all three places: `config/app_config.py` (mode constant + `AVAILABLE_MODES`), `components/agent_dispatch.py` (routing branch), and `app.py` (mode selector UI). Flag if any registration point is missing.

## Modification Impact Check

If any existing code lines were modified (not just new code added), run this additional check:

12. **Regression scope** — For each modified function/method, grep for all callers and importers. Verify that existing tests cover those call paths. Flag any caller that has no test coverage — these need manual verification or a new regression test before committing.

## Journal Check (soft)

If a `JOURNAL-<current-branch>.md` exists, check whether its Status section is up to date with the current state of the branch. If stories are completed but not checked off, warn (don't fail).

## Output

End with a summary table:

| Check | Result |
|-------|--------|
| Secrets | Pass/Fail |
| Imports | Pass/Fail |
| Requirements | Pass/Fail |
| Lint & format | Pass/Fail (N errors) |
| Tests | Pass/Fail (N passed, N failed) |
| Config | Pass/Fail |
| Planning artifacts | Pass/Fail |
| Debug artifacts | Pass/Fail |
| .gitignore | Pass/Fail |
| Doc sync | Pass/Fail |
| Mode registration | Pass/Fail |
| Regression scope | Pass/Fail/N/A |
| Journal | Up to date / Stale (soft) |

Then a one-line verdict: **Ready to commit** or **Fix N issues before committing**.
