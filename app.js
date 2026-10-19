// Deadline Tracker: loads deadlines, sorts them soonest first, and shows time left.

const STORAGE_DONE = "deadlineTracker.done";     // ids of deadlines marked done
const STORAGE_ADDED = "deadlineTracker.added";   // deadlines added from the page

const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;

// localStorage can throw (private windows, blocked storage), so fall back gracefully.
function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* not saved */ }
}

let builtIn = [];
let added = load(STORAGE_ADDED, []);
let done = new Set(load(STORAGE_DONE, []));

// Urgency bucket used for the color of each row.
function urgency(msLeft) {
  if (msLeft < 0) return "overdue";
  if (msLeft <= 2 * DAY) return "soon";
  if (msLeft <= 7 * DAY) return "week";
  return "later";
}

// Human-readable time left, e.g. "2 days 5 hours", "3 hours", "overdue by 1 day".
function timeLeft(msLeft) {
  const abs = Math.abs(msLeft);
  const days = Math.floor(abs / DAY);
  const hours = Math.floor((abs % DAY) / HOUR);
  const minutes = Math.floor((abs % HOUR) / 60000);
  let text;
  if (days > 0) text = `${days} day${days === 1 ? "" : "s"}` + (hours ? ` ${hours} hr` : "");
  else if (hours > 0) text = `${hours} hr ${minutes} min`;
  else text = `${minutes} min`;
  return msLeft < 0 ? `overdue by ${text}` : `${text} left`;
}

function formatDue(date) {
  return date.toLocaleString("en-US", {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
  });
}

function allDeadlines() {
  return [...builtIn, ...added.map(d => ({ ...d, custom: true }))];
}

function render() {
  const now = Date.now();
  const course = document.getElementById("course-filter").value;
  const showDone = document.getElementById("show-done").checked;

  const items = allDeadlines()
    .map(d => ({ ...d, date: new Date(d.due) }))
    .filter(d => course === "all" || d.course === course)
    .filter(d => showDone || !done.has(d.id))
    .sort((a, b) => a.date - b.date);

  const list = document.getElementById("list");
  list.replaceChildren();
  for (const d of items) {
    const msLeft = d.date - now;
    const li = document.createElement("li");
    li.className = `item ${urgency(msLeft)}` + (done.has(d.id) ? " done" : "");

    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = done.has(d.id);
    box.title = "Mark done";
    box.addEventListener("change", () => {
      box.checked ? done.add(d.id) : done.delete(d.id);
      save(STORAGE_DONE, [...done]);
      render();
    });

    const info = document.createElement("div");
    const courseEl = document.createElement("div");
    courseEl.className = "course";
    courseEl.textContent = d.course;
    const titleEl = document.createElement("div");
    titleEl.className = "title";
    if (d.link) {
      const a = document.createElement("a");
      a.href = d.link; a.target = "_blank"; a.rel = "noopener";
      a.textContent = d.title;
      titleEl.append(a);
    } else {
      titleEl.textContent = d.title;
    }
    const dueEl = document.createElement("div");
    dueEl.className = "due";
    dueEl.textContent = formatDue(d.date);
    info.append(courseEl, titleEl, dueEl);

    const right = document.createElement("div");
    const left = document.createElement("div");
    left.className = "left";
    left.textContent = done.has(d.id) ? "done" : timeLeft(msLeft);
    right.append(left);
    if (d.custom) {
      const rm = document.createElement("button");
      rm.className = "remove";
      rm.textContent = "remove";
      rm.addEventListener("click", () => {
        added = added.filter(x => x.id !== d.id);
        save(STORAGE_ADDED, added);
        render();
      });
      right.append(rm);
    }

    li.append(box, info, right);
    list.append(li);
  }

  document.getElementById("empty").hidden = items.length > 0;

  // Summary line counts only deadlines that are not done.
  const open = allDeadlines().filter(d => !done.has(d.id)).map(d => new Date(d.due) - now);
  const dueSoon = open.filter(ms => ms >= 0 && ms <= 7 * DAY).length;
  const overdue = open.filter(ms => ms < 0).length;
  document.getElementById("summary").textContent =
    `${dueSoon} due in the next 7 days` + (overdue ? ` · ${overdue} overdue` : "");
}

function fillCourseFilter() {
  const select = document.getElementById("course-filter");
  const current = select.value;
  const courses = [...new Set(allDeadlines().map(d => d.course))].sort();
  select.replaceChildren(new Option("All courses", "all"), ...courses.map(c => new Option(c, c)));
  select.value = courses.includes(current) ? current : "all";
}

document.getElementById("add-form").addEventListener("submit", event => {
  event.preventDefault();
  const deadline = {
    id: "custom-" + Date.now(),
    course: document.getElementById("add-course").value.trim(),
    title: document.getElementById("add-title").value.trim(),
    due: document.getElementById("add-due").value,
    link: document.getElementById("add-link").value.trim()
  };
  added.push(deadline);
  save(STORAGE_ADDED, added);
  event.target.reset();
  fillCourseFilter();
  render();
});

document.getElementById("course-filter").addEventListener("change", render);
document.getElementById("show-done").addEventListener("change", render);

fetch("deadlines.json")
  .then(response => response.json())
  .then(data => { builtIn = data; })
  .catch(() => { document.getElementById("summary").textContent = "Could not load deadlines.json"; })
  .finally(() => { fillCourseFilter(); render(); setInterval(render, 60 * 1000); });
