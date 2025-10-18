#!/usr/bin/env python3
"""Render SysML v2 source into a diagram approximating the BusbySim style."""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_ATTRIBUTE_PATTERN = re.compile(
    rf"attribute\s+({_IDENTIFIER})(?:\s*(=|:=)\s*([^;{{}}]+))?\s*;",
    re.MULTILINE,
)
_ITEM_PATTERN = re.compile(rf"(?:item|block)\s+def\s+({_IDENTIFIER})", re.MULTILINE)
_PART_PATTERN = re.compile(rf"part\s+({_IDENTIFIER})", re.MULTILINE)
_ACTION_PATTERN = re.compile(rf"action\s+def\s+({_IDENTIFIER})", re.MULTILINE)
_STATE_PATTERN = re.compile(rf"state\s+({_IDENTIFIER})", re.MULTILINE)
_PACKAGE_PATTERN = re.compile(rf"package\s+({_IDENTIFIER})", re.MULTILINE)
_PORT_PATTERN = re.compile(rf"port\s+({_IDENTIFIER})", re.MULTILINE)
_DEFINED_BY_PATTERN = re.compile(rf"defined\s+by\s+({_IDENTIFIER})", re.MULTILINE)
_DIRECTION_PATTERN = re.compile(rf"(in|out)\s+item\s+({_IDENTIFIER})", re.MULTILINE)
_TRANSITION_PATTERN = re.compile(
    rf"transition\s+(?:({_IDENTIFIER})\s+)?first\s+({_IDENTIFIER})"
    rf"(?:\s+if\s+(.+?))?\s+then\s+({_IDENTIFIER})\s*;",
    re.DOTALL,
)
_ENTRY_ACTION_PATTERN = re.compile(
    rf"entry\s+action\s+({_IDENTIFIER})\s+defined\s+by\s+({_IDENTIFIER})\s*;",
    re.MULTILINE,
)
_ENTRY_SIMPLE_PATTERN = re.compile(r"entry\s+([^;]+?)\s*;", re.MULTILINE)


@dataclass
class Attribute:
    name: str
    operator: Optional[str] = None
    value: Optional[str] = None

    def summary(self) -> str:
        if self.operator and self.value is not None:
            return f"{self.name} {self.operator} {self.value.strip()}"
        return self.name


@dataclass
class ActionDefinition:
    name: str
    body: str


@dataclass
class Transition:
    name: Optional[str]
    source: str
    target: str
    guard: Optional[str] = None


@dataclass
class State:
    name: str
    entries: List[str] = field(default_factory=list)
    substates: List["State"] = field(default_factory=list)
    transitions: List[Transition] = field(default_factory=list)


@dataclass
class Port:
    name: str
    direction: Optional[str] = None
    item_name: Optional[str] = None
    item_type: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)


@dataclass
class ItemDefinition:
    name: str
    attributes: List[Attribute] = field(default_factory=list)


@dataclass
class PartDefinition:
    name: str
    attributes: List[Attribute] = field(default_factory=list)
    ports: List[Port] = field(default_factory=list)
    actions: List[ActionDefinition] = field(default_factory=list)
    states: List[State] = field(default_factory=list)


@dataclass
class Package:
    name: str
    attributes: List[Attribute] = field(default_factory=list)
    items: List[ItemDefinition] = field(default_factory=list)
    parts: List[PartDefinition] = field(default_factory=list)


@dataclass
class BlockDefinition:
    name: str
    parts: List[Tuple[str, str]] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)


@dataclass
class SysMLModel:
    packages: List[Package] = field(default_factory=list)
    blocks: Dict[str, BlockDefinition] = field(default_factory=dict)


@dataclass
class Box:
    """Intermediate representation for SVG rendering."""

    title: str
    lines: List[str] = field(default_factory=list)
    children: List["Box"] = field(default_factory=list)


def _strip_comments(text: str) -> str:
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def _extract_brace_block(text: str, start: int) -> Tuple[str, int]:
    length = len(text)
    idx = start
    while idx < length and text[idx].isspace():
        idx += 1
    if idx >= length or text[idx] != "{":
        return "", idx
    depth = 0
    body_start = idx + 1
    for pos in range(idx, length):
        char = text[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[body_start:pos], pos + 1
    return text[body_start:], length


def _parse_attributes(text: str) -> List[Attribute]:
    attrs: List[Attribute] = []
    for match in _ATTRIBUTE_PATTERN.finditer(text):
        attrs.append(
            Attribute(
                name=match.group(1),
                operator=match.group(2),
                value=match.group(3),
            )
        )
    return attrs


def _parse_top_level_attributes(text: str) -> List[Attribute]:
    attrs: List[Attribute] = []
    pos = 0
    depth = 0
    length = len(text)
    while pos < length:
        char = text[pos]
        if char == "{":
            depth += 1
            pos += 1
            continue
        if char == "}":
            depth = max(depth - 1, 0)
            pos += 1
            continue
        if depth == 0:
            match = _ATTRIBUTE_PATTERN.match(text, pos)
            if match:
                attrs.append(
                    Attribute(
                        name=match.group(1),
                        operator=match.group(2),
                        value=match.group(3),
                    )
                )
                pos = match.end()
                continue
        pos += 1
    return attrs


def _parse_item_definitions(text: str) -> List[ItemDefinition]:
    items: List[ItemDefinition] = []
    pos = 0
    while True:
        match = _ITEM_PATTERN.search(text, pos)
        if not match:
            break
        name = match.group(1)
        body, next_pos = _extract_brace_block(text, match.end())
        items.append(ItemDefinition(name=name, attributes=_parse_top_level_attributes(body)))
        pos = max(next_pos, match.end())
    return items


def _parse_ports(text: str) -> List[Port]:
    ports: List[Port] = []
    pos = 0
    while True:
        match = _PORT_PATTERN.search(text, pos)
        if not match:
            break
        name = match.group(1)
        body, next_pos = _extract_brace_block(text, match.end())
        port = Port(name=name)
        if body:
            dir_match = _DIRECTION_PATTERN.search(body)
            if dir_match:
                port.direction = dir_match.group(1)
                port.item_name = dir_match.group(2)
            defined_match = _DEFINED_BY_PATTERN.search(body)
            if defined_match:
                port.item_type = defined_match.group(1)
            port.attributes = _parse_attributes(body)
        ports.append(port)
        pos = max(next_pos, match.end())
    return ports


def _parse_actions(text: str) -> List[ActionDefinition]:
    actions: List[ActionDefinition] = []
    pos = 0
    while True:
        match = _ACTION_PATTERN.search(text, pos)
        if not match:
            break
        name = match.group(1)
        body, next_pos = _extract_brace_block(text, match.end())
        actions.append(ActionDefinition(name=name, body=body.strip()))
        pos = max(next_pos, match.end())
    return actions


def _parse_state_block(name: str, text: str) -> State:
    state = State(name=name)
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        sub_state_match = _STATE_PATTERN.match(text, pos)
        if sub_state_match:
            sub_name = sub_state_match.group(1)
            body, next_pos = _extract_brace_block(text, sub_state_match.end())
            state.substates.append(_parse_state_block(sub_name, body))
            pos = max(next_pos, sub_state_match.end())
            continue
        transition_match = _TRANSITION_PATTERN.match(text, pos)
        if transition_match:
            state.transitions.append(
                Transition(
                    name=transition_match.group(1),
                    source=transition_match.group(2),
                    guard=transition_match.group(3).strip() if transition_match.group(3) else None,
                    target=transition_match.group(4),
                )
            )
            pos = transition_match.end()
            continue
        entry_action_match = _ENTRY_ACTION_PATTERN.match(text, pos)
        if entry_action_match:
            action_name = entry_action_match.group(1)
            defined_name = entry_action_match.group(2)
            state.entries.append(f"action {action_name} ({defined_name})")
            pos = entry_action_match.end()
            continue
        entry_simple_match = _ENTRY_SIMPLE_PATTERN.match(text, pos)
        if entry_simple_match:
            state.entries.append(entry_simple_match.group(1).strip())
            pos = entry_simple_match.end()
            continue
        semicolon = text.find(";", pos)
        if semicolon == -1:
            break
        pos = semicolon + 1
    return state


def _parse_states(text: str) -> List[State]:
    states: List[State] = []
    pos = 0
    while True:
        match = _STATE_PATTERN.search(text, pos)
        if not match:
            break
        name = match.group(1)
        body, next_pos = _extract_brace_block(text, match.end())
        states.append(_parse_state_block(name, body))
        pos = max(next_pos, match.end())
    return states


def _parse_parts(text: str) -> List[PartDefinition]:
    parts: List[PartDefinition] = []
    pos = 0
    while True:
        match = _PART_PATTERN.search(text, pos)
        if not match:
            break
        name = match.group(1)
        body, next_pos = _extract_brace_block(text, match.end())
        part = PartDefinition(name=name)
        if body:
            part.attributes = _parse_top_level_attributes(body)
            part.ports = _parse_ports(body)
            part.actions = _parse_actions(body)
            part.states = _parse_states(body)
        parts.append(part)
        pos = max(next_pos, match.end())
    return parts


def _parse_packages(text: str) -> List[Package]:
    packages: List[Package] = []
    pos = 0
    while True:
        match = _PACKAGE_PATTERN.search(text, pos)
        if not match:
            break
        name = match.group(1)
        body, next_pos = _extract_brace_block(text, match.end())
        package = Package(name=name)
        if body:
            package.attributes = _parse_top_level_attributes(body)
            package.items = _parse_item_definitions(body)
            package.parts = _parse_parts(body)
        packages.append(package)
        pos = max(next_pos, match.end())
    return packages


_BLOCK_DECL_PATTERN = re.compile(
    rf"block\s+({_IDENTIFIER})\s*\{{(?P<body>[\s\S]*?)\}}",
    re.MULTILINE,
)
_PART_DECL_PATTERN = re.compile(
    rf"part\s+(?:def\s+)?({_IDENTIFIER})\s+({_IDENTIFIER})",
    re.MULTILINE,
)
_EXTENDS_PATTERN = re.compile(rf"extends\s+({_IDENTIFIER})", re.MULTILINE)
_PART_BLOCK_PATTERN = re.compile(
    rf"part\s+({_IDENTIFIER})\s*\{{(?P<body>[\s\S]*?)\}}",
    re.MULTILINE,
)


def _parse_block_map(text: str) -> Dict[str, BlockDefinition]:
    blocks: Dict[str, BlockDefinition] = {}
    for match in _BLOCK_DECL_PATTERN.finditer(text):
        name = match.group(1)
        body = match.group("body")
        parts = [
            (part_name, part_type)
            for part_type, part_name in _PART_DECL_PATTERN.findall(body)
        ]
        bases = list(_EXTENDS_PATTERN.findall(body))
        blocks[name] = BlockDefinition(name=name, parts=parts, bases=bases)
    for match in _ITEM_PATTERN.finditer(text):
        name = match.group(1)
        blocks.setdefault(name, BlockDefinition(name=name))
    for match in _PART_BLOCK_PATTERN.finditer(text):
        name = match.group(1)
        body = match.group("body")
        block = blocks.get(name)
        if not block:
            block = BlockDefinition(name=name)
            blocks[name] = block
        for port in _parse_ports(body):
            if port.item_type:
                block.parts.append((port.name, port.item_type))
    return blocks


def parse_sysmlv2(source: str) -> SysMLModel:
    source = _strip_comments(source)
    packages = _parse_packages(source)
    blocks = _parse_block_map(source)
    return SysMLModel(packages=packages, blocks=blocks)


def _sanitize(*parts: str) -> str:
    return "_".join(re.sub(r"[^A-Za-z0-9]+", "_", part) for part in parts if part)


def _html_table(rows: List[str], border_color: str, fill_color: str) -> str:
    return (
        "<<TABLE BORDER=\"0\" CELLBORDER=\"1\" CELLSPACING=\"0\" CELLPADDING=\"6\" "
        f"COLOR=\"{border_color}\" BGCOLOR=\"{fill_color}\">"
        + "".join(rows)
        + "</TABLE>>"
    )


def _attribute_label(attr: Attribute) -> str:
    title = "<TR><TD ALIGN=\"LEFT\"><FONT FACE=\"Helvetica-Bold\" POINT-SIZE=\"11\">attribute</FONT></TD></TR>"
    detail = html.escape(attr.summary())
    body = f"<TR><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"11\">{detail}</FONT></TD></TR>"
    return _html_table([title, body], "#f3c999", "#fff8ec")


def _action_label(action: ActionDefinition) -> str:
    title = "<TR><TD ALIGN=\"LEFT\"><FONT FACE=\"Helvetica-Bold\" POINT-SIZE=\"11\">action def</FONT></TD></TR>"
    name_row = f"<TR><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"11\"><B>{html.escape(action.name)}</B></FONT></TD></TR>"
    body_text = html.escape(" ".join(action.body.split())) if action.body else ""
    body_row = (
        f"<TR><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"10\" COLOR=\"#444444\">{body_text}</FONT></TD></TR>"
        if body_text
        else ""
    )
    return _html_table([title, name_row] + ([body_row] if body_row else []), "#b9e0ff", "#eef7ff")


def _item_label(item: ItemDefinition) -> str:
    header = (
        f"<TR><TD ALIGN=\"LEFT\"><FONT FACE=\"Helvetica-Bold\" POINT-SIZE=\"11\">item def</FONT> "
        f"<FONT POINT-SIZE=\"11\"><B>{html.escape(item.name)}</B></FONT></TD></TR>"
    )
    attr_rows = [
        f"<TR><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"10\">{html.escape(attr.summary())}</FONT></TD></TR>"
        for attr in item.attributes
    ]
    if not attr_rows:
        attr_rows.append("<TR><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"10\" COLOR=\"#666666\">(empty)</FONT></TD></TR>")
    return _html_table([header] + attr_rows, "#f2bed1", "#fff0f4")


def _port_label(port: Port) -> str:
    header = f"<TR><TD ALIGN=\"LEFT\"><FONT FACE=\"Helvetica-Bold\" POINT-SIZE=\"11\">port {html.escape(port.name)}</FONT></TD></TR>"
    lines: List[str] = []
    if port.direction or port.item_name or port.item_type:
        direction = port.direction or ""
        item_name = port.item_name or "item"
        defined = port.item_type or ""
        descriptor = f"{direction} item {item_name}".strip()
        if defined:
            descriptor += f" defined by {defined}"
        lines.append(
            f"<TR><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"10\">{html.escape(descriptor)}</FONT></TD></TR>"
        )
    for attr in port.attributes:
        lines.append(
            f"<TR><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"10\">{html.escape(attr.summary())}</FONT></TD></TR>"
        )
    if not lines:
        lines.append("<TR><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"10\" COLOR=\"#666666\">(empty)</FONT></TD></TR>")
    return _html_table([header] + lines, "#d5c4ff", "#f3efff")


def _state_label(state: State) -> str:
    title = (
        f"<TR><TD ALIGN=\"LEFT\"><FONT FACE=\"Helvetica-Bold\" POINT-SIZE=\"11\">state</FONT> "
        f"<FONT POINT-SIZE=\"11\"><B>{html.escape(state.name)}</B></FONT></TD></TR>"
    )
    rows = [title]
    for entry in state.entries:
        rows.append(
            f"<TR><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"10\">entry {html.escape(entry)}</FONT></TD></TR>"
        )
    if not state.entries:
        rows.append("<TR><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"10\" COLOR=\"#666666\">(no entry)</FONT></TD></TR>")
    return _html_table(rows, "#b8e6c2", "#edf9f0")


def _build_package_graph(model: SysMLModel, diagram_type: str) -> str:
    lines: List[str] = [
        "digraph SysML {",
        "    graph [rankdir=TB, bgcolor=\"#faf9f6\", margin=0.4];",
        "    node [shape=plaintext, fontname=\"Helvetica\"];",
        "    edge [fontname=\"Helvetica\", color=\"#3b4252\", arrowsize=0.8];",
        f"    labelloc=\"t\"; label=\"SysML v2 {diagram_type.title()} Diagram\";",
    ]

    for package in model.packages:
        cluster_name = f"cluster_pkg_{_sanitize(package.name)}"
        lines.append(f"    subgraph {cluster_name} {{")
        lines.append("        style=\"rounded,filled\";")
        lines.append("        color=\"#d8c9ff\";")
        lines.append("        fillcolor=\"#f8f5ff\";")
        lines.append(
            f"        label=<<B>package {html.escape(package.name)}</B>>;"
        )

        for attr in package.attributes:
            attr_id = f"pkg_attr_{_sanitize(package.name, attr.name)}"
            lines.append(f"        {attr_id} [{_format_label(_attribute_label(attr))}];")

        for item in package.items:
            item_id = f"pkg_item_{_sanitize(package.name, item.name)}"
            lines.append(f"        {item_id} [{_format_label(_item_label(item))}];")

        for part in package.parts:
            part_cluster = f"cluster_part_{_sanitize(package.name, part.name)}"
            lines.append(f"        subgraph {part_cluster} {{")
            lines.append("            style=\"rounded,filled\";")
            lines.append("            color=\"#c7e8ff\";")
            lines.append("            fillcolor=\"#eef9ff\";")
            lines.append(
                f"            label=<<B>part {html.escape(part.name)}</B>>;"
            )

            for attr in part.attributes:
                attr_id = f"part_attr_{_sanitize(package.name, part.name, attr.name)}"
                lines.append(f"            {attr_id} [{_format_label(_attribute_label(attr))}];")

            for action in part.actions:
                action_id = f"part_action_{_sanitize(package.name, part.name, action.name)}"
                lines.append(f"            {action_id} [{_format_label(_action_label(action))}];")

            for port in part.ports:
                port_id = f"part_port_{_sanitize(package.name, part.name, port.name)}"
                lines.append(f"            {port_id} [{_format_label(_port_label(port))}];")
                if port.item_type:
                    item_id = f"pkg_item_{_sanitize(package.name, port.item_type)}"
                    if any(item.name == port.item_type for item in package.items):
                        lines.append(
                            f"            {port_id} -> {item_id} [color=\"#a390ff\", penwidth=1.2, arrowhead=\"vee\"];"
                        )

            for state in part.states:
                lines.extend(
                    _render_state_cluster(package.name, part.name, state, indent="            ")
                )

            lines.append("        }")

        lines.append("    }")

    lines.append("}")
    return "\n".join(lines)


def _format_label(label: str) -> str:
    return f"label={label}"  # label already HTML formatted


def _collect_state_names(state: State) -> Set[str]:
    names: Set[str] = {state.name}
    for sub_state in state.substates:
        names.update(_collect_state_names(sub_state))
    return names


def _render_state_cluster(pkg_name: str, part_name: str, state: State, indent: str = "") -> List[str]:
    lines: List[str] = []
    cluster = f"cluster_state_{_sanitize(pkg_name, part_name, state.name)}"
    lines.append(f"{indent}subgraph {cluster} {{")
    lines.append(f"{indent}    style=\"rounded,filled\";")
    lines.append(f"{indent}    color=\"#bce4d8\";")
    lines.append(f"{indent}    fillcolor=\"#f2fcf8\";")
    lines.append(
        f"{indent}    label=<<B>state {html.escape(state.name)}</B>>;"
    )
    node_id = f"state_node_{_sanitize(pkg_name, part_name, state.name)}"
    lines.append(
        f"{indent}    {node_id} [{_format_label(_state_label(state))}];"
    )

    for sub_state in state.substates:
        lines.extend(
            _render_state_cluster(pkg_name, part_name, sub_state, indent=indent + "    ")
        )

    all_nodes = _collect_state_names(state)
    transitions = list(state.transitions)
    for transition in transitions:
        src_id = (
            f"state_node_{_sanitize(pkg_name, part_name, transition.source)}"
            if transition.source in all_nodes
            else f"pseudo_state_{_sanitize(pkg_name, part_name, transition.source)}"
        )
        dst_id = (
            f"state_node_{_sanitize(pkg_name, part_name, transition.target)}"
            if transition.target in all_nodes
            else f"pseudo_state_{_sanitize(pkg_name, part_name, transition.target)}"
        )
        if transition.source not in all_nodes:
            lines.append(
                f"{indent}    {src_id} [shape=circle, width=0.25, height=0.25, style=filled, fillcolor=\"#3b4252\", label=\"\"];"
            )
        if transition.target not in all_nodes:
            lines.append(
                f"{indent}    {dst_id} [shape=doublecircle, width=0.35, height=0.35, style=filled, fillcolor=\"#eef9ff\", label=\"\"];"
            )
        label = html.escape(transition.guard) if transition.guard else ""
        if label:
            label = f"if {label}"
        label_attr = f" label=\"{label}\"" if label else ""
        lines.append(
            f"{indent}    {src_id} -> {dst_id}[color=\"#6d9886\", penwidth=1.2{label_attr}];"
        )
    lines.append(f"{indent}}}")
    return lines


def _build_block_graph(blocks: Dict[str, BlockDefinition], diagram_type: str) -> str:
    nodes = sorted({name for name in blocks} | {ptype for block in blocks.values() for _, ptype in block.parts} | {base for block in blocks.values() for base in block.bases})
    lines: List[str] = [
        "digraph SysML {",
        "    graph [rankdir=LR];",
        "    node [shape=record, style=filled, fillcolor=lightgray];",
        f"    labelloc=\"t\"; label=\"SysML v2 {diagram_type.title()} Diagram\";",
    ]
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



def build_dot_graph(model: SysMLModel, diagram_type: str) -> str:
    if model.packages:
        return _build_package_graph(model, diagram_type)
    return _build_block_graph(model.blocks, diagram_type)


_CHAR_WIDTH = 7.2
_LINE_HEIGHT = 18.0
_TITLE_FONT_SIZE = 16
_BODY_FONT_SIZE = 13
_HEADER_HEIGHT = 28.0
_BOX_PADDING_X = 14.0
_BOX_PADDING_Y = 10.0
_CHILD_GAP = 12.0
_CANVAS_PADDING = 24.0
_SECTION_GAP = 36.0
_MIN_BOX_WIDTH = 160.0


def _text_width(text: str) -> float:
    return max(len(text), 1) * _CHAR_WIDTH


def _format_attributes(attrs: List[Attribute]) -> List[str]:
    return [attr.summary() for attr in attrs]


def _port_to_box(port: Port) -> Box:
    lines: List[str] = []
    if port.direction or port.item_name:
        descriptor = ' '.join(filter(None, [port.direction, port.item_name]))
        lines.append(descriptor)
    if port.item_type:
        lines.append(f"defined by {port.item_type}")
    lines.extend(_format_attributes(port.attributes))
    return Box(title=f"port {port.name}", lines=lines)


def _action_to_box(action: ActionDefinition) -> Box:
    body_lines = [segment.strip() for segment in action.body.splitlines() if segment.strip()]
    if not body_lines:
        body_lines = ['<empty>']
    return Box(title=f"action {action.name}", lines=body_lines)


def _state_to_box(state: State) -> Box:
    lines: List[str] = []
    for entry in state.entries:
        lines.append(f"entry {entry}")
    for transition in state.transitions:
        pieces = []
        if transition.name:
            pieces.append(f"{transition.name}:")
        pieces.append(f"{transition.source} -> {transition.target}")
        if transition.guard:
            pieces.append(f"[{transition.guard}]")
        lines.append(' '.join(pieces))
    children = [_state_to_box(sub) for sub in state.substates]
    return Box(title=f"state {state.name}", lines=lines, children=children)


def _part_to_box(part: PartDefinition) -> Box:
    lines = _format_attributes(part.attributes)
    children: List[Box] = []
    for port in part.ports:
        children.append(_port_to_box(port))
    for action in part.actions:
        children.append(_action_to_box(action))
    for state in part.states:
        children.append(_state_to_box(state))
    return Box(title=f"part {part.name}", lines=lines, children=children)


def _item_to_box(item: ItemDefinition) -> Box:
    return Box(title=f"item {item.name}", lines=_format_attributes(item.attributes))


def _package_to_box(package: Package) -> Box:
    children: List[Box] = []
    for item in package.items:
        children.append(_item_to_box(item))
    for part in package.parts:
        children.append(_part_to_box(part))
    return Box(title=f"package {package.name}", lines=_format_attributes(package.attributes), children=children)


@dataclass
class LayoutResult:
    box: Box
    width: float
    height: float
    child_layouts: List[Tuple['LayoutResult', float, float]] = field(default_factory=list)


def _layout_box(box: Box) -> LayoutResult:
    child_layouts = [_layout_box(child) for child in box.children]
    max_text_width = max([_text_width(box.title)] + [_text_width(line) for line in box.lines], default=_text_width(box.title))
    max_child_width = max((child.width for child in child_layouts), default=0.0)
    inner_width = max(max_text_width, max_child_width)
    width = max(inner_width + 2 * _BOX_PADDING_X, _MIN_BOX_WIDTH)

    content_top = _HEADER_HEIGHT + _BOX_PADDING_Y
    line_area_height = len(box.lines) * _LINE_HEIGHT
    child_positions: List[Tuple[LayoutResult, float, float]] = []

    child_start_y = content_top + line_area_height
    if box.lines and child_layouts:
        child_start_y += _CHILD_GAP
    elif not box.lines and child_layouts:
        child_start_y += _BOX_PADDING_Y

    current_y = child_start_y
    for idx, child in enumerate(child_layouts):
        child_positions.append((child, _BOX_PADDING_X, current_y))
        current_y += child.height
        if idx < len(child_layouts) - 1:
            current_y += _CHILD_GAP

    base_height = content_top + line_area_height
    if child_layouts:
        base_height = max(base_height, current_y)
    height = max(base_height + _BOX_PADDING_Y, _HEADER_HEIGHT + 2 * _BOX_PADDING_Y + max(line_area_height, _LINE_HEIGHT))

    return LayoutResult(box=box, width=width, height=height, child_layouts=child_positions)


def _render_box(layout: LayoutResult, origin_x: float, origin_y: float, elements: List[str]) -> None:
    rect_attrs = (
        f"x=\"{origin_x:.1f}\" y=\"{origin_y:.1f}\" width=\"{layout.width:.1f}\" "
        f"height=\"{layout.height:.1f}\" rx=\"6\" ry=\"6\""
    )
    elements.append(
        f"<rect {rect_attrs} fill=\"#ffffff\" stroke=\"#333333\" stroke-width=\"1.4\" />"
    )
    elements.append(
        f"<rect x=\"{origin_x:.1f}\" y=\"{origin_y:.1f}\" width=\"{layout.width:.1f}\" "
        f"height=\"{_HEADER_HEIGHT:.1f}\" rx=\"6\" ry=\"6\" fill=\"#2f3b52\" />"
    )
    title_y = origin_y + _HEADER_HEIGHT / 2 + _TITLE_FONT_SIZE / 2 - 2
    elements.append(
        '<text '
        f"x=\"{origin_x + _BOX_PADDING_X:.1f}\" y=\"{title_y:.1f}\" "
        f"font-family=\"Helvetica\" font-size=\"{_TITLE_FONT_SIZE}\" fill=\"#ffffff\">"
        f"{html.escape(layout.box.title)}</text>"
    )

    text_y = origin_y + _HEADER_HEIGHT + _BOX_PADDING_Y + _BODY_FONT_SIZE
    for line in layout.box.lines:
        elements.append(
            '<text '
            f"x=\"{origin_x + _BOX_PADDING_X:.1f}\" y=\"{text_y:.1f}\" "
            f"font-family=\"Helvetica\" font-size=\"{_BODY_FONT_SIZE}\" fill=\"#2f3b52\">"
            f"{html.escape(line)}</text>"
        )
        text_y += _LINE_HEIGHT

    for child_layout, child_x, child_y in layout.child_layouts:
        _render_box(child_layout, origin_x + child_x, origin_y + child_y, elements)


def build_svg_diagram(model: SysMLModel, diagram_type: str) -> str:
    boxes: List[Box] = []
    if model.packages:
        for package in model.packages:
            boxes.append(_package_to_box(package))
    elif model.blocks:
        for block in model.blocks.values():
            lines = [f"part {name} : {type_name}" for name, type_name in block.parts]
            boxes.append(Box(title=f"block {block.name}", lines=lines or ['<no parts>']))
    else:
        boxes.append(Box(title='SysML Diagram', lines=['<empty model>']))

    layouts = [_layout_box(box) for box in boxes]
    total_width = max((layout.width for layout in layouts), default=_MIN_BOX_WIDTH) + 2 * _CANVAS_PADDING
    origins: List[Tuple[LayoutResult, float, float]] = []
    current_y = _CANVAS_PADDING
    for idx, layout in enumerate(layouts):
        origins.append((layout, _CANVAS_PADDING, current_y))
        current_y += layout.height
        if idx < len(layouts) - 1:
            current_y += _SECTION_GAP
    total_height = current_y + _CANVAS_PADDING

    elements: List[str] = [
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{total_width:.1f}\" height=\"{total_height:.1f}\" "
        "viewBox=\"0 0 {0:.1f} {1:.1f}\">".format(total_width, total_height),
        "<rect x=\"0\" y=\"0\" width=\"{0:.1f}\" height=\"{1:.1f}\" fill=\"#f5f6fa\"/>".format(total_width, total_height),
    ]

    for layout, origin_x, origin_y in origins:
        _render_box(layout, origin_x, origin_y, elements)

    elements.append('</svg>')
    return '\n'.join(elements)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", "-i", required=True, help="Path to a SysML v2 text file (use '-' for STDIN).")
    parser.add_argument(
        "--diagram",
        "-d",
        choices=["block", "internal"],
        default="block",
        help="Type of diagram to generate.",
    )
    parser.add_argument(
        "--dot-output",
        help="Path to write the Graphviz DOT description (use '-' for stdout; default: stdout).",
    )
    parser.add_argument(
        "--svg-output",
        help="Path to write the SVG diagram (default: <input_stem>_<diagram>.svg).",
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

    model = parse_sysmlv2(source)
    if not model.packages and not model.blocks:
        sys.stderr.write("No SysML constructs were recognized in the input.\n")

    dot_text = build_dot_graph(model, args.diagram)
    svg_text = build_svg_diagram(model, args.diagram)

    stem = Path(args.input).stem if args.input != '-' else 'diagram'
    dot_destination = args.dot_output if args.dot_output is not None else '-'
    svg_path = Path(args.svg_output) if args.svg_output else Path(f"{stem}_{args.diagram}.svg")

    outputs: List[str] = []

    try:
        if dot_destination == '-':
            if dot_text:
                sys.stdout.write(dot_text)
                if not dot_text.endswith("\n"):
                    sys.stdout.write("\n")
            outputs.append('DOT -> stdout')
        else:
            dot_path = Path(dot_destination)
            dot_path.parent.mkdir(parents=True, exist_ok=True)
            dot_path.write_text(dot_text, encoding='utf-8')
            outputs.append(f'DOT -> {dot_path.resolve()}')

        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(svg_text, encoding='utf-8')
        outputs.append(f'SVG -> {svg_path.resolve()}')
    except OSError as exc:
        sys.stderr.write(f"Failed to write output: {exc}\n")
        return 2

    sys.stderr.write("; ".join(outputs) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
