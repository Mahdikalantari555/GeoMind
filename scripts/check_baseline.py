#!/usr/bin/env python3
"""Run a lint/type command and fail only on violations absent from a baseline.

Full-repo ruff/mypy gates are useful even when a codebase carries known
pre-existing violations. This helper normalises diagnostic output (path
separators and line/column numbers) so a baseline survives edits that shift
lines, then compares the current set against a checked-in baseline.

Usage:
    python scripts/check_baseline.py --write scripts/baselines/ruff.txt -- ruff check ...
    python scripts/check_baseline.py --baseline scripts/baselines/ruff.txt -- ruff check ...

Exit codes: 0 = no new violations, 1 = new violations, 2 = bad invocation.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

_LINE_COL = re.compile(r":\d+(?::\d+)?(?=:)")
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


def normalize(line: str) -> str:
    """Strip volatile line/column numbers and normalise path separators."""
    text = line.strip().replace("\\", "/")
    text = _WINDOWS_DRIVE.sub("", text)
    text = _LINE_COL.sub(":", text)
    return text


def run(command: list[str]) -> tuple[int, Counter[str]]:
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    output = process.stdout + "\n" + process.stderr
    counts: Counter[str] = Counter()
    for line in output.splitlines():
        normalized = normalize(line)
        if not normalized or normalized.startswith(("Found ", "Success:", "All checks", "*[")):
            continue
        counts[normalized] += 1
    return process.returncode, counts


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--baseline", type=Path, help="checked-in baseline file")
    target.add_argument("--write", type=Path, help="write current violations to this file")
    parser.add_argument("command", nargs="+", help="command to run (after --)")
    args = parser.parse_args(argv)

    # argparse with a positional after options: everything after `--` is the command.
    if "--" in argv:
        command = argv[argv.index("--") + 1 :]
    else:
        command = args.command
    if not command:
        parser.error("no command supplied after --")

    _returncode, counts = run(command)
    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(
            "".join(f"{line}\n" for line in sorted(counts.elements())), encoding="utf-8"
        )
        print(f"wrote {sum(counts.values())} baseline entries to {args.write}")
        return 0

    assert args.baseline is not None
    if not args.baseline.is_file():
        parser.error(f"baseline file not found: {args.baseline}")
    baseline_lines = [
        normalize(line) for line in args.baseline.read_text(encoding="utf-8").splitlines()
    ]
    baseline = Counter(line for line in baseline_lines if line)
    new = counts - baseline
    fixed = baseline - counts
    if fixed:
        print(f"INFO: {sum(fixed.values())} baseline violation(s) no longer present:")
        for line in sorted(fixed.elements())[:10]:
            print(f"  - {line}")
    if new:
        print(f"FAIL: {sum(new.values())} new violation(s) not in baseline:")
        for line in sorted(new.elements())[:50]:
            print(f"  + {line}")
        return 1
    print(f"OK: no new violations ({sum(counts.values())} baseline entries present)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
