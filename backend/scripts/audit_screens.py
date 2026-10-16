"""Deep screen audit: title, breadcrumbs, actions, links, forms per page + link graph."""
import re
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402

app = create_app()
c = app.test_client()
D = "00000000-0000-0000-0000-000000000000"

issues = []
pages = 0
JS_FORMS = {"login-form", "entry-form", "feedback-form", "invoice-form"}
NO_CRUMB_PAGES = {"/dashboard", "/login", "/help", "/forgot-password",
                  "/register", "/start"}
NO_CRUMB_PREFIX = ("/reset-password", "/portal/")


def get(url):
    try:
        return c.get(url)
    except Exception as e:  # noqa: BLE001
        return type("R", (), {"status_code": 599, "get_data": lambda s, **k: str(e)})()


def fill(url):
    for p in ("acc_id", "e_id", "j_id", "p_id", "o_id", "q_id", "d_id", "i_id",
              "g_id", "b_id", "c_id", "a_id", "r_id", "u_id"):
        url = url.replace(f"<uuid:{p}>", D)
    url = (url.replace("<token>", "x").replace("<t_id>", "VAT16")
              .replace("<r_id>", "1").replace("<u_id>", "1")
              .replace("<name>", "trial-balance"))
    return url


rules = [r for r in app.url_map.iter_rules()
         if r.endpoint.startswith("web_") and "GET" in r.methods]
for r in sorted(rules, key=str):
    url = fill(str(r))
    if "<" in url:
        continue
    pages += 1
    rv = get(url)
    if rv.status_code == 302:
        continue
    if rv.status_code != 200:
        issues.append((url, f"HTTP {rv.status_code}", ""))
        continue
    html = rv.get_data(as_text=True)
    if "<h1" not in html:
        issues.append((url, "no-h1", ""))
    if "breadcrumb" not in html and url not in NO_CRUMB_PAGES \
            and not url.startswith(NO_CRUMB_PREFIX):
        issues.append((url, "no-breadcrumbs", ""))
    for m in re.finditer(r'(?:href|action)="(/(?!static|api)[^"#]*)"', html):
        link = m.group(1)
        if "<" in link or "{" in link:
            continue
        r2 = get(link)
        # 405 is expected for links that point at POST-only actions; only a
        # 404/500 means the target really does not exist.
        if r2.status_code >= 400 and r2.status_code not in (302, 405):
            issues.append((url, f"dead-link {r2.status_code}", link))
    for m in re.finditer(r"<form([^>]*)>", html):
        tag = m.group(0)
        if "action=" not in tag and "data-api-post" not in tag \
                and not any(f'id="{j}"' in tag for j in JS_FORMS):
            issues.append((url, "form-without-action", tag[:80]))

print("PAGES:", pages, "ISSUES:", len(issues))
seen = set()
for u, kind, extra in issues:
    key = (kind, extra.split("?")[0])
    if key in seen:
        continue
    seen.add(key)
    print(f"- [{kind}] {u} {extra}")
