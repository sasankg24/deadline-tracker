# Deadline Tracker

A small personal web page that lists my upcoming class deadlines (TCSS 305, 371, 490)
in one place, soonest first, so nothing sneaks up on me.

## Stack
- Plain HTML, CSS, and JavaScript. No framework, no build step, no server.
- Hosted on GitHub Pages.

## Files
- `index.html` – page layout
- `style.css` – styles (dark theme, urgency colors)
- `app.js` – loads deadlines, sorts, renders, handles done/add/delete
- `deadlines.json` – the built-in list of known deadlines (edit this to add permanent ones)
- `LOG.md` – log of plans and changes (update it every session)
- `tools/extract_deadlines.py` – reads a course page with Claude and adds its deadlines (see below)
- `tests/` – unit tests for the extractor, using a fake model

## How data works
- Built-in deadlines come from `deadlines.json`.
- Deadlines added in the page, and "done" checkmarks, are saved in the browser (localStorage),
  so they only live on the device/browser where they were added.

## Conventions
- Dates are ISO strings in local Pacific time, e.g. `2026-10-25T23:59`.
- Keep it small and readable; this is a personal tool.

## Deadline extractor (Artifact 3: AI Inside It)

`tools/extract_deadlines.py` reads a saved course page or syllabus and adds the deadlines it
finds to `deadlines.json`. A model does the reading every time it runs.

```
python3 tools/extract_deadlines.py PAGE.html --course "TCSS 371"          # dry run
python3 tools/extract_deadlines.py PAGE.html --course "TCSS 371" --write  # save
pbpaste | python3 tools/extract_deadlines.py - --course "TCSS 371"        # from the clipboard
```

It runs Claude Code headless (`claude -p`), which my course Claude access covers, so it needs
no paid API key. Only Python's standard library is used.

### What the model is responsible for
Only reading. It gets the page text on stdin and returns JSON (enforced with `--json-schema`)
listing each deadline: course, title, due date, due time if one is written, and the exact quote
from the page that states the date. It is told not to guess dates (for example from "week 5")
and not to use tools.

### What the code is responsible for
Everything else, and it trusts nothing the model says until it is checked:
- turns HTML into plain text (drops scripts and styles) before the model sees it
- **rejects any deadline whose quote is not actually in the page**, so an invented date can't
  get in
- normalizes the course to `TCSS 123` and rejects anything that isn't a course code
- rejects dates that aren't real calendar dates or aren't within a year of the current one
- fills in a missing time as 11:59 PM (a rule in code, not a guess by the model)
- skips anything already in `deadlines.json`, and duplicates within one answer
- builds the id (`371-assignment-2`), keeps the file sorted by due date, and saves nothing
  unless `--write` is given
- reports model failures (not installed, not logged in, non-JSON reply) without touching the file

If a result looks wrong, the printed report shows which side caused it: a "skipped ... because"
line is the code catching the model; a wrong date that was accepted means the quote really is
in the page, so read the page.

### Tests
`python3 -m unittest discover -s tests -v` runs 22 tests. They use `tests/fake_claude.py` in
place of `claude` (set through `EXTRACT_CLAUDE_CMD`), so they test the code's checks without
calling the model.
