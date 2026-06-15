# /docsync

Audit all folder-level documentation (README.md, DESIGN.md, BEHAVIOR.md) for staleness against actual code.

## Scope

Check every folder in the project that contains a markdown doc file. Do NOT limit to changed files — scan everything.

Folders to check:
- `agents/` and each subfolder (`agents/file_based/`, `agents/vector/`, `agents/rlm/`, `agents/nla/`)
- `engines/`
- `components/`
- `services/`
- `models/`
- `static/`
- Any other non-`env/`, non-`chroma_db/` folder that contains a README.md or DESIGN.md

## For each folder

1. List all `.py` files in the folder.
2. Read the folder's README.md (and DESIGN.md / BEHAVIOR.md if they exist).
3. Compare docs against code:
   - **Missing files** — `.py` files that exist in the folder but are not mentioned in the docs.
   - **Ghost references** — files, classes, or functions described in the docs that no longer exist in the code.
   - **Stale descriptions** — doc describes behavior or interfaces that don't match the current code (e.g., wrong function signature, removed parameter, changed return type).
   - **New public interfaces** — classes or public functions added to existing files but not reflected in docs.

## Output

For each folder with findings, show:

```
## folder/
- MISSING: new_file.py not documented in README.md
- GHOST: README.md references old_file.py which was deleted
- STALE: DESIGN.md says completion() returns (text, tokens) but it now returns (text, tokens, analysis)
- NEW: calendly.py added CalendlyClient class, not in README.md
```

Skip folders with no issues.

End with a summary:

| Folder | Missing | Ghost | Stale | New |
|--------|---------|-------|-------|-----|
| agents/rlm/ | 0 | 1 | 0 | 0 |
| services/ | 1 | 0 | 0 | 1 |

Then a one-line verdict: **All docs current** or **N folders need updates**.
