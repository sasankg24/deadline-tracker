#!/usr/bin/env python3
"""Extract deadlines from a saved assignment page or syllabus and add them to deadlines.json.

The work is split on purpose:

  The MODEL (Claude Code, run headless with `claude -p`) only reads the text and reports
  each deadline it finds: course, title, due date, due time if stated, and the exact
  quote from the text that the date came from.

  This SCRIPT does everything else: it turns HTML into plain text, calls the model,
  and then checks every answer before anything is saved:
    - the quote really appears in the input (so the model cannot invent a deadline),
    - the course looks like "TCSS 123",
    - the date is a real calendar date in a sensible year,
    - a missing time becomes 11:59 PM (a rule in code, not a guess by the model),
    - the deadline is not already in deadlines.json.
  Nothing is written unless you pass --write.

Usage:
  python3 tools/extract_deadlines.py PAGE.html [--course "TCSS 371"] [--write]
  pbpaste | python3 tools/extract_deadlines.py - --course "TCSS 371"

Set EXTRACT_CLAUDE_CMD to use a different command instead of `claude` (the tests use
this to swap in a fake model).
"""

import argparse
import datetime as dt
import html.parser
import json
import os
import re
import shlex
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEADLINES_FILE = os.path.join(REPO_ROOT, "deadlines.json")
DEFAULT_TIME = "23:59"
MAX_INPUT_CHARS = 60_000

# The shape the model must answer in. Claude Code enforces it with --json-schema.
SCHEMA = {
    "type": "object",
    "properties": {
        "deadlines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "course": {"type": "string"},
                    "title": {"type": "string"},
                    "due_date": {"type": "string"},
                    "due_time": {"type": "string"},
                    "source_quote": {"type": "string"},
                },
                "required": ["course", "title", "due_date", "due_time", "source_quote"],
            },
        }
    },
    "required": ["deadlines"],
}

PROMPT = """You read course pages and list their deadlines. The page text is on stdin.

Report every assignment, quiz, exam or project that has a specific due date written in
the text. For each one give:
- course: the course code, like "TCSS 371". {course_hint}
- title: a short name, like "Assignment 2" or "Quiz 3".
- due_date: YYYY-MM-DD. If the text gives no year, use {year}.
- due_time: HH:MM in 24-hour time if the text states a time, otherwise "".
- source_quote: the exact words from the text that state this due date, copied
  character for character (a short phrase, under 200 characters).

Rules:
- Only report dates that are written in the text. Never guess or calculate a date
  (for example from "week 5"). If there are no dated deadlines, return an empty list.
- Do not use any tools. Answer only from the text you were given.
"""


# ---------------------------------------------------------------- reading input

class _TextExtractor(html.parser.HTMLParser):
    """Collects visible text from HTML, skipping scripts and styles."""

    SKIP = {"script", "style", "noscript", "svg"}
    BLOCK = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
             "section", "article", "table", "ul", "ol", "dt", "dd"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def to_plain_text(raw):
    """Turns HTML into plain text; leaves plain text alone."""
    if re.search(r"<(html|body|div|p|table|h[1-6])\b", raw, re.IGNORECASE):
        parser = _TextExtractor()
        parser.feed(raw)
        raw = "".join(parser.parts)
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in raw.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text[:MAX_INPUT_CHARS]


# ---------------------------------------------------------------- calling the model

class ModelError(Exception):
    """The model call failed or returned something unusable."""


def call_model(text, course_hint, year):
    """Runs `claude -p` once and returns (list of raw deadline dicts, cost in USD or None)."""
    hint = (f'If the page does not name its course, use "{course_hint}".'
            if course_hint else "")
    prompt = PROMPT.format(course_hint=hint, year=year)
    command = shlex.split(os.environ.get("EXTRACT_CLAUDE_CMD", "claude"))
    command += ["-p", prompt, "--output-format", "json", "--json-schema", json.dumps(SCHEMA)]
    try:
        done = subprocess.run(command, input=text, capture_output=True, text=True,
                              timeout=300, check=False)
    except FileNotFoundError:
        raise ModelError("could not find the `claude` command. Is Claude Code installed?")
    except subprocess.TimeoutExpired:
        raise ModelError("the model took longer than 5 minutes")

    try:
        reply = json.loads(done.stdout)
    except json.JSONDecodeError:
        detail = (done.stderr or done.stdout).strip()[:500]
        raise ModelError(f"claude did not return JSON (exit code {done.returncode}): {detail}")
    if not isinstance(reply, dict):
        raise ModelError("claude returned JSON that is not an object")
    if reply.get("is_error") or done.returncode != 0:
        raise ModelError(f"claude reported an error: {str(reply.get('result'))[:500]}")

    answer = reply.get("structured_output")
    if answer is None:  # older versions: the JSON is in the text result
        try:
            answer = json.loads(reply.get("result") or "")
        except json.JSONDecodeError:
            raise ModelError("the model's answer was not in the expected format")
    items = answer.get("deadlines") if isinstance(answer, dict) else None
    if not isinstance(items, list):
        raise ModelError("the model's answer has no 'deadlines' list")
    return items, reply.get("total_cost_usd")


# ---------------------------------------------------------------- checking answers

def _squash(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def slugify(text):
    # Cut to 40 characters first, then trim, so an id never ends in "-".
    return re.sub(r"[^a-z0-9]+", "-", text.lower())[:40].strip("-")


def normalize_course(course):
    """'tcss371', 'TCSS-371' and 'TCSS 371' all become 'TCSS 371'. Returns None if not a course code."""
    match = re.fullmatch(r"\s*([A-Za-z]{2,5})[\s-]*(\d{3})\s*", course or "")
    return f"{match.group(1).upper()} {match.group(2)}" if match else None


def check_item(item, source_text, year, existing):
    """Validates one model answer. Returns (deadline dict, None) or (None, reason it was rejected)."""
    if not isinstance(item, dict):
        return None, "not an object"
    title = str(item.get("title", "")).strip()
    if not title:
        return None, "missing title"
    if len(title) > 120:
        return None, "title is too long"

    course = normalize_course(str(item.get("course", "")))
    if not course:
        return None, f"course {item.get('course')!r} is not a course code like 'TCSS 371'"

    quote = str(item.get("source_quote", ""))
    if not quote.strip() or _squash(quote) not in _squash(source_text):
        return None, f"its quote {quote!r} is not in the page, so the date may be invented"

    due_date = str(item.get("due_date", "")).strip()
    try:
        day = dt.datetime.strptime(due_date, "%Y-%m-%d").date()
    except ValueError:
        return None, f"due date {due_date!r} is not a real YYYY-MM-DD date"
    if abs(day.year - year) > 1:
        return None, f"due date {due_date} is not near {year}"

    due_time = str(item.get("due_time", "")).strip() or DEFAULT_TIME
    try:
        clock = dt.datetime.strptime(due_time, "%H:%M").time()
    except ValueError:
        return None, f"due time {due_time!r} is not HH:MM"

    due = dt.datetime.combine(day, clock).strftime("%Y-%m-%dT%H:%M")
    number = course.split()[1]
    deadline = {"id": f"{number}-{slugify(title)}", "course": course, "title": title, "due": due}

    if deadline["id"] in existing["ids"] or (course, title.lower()) in existing["names"]:
        return None, "already in deadlines.json"
    return deadline, None


def check_all(items, source_text, year, current):
    """Checks every model answer against the input text and the current list."""
    existing = {"ids": {d["id"] for d in current},
                "names": {(d["course"], d["title"].lower()) for d in current}}
    accepted, rejected = [], []
    for item in items:
        deadline, reason = check_item(item, source_text, year, existing)
        if deadline:
            accepted.append(deadline)
            existing["ids"].add(deadline["id"])
            existing["names"].add((deadline["course"], deadline["title"].lower()))
        else:
            label = item.get("title", "?") if isinstance(item, dict) else "?"
            rejected.append((label, reason))
    return accepted, rejected


# ---------------------------------------------------------------- deadlines.json

def load_deadlines(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_deadlines(path, deadlines):
    """Writes one deadline per line, sorted by due date, matching the hand-written file."""
    deadlines = sorted(deadlines, key=lambda d: d["due"])
    lines = ",\n".join("  " + json.dumps(d, ensure_ascii=False) for d in deadlines)
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + lines + "\n]\n")


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(description="Add deadlines from a course page to deadlines.json.")
    parser.add_argument("source", help="saved page (.html or .txt), or - to read from stdin")
    parser.add_argument("--course", help='course to use if the page does not say, e.g. "TCSS 371"')
    parser.add_argument("--year", type=int, default=dt.date.today().year,
                        help="year to assume when the page leaves it out")
    parser.add_argument("--write", action="store_true", help="save the accepted deadlines")
    parser.add_argument("--file", default=DEADLINES_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.course and not normalize_course(args.course):
        parser.error(f"--course {args.course!r} should look like 'TCSS 371'")

    if args.source == "-":
        raw = sys.stdin.read()
    else:
        with open(args.source, encoding="utf-8", errors="replace") as f:
            raw = f.read()
    text = to_plain_text(raw)
    if not text:
        print("The input is empty, so there is nothing to read.")
        return 1

    current = load_deadlines(args.file)
    print(f"Asking Claude to read {len(text):,} characters...")
    try:
        items, cost = call_model(text, normalize_course(args.course or ""), args.year)
    except ModelError as e:
        print(f"Model step failed: {e}")
        return 2

    accepted, rejected = check_all(items, text, args.year, current)

    print(f"\nThe model reported {len(items)} deadline(s).")
    for d in accepted:
        print(f"  + {d['course']}  {d['title']:<40}  due {d['due']}")
    for title, reason in rejected:
        print(f"  - skipped {title!r}: {reason}")
    if cost is not None:
        print(f"Estimated model cost: ${cost:.4f}")

    if not accepted:
        print("\nNothing new to add.")
    elif args.write:
        save_deadlines(args.file, current + accepted)
        print(f"\nAdded {len(accepted)} deadline(s) to {os.path.relpath(args.file, REPO_ROOT)}.")
    else:
        print("\nDry run: nothing saved. Run again with --write to add these.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
