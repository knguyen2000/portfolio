# /kickoff

Intake raw tasks from the backlog, clarify requirements, generate a SPEC.md, and recommend a workflow.

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

Once all gaps are filled, generate a proper `SPEC.md` following the template. Include:
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

Report the result:

```
## Workflow Recommendation

### Independence Matrix
| | Task 1 | Task 2 | Task 3 |
|---|---|---|---|
| Task 1 | - | CONFLICT: both touch app.py | OK |
| Task 2 | CONFLICT | - | OK |
| Task 3 | OK | OK | - |

### Recommendation: Serial
Tasks 1 and 2 share app.py and styles.py. Parallel execution would cause merge conflicts.

Suggested order:
1. Task 1 (TTFB) — foundational, changes load timing for everything else
2. Task 2 (CLS) — depends on stable load timing from Task 1
3. Task 3 (Render chain) — most isolated, can go last

Each task gets its own branch and PR.
```

Or if independent:

```
### Recommendation: Parallel
All tasks touch separate files with no shared state.

Each task gets its own git worktree and branch.
Define shared interfaces before splitting:
- [list any contracts between tasks]
```

## Step 5: Confirm and start

Present the SPEC.md and workflow recommendation to the developer. Wait for approval.

Once approved:
- **Serial**: Start with the first task. Follow TDD. Commit per story. Run the shipping checklist (`/conform` → `/preflight` → `/inspect`) before creating each PR.
- **Parallel**: Create worktrees for each task. Start each with its own SPEC section. Each finishes independently. Merge in the recommended order, rebasing and re-testing between each merge.

## Rules

- Never assume missing information — always ask
- Never start implementing before the dev approves the SPEC and workflow
- Never skip the independence analysis, even if the dev says "just do them in parallel"
- If the dev overrides the recommendation (e.g., forces parallel on conflicting tasks), warn about the specific conflicts but proceed if they insist
