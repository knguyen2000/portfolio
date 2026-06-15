# SPEC: [Feature/Fix Name]

## Goal

[One sentence: what this achieves and why it matters.]

## User Stories

### Story 1: [Title]

**Description:** As a [user type], I want [capability] so that [benefit].

**Acceptance criteria:**
- [ ] [Verifiable criterion — not vague like "works correctly"]
- [ ] [Another criterion]
- [ ] Tests pass
- [ ] Typecheck/lint passes

**Files likely touched:** [list files — used for independence analysis]

### Story 2: [Title]

[Same structure. Add as many stories as needed.]

## Technical Notes

- [Constraints, API details, rate limits, compatibility requirements]
- [Dependencies on external services or other features]

## Modification Risk Assessment

For each story, classify its approach:

| Story | Approach | Modified Lines | Affected Features |
|-------|----------|---------------|-------------------|
| US-1 | Extend only | 0 | — |
| US-2 | Modify + extend | ~5 lines in `engines/trace_engine.py` | Trace display, source citations |

For any story that modifies existing code:
- **What is being modified and why extending isn't possible:** [explanation]
- **Callers/dependents of modified code:** [list files and functions]
- **Regression tests needed:** [list tests that must pass, including any new ones to add]

If all stories are extend-only, write: "All stories use extend-only approach — no existing code modified."

## Out of Scope

- [What this intentionally does NOT cover]

## Phases (large tasks only)

If this task touches 15+ files or introduces new architecture, break stories into phases:

### Phase 1: [Interface/Schema]
Stories: US-1, US-2
Goal: Define contracts before implementation.

### Phase 2: [Implementation]
Stories: US-3, US-4, US-5
Goal: Implement behind the interfaces defined in Phase 1.

### Phase 3: [Integration]
Stories: US-6
Goal: Wire up, remove old code, verify end-to-end.

## Delete This File

When all stories are implemented and tested, this file's content is used for the commit/PR description, then the file is deleted.
