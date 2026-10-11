# Sourced by setup scripts: picks a supported Python unless POCKETGRID_PYTHON is set.
supported() { "$1" -c 'import sys; sys.exit(sys.version_info[:2] not in ((3, 11), (3, 12)))' >/dev/null 2>&1; }
PYTHON="${POCKETGRID_PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  for candidate in python3.12 python3.11 python3; do
    if supported "$candidate"; then PYTHON="$candidate"; break; fi
  done
fi
if [[ -z "$PYTHON" ]] || ! supported "$PYTHON"; then
  echo 'Install Python 3.11 or 3.12, or set POCKETGRID_PYTHON to one (e.g. with pyenv: POCKETGRID_PYTHON=$(pyenv prefix 3.12.9)/bin/python3.12).' >&2
  exit 1
fi
