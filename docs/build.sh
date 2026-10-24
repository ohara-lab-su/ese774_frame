#!/usr/bin/env bash
set -euo pipefail

DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$DOCS_DIR/.." && pwd)"
PACKAGE_DIR="$ROOT_DIR/src/ese774_frame"
BUILD_DIR="$DOCS_DIR/_build/html"

if [[ ! -d "$PACKAGE_DIR" ]]; then
  echo "ERROR: Python package not found: $PACKAGE_DIR" >&2
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}"
rm -rf "$DOCS_DIR/_build"
mkdir -p "$BUILD_DIR"

for lang in en ja; do
  rm -f "$DOCS_DIR/$lang/api/"*.rst
  sphinx-apidoc --force --module-first -o "$DOCS_DIR/$lang/api" "$PACKAGE_DIR"
  if [[ ! -f "$DOCS_DIR/$lang/api/modules.rst" ]]; then
    echo "ERROR: Missing generated API index for $lang" >&2
    exit 1
  fi
done

# Independent source trees give independent language-specific toctrees.
sphinx-build -b html -c "$DOCS_DIR" -D language=en "$DOCS_DIR/en" "$BUILD_DIR"
sphinx-build -b html -c "$DOCS_DIR" -D language=en "$DOCS_DIR/en" "$BUILD_DIR/en"
sphinx-build -b html -c "$DOCS_DIR" -D language=ja "$DOCS_DIR/ja" "$BUILD_DIR/ja"

for page in index.html en/index.html ja/index.html \
  tutorials/ese774_intro.html en/tutorials/ese774_intro.html ja/tutorials/ese774_intro.html \
  api/index.html en/api/index.html ja/api/index.html \
  api/modules.html en/api/modules.html ja/api/modules.html; do
  if [[ ! -f "$BUILD_DIR/$page" ]]; then
    echo "ERROR: Missing generated page: $page" >&2
    exit 1
  fi
done

touch "$BUILD_DIR/.nojekyll"
