#!/usr/bin/env python3
"""Print the canonical smoke-test command for the diagram generator."""

from __future__ import annotations

import shlex
from pathlib import Path


def build_test_command() -> str:
    repo_dir = Path(__file__).resolve().parent
    generator = repo_dir / "diagram_generator.py"
    sample = repo_dir / "test.sysml"
    parts = [
        "python3",
        str(generator),
        "--input",
        str(sample),
        "--svg-output",
        "light_switch.svg",
    ]
    command = " ".join(shlex.quote(part) for part in parts)
    return f"{command} > light_switch.dot"


def main() -> int:
    print(build_test_command())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
