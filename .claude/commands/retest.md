# /retest

Re-validate a fix after manual testing revealed an issue. Enforces test integrity: existing tests are never modified or deleted.

## Context

This command is used when:
- Feature A was implemented with TDD (tests written, code passes)
- Manual testing revealed a bug or edge case
- Claude fixed the bug in the source code
- Now we need to verify the fix without corrupting the original test suite

## Steps

1. **Identify what changed.** Run `git diff` to see what source files were modified for the fix. Note which test files already exist for the affected modules.

2. **Classify the fix.**
   - **Existing story** — the fix addresses behavior already covered by existing tests (e.g., an off-by-one, a missed edge in an existing flow). Skip to step 4.
   - **New story** — the fix addresses behavior NOT covered by any existing test (e.g., a new edge case, a new input type, a newly discovered interaction). Go to step 3.

3. **Append new test cases (new story only).**
   - Open the relevant test file.
   - **APPEND new test functions at the end of the file.** Do not modify, reorder, or delete any existing lines.
   - Each new test must have a clear name describing the edge case or story it covers.
   - If no test file exists for the module, create a new one following the project's test naming convention (`tests/test_<module>.py`).

4. **Run the full test suite.** Run `pytest` with no file filters — all tests must pass, not just the new ones.

5. **If any test fails:**
   - Do NOT modify the failing test.
   - The failure means the fix is incomplete or introduced a regression. Fix the **source code**, not the test.
   - Return to step 4.

6. **Verify conformance.** Run a quick pattern check on the changed source files:
   - Does the fix follow the same naming, import, and error handling patterns as neighboring code?
   - If existing code was modified: was the change minimal? Are callers tested?
   - If the fix introduced new functions: is there a test for each?
   - If any conformance issue is found, fix it before reporting results.

7. **Report results.** Show:
   - Which source files were fixed
   - Whether new test cases were added (list them by name)
   - Conformance status of the fix
   - Full pytest output summary
   - One-line verdict: **All tests pass** or **N failures remain**

## Rules

- **Default: never delete, rename, or modify existing test lines.** Not even whitespace or comments.
- **Exception:** If a test asserts behavior that the bugfix *intentionally and correctly* changes (e.g., the old assertion encoded the bug), explain why the test is wrong and get explicit user approval before modifying it. Show the old assertion, the new assertion, and why the new behavior is correct.
- **Never use `--no-verify` or skip hooks.**
- If uncertain whether a test is wrong or the fix is incomplete, stop and ask the user.
