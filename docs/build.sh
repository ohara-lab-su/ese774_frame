#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="$SCRIPT_DIR"
ROOT_DIR="$(cd "$DOCS_DIR/.." && pwd)"
SRC_DIR="$ROOT_DIR/src"

PKG_NAME="fastapi_frame"   # パッケージ名を明示

export PYTHONPATH="$SRC_DIR:${PYTHONPATH:-}"

echo "Cleaning build..."
rm -rf "$DOCS_DIR/_build" "$DOCS_DIR/api"
mkdir -p "$DOCS_DIR/api"

echo "Generating API stubs with sphinx-apidoc..."
sphinx-apidoc -o "$DOCS_DIR/api" "$SRC_DIR/$PKG_NAME" -f --module-first

echo "Building HTML..."
sphinx-build -b html "$DOCS_DIR" "$DOCS_DIR/_build/html"

echo "Done."