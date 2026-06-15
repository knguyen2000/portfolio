# /hotfix

Fast on-ramp for urgent or trivial fixes. Same quality bar as `/kickoff`, but skips multi-task ceremony (independence analysis, workflow recommendation, journal).

Use when the fix is:
- A single task (not a batch)
- Clearly scoped (you can describe it in one sentence)
- Unlikely to need session recovery (fits in one session)

If the fix turns out to be larger than expected (>5 files, new behavior emerging, multiple stories), stop and switch to `/kickoff`.

## Step 1: Sync main

```
git checkout main
git pull
```

If main is dirty, stop and ask the dev to resolve first.

## Step 2: Understand the fix

Ask the developer to describe the fix in one sentence. If they haven't already, ask:
- What's broken or needs changing?
- What's the expected behavior after the fix?

## Step 3: Generate a minimal SPEC

Create `SPEC.md` with a single story. Use the template (`.claude/templates/SPEC.md`) but keep it tight:

```markdown
# SPEC: [Fix Name]

## Goal
[One sentence.]

## User Stories

### Story 1: [Title]

**Description:** [What needs to happen.]

**Acceptance criteria:**
- [ ] [Verifiable criterion]
- [ ] Tests pass
- [ ] Lint passes

**Files likely touched:** [list files]

## Modification Risk Assessment

| Story | Approach | Modified Lines | Affected Features |
|-------|----------|---------------|-------------------|
| US-1 | [Extend only / Modify + extend] | [count] | [list] |

[If modifying existing code, fill in the full assessment per the template.]

## Out of Scope
- [Anything adjacent that this fix intentionally does NOT address]
```

Present to the dev for approval. Wait before implementing.

## Step 4: Branch and implement

```
git checkout -b fix/<short-slug>
```

Follow the standard per-task cycle:

```
implement (TDD, extend-first)
  │
  /inspect (light)
  │  fix any issues, commit fixes
  │
  ← dev manual tests
  │
  if dev found bugs:
  │  /retest → fix → /inspect again
  │
  /conform (on committed diff)
  │
  /preflight (full gate — all checks including regression scope)
  │
  done — ready for PR
```

Commit per meaningful unit (usually one commit for a hotfix, but split if the fix has a distinct refactor step).

## Step 5: PR

Read `SPEC.md` for PR description context, then delete it.

Create PR against main using the standard template:

```
## Summary
- [what was broken and why]

## Changes
- [files changed]

## Test Plan
- [ ] [how to verify the fix]
- [ ] [regression checks for affected features]
```

Report PR URL. Dev reviews and merges.

## Step 6: Post-merge verification

After the dev merges the PR, run `/postmerge` to verify main is healthy. This is especially important for hotfixes that modified existing code — the fix may interact with recent changes on main that weren't present when the branch was created.

## What hotfix does NOT skip

- SPEC (minimal single-story version) — forces you to think before coding
- TDD — failing test first, then fix
- Extend-first policy — impact analysis if modifying existing code
- `/inspect` (light) — catches rendering/console regressions
- `/conform` — pattern compliance
- `/preflight` — full quality gate including regression scope
- Dev approval before merge

## What hotfix skips

- Independence analysis (single task, nothing to compare)
- Workflow recommendation (always serial, single branch)
- Journal file (should fit in one session; if it doesn't, switch to `/kickoff`)
- Multi-story SPEC structure (one story only)
