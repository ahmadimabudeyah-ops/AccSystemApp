"""Render-check every web GET route. Exit nonzero on failure."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402

D = "00000000-0000-0000-0000-000000000000"
app = create_app()
client = app.test_client()
fails = []
n = 0
for r in app.url_map.iter_rules():
    if not r.endpoint.startswith("web_") or "GET" not in r.methods:
        continue
    url = str(r)
    for p in ("acc_id", "e_id", "j_id", "p_id", "o_id", "q_id", "d_id",
              "i_id", "g_id", "b_id", "c_id", "a_id", "r_id"):
        url = url.replace("<uuid:%s>" % p, D)
    url = (url.replace("<token>", "x").replace("<t_id>", "VAT16")
              .replace("<r_id>", "1").replace("<u_id>", "1")
              .replace("<name>", "trial-balance"))
    if "<" in url:
        continue
    n += 1
    rv = client.get(url)
    # / and /logout legitimately redirect to the login screen when not authed
    ok = (url in ("/", "/logout") and rv.status_code == 302) or rv.status_code == 200
    if not ok:
        fails.append((url, rv.status_code))
print("RENDERED:", n, "FAILS:", len(fails))
for f in fails:
    print(f)
sys.exit(1 if fails else 0)
