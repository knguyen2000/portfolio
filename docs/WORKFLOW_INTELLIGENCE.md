# Workflow Intelligence System

A passive feedback loop built into the portfolio chatbot. It listens to every visitor turn, classifies whether the user is expressing an unmet need, and — with consent — captures it as a structured concern for Khuong to review later.

---

## Why It Exists

Most portfolio feedback dies in inboxes or never gets sent at all. Workflow Intelligence turns casual chat messages into an actionable product backlog by detecting pain points in real time without interrupting the conversation.

---

## Architecture Overview

```
Chat Turn
    │
    ▼
agent_dispatch.py
    │  generate_answer() runs the chosen agent normally
    │
    ├─► [After answer is ready]
    │       detect_concern(client, user_message)
    │           │
    │           ├─ loads data/portfolio_capabilities.md (ground truth)
    │           └─ calls Gemini → returns concern JSON
    │
    ├─► if is_concern == True
    │       session_state.pending_concern = concern_data
    │
    ▼
append_response() → st.rerun()
    │
    ▼
render_chat_history()   (chat_renderer.py)
    │
    ├─► if pending_concern:
    │       render Consent UI form
    │           ├─ Submit          → insert_concern() + rewrite last msg
    │           ├─ Submit Anon     → insert_concern() with role="Anonymous"
    │           └─ Do not submit  → clear pending_concern
    │
    ▼
workflow_db.py  (SQLite at data/db/workflow.db)
    ├─ feedback_concerns table
    ├─ backlog_candidates table
    └─ activity_log table
```

---

## Classification Rules

The concern detector uses `data/portfolio_capabilities.md` as its authoritative guide. Classification follows three rules in order:

| Rule | Condition | Result |
|---|---|---|
| 1 | Feature exists in capabilities guide | `is_concern = false` — answer the question normally |
| 2 | Feature listed under "What Is NOT Currently Supported" — even if phrased as "how do I…" | `is_concern = true`, category = `feature request` |
| 3 | Explicit complaint, bug report, or trust concern | `is_concern = true` |

Normal questions about Khuong's background, skills, or projects are never flagged.

### Concern Categories

| Category | Example |
|---|---|
| `feature request` | "How do I toggle dark mode?" |
| `workflow pain` | "The chat is really slow" |
| `trust concern` | "Did you actually write all this code?" |
| `bug report` | "The gallery doesn't load on mobile" |
| `tool confusion` | "What does Verify Sources do?" |

---

## Data Schema

### `feedback_concerns`

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (UUID) | Primary key |
| `original_quote` | TEXT | User's exact message |
| `concern_category` | TEXT | Category from classification |
| `workflow_stage` | TEXT | Stage of the user's journey |
| `affected_role` | TEXT | Visitor / Recruiter / Anonymous Visitor |
| `likely_root_cause` | TEXT | Root cause from classifier |
| `existing_tool_match` | TEXT | Partial solution if any |
| `status` | TEXT | `unresolved` → `solved` \| `discarded` \| `accepted_to_backlog` |
| `created_at` | TEXT (ISO) | Submission timestamp |

### `backlog_candidates`

AI-generated structured tickets linked to one or more concerns. Fields: `title`, `problem`, `original_evidence`, `workflow_stage`, `user_group`, `existing_tool_check`, `hypothesized_root_causes`, `impact`, `risk`, `suggested_validation`, `potential_mvp`, `acceptance_criteria`, `status`, `created_at`.

### `activity_log`

Immutable record of every status change. Fields: `id`, `action`, `concern_id`, `note`, `timestamp`. Joined with `feedback_concerns` in the Audit Log tab for full context.

---

## Admin Review Dashboard (`pages/feedback_dashboard.py`)

Accessible only after Admin login via the sidebar expander.

### Tabs

| Tab | Description |
|---|---|
| **Unresolved Concerns** | Concerns grouped by category. Checkbox each one you want to batch into a backlog ticket. "Mark Solved" and "Discard" (with optional reason) change the status immediately. |
| **Backlog Candidates** | AI-drafted product tickets. Each ticket shows impact, risk, suggested validation, potential MVP, and acceptance criteria. |
| **Metrics** | Live counters: Total Captured, Unresolved, Solved, Discarded, In Backlog. Category breakdown below. |
| **Audit Log** | Reverse-chronological feed of every action taken — who did what, when, with the original quote and note. |

### Backlog Generation Flow

1. Check one or more concern checkboxes in the Unresolved Concerns tab.
2. Click **"🧠 Generate Backlog Candidate (N selected)"**.
3. `generate_backlog_candidate(client, selected_items)` sends all quotes to Gemini.
4. The returned JSON is saved via `insert_backlog_candidate()`.
5. Each selected concern is automatically transitioned to `accepted_to_backlog` and linked by backlog ID in the audit log.

---

## Extending the System

### Adding a new concern category
Edit the `category` field in `detect_concern()`'s prompt inside `workflow_intelligence.py`. No schema changes needed — the category is stored as free text.

### Adding a new portfolio feature visitors can ask about
Update `data/portfolio_capabilities.md`. The classifier loads this file at runtime, so no code changes are needed.

### Adding a new unsupported feature to track
Add it to the "What Is NOT Currently Supported" section in `data/portfolio_capabilities.md`. The classifier will automatically start flagging implicit requests for it.

### Keeping the chat fast
`detect_concern` runs synchronously after the main response is generated, before `append_response`. If latency becomes noticeable at scale, move it to a `threading.Thread` call and store results in a temporary session key.

---

## File Map

| File | Role |
|---|---|
| `components/workflow_intelligence.py` | LLM classifier + backlog generator |
| `utils/workflow_db.py` | SQLite persistence layer (3 tables) |
| `pages/feedback_dashboard.py` | Admin dashboard UI (4 tabs) |
| `components/agent_dispatch.py` | Integration point — runs classifier post-answer |
| `components/chat_renderer.py` | Renders the consent UI form |
| `data/portfolio_capabilities.md` | Ground truth for feature classification |
| `data/db/workflow.db` | SQLite database file (auto-created on first boot) |
