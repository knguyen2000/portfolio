# /inspect

Final browser-level check of the running app using chrome-devtools MCP. Catches issues that code analysis and tests cannot: rendering problems, console errors, network failures, and performance regressions.

## Prerequisites

- App must be running (`streamlit run app.py`)
- Chrome DevTools MCP must be connected

If the app is not running, start it first and wait for it to be ready.

## Checks

### 1. Page load — all pages

Navigate to each page in the app and verify it loads without errors:
- Home / Chat (`/`)
- About (`/about`)
- Projects (`/projects`)
- Gallery (`/gallery`)
- Availability (`/availability`)
- Guestbook (`/guestbook`)
- Feedback Dashboard (`/feedback_dashboard`)

For each page:
- Take a screenshot
- Check for console errors (`list_console_messages`) — flag any errors or warnings
- Check for failed network requests (`list_network_requests`) — flag any 4xx/5xx responses
- Verify the page renders content (not a blank screen or error page)

### 2. Console errors

After visiting all pages, report all console errors and warnings. Categorize:
- **Blocking** — JavaScript errors, uncaught exceptions, React/Streamlit errors
- **Warning** — deprecation notices, minor warnings
- **Ignorable** — third-party analytics, browser extension noise

### 3. Lighthouse audit

Run a Lighthouse audit on the main page (`/`):
- Performance score
- Accessibility score
- Best Practices score
- Flag any score below 70 as a concern

### 4. Performance trace

Run a performance trace on the main page:
- Start trace → interact with the page (type a short query, wait for response) → stop trace
- Analyze the trace for:
  - Long tasks (>50ms)
  - Layout shifts
  - Slow network requests (>3s)

### 5. Responsive check

Test the app at three viewport sizes using `emulate` or `resize_page`:

| Device | Width | Height |
|--------|-------|--------|
| Mobile | 375px | 812px |
| Tablet | 768px | 1024px |
| Desktop | 1440px | 900px |

For each viewport, navigate to the main page (`/`) and the About page (`/about`) — these have the most layout-sensitive content (chat UI, map, cards).

At each viewport:
- Take a screenshot
- Check for horizontal overflow (content wider than viewport)
- Check for overlapping elements or unreadable text
- Check that navigation/sidebar is usable
- Check that interactive elements (buttons, inputs, dropdowns) are tappable at mobile size

Flag any layout issues with the viewport size and page where they occur.

### 6. Interactive smoke test

On the main page:
- Type a short test query in the chat input
- Verify a response appears (or loading indicator shows)
- Check that no console errors appeared during the interaction

## Output

```
## Page Load Results
| Page | Status | Console Errors | Network Failures |
|------|--------|---------------|-----------------|
| Home | OK/Fail | N | N |
| About | OK/Fail | N | N |
| ... | ... | ... | ... |

## Console Errors (if any)
- [Blocking] error description (page)
- [Warning] warning description (page)

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

## Interactive Test
- Chat input: OK/Fail
- Response received: OK/Fail
```

Then a one-line verdict: **App looks good** or **N issues found**.
