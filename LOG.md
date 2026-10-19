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
