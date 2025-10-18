# SysML v2 Diagram Generator

A lightweight command-line tool that converts a subset of SysML v2 text into Graphviz diagrams. The renderer understands BusbySim-style packages, ports, items, actions, and state machines so the resulting graphics resemble the hand-crafted mock-ups commonly used in BusbySim documentation.

## Features
- Parses `package` bodies with attributes, BusbySim `item def` declarations, `part` blocks (including ports and actions), and `state` machines with transitions
- Still understands simple SysML v2 `block`/`part`/`extends` syntax for legacy inputs
- Emits Graphviz DOT by default, with optional PNG or SVG rendering when Graphviz is installed
- Accepts input from files or standard input for easy integration with other tooling

## Requirements
- Python 3.8+
- Optional: [Graphviz](https://graphviz.org) for PNG/SVG rendering (DOT output works without it)

## Installation
No package installation is required. Clone the repository and run the script directly:

```bash
python3 diagram_generator.py --help
```

## Usage
Generate a DOT diagram from a SysML v2 file:

```bash
python3 diagram_generator.py --input path/to/model.sysml --diagram block --output diagrams/model.dot
```

Render an SVG when Graphviz is available:

```bash
python3 diagram_generator.py --input path/to/model.sysml --format svg
```

### Quick start with the bundled example

This repository includes `test.sysml`, a BusbySim-generated model of a light switch. Render it to SVG (Graphviz required) for a diagram that mirrors the BusbySim house style:

```bash
python3 diagram_generator.py --input test.sysml --format svg --output light_switch.svg
```

Use `--format dot` if Graphviz is not installed—the script will emit DOT text instead of rendering an image. The DOT can be post-processed later once Graphviz is available.

Read SysML v2 content from standard input:

```bash
cat model.sysml | python3 diagram_generator.py --input - --output model.dot
```

The resulting diagram nests packages, parts, ports, and state machines with color-coded panels, connects ports to their item definitions, and labels transitions with their guards. Unsupported constructs are ignored gracefully so the tool remains useful even with partial models.
