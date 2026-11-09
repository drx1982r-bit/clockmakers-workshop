#!/usr/bin/env bash
# Usage: ./render.sh [render.py options]   e.g.  ./render.sh --preset MEDIUM --engine EEVEE --encode
cd "$(dirname "$0")"
BLENDER="${BLENDER:-$(command -v blender || echo /Applications/Blender.app/Contents/MacOS/Blender)}"
exec "$BLENDER" -b project.blend -P scripts/render.py -- "$@"
