"""Stable dev server for verification runs (no auto-reloader).

Usage:  python scripts/run_server.py [port]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app  # noqa: E402

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    create_app().run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
