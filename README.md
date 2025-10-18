# SysML v2 Diagram Generator

A lightweight command-line tool that converts a subset of SysML v2 text into Graphviz diagrams. Use it to quickly visualize block definitions, part relationships, BusbySim-style item/port connections, and inheritance without leaving your editor.

## Features
- Parses `block` declarations, `part` properties, BusbySim `item`/`port` constructs, and `extends` relationships from SysML v2 text
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

This repository includes `test.sysml`, a BusbySim-generated example of a light switch package. Generate a PNG diagram directly:

```bash
python3 diagram_generator.py --input test.sysml --format png --output light_switch.png
```

Use `--format dot` if Graphviz is not installed—the script will emit DOT text instead of rendering an image.

Read SysML v2 content from standard input:

```bash
cat model.sysml | python3 diagram_generator.py --input - --output model.dot
```

The resulting diagram highlights part relationships with diamond arrows and inheritance with open arrows. Unsupported constructs are ignored gracefully so the tool remains useful even with partial models.
