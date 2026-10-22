"""Parties API: CRUD + statement (from posted journal lines by partner)."""
from __future__ import annotations
import uuid
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.party import Party, PartyAddress, PartyContact
from ...models.journal import JournalEntry, JournalLine

bp = Blueprint("parties", __name__)
PAGE = 50

DEFAULT_TYPES = [
    ("customer", "عميل", "Customer"), ("supplier", "مورد", "Supplier"),
    ("employee", "موظف", "Employee"), ("student", "طالب", "Student"),
    ("guardian", "ولي أمر", "Guardian"), ("bank", "بنك", "Bank"),
    ("government", "جهة حكومية", "Government"), ("shareholder", "مساهم", "Shareholder"),
    ("partner", "شريك", "Partner"), ("agent", "وكيل", "Agent"),
    ("distributor", "موزع", "Distributor"), ("contractor", "مقاول", "Contractor"),
    ("consultant", "مستشار", "Consultant"), ("landlord", "مالك عقار", "Landlord"),
    ("other", "أخرى", "Other"),
]


def _ensure_types(tenant_id) -> None:
    """ضمان وجود أنواع الأطراف الافتراضية لهذه المؤسسة (تُزرع عند أول استخدام)."""
    from sqlalchemy import text as _text
    for code, ar, en in DEFAULT_TYPES:
        db.session.execute(_text(
            "INSERT INTO party_types (tenant_id, code, name_ar, name_en) "
            "VALUES (:t, :c, :a, :e) ON CONFLICT (tenant_id, code) DO NOTHING"),
            {"t": str(tenant_id), "c": code, "a": ar, "e": en})
    db.session.flush()


def _assign_types(tenant_id, party_id, codes: list[str], actor_id) -> None:
    from sqlalchemy import text as _text
    _ensure_types(tenant_id)
    clean = [c for c in dict.fromkeys(codes or []) if c]
    for i, code in enumerate(clean):
        row = db.session.execute(_text(
            "SELECT id FROM party_types WHERE tenant_id = :t AND code = :c"),
            {"t": str(tenant_id), "c": code}).first()
        if row is None:
            continue
        db.session.execute(_text(
            "INSERT INTO party_type_assignments "
            "(tenant_id, party_id, party_type_id, is_primary, created_by, updated_by) "
            "VALUES (:t, :p, :pt, :pr, :u, :u) "
            "ON CONFLICT (tenant_id, party_id, party_type_id) DO NOTHING"),
            {"t": str(tenant_id), "p": str(party_id), "pt": str(row[0]),
             "pr": i == 0, "u": str(actor_id) if actor_id else None})


def _types_for(tenant_id, party_id) -> list[str]:
    from sqlalchemy import text as _text
    rows = db.session.execute(_text(
        "SELECT t.code FROM party_type_assignments a "
        "JOIN party_types t ON t.id = a.party_type_id "
        "WHERE a.tenant_id = :t AND a.party_id = :p AND a.is_deleted = FALSE"),
        {"t": str(tenant_id), "p": str(party_id)}).fetchall()
    return [r[0] for r in rows]


def _next_party_code(tenant_id, entity_id, prefix: str) -> str:
    from sqlalchemy import text as _text
    rows = db.session.execute(_text(
        "SELECT code FROM parties WHERE tenant_id = :t AND entity_id = :e "
        "AND is_deleted = FALSE AND code LIKE :p"),
        {"t": str(tenant_id), "e": str(entity_id), "p": f"{prefix}-%"}).fetchall()
    used = set()
    for (code,) in rows:
        suffix = code[len(prefix) + 1:]
        if suffix.isdigit():
            used.add(int(suffix))
    n = 1
    while n in used:
        n += 1
    return f"{prefix}-{n:04d}"


def _deny(perm: str):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _dump(p: Party) -> dict:
    return {"id": str(p.id), "entity_id": str(p.entity_id), "code": p.code,
            "name_ar": p.name_ar, "name_en": p.name_en, "status": p.status,
            "credit_limit": float(p.credit_limit)}


@bp.get("/parties")
@jwt_required()
def list_parties():
    page = max(int(request.args.get("page", 1)), 1)
    q = db.session.query(Party).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("entity_id"):
        q = q.filter_by(entity_id=uuid.UUID(str(request.args["entity_id"])))
    if request.args.get("q"):
        like = f"%{request.args['q']}%"
        q = q.filter((Party.code.like(like)) | (Party.name_ar.like(like)))
    if request.args.get("type"):
        from sqlalchemy import text as _text
        q = q.filter(Party.id.in_(db.session.execute(_text(
            "SELECT a.party_id FROM party_type_assignments a "
            "JOIN party_types t ON t.id = a.party_type_id "
            "WHERE a.tenant_id = :t AND a.is_deleted = FALSE AND t.code = :c"),
            {"t": str(g.tenant_id), "c": request.args["type"]}).scalars().all()))
    total = q.count()
    rows = q.order_by(Party.code).offset((page - 1) * PAGE).limit(PAGE).all()
    type_map = {}
    if rows:
        from sqlalchemy import text as _text
        for pid, code in db.session.execute(_text(
                "SELECT a.party_id::text, t.code FROM party_type_assignments a "
                "JOIN party_types t ON t.id = a.party_type_id "
                "WHERE a.tenant_id = :t AND a.party_id IN :p AND a.is_deleted = FALSE"),
                {"t": g.tenant_id, "p": tuple(str(p.id) for p in rows)}).all():
            type_map.setdefault(pid, []).append(code)
    out = []
    for p in rows:
        d = _dump(p)
        d["types"] = type_map.get(str(p.id), [])
        out.append(d)
    return jsonify({"data": out, "page": page, "page_size": PAGE, "total": total})


@bp.post("/parties")
@jwt_required()
def create_party():
    denied = _deny("parties.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    entity_id = uuid.UUID(str(data["entity_id"]))
    types = data.get("types")
    if not types:
        mapped = data.get("party_type") or data.get("type")
        types = {"customer": ["customer"], "supplier": ["supplier"],
                 "both": ["customer", "supplier"]}.get(mapped or "customer", ["customer"])
    code = (data.get("code") or "").strip()
    if not code:
        prefix = "SUP" if types and types[0] == "supplier" else "CUS"
        code = _next_party_code(g.tenant_id, entity_id, prefix)
    p = Party(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=entity_id,
              code=code, name_ar=data["name_ar"], name_en=data.get("name_en"),
              legal_type=data.get("legal_type", "company"), status="active",
              credit_limit=data.get("credit_limit", 0), notes=data.get("notes"),
              created_by=me, updated_by=me)
    db.session.add(p)
    db.session.flush()
    _assign_types(g.tenant_id, p.id, types, me)
    for a in data.get("addresses", []):
        db.session.add(PartyAddress(tenant_id=p.tenant_id, party_id=p.id,
                                    address_type=a.get("address_type", "primary"),
                                    address1=a["address1"], city=a.get("city"),
                                    country=a.get("country", "JO"),
                                    is_primary=a.get("is_primary", False),
                                    created_by=me, updated_by=me))
    for c in data.get("contacts", []):
        db.session.add(PartyContact(tenant_id=p.tenant_id, party_id=p.id,
                                    contact_type=c["contact_type"], contact_value=c["contact_value"],
                                    is_primary=c.get("is_primary", False),
                                    created_by=me, updated_by=me))
    db.session.commit()
    return jsonify({"data": _dump(p)}), 201


@bp.get("/parties/<uuid:party_id>")
@jwt_required()
def get_party(party_id):
    p = db.session.get(Party, party_id)
    if p is None or p.is_deleted or str(p.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    d = _dump(p)
    d["types"] = _types_for(g.tenant_id, p.id)
    d["party_type"] = ("both" if {"customer", "supplier"} <= set(d["types"])
                       else (d["types"][0] if d["types"] else "customer"))
    d["addresses"] = [{"id": str(a.id), "address_type": a.address_type, "address1": a.address1,
                       "city": a.city, "is_primary": a.is_primary} for a in p.addresses if not a.is_deleted]
    d["contacts"] = [{"id": str(c.id), "contact_type": c.contact_type,
                      "contact_value": c.contact_value, "is_primary": c.is_primary}
                     for c in p.contacts if not c.is_deleted]
    return jsonify({"data": d})


@bp.put("/parties/<uuid:party_id>")
@jwt_required()
def update_party(party_id):
    denied = _deny("parties.manage")
    if denied:
        return denied
    p = db.session.get(Party, party_id)
    if p is None or p.is_deleted or str(p.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    for field in ("name_ar", "name_en", "status", "credit_limit", "notes"):
        if field in data:
            setattr(p, field, data[field])
    p.updated_by = uuid.UUID(str(get_jwt().get("sub")))
    types = data.get("types")
    if not types:
        mapped = data.get("party_type") or data.get("type")
        if mapped:
            types = {"customer": ["customer"], "supplier": ["supplier"],
                     "both": ["customer", "supplier"]}.get(mapped, [mapped])
    if types:
        from sqlalchemy import text as _text
        db.session.execute(_text(
            "UPDATE party_type_assignments SET is_deleted = TRUE "
            "WHERE tenant_id = :t AND party_id = :p AND is_deleted = FALSE"),
            {"t": str(p.tenant_id), "p": str(p.id)})
        _assign_types(p.tenant_id, p.id, types, p.updated_by)
    db.session.commit()
    return jsonify({"data": _dump(p)})


@bp.get("/parties/<uuid:party_id>/statement")
@jwt_required()
def party_statement(party_id):
    """كشف حساب الطرف من القيود المرحلة (مدين/دائن/رصيد)."""
    p = db.session.get(Party, party_id)
    if p is None or p.is_deleted or str(p.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    rows = (db.session.query(JournalLine, JournalEntry)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .filter(JournalLine.partner_id == p.id, JournalEntry.status.in_(("posted", "reversed")),
                    JournalEntry.is_deleted.is_(False), JournalLine.is_deleted.is_(False))
            .order_by(JournalEntry.posting_date).all())
    lines = [{"date": e.posting_date.isoformat(), "doc": e.official_number,
              "description": l.description or e.description,
              "debit": float(l.debit), "credit": float(l.credit)} for l, e in rows]
    bal = sum(x["debit"] - x["credit"] for x in lines)
    return jsonify({"data": {"party_id": str(p.id), "lines": lines, "balance": round(bal, 3)}})


# ------------------------------------------------------------- countries & cities (global)

@bp.get("/countries")
@jwt_required()
def list_countries():
    from ...models.addons import Country
    rows = db.session.query(Country).filter_by(is_deleted=False).order_by(
        Country.code).limit(300).all()
    return jsonify({"data": [{"id": str(c.id), "code": c.code,
                              "name_ar": c.name_ar, "name_en": c.name_en}
                             for c in rows]})


@bp.post("/countries")
@jwt_required()
def create_country():
    denied = _deny("admin.*")
    if denied:
        return denied
    from ...models.addons import Country
    data = request.get_json(force=True)
    c = Country(code=data["code"].upper()[:2], name_ar=data["name_ar"],
                name_en=data["name_en"])
    db.session.add(c)
    db.session.commit()
    return jsonify({"data": {"id": str(c.id), "code": c.code}}), 201


@bp.get("/cities")
@jwt_required()
def list_cities():
    from ...models.addons import City
    q = db.session.query(City).filter_by(is_deleted=False)
    if request.args.get("country_id"):
        q = q.filter_by(country_id=uuid.UUID(request.args["country_id"]))
    rows = q.order_by(City.code).limit(500).all()
    return jsonify({"data": [{"id": str(c.id), "country_id": str(c.country_id),
                              "code": c.code, "name_ar": c.name_ar} for c in rows]})


@bp.post("/cities")
@jwt_required()
def create_city():
    denied = _deny("admin.*")
    if denied:
        return denied
    from ...models.addons import City
    data = request.get_json(force=True)
    c = City(country_id=uuid.UUID(str(data["country_id"])),
             code=data["code"], name_ar=data["name_ar"])
    db.session.add(c)
    db.session.commit()
    return jsonify({"data": {"id": str(c.id), "code": c.code}}), 201
