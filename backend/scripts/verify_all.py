"""Run the whole verification suite for a delivery build.

Usage:  python scripts/verify_all.py [--port 5001]

Order matters: schema -> data integrity -> unit tests -> page render ->
screen audit -> live route sweep.  Any failure stops the chain so the report
always reflects the first real problem.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

STEPS = [
    ("schema", "check_schema.py"),
    ("integrity", "check_integrity.py"),
    ("unit tests", None),                       # pytest, handled inline
    ("page render", "check_pages.py"),
    ("screen audit", "audit_screens.py"),
    ("sections", "check_sections.py"),
    ("api audit", "audit_api.py"),
    ("live route sweep", "audit_all.py"),
    ("cycles", None),                            # multiple scripts
]

CYCLES = ["cycle_test.py", "cycle_sales.py", "cycle_hr.py",
          "cycle_biz.py", "cycle_ops.py"]

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(HERE, "..")


def run(label: str, argv: list[str], cwd: str) -> tuple[bool, str]:
    print(f"\n=== {label} ===", flush=True)
    t0 = time.time()
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=1800)
    out = p.stdout + p.stderr
    tail = "\n".join(out.strip().splitlines()[-6:])
    print(tail, flush=True)
    ok = p.returncode == 0
    print(f"--- {label}: {'OK' if ok else 'FAIL'} ({time.time()-t0:.1f}s)", flush=True)
    return ok, out


def main() -> int:
    backend = os.path.abspath(BACKEND)
    port = "5000"
    if "--port" in sys.argv:
        port = sys.argv[sys.argv.index("--port") + 1]
    env = dict(os.environ, BASE_PORT=port)
    os.environ.update(env)

    results: list[tuple[str, bool]] = []

    for label, script in STEPS:
        if label == "unit tests":
            ok, _ = run(label, [sys.executable, "-m", "pytest", "tests", "-q"], backend)
        elif label == "cycles":
            all_ok = True
            for c in CYCLES:
                ok, _ = run(f"cycle {c}", [sys.executable, f"scripts/{c}"], backend)
                all_ok = all_ok and ok
            ok = all_ok
        else:
            ok, _ = run(label, [sys.executable, f"scripts/{script}"], backend)
        results.append((label, ok))
        if not ok:
            break

    print("\n================ SUMMARY ================")
    for label, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    failed = [l for l, ok in results if not ok]
    print(f"\n{'ALL GREEN' if not failed else 'FAILED: ' + ', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
