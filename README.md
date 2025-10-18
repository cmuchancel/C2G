# SysML v2 Diagram Generator

A lightweight command-line tool that converts a subset of SysML v2 text into visual diagrams inspired by the BusbySim style. The parser understands packages, items, parts, ports, actions, and state machines so the generated graphics retain the structure of the original model.

## Features
- Parses `package` bodies with attributes, BusbySim `item def` declarations, `part` blocks (including ports and actions), and `state` machines with transitions.
- Keeps support for simple SysML v2 `block`/`part`/`extends` syntax used by legacy inputs.
- Emits Graphviz DOT text and a fully self-contained SVG rendering without requiring the Graphviz CLI.
- Accepts input from files or standard input for easy integration with other tooling.

## Requirements
- Python 3.8+

## Usage
Run the CLI directly from the repository:

```bash
python3 diagram_generator.py --help
```

### Generate DOT and SVG in one call

By default the script prints the DOT description to standard output and writes an SVG file next to your SysML source (override the paths with the flags shown below):

```bash
python3 diagram_generator.py --input test.sysml --svg-output light_switch.svg > light_switch.dot
```

The command above saves `light_switch.svg`, emits the DOT source to `stdout` (captured in `light_switch.dot`), and reports the output locations on `stderr`.

### Custom output locations

```bash
python3 diagram_generator.py --input path/to/model.sysml \
    --diagram block \
    --dot-output diagrams/model.dot \
    --svg-output diagrams/model.svg
```

When `--dot-output` is omitted the DOT text is written to `stdout`. If `--svg-output` is omitted the SVG defaults to `<input_stem>_<diagram>.svg` (or `diagram_<diagram>.svg` when reading from `stdin`).

### Reading from standard input

```bash
cat model.sysml | python3 diagram_generator.py --input - --svg-output model.svg > model.dot
```

### Bundled example

The repository ships with `test.sysml`, a BusbySim-generated light-switch model. Render it with:

```bash
python3 diagram_generator.py --input test.sysml --svg-output light_switch.svg > light_switch.dot
```

Open the SVG in a browser to inspect the nested panels for packages, parts, ports, and states. Unsupported constructs are ignored gracefully so the tool remains useful even with partial models.

## Test command

Run the bundled regression check to render `test.sysml` into both SVG and DOT outputs in one step:

```bash
./run_test.sh
```

The script exits with a non-zero status if either artifact cannot be written, making it suitable for quick smoke testing.

### Print the exact test command

If you just need the copy/pasteable invocation for manual testing, use the helper script to echo it to the terminal:

```bash
python3 print_test_command.py
```

It responds with the fully qualified `python3 diagram_generator.py --input …` command so you can run or share it directly.
