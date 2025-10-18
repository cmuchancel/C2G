#!/usr/bin/env bash
set -euo pipefail

python3 diagram_generator.py --input test.sysml --svg-output light_switch.svg --dot-output light_switch.dot
