"""Tests for tools/extract_deadlines.py. Run from the repo root:  python3 -m unittest -v"""
import io
import json
import os
import shlex
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import extract_deadlines as ex  # noqa: E402

PAGE = """<html><body><script>var x = "Due 2026-01-01";</script>
<h2>TCSS 371 Schedule</h2>
<ul><li>Assignment 2 is due Friday, October 30 at 11:59 PM.</li>
<li>Quiz 3 on November 4</li>
<li>Week 8: Assignment 4 (date TBA)</li></ul></body></html>"""

EXISTING = [{"id": "305-a2", "course": "TCSS 305", "title": "Assignment 2: Road Rage",
             "due": "2026-11-08T23:59"}]


def item(**overrides):
    base = {"course": "TCSS 371", "title": "Assignment 2", "due_date": "2026-10-30",
            "due_time": "23:59", "source_quote": "Assignment 2 is due Friday, October 30 at 11:59 PM"}
    base.update(overrides)
    return base


class TextTests(unittest.TestCase):
    def test_html_becomes_text_without_scripts(self):
        text = ex.to_plain_text(PAGE)
        self.assertIn("Assignment 2 is due Friday, October 30 at 11:59 PM.", text)
        self.assertNotIn("2026-01-01", text)
        self.assertNotIn("<li>", text)

    def test_plain_text_is_kept(self):
        self.assertEqual("Quiz 1 due Oct 5", ex.to_plain_text("  Quiz 1   due Oct 5  \n\n"))


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.text = ex.to_plain_text(PAGE)

    def check(self, raw, existing=None):
        return ex.check_all([raw], self.text, 2026, existing or EXISTING)

    def test_good_item_is_accepted(self):
        accepted, rejected = self.check(item())
        self.assertEqual([], rejected)
        self.assertEqual({"id": "371-assignment-2", "course": "TCSS 371",
                          "title": "Assignment 2", "due": "2026-10-30T23:59"}, accepted[0])

    def test_missing_time_defaults_to_end_of_day(self):
        accepted, _ = self.check(item(title="Quiz 3", due_date="2026-11-04", due_time="",
                                      source_quote="Quiz 3 on November 4"))
        self.assertEqual("2026-11-04T23:59", accepted[0]["due"])

    def test_quote_not_in_page_is_rejected(self):
        accepted, rejected = self.check(item(title="Assignment 4", due_date="2026-11-13",
                                             source_quote="Assignment 4 due November 13"))
        self.assertEqual([], accepted)
        self.assertIn("not in the page", rejected[0][1])

    def test_quote_matches_despite_case_and_spacing(self):
        accepted, _ = self.check(item(source_quote="assignment 2   is due friday,\nOctober 30"))
        self.assertEqual(1, len(accepted))

    def test_impossible_date_is_rejected(self):
        _, rejected = self.check(item(due_date="2026-02-30"))
        self.assertIn("not a real", rejected[0][1])

    def test_far_year_is_rejected(self):
        _, rejected = self.check(item(due_date="2031-10-30"))
        self.assertIn("not near 2026", rejected[0][1])

    def test_bad_time_is_rejected(self):
        _, rejected = self.check(item(due_time="11:59 PM"))
        self.assertIn("HH:MM", rejected[0][1])

    def test_long_title_id_does_not_end_in_dash(self):
        accepted, _ = self.check(item(title="Assignment 3 - Von Neumann Model and LC-3 Machine Code"))
        self.assertEqual("371-assignment-3-von-neumann-model-and-lc-3", accepted[0]["id"])

    def test_course_is_normalized(self):
        accepted, _ = self.check(item(course="tcss371"))
        self.assertEqual("TCSS 371", accepted[0]["course"])

    def test_non_course_is_rejected(self):
        _, rejected = self.check(item(course="Computer Organization"))
        self.assertIn("course code", rejected[0][1])

    def test_duplicate_of_existing_is_rejected(self):
        existing = EXISTING + [{"id": "371-assignment-2", "course": "TCSS 371",
                                "title": "Assignment 2", "due": "2026-10-30T23:59"}]
        _, rejected = self.check(item(), existing)
        self.assertIn("already", rejected[0][1])

    def test_duplicate_within_one_answer_is_rejected(self):
        accepted, rejected = ex.check_all([item(), item()], self.text, 2026, EXISTING)
        self.assertEqual(1, len(accepted))
        self.assertEqual(1, len(rejected))

    def test_missing_title_is_rejected(self):
        _, rejected = self.check(item(title="  "))
        self.assertIn("title", rejected[0][1])

    def test_non_object_is_rejected(self):
        _, rejected = self.check("Assignment 2")
        self.assertEqual("not an object", rejected[0][1])


class EndToEndTests(unittest.TestCase):
    """Runs main() with the fake model in place of claude."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.page = os.path.join(self.tmp, "page.html")
        with open(self.page, "w") as f:
            f.write(PAGE)
        self.deadlines = os.path.join(self.tmp, "deadlines.json")
        ex.save_deadlines(self.deadlines, EXISTING)
        self.reply = os.path.join(self.tmp, "reply.json")
        os.environ["FAKE_CLAUDE_REPLY"] = self.reply
        # shlex.join quotes the path, which matters because "TCSS 490" contains a space.
        os.environ["EXTRACT_CLAUDE_CMD"] = shlex.join([sys.executable, os.path.join(HERE, "fake_claude.py")])

    def tearDown(self):
        shutil.rmtree(self.tmp)
        os.environ.pop("FAKE_CLAUDE_REPLY", None)
        os.environ.pop("EXTRACT_CLAUDE_CMD", None)

    def set_reply(self, reply):
        with open(self.reply, "w") as f:
            f.write(reply if isinstance(reply, str) else json.dumps(reply))

    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = ex.main([self.page, "--year", "2026", "--file", self.deadlines, *args])
        return code, out.getvalue()

    def saved(self):
        with open(self.deadlines) as f:
            return json.load(f)

    def test_dry_run_saves_nothing(self):
        self.set_reply({"structured_output": {"deadlines": [item()]}, "total_cost_usd": 0.01})
        code, out = self.run_main()
        self.assertEqual(0, code)
        self.assertIn("Dry run", out)
        self.assertEqual(1, len(self.saved()))

    def test_write_adds_good_items_and_skips_invented_ones(self):
        invented = item(title="Assignment 4", due_date="2026-11-13",
                        source_quote="Assignment 4 due November 13")
        self.set_reply({"structured_output": {"deadlines": [item(), invented]}})
        code, out = self.run_main("--write")
        self.assertEqual(0, code)
        saved = self.saved()
        # Saved sorted by due date: the Oct 30 assignment comes before the Nov 8 one.
        self.assertEqual(["371-assignment-2", "305-a2"], [d["id"] for d in saved])
        self.assertIn("skipped 'Assignment 4'", out)

    def test_written_file_is_sorted_by_due_date(self):
        self.set_reply({"structured_output": {"deadlines": [item()]}})
        self.run_main("--write")
        dues = [d["due"] for d in self.saved()]
        self.assertEqual(sorted(dues), dues)

    def test_answer_in_result_text_still_works(self):
        self.set_reply({"result": json.dumps({"deadlines": [item()]})})
        _, out = self.run_main()
        self.assertIn("+ TCSS 371  Assignment 2", out)

    def test_model_error_is_reported_and_nothing_saved(self):
        self.set_reply({"is_error": True, "result": "Not logged in"})
        code, out = self.run_main("--write")
        self.assertEqual(2, code)
        self.assertIn("Not logged in", out)
        self.assertEqual(1, len(self.saved()))

    def test_non_json_reply_is_reported(self):
        self.set_reply("Here are your deadlines!")
        code, out = self.run_main()
        self.assertEqual(2, code)
        self.assertIn("did not return JSON", out)

    def test_missing_claude_command_is_reported(self):
        os.environ["EXTRACT_CLAUDE_CMD"] = "definitely-not-a-real-command-xyz"
        code, out = self.run_main()
        self.assertEqual(2, code)
        self.assertIn("Is Claude Code installed", out)


if __name__ == "__main__":
    unittest.main()
