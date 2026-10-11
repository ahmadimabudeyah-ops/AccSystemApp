"""Shared web helpers: page context + crumbs."""


def ctx(title, crumbs, active="", **kw):
    """crumbs: list of (label, endpoint_or_url). Extra kwargs are exposed
    BOTH as page.* (for shared bodies) AND top-level (for custom templates)."""
    return {"page": {"title": title, **kw}, "crumbs": crumbs, "active": active, **kw}
