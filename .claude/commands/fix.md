# /fix

Auto-fix all lint issues and format the entire codebase.

## Steps

1. Run `ruff check --fix .` to auto-fix lint issues.
2. Run `ruff format .` to format all files.
3. Run `ruff check .` again to report any remaining issues that need manual fixes.
4. Run `pytest` to verify nothing broke.
5. Show a summary: files changed, issues fixed, issues remaining, test results.
