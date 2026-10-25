# Build Log: Deadline Tracker (TCSS 490 Artifact 2)

Built with Claude (an AI coding agent) working in this repository on my Mac.

## Session 1: October 18, 2026

### Plan
- **Problem:** my deadlines are spread across three course websites and Canvas, and I
  keep having to check each one.
- **Goal:** one page that shows every upcoming deadline across TCSS 305, 371, and 490,
  sorted soonest first, with how much time is left.
- **Must have:**
  1. List of deadlines sorted by due date, with course, title, and due date/time
  2. "Time left" countdown and color by urgency (overdue / due in 48h / this week / later)
  3. Mark a deadline done (checkbox), and hide or show done items
  4. Add my own deadline from the page (e.g. TCSS 371 assignments and quizzes)
- **Nice to have:** filter by course, link to each assignment page.
- **Stack:** plain HTML/CSS/JS on GitHub Pages, so I can bookmark it and open it anywhere.
- **What "working" means:** I can open the page, see the right deadlines in the right
  order, check one off, add a new one, and the page remembers that after a reload.

### Changes
1. **Gathered real deadlines.** Pulled the due dates for TCSS 305 (A1b, A1c, A2, A3) and
   TCSS 490 (Artifacts 2–5) from the course websites into `deadlines.json`. TCSS 371's
   syllabus only lists assignments by week, not by date, so 371 deadlines get added from
   the page instead.
2. **Built the page** (`index.html`, `style.css`, `app.js`):
   - Sorts deadlines soonest first and shows "time left" (e.g. "2 days 6 hr left").
   - Colors each row by urgency: red overdue, orange within 48 hours, yellow within a
     week, green later. The countdown refreshes every minute.
   - Checkbox to mark a deadline done, plus a "Show done" toggle.
   - Form to add my own deadline (course, title, due date, optional link), with a
     "remove" button on added ones.
   - Course filter dropdown.
   - Done marks and added deadlines are saved in the browser with localStorage. Reads and
     writes are wrapped in try/catch so the page still works if storage is blocked.
3. **Verified it in a real browser** (automated headless Chrome, with the clock set to
   Sun Oct 18, 5:00 PM):
   - Order and countdowns were correct: A2 and A1b at "6 hr 59 min left", A1c and
     Artifact 3 at "7 days 6 hr left", and so on.
   - Checking an item hid it; adding "TCSS 371 – Assignment 1" (due Oct 20) placed it in
     the right spot; both survived a page reload.
   - The course filter and "Show done" worked, with no JavaScript errors.
   - **Issue found while testing:** my first test script failed on the checkbox step.
     The cause was the test, not the app: the app redraws the list after each change, so
     the checkbox the test held onto was replaced. The test was fixed to click instead.

## Session 2: October 25, 2026 (Artifact 3: AI Inside It)

### Plan
- **Problem:** TCSS 371 deadlines never made it into the tracker. Its syllabus only lists
  weeks, and typing every quiz and assignment by hand from Canvas is exactly the chore the
  tracker was supposed to remove.
- **Goal:** a script that reads a course page and adds its deadlines to `deadlines.json`, with
  a model doing the reading every time it runs.
- **Shape:** a Python script that runs Claude Code headless (`claude -p`) as one step. My
  course access covers Claude Code, so no paid API key is needed.
- **Split between model and code** (written up in `CLAUDE.md`):
  - Model: read the page text and return each deadline as JSON (forced by `--json-schema`),
    including the exact quote that states the date.
  - Code: strip HTML, then check everything: the quote must really be in the page, the
    course must be a course code, the date must be real and near this year, a missing time
    becomes 11:59 PM, duplicates are skipped, and nothing is saved without `--write`.
- **What "working" means:** run it on the real TCSS 371 Canvas assignments list and get the
  right dates into the tracker, with tests proving the checks reject bad answers.

### Changes
1. **Wrote `tools/extract_deadlines.py`** (standard library only). It prints what it would
   add, what it skipped and why, and the run's estimated cost.
2. **Wrote 22 tests** (`tests/`) that swap in a fake model (`tests/fake_claude.py`) so the
   checks can be tested without calling Claude. Two problems came up while testing:
   - **Real bug:** the end-to-end tests failed because the folder "TCSS 490" contains a
     space and the fake model's command path wasn't quoted. Fixed with `shlex.join`. The
     script itself uses a list of arguments, so it was not affected.
   - **Wrong test:** one test expected the old order of the saved file, but the file is
     sorted by due date on purpose, so Oct 30 correctly comes before Nov 8. Fixed the test.
3. **Set up Claude Code on my Mac.** The first two runs failed with "Not logged in". The
   script reported the error and left `deadlines.json` untouched, which is what it should
   do. The login had stopped at the first setup screen; after finishing it (Claude Pro),
   the run worked.
4. **Real run** on the saved TCSS 371 Canvas assignments list (my scores left out):
   - The model reported 13 deadlines and all 13 passed the checks: Quizzes 4–8, Online
     quizzes B–D, Assignments 2–5, and the Final Exam.
   - I compared every date with Canvas and all 13 were right. The page also lists
     "Not available until" dates right next to each due date, and the model picked the
     due date every time.
   - Estimated cost was about $0.16–0.21 per run (covered by my subscription). Most of
     that is Claude Code's own setup, not my small page.
5. **Bug from the real run:** two long titles got ids ending in "-" because the id was
   trimmed before it was cut to 40 characters. Fixed the order in `slugify`, added a test
   (23 now), and regenerated the 371 ids.

### What I'd do next
- The quote check proves a date appears on the page, but not that it belongs to that
  assignment. A stricter check could require the title to appear near the quote.
- Running it straight from a Canvas URL instead of a saved file.
