# Portfolio UI Capabilities & Navigation Guide

This document describes every feature, page, and UI element available in Khuong's portfolio.
Use this as the authoritative reference when a user asks "how do I...", "where is...", or "can I...".
If the user's request is addressed here, answer it directly. Do NOT flag it as a workflow concern.

---

## Sidebar (always visible on the left)

The sidebar contains:
- **Profile photo** of Khuong at the top.
- **Name**: Khuong Nguyen
- **Title**: Master CS @ UVA
- **Subtitle**: Research Interest: NLP, LLM, and Trustworthy AI
- **Four social icon links** displayed in a row beneath the subtitle, in this order (left to right):
  1. LinkedIn icon (blue) — links to Khuong's LinkedIn profile
  2. GitHub icon — links to Khuong's GitHub
  3. Email icon (red envelope) — opens a new email to Khuong
  4. Resume icon (address card / contact card symbol) — opens Khuong's resume on Google Drive
- **Navigation links** (below social icons):
  - 🐼 Chat — the main AI chat page (app.py)
  - ✈️ About Me — Khuong's life story with an interactive map
  - 🛋️ Projects — a reading corner with project write-ups
  - 🖼️ Gallery — a scroll-based photo gallery of Khuong's travels
  - 📝 Community Guestbook — a collaborative living document
  - ⚙️ Review Dashboard — admin-only page for reviewing visitor feedback (only visible after logging in as Admin)
- **Reset Conversation** button — clears the entire chat history
- **Admin Login** expander at the bottom of the sidebar — allows entering a password to gain Admin role, which unlocks the Review Dashboard

---

## Chat Page (main page)

- **Header**: "Hey there! Ask me anything about Khuong"
- **Agent Mode selector** — three radio button options at the top:
  - Recursive Language Model (RLM): iterative reasoning agent; default mode.
  - Standard RAG (Vector + Sliding Window): fast, low-token retrieval mode.
  - File-Based Context: loads all raw documents into context; thorough but token-heavy.
- **Feature Bar** — a row of buttons below the mode selector:
  - **Reasoning Mode toggle** (Thinking vs Instant):
    - **🧠 Thinking Mode**: The AI pauses to analyze your intent and ask for clarification if your question is ambiguous.
    - **⚡ Instant Mode**: The AI skips the analysis and generates an answer immediately.
  - **Verify Sources toggle** (appears for RAG and File-Based modes):
    - When ON ("✅ Verify: ON"), the AI highlights phrases in its response that are verbatim matches from source documents. Clicking these highlights opens the document viewer.
- **Chat input box** at the bottom — type any question about Khuong here.
- **Document viewer panel** (right side, only visible when Verify Sources is ON and a user clicks a highlighted phrase):
  - Shows the original source document with the matched phrase highlighted in green.
  - Has a "Verified Source Context (Click to Close)" button to close the panel.
  - For Editors/Admins or guestbook docs: shows a "Propose Change" button to submit an edit suggestion.
- **Edit suggestion panel** (replaces document viewer when "Propose Change" is clicked):
  - A large text area pre-filled with the current document content.
  - "Submit Suggestion" to create a change request.
  - "Cancel" to go back.
- **Workflow Intelligence Consent UI** — if the AI detects a genuine pain point or unimplemented feature request in the user's message, a consent form appears in the chat asking: "Would you like to share this with Khuong as feedback?" Options: Submit, Submit Anonymously, Do not submit.

---

## About Me Page

- An **interactive dark globe/map** at the top built with PyDeck.
  - Cyan dots mark places Khuong has visited; a magenta dot marks his hometown (Vung Tau, Vietnam).
  - Clicking a dot scrolls the page and highlights the corresponding chapter of his life story.
- An **intro video** plays automatically when first visiting the page (can be closed).
  - A "Replay" button appears after the video is closed.
- **Life story narrative** displayed as a timeline of glassmorphism cards, one card per life chapter.
  - Chapters cover: Vietnam origins, New Zealand, Japan, Finland/Europe student life, work in Vietnam, and graduate school in the US.

---

## Projects Page

- A **grid of clickable project cards** (the "reading corner").
  - Each card shows the project title, abstract snippet, and tech tags.
  - Hovering over a card produces a cyan glow effect.
  - Clicking a card navigates to the full project detail view.
- **Project detail view** (after clicking a card):
  - Full markdown content with images embedded.
  - A **Table of Contents** panel on the right side that is fixed/sticky while scrolling.
  - TOC links allow jumping to any section.
  - A "← Back to Projects" button in the sidebar returns to the project list.

---

## Gallery Page

- A **full-screen scroll-based photo gallery** of Khuong's travel photos.
  - Each scroll reveals a new photo with a cinematic clip-path reveal animation.
  - Each photo has a large typographic caption and a subtitle (a quote or short description).
  - A "scroll down" indicator appears at first and fades after the first scroll.
  - The gallery uses a grid background (8×6 tiles) for a magazine-like aesthetic.

---

## Community Guestbook Page

- A **living document** that visitors can collaboratively edit.
- Shows a list of all open edit suggestions (change requests) submitted by visitors.
- To leave a message or suggest an edit:
  1. Go to the Chat page.
  2. Turn on Verify Sources.
  3. Ask the AI about the guestbook (e.g. "show me the guestbook").
  4. Click the highlighted text in the AI response to open the source document viewer.
  5. Click "Propose Change" to open the editor and submit a suggestion.
- Admins can Approve & Apply or Reject suggestions directly from the Guestbook page.

---

## Admin / Review Dashboard Page

- Only accessible after logging in as Admin via the Admin Login expander in the sidebar.
- Shows three tabs:
  - **Unresolved Concerns**: feedback submitted by visitors, grouped by concern category (e.g., feature request, bug report). Each concern shows the original quote, workflow stage, root cause, and tool match. Admin can mark concerns as resolved or generate a backlog candidate.
  - **Backlog Candidates**: AI-generated draft opportunity tickets based on clusters of visitor concerns. Shows title, problem, impact, risk, root causes, suggested MVP, and acceptance criteria.
  - **Metrics**: total concerns captured, number unresolved, and resolution rate percentage.

---

## What Is NOT Currently Supported

The following capabilities do NOT currently exist and would be valid feature requests:
- Dark mode toggle (it follows the system/browser preference automatically)
- Downloading a PDF version of any project write-up
- A search bar to filter projects by keyword
- Commenting directly on a project page
- A notification system when a guestbook suggestion is approved
- Any real-time collaboration feature
