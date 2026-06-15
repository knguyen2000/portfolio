# /inspect

Browser-level check of the running app using chrome-devtools MCP. Catches issues that code analysis and tests cannot: rendering problems, console errors, network failures, and performance regressions.

## Modes

`/inspect` runs in **light** mode by default. Use `/inspect full` for the complete suite.

| Mode | When to use | Tool calls |
|------|-------------|------------|
| **Light** (default) | After every implementation cycle | ~10-12 |
| **Full** | Before first PR, after UI-heavy changes, or when dev requests | ~25-30 |

## Prerequisites

- App must be running (`streamlit run app.py`)
- Chrome DevTools MCP must be connected

If the app is not running, start it first and wait for it to be ready.

---

## Light Mode (default)

### 1. Page load — changed pages + home

Identify which pages were affected by recent changes (check `git diff --name-only`). Always include Home (`/`). Navigate to each affected page:
- Check for console errors (`list_console_messages`) — flag errors and warnings
- Check for failed network requests (`list_network_requests`) — flag 4xx/5xx
- Take a screenshot of the primary changed page only (not every page)

### 2. Console error triage

Categorize all errors found:
- **Blocking** — JavaScript errors, uncaught exceptions, React/Streamlit errors
- **Warning** — deprecation notices, minor warnings
- **Ignorable** — third-party analytics, browser extension noise

### 3. Interactive smoke test

On the main page:
- Type a short test query in the chat input
- Verify a response appears (or loading indicator shows)
- Check that no console errors appeared during the interaction

### Light Mode Output

```
## Page Load Results
| Page | Status | Console Errors | Network Failures |
|------|--------|---------------|-----------------|
| Home | OK/Fail | N | N |
| [changed page] | OK/Fail | N | N |

## Console Errors (if any)
- [Blocking] error description (page)

## Interactive Test
- Chat input: OK/Fail
- Response received: OK/Fail
```

Verdict: **App looks good** or **N issues found**.

---

## Full Mode (`/inspect full`)

Runs everything in light mode, plus the following additional checks.

### 4. Full page load — all pages

Navigate to every page not already checked in light mode:
- Home / Chat (`/`)
- About (`/about`)
- Projects (`/projects`)
- Gallery (`/gallery`)
- Availability (`/availability`)
- Guestbook (`/guestbook`)
- Feedback Dashboard (`/feedback_dashboard`)

For each: screenshot, console errors, network failures, verify content renders.

### 5. Lighthouse audit

Run a Lighthouse audit on the main page (`/`):
- Performance score
- Accessibility score
- Best Practices score
- Flag any score below 70 as a concern

### 6. Performance trace

Run a performance trace on the main page:
- Start trace → interact with the page (type a short query, wait for response) → stop trace
- Analyze the trace for:
  - Long tasks (>50ms)
  - Layout shifts
  - Slow network requests (>3s)

### 7. Responsive check

Test at three viewport sizes using `emulate` or `resize_page`:

| Device | Width | Height |
|--------|-------|--------|
| Mobile | 375px | 812px |
| Tablet | 768px | 1024px |
| Desktop | 1440px | 900px |

For each viewport, navigate to Home (`/`) and About (`/about`):
- Take a screenshot
- Check for horizontal overflow
- Check for overlapping elements or unreadable text
- Check that navigation/sidebar is usable
- Check that interactive elements are tappable at mobile size

### Full Mode Output

All light mode output, plus:

```
## Lighthouse Scores
| Metric | Score |
|--------|-------|
| Performance | N |
| Accessibility | N |
| Best Practices | N |

## Performance Concerns (if any)
- Long task: Nms on page X
- Slow request: Nms to endpoint Y

## Responsive Check
| Viewport | Page | Status | Issues |
|----------|------|--------|--------|
| Mobile (375px) | Home | OK/Fail | overflow, overlap, etc. |
| Tablet (768px) | Home | OK/Fail | ... |
| Desktop (1440px) | Home | OK/Fail | ... |
```

Verdict: **App looks good** or **N issues found**.
