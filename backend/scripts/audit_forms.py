"""Audit web forms: api_post (live) vs stub action."""
import glob
import re

for path in sorted(glob.glob("app/web/*.py")):
    src = open(path, encoding="utf-8").read()
    name = path.split("\\")[-1]
    for m in re.finditer(r"def (\w+)\([^)]*\):(.*?)(?=\n@bp|\ndef |\Z)", src, re.S):
        fn, body = m.group(1), m.group(2)
        if "render_template" in body and ("form.html" in body or "form\"" in body):
            mode = "LIVE" if "api_post" in body else ("STUB" if "flash(" in open(path, encoding='utf-8').read() else "?")
            print(f"{name}:{fn:22} {mode}")
