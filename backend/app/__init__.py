"""Flask application factory — Multi-tenant accounting platform."""
from flask import Flask, jsonify, request
from .config import get_config
from .extensions import db, migrate, jwt, cors, ma, limiter


def create_app(config_name: str | None = None) -> Flask:
    import logging
    from logging.handlers import RotatingFileHandler
    import os as _os

    class _SafeRotatingFileHandler(RotatingFileHandler):
        """تدوير آمن على ويندوز: عمليتا المُعيد (watcher+child) تمسكان نفس
        الملف، وos.rename يفشل والملف مفتوح (WinError 32). ملاحظة: emit الأم
        يبتلع الاستثناء داخليًا (handleError) لذلك يُتجاوز doRollover نفسه:
        عند التعذر تُعاد الكتابة في نفس الملف بهدوء بدل ضجيج Logging error
        مع كل طلب. (أثناء عمل خادم التطوير قد يكبر app.log فوق الحد حتى
        إعادة التشغيل — نظّفه دوريًا)."""

        def doRollover(self):
            try:
                super().doRollover()
            except (PermissionError, OSError):
                try:
                    if self.stream:
                        try:
                            self.stream.close()
                        except Exception:
                            pass
                    self.stream = self._open()
                except Exception:
                    pass

    _log = _os.path.join(_os.path.dirname(__file__), "..", "app.log")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        handlers=[_SafeRotatingFileHandler(_log, maxBytes=2_000_000, backupCount=3),
                                  logging.StreamHandler()])
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app)
    ma.init_app(app)
    limiter.init_app(app)

    # Middleware: tenant context -> RLS (must run before auth)
    from .middleware import tenant_context as _tc
    app.before_request(_tc.tenant_context)
    _tc.init_app(app)

    # Blueprints
    from .api.v1.auth import bp as auth_bp
    from .api.v1.tenants import bp as tenants_bp
    from .api.v1.accounts import bp as accounts_bp
    from .api.v1.journals import bp as journals_bp
    from .api.v1.reports import bp as reports_bp
    from .api.v1.users import bp as users_bp
    from .api.v1.treasury import bp as treasury_bp
    from .api.v1.assets import bp as assets_bp
    from .api.v1.parties import bp as parties_bp
    from .api.v1.products import bp as products_bp
    from .api.v1.inventory import bp as inventory_bp
    from .api.v1.sales import bp as sales_bp
    from .api.v1.purchases import bp as purchases_bp
    from .api.v1.hr import bp as hr_bp
    from .api.v1.edu import bp as edu_bp
    from .api.v1.projects import bp as projects_bp
    from .api.v1.misc import bp as misc_bp
    from .api.v1.biz import bp as biz_bp
    from .api.v1.imports import bp as imports_bp
    from .api.v1.provisioning import bp as provisioning_bp
    from .api.v1.settings import bp as settings_bp
    from .api.v1.finance import bp as finance_bp
    from .web import register as register_web
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(tenants_bp, url_prefix="/api/v1/tenants")
    app.register_blueprint(accounts_bp, url_prefix="/api/v1/accounts")
    app.register_blueprint(journals_bp, url_prefix="/api/v1")
    app.register_blueprint(reports_bp, url_prefix="/api/v1/reports")
    app.register_blueprint(users_bp, url_prefix="/api/v1")
    app.register_blueprint(treasury_bp, url_prefix="/api/v1/treasury")
    app.register_blueprint(assets_bp, url_prefix="/api/v1")
    app.register_blueprint(parties_bp, url_prefix="/api/v1")
    app.register_blueprint(products_bp, url_prefix="/api/v1")
    app.register_blueprint(inventory_bp, url_prefix="/api/v1/inventory")
    app.register_blueprint(sales_bp, url_prefix="/api/v1/sales")
    app.register_blueprint(purchases_bp, url_prefix="/api/v1/purchases")
    app.register_blueprint(hr_bp, url_prefix="/api/v1/hr")
    app.register_blueprint(edu_bp, url_prefix="/api/v1/education")
    app.register_blueprint(projects_bp, url_prefix="/api/v1")
    app.register_blueprint(misc_bp, url_prefix="/api/v1")
    app.register_blueprint(provisioning_bp, url_prefix="/api/v1")
    app.register_blueprint(settings_bp, url_prefix="/api/v1")
    app.register_blueprint(finance_bp, url_prefix="/api/v1/finance")
    app.register_blueprint(biz_bp, url_prefix="/api/v1")
    app.register_blueprint(imports_bp, url_prefix="/api/v1")
    try:
        register_web(app)
    except ImportError:
        pass

    @app.get("/health")
    def health():
        return {"status": "ok"}

    from flask import render_template

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("errors/500.html"), 500

    @app.errorhandler(ValueError)
    def bad_value(_e):
        if request.path.startswith("/api/"):
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Invalid parameter"}}), 400
        return render_template("errors/404.html"), 404

    return app
