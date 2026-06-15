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

Example:
```
## Task 1: Slow Server Response (TTFB)
1. What's the target TTFB? (e.g., under 600ms, under 1s?)
2. Should lazy loading use a loading skeleton or spinner?
3. Are there specific resources you know are slow to init?

## Task 2: Layout Shift (CLS)
4. Target CLS score? (e.g., under 0.1?)
5. Should we fix all pages or just the main page?
```

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

Report the result as an independence matrix and recommend one of three workflows:

### Recommendation: Serial
When most or all tasks have conflicts.
```
### Independence Matrix
| | Task 1 | Task 2 | Task 3 |
|---|---|---|---|
| Task 1 | - | CONFLICT: both touch app.py | CONFLICT: shared styles.py |
| Task 2 | CONFLICT | - | CONFLICT: shared state keys |
| Task 3 | CONFLICT | CONFLICT | - |

### Recommendation: Serial
All tasks share files. Work sequentially.

Suggested order:
1. Task 1 — foundational, changes load timing
2. Task 3 — depends on stable load timing
3. Task 2 — most isolated

Each task gets its own branch and PR.
```

### Recommendation: Parallel
When all tasks are fully independent.
```
### Recommendation: Parallel
All tasks touch separate files with no shared state.

Each task gets its own git worktree and branch.
Define shared interfaces before splitting:
- [list any contracts between tasks]
```

### Recommendation: Hybrid
When some tasks are independent but others conflict. Group conflicting tasks into serial chains, run independent groups in parallel.
```
### Independence Matrix
| | Task 1 | Task 2 | Task 3 | Task 4 |
|---|---|---|---|---|
| Task 1 | - | CONFLICT | OK | OK |
| Task 2 | CONFLICT | - | OK | OK |
| Task 3 | OK | OK | - | CONFLICT |
| Task 4 | OK | OK | CONFLICT | - |

### Recommendation: Hybrid
Two independent groups with internal dependencies.

Group A (worktree 1): Task 1 → Task 2 (serial, share app.py)
Group B (worktree 2): Task 3 → Task 4 (serial, share state keys)

Groups A and B run in parallel — no shared files between groups.
```

## Step 5: Confirm and start

Present the SPEC.md and workflow recommendation to the developer. Wait for approval before any implementation.

Once approved, create a journal file for each task: `JOURNAL-<branch-name>.md` in the project root. Initialize it with the task name, branch, SPEC reference, and story checklist. See CLAUDE.md "Task Journal" for the format and rules.

---

## Execution: Serial

```
main (up to date)
  │
  git checkout -b feat/task-1
  │  implement (TDD) → commit per story
  │  /conform → /preflight → /inspect
  │  git push -u origin feat/task-1
  │  create PR #1 → report URL to dev
  │  ← dev reviews + merges PR #1
  │
  git checkout main && git pull
  │
  git checkout -b feat/task-2
  │  implement → ship checklist → PR #2
  │  ← dev reviews + merges PR #2
  │
  (repeat per task)
```

Each task starts from a fresh, up-to-date main. Never stack branches.

## Execution: Parallel

```
main (up to date)
  │
  ── Branch out ──────────────────────────────────
  git worktree add ../task-1 -b feat/task-1
  git worktree add ../task-2 -b feat/task-2
  git worktree add ../task-3 -b feat/task-3

  ── Implement (each agent in its worktree) ──────
  Each agent: TDD → implement → /conform → /preflight → /inspect → push

  ── Stage 1: Test each worktree individually ────
  cd ../task-1 → streamlit run app.py → manual test
  cd ../task-2 → manual test
  cd ../task-3 → manual test
  (catches bugs within each task's scope)

  ── Stage 2: Integration test ───────────────────
  git checkout main
  git checkout -b test/integration        ← throwaway, never pushed
  git merge feat/task-1
  git merge feat/task-2
  git merge feat/task-3
  streamlit run app.py → test everything together
  (catches cross-task conflicts)

  ── Stage 3: Create PRs (1 per task) ────────────
  Each feature branch creates its own PR against main:
    PR #1: feat/task-1 → main
    PR #2: feat/task-2 → main
    PR #3: feat/task-3 → main
  Report all PR URLs with recommended merge order.

  ── Stage 4: Merge in dependency order ──────────
  Dev reviews + merges PR #1 (most foundational)
  Rebase feat/task-2 onto updated main → retest → dev merges PR #2
  Rebase feat/task-3 onto updated main → retest → dev merges PR #3

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

  ── Implement groups in parallel ────────────────
  Group A worktree:
    Task 1: implement → commit → ship checklist
    git checkout -b feat/group-a-task-2   ← branch from task-1
    Task 2: implement → commit → ship checklist

  Group B worktree:
    Task 3: implement → commit → ship checklist
    git checkout -b feat/group-b-task-4   ← branch from task-3
    Task 4: implement → commit → ship checklist

  ── Stage 1: Test each group's final branch ─────
  cd ../group-a → streamlit run app.py → manual test
  cd ../group-b → manual test

  ── Stage 2: Integration test ───────────────────
  git checkout -b test/integration        ← throwaway
  git merge feat/group-a-task-2           ← tip of group A chain
  git merge feat/group-b-task-4           ← tip of group B chain
  streamlit run app.py → test everything together

  ── Stage 3: Create PRs ────────────────────────
  Within each group, create 1 PR per task (not 1 per group):
    PR #1: feat/group-a-task-1 → main
    PR #2: feat/group-a-task-2 → main (after PR #1 merges)
    PR #3: feat/group-b-task-3 → main
    PR #4: feat/group-b-task-4 → main (after PR #3 merges)

  ── Stage 4: Merge ──────────────────────────────
  Merge the most foundational group first:
    merge PR #1 → rebase PR #2 → retest → merge PR #2
    merge PR #3 → rebase PR #4 → retest → merge PR #4
  (groups can interleave if they don't conflict)

  ── Stage 5: Cleanup ────────────────────────────
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
- Never push or PR the `test/integration` branch — it's local and throwaway
- If the dev overrides the recommendation (e.g., forces parallel on conflicting tasks), warn about the specific conflicts but proceed if they insist
