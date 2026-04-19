# Application Data (`/data`)

This directory serves as the static "database" for the portfolio application. Because Streamlit applications are entirely stateless in production, everything the UI renders or the AI learns must be read from these flat files when the app boots.

## Directory Structure

### 1. The Knowledge Base (Text Files)
Files like `my_life.txt`, `how_it_works.txt` are my initial design choice, but then I switch to markdown as it's easier to format
- When the application starts, `trace_engine.py` sweeps this directory, reads these exact text files, and builds a strict corpus.
- If you want to teach the AI a new skill you learned or a new job you got, simply write it down in plain English inside `my_life.txt`. Do not put it in the Python code.

### 2. The Project Catalog (`/projects`)
This subdirectory dynamically fuels the **Projects** page (`pages/projects.py`).
- **Markdown Files (`*.md`)**: Every file here represents one project card in the UI (e.g., `adaptive_rag.md`, `long_context.md`). 
- **Dynamic Loading:** You do not need to update any Python code when you add a new project. Just drop a properly formatted `.md` file in this folder (ensuring it contains `# Title`, `**Tags:**`, etc.) and the UI will parse and render it automatically.
- **Project Assets (`/projects/images/`)**: Any images or diagrams you reference locally inside those markdown files belong here.

### 3. The Summary Cloud (`/summaries`)
This directory contains high-level, condensed versions of the knowledge base.
- **Purpose**: Primarily used by the **File-Based Agent** in "Router Mode" to quickly scan the entire portfolio without hitting LLM context limits.
- **Current Limitation**: This is a manually maintained directory. If you update `my_life.txt`, you must also update `summaries/my_life.txt` to keep the librarian agent accurate.

By separating the raw text content into `/data` and the display logic into `/pages`, we treat content like a headless CMS. Non-technical users can entirely rewrite the biography and add new projects simply by dragging and dropping text files into this folder without risking crashing the Python runtime.

---

## TODO: 

### Content Synchronization
Currently, the dual-structure of raw data and summaries requires manual double-entry.
- [ ] **Automated Summarizer**: Implement a script (or a background task in `app.py`) that detects changes in root `/data` or `/projects` and automatically regenerates the corresponding files in `/summaries` using the Gemini API.

### Change all txt to md