# Engines (`/engines`)

This directory is the parent folder for all core, specialized processing logic in the portfolio. By centralizing "Heavy Lifting" modules here, the architecture remains modular and extensible.

The `/engines` structure is designed to host future specialized modules without cluttering the root directory. This includes potential additions like:
- **`SearchEngine`**: For advanced keyword or hybrid search.
- **`EvaluationEngine`**: For automated RAG scoring and fact-checking.

---

## The Trace Engine (`trace_engine.py`)

Explainability layer of the portfolio. Its mission is to prove that every word the AI speaks is grounded in the owner's actual history and data. It achieves this through a high-precision, multi-step verification pipeline.

### 1. The Multi-Format Corpus Pipeline (`load_corpus`)
The engine performs a recursive sweep of the `/data` directory to build a comprehensive in-memory knowledge base.
- **Universal Support**: It handles `.txt`, `.md`, `.pdf` (using `PyPDF2`), and `.docx` (using `docx`) natively.
- **Normalization Strategy**: The `clean_extracted_text` helper strips newlines and collapses whitespace. This ensures that the matching algorithm isn't tripped up by the erratic formatting common in PDF and Word exports.
- **Relative Path Identity**: Files are identified by their relative paths (e.g., `projects/grace.md`) to resolve naming collisions across subdirectories.

### 2. The Verification Algorithm (`find_maximal_matches`)
The engine implements a **Greedy Maximal Exact Match (MEM)** algorithm. It doesn't just look for keywords; it looks for the longest possible sequences of verbatim text shared between the AI's answer and the source files.

**How it works:**
- **Sliding Execution Window**: The algorithm iterates through every character of the AI response.
- **Maximum Lookahead (400 Chars)**: To maintain performance, the engine only attempts to find matches up to 400 characters long per window.
- **Iterative Substring Expansion**: For every starting position, it incrementally builds a substring and checks its existence across the *entire* corpus. It keeps growing the match until nothing in the database contains that specific sequence.
- **Word Boundary Heuristics**: To ensure high-quality highlights, the engine uses an `isalnum()` check to prefer matches that start at the beginning of words rather than in the middle.
- **Length Filtering**: A `min_len` threshold (default: 15 characters) prevents the engine from highlighting trivial filler words or short common phrases.

### 3. Frontend Interactivity
The Trace Engine doesn't just find matches; it annotates them for the UI.
- **HTML Annotation**: Matches are wrapped in `<a>` tags with a custom class `verbatim-match`.
- **Encoded Payload**: The file source and the exact URI-encoded match text are embedded directly into the tag's `id` (format: `source:::encoded_text`). 
- **The Result**: This allows the Streamlit frontend to catch click events on phrases and immediately open the corresponding source file at the exact matching location.

### 4. Trade-off:

The algorithm is O(N × M × L) in the worst case (response length × documents × lookahead of 400 chars). For a portfolio-sized corpus this is fine; for a million-document RAG system this would need a suffix array or an approximate matcher.

## TODO

### Trace Engine Isolation
Currently, the Trace Engine scans the full string returned by an agent. If an agent prepends a system note (e.g., the "Low Confidence" warning in Vector RAG), the engine attempts to verify the words in that note against the corpus.
- **Problem**: This leads to confusing UI highlights on words like "information" or "confidence" inside the disclaimer itself.
- **Fix**: Refactor the `.completion()` return signature across all agents to separate the **claim text** (which should be traced) from the **meta note** (which should be displayed as plain text).

