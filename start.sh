#!/bin/bash
# WeasyPrint needs Homebrew's GLib/GObject on macOS — set library path before launching
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:${DYLD_LIBRARY_PATH}
exec python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 "$@"
