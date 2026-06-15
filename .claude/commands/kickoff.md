# /kickoff

Intake raw tasks from the backlog, clarify requirements, generate a SPEC.md, and recommend a workflow.

## Prerequisite: Sync main

Before anything else, ensure main is up to date:

```
git checkout main
git pull
```

If there are uncommitted changes on main, stop and ask the dev to resolve them first. Never plan or branch from a stale or dirty main.

All planning happens on main. `SPEC.md` and `TASKS.md` are gitignored — no tracked changes are created during planning.

## Input

The developer pastes raw tasks into `TASKS.md` in the project root. Tasks can be in any format — copied from GitHub Issues, Linear, Jira, Slack, or plain text. The file should indicate how many tasks the dev wants to tackle in this round.

If `TASKS.md` does not exist, ask the developer to create it and paste their tasks.

## Step 0: Size check — redirect to /hotfix if appropriate

Read `TASKS.md`. If the round contains **a single task** that is clearly a small fix (bug, config change, <5 files, one story), suggest: "This looks like a single fix — want to use `/hotfix` instead? Same quality checks, faster on-ramp."

If the dev confirms, stop and run `/hotfix`. If they decline or there are multiple tasks, continue below.

## Step 1: Parse and understand

Read `TASKS.md`. For each task, extract:
- What needs to be done (the goal)
- Any acceptance criteria mentioned
- Any technical constraints or context given
- Dependencies between tasks (explicit or implied)

## Step 2: Identify gaps

For each task, compare against the SPEC template (`.claude/templates/SPEC.md`). Identify what's missing:
- Unclear scope ("improve performance" — which metric? what target?)
- Missing acceptance criteria
- Ambiguous user impact ("better UX" — how specifically?)
- Unknown technical constraints (which files? which APIs? what limits?)
- Unstated dependencies between tasks

**Do NOT assume answers.** Ask the developer to fill every gap. Present questions grouped by task, clearly numbered, so the dev can answer efficiently.

Wait for answers before proceeding.

## Step 3: Generate SPEC.md

Once all gaps are filled, generate a proper `SPEC.md` following the template (`.claude/templates/SPEC.md`). Include:
- Goal (one sentence per task)
- User stories with verifiable acceptance criteria
- "Files likely touched" for each story (scan the codebase to determine this)
- Technical notes and out of scope
- Phases section if any task is large (15+ files)

## Step 4: Independence analysis

For tasks the dev wants to do in this round, run the parallel eligibility check:

```
For each pair of tasks:
  1. Compare "files likely touched" lists — any overlap?
  2. Check for import dependencies — would one task's code import the other's?
  3. Check for shared state — do they both modify session_state keys or config values?
  4. Check for shared UI — do they both modify the same page or component?
```

Report the result as an independence matrix and recommend one of three workflows: **Serial**, **Parallel**, or **Hybrid**.

## Step 5: Confirm and start

Present the SPEC.md and workflow recommendation to the developer. Wait for approval before any implementation.

Once approved, create a journal file for each task: `JOURNAL-<branch-name>.md` in the project root. See CLAUDE.md "Task Journal" for format and rules.

---

## Worktree Setup

Gitignored files (secrets, config) don't exist in new worktrees. After creating any worktree, immediately copy required config:

```
mkdir -p <worktree>/.streamlit
cp .streamlit/secrets.toml <worktree>/.streamlit/secrets.toml
```

Copy any other gitignored config the app needs (`.env`, etc.). Do this BEFORE implementation starts.

Applies to parallel and hybrid workflows only. Serial doesn't use worktrees.

---

## Per-Task Cycle

Every task — regardless of serial, parallel, or hybrid — follows this cycle:

```
implement (TDD, extend-first) → commit per story
  │
  /inspect (light — page loads, console errors, smoke test)
  │  fix any issues found, commit fixes
  │
  ← dev manual tests (business logic, UX, edge cases only —
  │  Claude already verified the app runs and renders)
  │
  if dev found bugs:
  │  /retest → fix → /inspect again (only now, not otherwise)
  │
  /conform (on committed diff — checks patterns and style)
  │  fix any conformance issues, commit fixes
  │
  /preflight (pre-PR gate — all 11+ checks including regression scope)
  │
  done — ready for PR
```

**Ordering:** `/conform` runs on the committed diff (post-commit). `/preflight` runs last as the final gate before PR creation. If `/preflight` fails, fix issues and run `/preflight recheck` to re-run only the failed checks.

**`/inspect` runs in light mode by default.** Use `/inspect full` only before the first PR on a UI-heavy branch or when the dev requests it. `/inspect` only runs a second time if code changed from bugfixes.

**Extend-first implementation:** During TDD, prefer adding new functions/modules over modifying existing code. If modification is needed, follow the Modification Policy in CLAUDE.md — impact analysis, minimal scope, test all affected paths.

---

## Execution: Serial

```
main (up to date)
  │
  git checkout -b feat/task-1
  │  [per-task cycle]
  │  git push -u origin feat/task-1
  │  create PR #1 → report URL to dev
  │  ← dev reviews + merges PR #1
  │
  git checkout main && git pull
  /postmerge — verify main is healthy after merge
  │
  git checkout -b feat/task-2
  │  [per-task cycle]
  │  git push → PR #2
  │  ← dev reviews + merges PR #2
  │
  git checkout main && git pull
  /postmerge
  │
  (repeat per task)
```

Each task starts from a fresh, verified main. Never stack branches. Never start the next task until `/postmerge` confirms main is healthy.

## Execution: Parallel

```
main (up to date)
  │
  ── Branch out ──────────────────────────────────
  git worktree add ../task-1 -b feat/task-1
  git worktree add ../task-2 -b feat/task-2
  git worktree add ../task-3 -b feat/task-3
  + copy gitignored config (see Worktree Setup)

  ── Implement ───────────────────────────────────
  Each agent in its worktree: [per-task cycle]

  ── Stage 1: Dev manual tests each worktree ─────
  (included in per-task cycle above)

  ── Stage 2: Sequential integration test ────────
  Simulate the real merge order on a throwaway branch:

  git checkout main
  git checkout -b test/integration        ← throwaway, never pushed

  Step 1: merge task-1, then test
    git merge feat/task-1
    pytest
    streamlit run app.py → smoke test

  Step 2: merge task-2 on top, then test again
    git merge feat/task-2
    pytest
    streamlit run app.py → smoke test (both task-1 + task-2 features)

  Step 3: merge task-3 on top, then test everything
    git merge feat/task-3
    pytest
    streamlit run app.py → full manual test (all 3 together)
    /inspect (light) — final combined check

  If any step fails, the issue is between that task and the ones
  already merged. Fix on the failing task's branch, then re-run
  the sequential integration from the top.

  ── Stage 3: Create PRs (1 per task) ────────────
  Each feature branch creates its own PR against main:
    PR #1: feat/task-1 → main
    PR #2: feat/task-2 → main
    PR #3: feat/task-3 → main
  Report all PR URLs with recommended merge order.

  ── Stage 4: Merge with post-merge verification ─
  Dev reviews + merges PR #1
    → /postmerge (verify main after PR #1)
    → only proceed to PR #2 after /postmerge passes

  Rebase feat/task-2 onto updated main → retest
  Dev merges PR #2
    → /postmerge (verify main after PR #1 + PR #2)
    → only proceed to PR #3 after /postmerge passes

  Rebase feat/task-3 onto updated main → retest
  Dev merges PR #3
    → /postmerge (final — verify main with all 3 merged)

  ── If rebase conflicts ─────────────────────────
  1. Resolve conflicts in the conflicting branch
  2. Run pytest to verify all tests pass
  3. Run /inspect (light) only if UI files were in the conflict
  4. Amend or add a fixup commit with the resolution
  5. Update the PR — do NOT force-push; push the resolution commit
  6. Dev re-reviews the conflict resolution before merging

  ── Stage 5: Cleanup ────────────────────────────
  git worktree remove ../task-1
  git worktree remove ../task-2
  git worktree remove ../task-3
  git branch -D test/integration
```

## Execution: Hybrid

Combine serial and parallel. Each independent group gets its own worktree. Within a group, tasks run serially.

```
main (up to date)
  │
  ── Branch out (1 worktree per group) ───────────
  git worktree add ../group-a -b feat/group-a-task-1
  git worktree add ../group-b -b feat/group-b-task-3
  + copy gitignored config (see Worktree Setup)

  ── Implement groups in parallel ────────────────
  Group A worktree:
    Task 1: [per-task cycle]
    git checkout -b feat/group-a-task-2   ← branch from task-1
    Task 2: [per-task cycle]

  Group B worktree:
    Task 3: [per-task cycle]
    git checkout -b feat/group-b-task-4   ← branch from task-3
    Task 4: [per-task cycle]

  ── Stage 1: Sequential integration test ────────
  Simulate the real merge order on a throwaway branch:

  git checkout main
  git checkout -b test/integration        ← throwaway, never pushed

  Step 1: merge group A tip, then test
    git merge feat/group-a-task-2
    pytest
    streamlit run app.py → smoke test

  Step 2: merge group B tip on top, then test everything
    git merge feat/group-b-task-4
    pytest
    streamlit run app.py → full manual test (all groups together)
    /inspect (light) — final combined check

  If any step fails, fix on the failing group's branch,
  then re-run the sequential integration from the top.

  ── Stage 2: Create PRs ────────────────────────
  Within each group, create 1 PR per task (not 1 per group):
    PR #1: feat/group-a-task-1 → main
    PR #2: feat/group-a-task-2 → main (after PR #1 merges)
    PR #3: feat/group-b-task-3 → main
    PR #4: feat/group-b-task-4 → main (after PR #3 merges)

  ── Stage 3: Merge with post-merge verification ─
  Merge the most foundational group first:

    merge PR #1 → /postmerge
    rebase PR #2 → retest → merge PR #2 → /postmerge

    merge PR #3 → /postmerge
    rebase PR #4 → retest → merge PR #4 → /postmerge (final)

  (groups can interleave if they don't conflict)
  Never merge the next PR until /postmerge passes on main.

  ── If rebase conflicts ─────────────────────────
  Same protocol as parallel workflow:
  1. Resolve conflicts in the conflicting branch
  2. Run pytest to verify all tests pass
  3. Run /inspect (light) only if UI files were in the conflict
  4. Add a resolution commit (don't force-push)
  5. Dev re-reviews before merging

  ── Stage 4: Cleanup ────────────────────────────
  git worktree remove ../group-a
  git worktree remove ../group-b
  git branch -D test/integration
```

## Rules

- Always `git pull` on main before planning or branching
- Never edit main directly — all work happens on feature branches
- Never assume missing information — always ask the dev
- Never start implementing before the dev approves the SPEC and workflow
- Never skip the independence analysis, even if the dev says "just do them in parallel"
- Never merge PRs without dev approval — Claude creates PRs but dev merges
- Never merge the next PR until `/postmerge` passes on main (all workflows — serial, parallel, and hybrid)
- Never push or PR the `test/integration` branch — it's local and throwaway
- If the dev overrides the recommendation (e.g., forces parallel on conflicting tasks), warn about the specific conflicts but proceed if they insist
- **Extend, don't modify** — when implementing, prefer adding new code over changing existing lines. If modification is unavoidable, follow the Modification Policy in CLAUDE.md (impact analysis, minimal scope, test all affected paths)
