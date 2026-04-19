## 1. What Does This Page Do?
`projects.py` creates a dynamic catalog of all your projects. It reads Markdown (`.md`) files from your data folder, generates summary cards on the screen, and lets users click them to read the full project details.

## 2. Dynamic Markdown Parsing

Instead of typing the project details (like Title, Tags, and Abstract) directly into Python code, the app reads files from `data/projects/`. We wrote a custom parser inside `load_projects()` that opens the file, looks for the `# ` symbol for the title, and looks for `**Tags:**` to extract metadata dynamically.

**Why we chose this (Headless CMS pattern):**
We wanted to be able to add a new project just by dropping a `.md` file into a folder, without ever having to touch Python. This makes maintaining the portfolio extremely fast and safe.

**Tradeoff:**
- **Fragility:** Our parser is "naive" (simple). If write a `.md` file but forgets the space after the `#`, or spells `**Tags:**` wrong, the parser will fail to find the title or tags. 
- A safer, heavier approach would be using a database or YAML Frontmatter, but we decided that was overkill for a small personal portfolio.

## 3. Native Markdown Rendering

When a project is clicked, we pass the raw text into `st.markdown()`. Streamlit natively converts Markdown into beautiful HTML, complete with headers and bold text.

**Tradeoff:**
Streamlit's markdown renderer gets very confused if you inject raw HTML strings or complex CSS inside your `.md` files. Therefore, keep your project files pure.

## 4. Deep Links and Click Detectors

Streamlit buttons (`st.button`) require you to manage complex state variables. If you have 20 projects, managing 20 buttons is very difficult.
Instead, we used a third-party library called `st_click_detector`. 
1. We wrap every project card in standard HTML links: `<a href='#' id='project_filename'>`.
2. The click detector listens for that specific HTML click.
3. If clicked, we modify the URL directly using `st.query_params` (adding `?project=filename`).

**Why we chose it:**
This allows "Deep Linking". This means if you copy the URL of your browser while viewing a specific project, you can send that exact link to a recruiter, and the page will automatically boot into that project instead of forcing them to click the menu.

**Tradeoff:**
We depend on `st_click_detector`, which is an external community library. If Streamlit updates and breaks compatibility with this library, the entire project selection grid will break and will need to be rewritten using native Streamlit columns and buttons.

## 5. Auto-Generating Table of Contents

When rendering a long project, we read through the lines and extract anything starting with `#` to build a sidebar Table of Contents. We then calculate a clean "URL Slug" (removing spaces) and embed a hidden HTML anchor (`<a id='clean-slug'></a>`) so you can jump to specific headers.

---

## Maintaining:
If project cards are showing up with missing Titles or Tags, check the `.md` files in `data/projects/`. Ensure they strictly follow the formatting rules. If you want to change the visual look of the cards, update the CSS string injected near the top of the file.
