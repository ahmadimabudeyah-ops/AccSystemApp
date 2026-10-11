"""Web blueprints package — all Arabic pages, interlinked via url_for.

Modules self-register when their files land; missing modules are skipped
so the app boots at every stage of the rollout.
"""
import importlib
import logging

log = logging.getLogger(__name__)

_MODULES = [
    "auth", "dashboard", "accounts", "journals", "journal_entries",
    "parties", "products", "inventory", "sales", "purchases",
    "treasury", "assets", "taxes", "reports", "settings",
    "hr", "edu", "projects", "portal",
]


def register(app):
    from flask import Blueprint
    for name in _MODULES + ["assets_taxes"]:
        try:
            mod = importlib.import_module(f".{name}", __name__)
        except ImportError as exc:
            log.info("web module %s not yet present (%s)", name, exc)
            continue
        found = [v for v in vars(mod).values() if isinstance(v, Blueprint)]
        for bp in found:
            app.register_blueprint(bp)
            log.info("web blueprint registered: %s", bp.name)
