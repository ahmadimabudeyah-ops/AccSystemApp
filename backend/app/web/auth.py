"""Auth web pages: login/logout/password/register."""
from flask import Blueprint, render_template, redirect, url_for, request, flash

bp = Blueprint("web_auth", __name__)


@bp.get("/")
def index():
    return redirect(url_for("web_auth.login"))


@bp.get("/login")
def login():
    return render_template("auth/login.html")


@bp.get("/logout")
def logout():
    flash("تم تسجيل الخروج بنجاح", "success")
    return redirect(url_for("web_auth.login", logged_out=1))


@bp.get("/forgot-password")
def forgot_password():
    return render_template("auth/forgot_password.html")


@bp.post("/forgot-password")
def forgot_password_post():
    from ..services import ops_service
    tenant = request.form.get("tenant_code") or request.form.get("tenant_id") or ""
    username = request.form.get("email") or request.form.get("username") or ""
    try:
        ops_service.request_password_reset(tenant_id=tenant.strip(), username=username.strip())
    except Exception:
        pass  # لا تكشف وجود الحساب — نفس الرسالة دائمًا
    flash("أُرسل رابط الاستعادة إن كان البريد مسجلًا", "success")
    return redirect(url_for("web_auth.login"))


@bp.get("/reset-password/<token>")
def reset_password(token):
    return render_template("auth/reset_password.html", token=token)


@bp.post("/reset-password/<token>")
def reset_password_post(token):
    from ..services import ops_service
    from ..services.errors import ValidationError
    new_password = request.form.get("new_password") or request.form.get("password") or ""
    try:
        ops_service.reset_password(token=token, new_password=new_password)
    except ValidationError as exc:
        flash(str(exc) or "رابط الاستعادة غير صالح أو منتهي", "error")
        return redirect(url_for("web_auth.reset_password", token=token))
    except Exception:
        flash("تعذر تحديث كلمة المرور — تحقق من الرابط", "error")
        return redirect(url_for("web_auth.reset_password", token=token))
    flash("تم تحديث كلمة المرور — سجّل الدخول", "success")
    return redirect(url_for("web_auth.login"))


@bp.get("/register")
def register():
    return render_template("auth/register.html")


@bp.get("/start")
def onboarding():
    return render_template("auth/onboarding.html")


@bp.post("/register")
def register_post():
    flash("استلمنا طلبك — سيتواصل معك فريق المبيعات", "success")
    return redirect(url_for("web_auth.login"))
