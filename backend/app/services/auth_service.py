"""Authentication service: login, refresh, permission loading."""
import uuid
from flask_jwt_extended import create_access_token, create_refresh_token
from ..extensions import db
from ..models.user import User, UserRole, RolePermission, Permission
from ..utils.security import verify_password


class AuthError(Exception):
    pass


def authenticate(tenant_id, username: str, password: str):
    """Accept tenant UUID *or* code (e.g. DEMO), and username *or* email."""
    from ..models.tenant import Tenant
    try:
        tenant_uuid = uuid.UUID(str(tenant_id))
    except (ValueError, AttributeError):
        tenant = db.session.query(Tenant).filter_by(
            code=str(tenant_id).strip(), is_deleted=False).first()
        if tenant is None:
            raise AuthError("Unknown tenant")
        tenant_uuid = tenant.id
    else:
        tenant = db.session.query(Tenant).filter_by(id=tenant_uuid).first()
        if tenant is None:
            raise AuthError("Unknown tenant")
    tenant_id = tenant_uuid
    # إنفاذ الاشتراك: تجريبي/نشط وسارٍ — وإلا رفض الدخول برسالة تجديد
    from datetime import date as _date
    from ..models.tenant import Subscription
    sub = (db.session.query(Subscription)
           .filter_by(tenant_id=tenant_id, is_deleted=False)
           .order_by(Subscription.ends_on.desc()).first())
    if sub is not None and (sub.status not in ("trial", "active") or sub.ends_on < _date.today()):
        raise AuthError("Subscription expired — renew to continue")
    # login is an open path (no middleware context yet): scope RLS to the
    # claimed tenant BEFORE reading. Password check still enforced below.
    from sqlalchemy import text
    from datetime import datetime, timedelta, timezone
    db.session.execute(text('SET LOCAL "app.current_tenant_id" = :t'), {"t": str(tenant_id)})
    fails = db.session.execute(text(
        "SELECT count(*) FROM login_attempts WHERE tenant_id = :t AND username = :u "
        "AND success = FALSE AND attempted_at > :since"),
        {"t": str(tenant_id), "u": username,
         "since": datetime.now(timezone.utc) - timedelta(minutes=15)}).scalar() or 0
    if fails >= 5:
        raise AuthError("Account locked: too many failed attempts")
    user = db.session.query(User).filter(
        User.tenant_id == tenant_id,
        ((User.username == username) | (User.email == username)),
        User.is_deleted.is_(False)).first()
    ok = bool(user and user.is_active and verify_password(password, user.password_hash))
    if not ok:
        db.session.execute(text(
            "INSERT INTO login_attempts(tenant_id, username, success) VALUES (:t, :u, FALSE)"),
            {"t": str(tenant_id), "u": username})
        db.session.commit()
        raise AuthError("Invalid credentials")
    # كل القراءات (المستخدم + الصلاحيات) قبل أي commit حتى لا يضيع سياق RLS
    perms = (
        db.session.query(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .filter(UserRole.user_id == user.id, UserRole.tenant_id == tenant_id)
        .all()
    )
    claims = {"tenant_id": str(tenant_id), "permissions": sorted({p.code for p in perms})}
    identity = str(user.id)
    db.session.execute(text(
        "INSERT INTO login_attempts(tenant_id, username, success) VALUES (:t, :u, TRUE)"),
        {"t": str(tenant_id), "u": username})
    db.session.commit()
    return {
        "access_token": create_access_token(identity=identity, additional_claims=claims),
        "refresh_token": create_refresh_token(identity=identity, additional_claims={"tenant_id": str(tenant_id)}),
        "permissions": claims["permissions"],
    }


def get_user_permissions(user_id, tenant_id):
    """Reload permission codes for refresh — single source for JWT claims."""
    rows = (
        db.session.query(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .filter(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
        .all()
    )
    return sorted({r.code for r in rows})
