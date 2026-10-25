#!/usr/bin/env python3
"""Stands in for `claude -p` in tests. Prints the reply stored in the FAKE_CLAUDE_REPLY file."""
import os
import sys

sys.stdin.read()
with open(os.environ["FAKE_CLAUDE_REPLY"], encoding="utf-8") as f:
    sys.stdout.write(f.read())
