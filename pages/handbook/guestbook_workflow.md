# Docs-as-Code Guestbook Workflow

The Community Guestbook feature implements a "docs-as-code" workflow directly inside the portfolio's Streamlit application. It allows visitors to propose edits to public documents (like the Guestbook) and gives the portfolio owner an interface to review, diff, and merge these changes into the RAG knowledge base.

## Architecture & Design Choices

### 1. Persistence via SQLite
**Choice**: `sqlite3` was chosen to track `change_requests`, `document_versions`, and `audit_logs`.
**Reasoning**: It is built into Python standard library, requiring no external docker containers or cloud configuration. It provides ACID compliance for tracking change request statuses (pending, approved, rejected).

### 2. Python-Native HTML Diffing
**Choice**: Used Python's standard `difflib.HtmlDiff()` instead of integrating an external JavaScript diff viewer (like Monaco Diff Editor).
**Reasoning**: Injecting massive JS dependencies into Streamlit can be unstable and slow. `difflib` reliably generates static side-by-side HTML tables with red/green highlighting that can be safely embedded using `st.components.v1.html()`.

### 3. Role-Based Access Control
**Choice**: Admin privileges are gated via a simple `st.secrets` password check in an expander, rather than a full user management system.
**Reasoning**: Since this is a personal portfolio, the owner is the only Admin. A heavyweight auth system (Auth0, NextAuth) is overkill. The simple expander successfully prevents unauthorized change request merges.

### 4. Incremental Indexing Integration
**Choice**: When a change request is merged, the raw file is modified on disk. The RAG vector database uses a per-file MD5 hash check (`corpus_fingerprint`).
**Reasoning**: Instead of blowing away the entire ChromaDB collection and re-embedding everything on every merge, the VectorEngine detects exactly which file changed and only re-indexes that specific file. This significantly cuts down on embedding API costs and latency.

## Core Methods & Functions Implemented

To ensure a complete overview, here is the breakdown of the specific methods and functions implemented across the codebase to support this workflow:

### Database & State (`utils/guestbook_db.py`)
- `get_connection()`: Establishes a connection to the local SQLite database.
- `init_db()`: Initializes the schema (tables: `documents`, `document_versions`, `change_requests`, `audit_log`).
- `create_change_request(document_id, base_content, proposed_content, user_id)`: Inserts a new change request into the database with a 'pending' status.
- `get_open_change_requests()`: Retrieves all change requests currently awaiting review.
- `update_change_request_status(request_id, status, user_id)`: Transitions a request to 'merged' or 'rejected' and logs the action.
- `log_audit(action, user_id, document_id)`: Simple audit trailing for critical DB operations.

### UI Components (`components/`)
- `render_editor_panel(docs)` (in `editor_panel.py`): Renders the `st.text_area` pre-filled with the raw markdown of the selected file, allowing Editors/Admins to submit a new suggestion.
- `generate_html_diff(base_content, proposed_content)` (in `guestbook.py`): Wraps Python's `difflib.HtmlDiff` to generate a side-by-side visual diff.
- `render_guestbook(docs)` (in `guestbook.py`): Iterates through open requests, displays the HTML diff, and provides the 'Approve & Merge' or 'Reject' action buttons.

---

## Trade-offs

- **Ephemeral Cloud Filesystems**: When deployed to platforms like Streamlit Community Cloud or Heroku, the local disk is ephemeral. If the app goes to sleep or reboots, the SQLite database and the modifications to `data/` will be wiped out. 
- **Rigid Diff Styling**: While `difflib` works out of the box, its styling is a bit dated and lacks the dynamic line-wrapping and syntax highlighting found in modern IDEs.
- **Merge Conflicts**: The current system overwrites the base file upon merge. If two visitors propose changes to the same file simultaneously, the second merge will silently overwrite the first one's context.

---

## TODOs

- [ ] **Cloud Persistence**: Migrate `guestbook.db` to a managed cloud database (e.g., Supabase or Firebase) to ensure suggestion histories survive server restarts.
- [ ] **Git Integration**: Instead of modifying the local disk, use the GitHub API (`PyGithub`) so that clicking "Approve & Merge" actually pushes a Git commit to the repository.
- [ ] **Rich Text Editor**: Replace the plain `st.text_area` with `streamlit-code-editor` or `streamlit-monaco` to give users a better Markdown writing experience when proposing changes.
- [ ] **Concurrency Handling**: Implement a basic check before merging to ensure the `base_content` of the change request matches the current live file, throwing a "Merge Conflict" error if they differ.
