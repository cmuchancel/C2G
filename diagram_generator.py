#!/usr/bin/env python3
"""Generate simple SysML v2 diagrams from textual definitions.

This module provides a lightweight command line interface that accepts a
SysML v2 text file (as exported by SysON or authored manually) and produces a
Graphviz representation of the block structure.  The goal is not to implement
the entire SysML v2 language but to cover a pragmatic subset that captures
block declarations, part properties, and generalization relationships so that
engineers can quickly visualize their system decomposition.

Example usage:

```
python diagram_generator.py --input path/to/model.sysml --diagram block \
    --output diagrams/model.dot
```

If Graphviz is installed locally the script can optionally emit PNG or SVG
files directly by specifying ``--format png`` or ``--format svg``.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# Regular expressions for a minimal subset of SysML v2 textual syntax.
_BLOCK_PATTERN = re.compile(
    r"block\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{(?P<body>[\s\S]*?)\}",
    re.MULTILINE,
)
_PART_PATTERN = re.compile(
    r"part\s+(?:def\s+)?([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)
_EXTENDS_PATTERN = re.compile(
    r"extends\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


@dataclass
class BlockDefinition:
    """Represents a parsed block definition."""

    name: str
    parts: List[Tuple[str, str]] = field(default_factory=list)  # (part_name, type)
    bases: List[str] = field(default_factory=list)


def parse_sysmlv2(source: str) -> Dict[str, BlockDefinition]:
    """Parse a subset of SysML v2 block syntax from ``source``.

    The parser is intentionally lightweight: it extracts ``block`` declarations,
    ``part`` properties (including optional ``def`` keyword), and ``extends``
    relationships inside each block body.  The resulting mapping is keyed by the
    block name.
    """

    blocks: Dict[str, BlockDefinition] = {}

    for match in _BLOCK_PATTERN.finditer(source):
        name = match.group(1)
        body = match.group("body")
        parts = [
            (part_name, part_type) for part_type, part_name in _PART_PATTERN.findall(body)
        ]
        bases = list(_EXTENDS_PATTERN.findall(body))
        blocks[name] = BlockDefinition(name=name, parts=parts, bases=bases)

    return blocks


def _collect_nodes(blocks: Dict[str, BlockDefinition]) -> Iterable[str]:
    """Return the set of node names present in the model."""

    node_names = set(blocks.keys())
    for block in blocks.values():
        for _, part_type in block.parts:
            node_names.add(part_type)
        for base in block.bases:
            node_names.add(base)
    return sorted(node_names)


def build_dot_graph(blocks: Dict[str, BlockDefinition], diagram_type: str) -> str:
    """Render the provided ``blocks`` as a Graphviz DOT graph.

    ``diagram_type`` is currently informational; both ``block`` and ``internal``
    diagram types produce the same graph structure, but the type is embedded in
    the graph label so future extensions can differentiate behaviors.
    """

    nodes = _collect_nodes(blocks)
    lines: List[str] = ["digraph SysML {", "    graph [rankdir=LR];"]
    lines.append("    node [shape=record, style=filled, fillcolor=lightgray];")
    lines.append(f"    labelloc=\"t\"; label=\"SysML v2 {diagram_type.title()} Diagram\";")

    for name in nodes:
        block = blocks.get(name)
        if block and block.parts:
            part_labels = "|".join(f"{pname}:{ptype}" for pname, ptype in block.parts)
            label = f"{{{name}|{part_labels}}}"
        else:
            label = name
        lines.append(f"    \"{name}\" [label=\"{label}\"];")

    for block in blocks.values():
        for part_name, part_type in block.parts:
            lines.append(
                "    \"{src}\" -> \"{dst}\" [label=\"{label}\", arrowhead=\"diamond\"];".format(
                    src=block.name,
                    dst=part_type,
                    label=part_name,
                )
            )
        for base in block.bases:
            lines.append(
                "    \"{src}\" -> \"{dst}\" [label=\"extends\", arrowhead=\"onormal\"];".format(
                    src=block.name,
                    dst=base,
                )
            )

    lines.append("}")
    return "\n".join(lines)


def write_output(dot_text: str, output_path: Path, fmt: str) -> None:
    """Write the DOT source or render it using Graphviz if available."""

    fmt = fmt.lower()
    if fmt == "dot":
        output_path.write_text(dot_text, encoding="utf-8")
        return

    dot_binary = "dot"
    if not shutil.which(dot_binary):  # type: ignore[arg-type]
        raise RuntimeError(
            "Graphviz 'dot' executable not found; install Graphviz or use --format dot"
        )

    proc = subprocess.run(
        [dot_binary, f"-T{fmt}", "-o", os.fspath(output_path)],
        input=dot_text.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Graphviz rendering failed: " + proc.stderr.decode("utf-8", errors="ignore")
        )


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to a SysML v2 text file (use '-' to read from STDIN).",
    )
    parser.add_argument(
        "--diagram",
        "-d",
        choices=["block", "internal"],
        default="block",
        help="Type of diagram to generate (currently informational).",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path. Defaults to <input_stem>_<diagram>.dot",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["dot", "png", "svg"],
        default="dot",
        help="Output format. Non-dot formats require Graphviz to be installed.",
    )
    return parser.parse_args(argv)


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    try:
        source = _read_input(args.input)
    except OSError as exc:
        sys.stderr.write(f"Failed to read input file: {exc}\n")
        return 1

    blocks = parse_sysmlv2(source)
    if not blocks:
        sys.stderr.write("No block definitions were found in the input.\n")

    dot_text = build_dot_graph(blocks, args.diagram)

    output_arg = args.output
    if output_arg:
        output_path = Path(output_arg)
    else:
        suffix = args.format.lower()
        stem = Path(args.input).stem if args.input != "-" else "diagram"
        default_name = f"{stem}_{args.diagram}.{suffix}"
        output_path = Path(default_name)

    try:
        write_output(dot_text, output_path, args.format)
    except RuntimeError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2

    print(f"Diagram written to {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
