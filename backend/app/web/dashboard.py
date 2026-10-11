"""Dashboard web page."""
from flask import Blueprint, render_template

bp = Blueprint("web_dashboard", __name__)


@bp.get("/dashboard")
def index():
    return render_template("dashboard/index.html", crumbs=[], active="dashboard")


@bp.get("/help")
def help_page():
    return render_template("help.html", crumbs=[("المساعدة", None)], active="")
