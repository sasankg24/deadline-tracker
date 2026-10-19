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

## How data works
- Built-in deadlines come from `deadlines.json`.
- Deadlines added in the page, and "done" checkmarks, are saved in the browser (localStorage),
  so they only live on the device/browser where they were added.

## Conventions
- Dates are ISO strings in local Pacific time, e.g. `2026-10-25T23:59`.
- Keep it small and readable; this is a personal tool.
