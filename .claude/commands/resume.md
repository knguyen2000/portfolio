# /resume

Recover context and continue work from a previous session using task journals.

## Steps

### 1. Discover active journals

List all `JOURNAL-*.md` files in the project root. For each, read only the **Status** and **Current State** sections (not the full log).

If no journals exist, tell the developer there's nothing to resume and suggest `/kickoff`.

### 2. Present options

If multiple journals exist, show a summary of each:

```
1. JOURNAL-feat-voice-agent.md — Branch: feat/voice-agent
   Status: 3/5 stories done
   Current: Implementing story 4 (audio playback)

2. JOURNAL-fix-calendly-booking.md — Branch: fix/calendly-booking
   Status: 2/2 stories done, pending PR
   Current: Ready for /preflight and PR creation
```

Ask the developer which task to resume. If only one journal exists, proceed automatically.

### 3. Restore branch state

```
git checkout <branch-name>
git status
```

If the branch doesn't exist locally, check remote:
```
git fetch origin
git checkout -b <branch> origin/<branch>
```

If neither exists, warn the developer — the journal may be stale.

### 4. Check if branch needs rebasing

```
git fetch origin
git log HEAD..origin/main --oneline
```

If main has moved (new commits since the branch was created), warn the developer:

```
⚠ Main has N new commits since this branch was created.
Recommend rebasing before continuing to avoid building on stale code:
  git rebase origin/main

This may cause conflicts if the new commits touch files this branch modified.
```

Wait for the dev to decide whether to rebase now or continue as-is. If they rebase, re-run step 5 after the rebase completes.

### 5. Verify current state

- Run `pytest` to check if tests still pass
- Run `ruff check .` for a quick lint scan
- Read the journal's **Current State** and latest **Log** entry

### 6. Present a continuation plan

Based on the journal's "Next" section and remaining unchecked stories in Status, present:

```
## Resuming: [task name]
Branch: feat/xxx

### Completed
- [x] Story 1: ...
- [x] Story 2: ...

### Remaining
- [ ] Story 3: ... (next up)
- [ ] Story 4: ...

### Context from last session
[Current State and last Log entry]

Ready to continue with Story 3?
```

Wait for developer approval before implementing.

## Rules

- Never start implementing without developer confirmation
- If the journal says "blocked" or "waiting on dev," surface that prominently
- If tests fail on checkout, report the failures before proposing to continue — the branch may need fixes from a merged dependency
