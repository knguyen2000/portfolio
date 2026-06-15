# /sweep

Audit the codebase for stale code, dead files, debug leftovers, and .gitignore gaps.

## Checks

Run all of these and report findings grouped by category:

### 1. Dead imports and unused variables
- Run `ruff check . --select F401,F841` to find unused imports and unused local variables.
- List each finding with file and line number.

### 2. Unreachable or commented-out code
- Search for blocks of commented-out code (3+ consecutive commented lines that look like code, not documentation).
- Search for functions/classes that are defined but never imported or called anywhere in the project.
- Ignore: `env/`, `chroma_db/`, `__pycache__/`, `scripts/debug/`, `.claude/`.

### 3. Debug artifacts
- Search for `print(` statements that look like debug output (not in logging or UI rendering).
- Search for `breakpoint()`, `pdb`, `ipdb`, `debugger` references.
- Search for files matching `check_*.py`, `debug_*.py`, `verify_*.py`, `test_results.txt` that are tracked by git.
- Search for TODO/FIXME/HACK/XXX comments.

### 4. Empty or stub files
- Find `.py` files that are empty or contain only imports/pass/docstrings with no real logic.
- Ignore `__init__.py` files (those are legitimately empty).

### 5. .gitignore gaps
- Check if these are covered: `.env`, `*.log`, `.DS_Store`, `Thumbs.db`, `.vscode/`, `.idea/`, `*.egg-info/`, `dist/`, `build/`, `*.bak`, `*.tmp`.
- Check if any currently tracked files should be gitignored (run `git ls-files` and flag anything matching common ignore patterns).
- Suggest additions if gaps are found.

### 6. Stale dependencies
- Cross-reference `requirements.txt` against actual imports in `.py` files.
- Flag packages listed in requirements but never imported.
- Flag packages imported but not in requirements.

## Output

End with a summary table:

| Category | Findings |
|----------|----------|
| Dead imports | N |
| Commented-out code | N |
| Debug artifacts | N |
| Empty files | N |
| .gitignore gaps | N |
| Stale dependencies | N |

Then a one-line verdict: **Clean** or **N items to address**.
