"""Chart-of-accounts structure service: levels, parenting rules, maintenance.

المستويات الوظيفية (تصميم محلي): section ثم general ثم subsidiary ثم detail.
- hierarchy_role=NULL يعني حسابًا قديمًا غير مصنف (legacy) — لا يُستنتج تخمينًا.
- parent_id هو مصدر العلاقة. level/path/is_leaf مشتقة (المشغل يصون الصف نفسه،
  وهذه الخدمة تصون الأحفاد وجدول الإغلاق).
- is_postable: التجميعي (section/general/subsidiary) دائمًا False، والتفصيلي True.
- التفصيلي غير النشط يحتفظ بقابليته للترحيل؛ المنع من الحالة لا من الطبيعة.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import text

from ..extensions import db
from ..models.account import (
    Account, AccountHierarchy, ACCOUNT_TYPES, CONTROL_TYPES,
    HIERARCHY_ROLES, ACCOUNT_FAMILIES,
)
from .errors import AccountingError

CODE_RE = re.compile(r"^[0-9A-Za-z-]+$")

# رموز تعتمد عليها خدمات/تقارير قائمة — تغيير رمز حاملها مرفوض برسالة سبب.
# (القائمة موثقة؛ المراجع الديناميكية كـ journals.default_account_id تُفحص أيضًا).
# جُمعت من: sales/purchases/credit/docs/edu (1210/4010/2140/2141/2010/1310/4020/5010/5590)،
# currency (4095)، payroll (5110/5111/2150/2151/2160)، treasury/edu (101001).
# هذه الحسابات رقابية وظيفيًا (detail) أيًا كان عمقها — لا تُستنتج من العمق.
LOCKED_CODES = frozenset({
    "1210", "4010", "2140", "2141", "2010", "1310", "4095", "5010", "4020", "5590",
    "101001", "5110", "5111", "2150", "2151", "2160",
    "1519", "5130", "5160", "102001", "102002", "101002",
})

# تقارير تعتمد بادئات الرموز (توثيق خطر، لا قفل شامل).
PREFIX_DEPENDENT_REPORTS = (
    ("cash-flow", ("101", "102"), "تقرير التدفق النقدي يجمع الرموز ببادئة 101/102"),
)

# الدور -> الدور المطلوب للأب (None = بلا أب).
ROLE_PARENT = {
    "section": None,
    "general": "section",
    "subsidiary": "general",
    "detail": "subsidiary",
}

ROLE_LABEL_AR = {
    "section": "قسم محاسبي",
    "general": "أستاذ عام",
    "subsidiary": "أستاذ مساعد",
    "detail": "حساب تفصيلي",
}


class ChartError(AccountingError):
    code = "CHART_RULE"
    status = 422


class ChartConflict(AccountingError):
    code = "CHART_CONFLICT"
    status = 409


def family_of(account_type: str) -> str | None:
    return ACCOUNT_FAMILIES.get(account_type)


def lock_parent_row(account_id: uuid.UUID) -> None:
    """قفل صف الأب لمنع سباق إضافة ابن أثناء تحويل الأب إلى تفصيلي."""
    db.session.execute(
        text("SELECT id FROM accounts WHERE id = :i FOR UPDATE"),
        {"i": str(account_id)},
    )


def get_account(account_id: uuid.UUID) -> Account | None:
    return db.session.get(Account, account_id)


def _ensure_same_scope(acc: Account, *, tenant_id, entity_id, what: str = "الحساب") -> None:
    if str(acc.tenant_id) != str(tenant_id) or str(acc.entity_id) != str(entity_id):
        raise ChartError(f"{what} خارج نطاق الشركة الحالية")


def validate_parent(*, tenant_id, entity_id, parent: Account | None,
                    wanted_role: str | None, account_type: str,
                    self_id: uuid.UUID | None = None) -> None:
    """فحص الأب: الوجود والنطاق والحالة والدور والعائلة وعدم الدوران."""
    if parent is None:
        if wanted_role is not None and wanted_role != "section":
            raise ChartError(
                f"مستوى {ROLE_LABEL_AR[wanted_role]} يتطلب أبًا من مستوى "
                f"{ROLE_LABEL_AR[ROLE_PARENT[wanted_role]]}")
        return
    if parent.is_deleted:
        raise ChartError("الأب المختار محذوف")
    _ensure_same_scope(parent, tenant_id=tenant_id, entity_id=entity_id, what="الأب")
    if self_id is not None and parent.id == self_id:
        raise ChartError("لا يمكن ربط الحساب بنفسه")
    if self_id is not None and _is_descendant(ancestor_id=self_id, node_id=parent.id):
        raise ChartError("لا يمكن الربط بأحد الأحفاد (دورة)")
    if not parent.is_active or parent.status != "active":
        raise ChartError("الأب المختار غير نشط — اختر أبًا نشطًا أو فعّله أولًا")
    if parent.hierarchy_role == "detail":
        raise ChartError("الحساب التفصيلي لا يقبل أبناء — اختر أبًا تجميعيًا")
    if wanted_role is None:
        # امتداد فرع قديم: يبقى غير مصنف، مع فحص العائلة فقط.
        if family_of(account_type) != family_of(parent.account_type):
            raise ChartError(
                "التصنيف خارج عائلة الأب — حسابات الأصول تحت الأصول وهكذا")
        return
    need = ROLE_PARENT[wanted_role]
    if need is None:
        raise ChartError(f"مستوى {ROLE_LABEL_AR[wanted_role]} بلا أب")
    if parent.hierarchy_role != need:
        if parent.hierarchy_role is None:
            raise ChartError(
                f"مستوى {ROLE_LABEL_AR[wanted_role]} يتطلب أبًا مصنفًا "
                f"({ROLE_LABEL_AR[need]}) — الأب المختار قديم غير مصنف؛ "
                "وائمه أولًا أو أنشئ الحساب امتدادًا قديمًا")
        raise ChartError(
            f"الأب غير صالح: {ROLE_LABEL_AR[wanted_role]} يتطلب أبًا "
            f"{ROLE_LABEL_AR[need]} وليس {ROLE_LABEL_AR.get(parent.hierarchy_role, parent.hierarchy_role)}")
    if family_of(account_type) != family_of(parent.account_type):
        raise ChartError("التصنيف خارج عائلة القسم — راجع عائلة الأب")


def coerce_postable(wanted_role: str | None, is_postable) -> bool:
    """اشتقاق قابلية الترحيل من المستوى؛ رفض التناقض الصريح بدل تجاهله."""
    if wanted_role is None:
        return bool(is_postable) if is_postable is not None else True
    if wanted_role == "detail":
        if is_postable is not None and not _as_bool(is_postable):
            raise ChartError("الحساب التفصيلي يقبل الحركات حتمًا — لا يمكن جعله تجميعيًا")
        return True
    if is_postable is not None and _as_bool(is_postable):
        raise ChartError(
            f"مستوى {ROLE_LABEL_AR[wanted_role]} تجميعي ولا يقبل الحركات")
    return False


def _as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def validate_code(code: str) -> str:
    code = str(code or "").strip()
    if not code:
        raise ChartError("الرمز مطلوب")
    if not CODE_RE.match(code):
        raise ChartError("الرمز نص (أرقام/حروف/-) يحفظ الأصفار البادئة")
    return code


def _is_descendant(*, ancestor_id: uuid.UUID, node_id: uuid.UUID) -> bool:
    row = db.session.execute(text("""
        WITH RECURSIVE c AS (
          SELECT id, parent_id FROM accounts WHERE id = :node
          UNION ALL
          SELECT a.id, a.parent_id FROM accounts a JOIN c ON a.id = c.parent_id
        ) SELECT 1 FROM c WHERE id = :anc
    """), {"node": str(node_id), "anc": str(ancestor_id)}).first()
    return row is not None


def subtree_ids(root_id: uuid.UUID) -> list[uuid.UUID]:
    rows = db.session.execute(text("""
        WITH RECURSIVE c AS (
          SELECT id FROM accounts WHERE id = :root AND is_deleted = FALSE
          UNION ALL
          SELECT a.id FROM accounts a JOIN c ON a.parent_id = c.id
          WHERE a.is_deleted = FALSE
        ) SELECT id FROM c
    """), {"root": str(root_id)}).fetchall()
    return [r[0] for r in rows]


def subtree_has_lines(root_id: uuid.UUID) -> bool:
    return db.session.execute(text("""
        WITH RECURSIVE c AS (
          SELECT id FROM accounts WHERE id = :root AND is_deleted = FALSE
          UNION ALL
          SELECT a.id FROM accounts a JOIN c ON a.parent_id = c.id
          WHERE a.is_deleted = FALSE
        ) SELECT 1 FROM journal_lines l JOIN c ON c.id = l.account_id
          WHERE l.is_deleted = FALSE LIMIT 1
    """), {"root": str(root_id)}).first() is not None


def account_use_count(account_id: uuid.UUID) -> int:
    row = db.session.execute(text(
        "SELECT count(*) FROM journal_lines WHERE account_id = :i AND is_deleted = FALSE"),
        {"i": str(account_id)}).first()
    return int(row[0]) if row else 0


def dynamic_code_refs(acc: Account) -> list[str]:
    """مراجع تشغيلية تمنع تغيير الرمز (رسائل أسباب صريحة)."""
    refs: list[str] = []
    if acc.code in LOCKED_CODES:
        refs.append("رمز معتمد في خدمات الترحيل (مبيعات/مشتريات/عملات)")
    j = db.session.execute(text(
        "SELECT code FROM journals WHERE default_account_id = :i AND is_deleted = FALSE LIMIT 1"),
        {"i": str(acc.id)}).first()
    if j:
        refs.append(f"الحساب الافتراضي للدفتر {j[0]}")
    pa = db.session.execute(text(
        "SELECT 1 FROM product_accounts WHERE account_id = :i AND is_deleted = FALSE LIMIT 1"),
        {"i": str(acc.id)}).first()
    if pa:
        refs.append("مرتبط بأصناف عبر product_accounts")
    return refs


def refresh_is_leaf(account_ids: set[uuid.UUID]) -> None:
    """إعادة حساب is_leaf للآباء المتأثرة (المشغل لا يفعل ذلك)."""
    for aid in account_ids:
        if aid is None:
            continue
        has = db.session.execute(text(
            "SELECT 1 FROM accounts WHERE parent_id = :i AND is_deleted = FALSE LIMIT 1"),
            {"i": str(aid)}).first()
        db.session.execute(text(
            "UPDATE accounts SET is_leaf = :v WHERE id = :i"),
            {"v": not bool(has), "i": str(aid)})


def rebuild_closure(account_id: uuid.UUID) -> None:
    """إعادة بناء علاقات الإغلاق للعقدة وأحفادها ضمن المعاملة الحالية."""
    acc = get_account(account_id)
    if acc is None:
        return
    ids = subtree_ids(account_id)
    if ids:
        db.session.execute(text(
            "DELETE FROM account_hierarchy WHERE descendant_id IN :ids"
        ).bindparams(), {"ids": tuple(str(i) for i in ids)})
    for aid in ids:
        a = get_account(aid)
        chain: list[tuple[uuid.UUID, int]] = [(a.id, 0)]
        p = a.parent_id
        d = 1
        while p is not None:
            chain.append((p, d))
            prow = db.session.execute(
                text("SELECT parent_id FROM accounts WHERE id = :i"),
                {"i": str(p)}).first()
            p = prow[0] if prow else None
            d += 1
        for anc_id, depth in chain:
            db.session.execute(text("""
                INSERT INTO account_hierarchy
                  (ancestor_id, descendant_id, tenant_id, entity_id, depth,
                   sort_order, is_leaf, created_by, updated_by, version, is_deleted)
                VALUES (:a, :d, :t, :e, :depth, 0, :leaf, :u, :u, 1, FALSE)
                ON CONFLICT (ancestor_id, descendant_id) DO UPDATE
                  SET depth = EXCLUDED.depth, tenant_id = EXCLUDED.tenant_id,
                      entity_id = EXCLUDED.entity_id, is_deleted = FALSE
            """), {"a": str(anc_id), "d": str(aid), "t": str(a.tenant_id),
                   "e": str(a.entity_id), "depth": depth,
                   "leaf": True, "u": str(a.updated_by or a.created_by)})


def refresh_subtree_paths(root: Account) -> None:
    """تحديث path/level للأحفاد بعد نقل/إعادة ترميز (المشغل يغطي الصف نفسه فقط)."""
    rows = db.session.execute(text("""
        WITH RECURSIVE c AS (
          SELECT id, parent_id FROM accounts WHERE id = :root AND is_deleted = FALSE
          UNION ALL
          SELECT a.id, a.parent_id FROM accounts a JOIN c ON a.parent_id = c.id
          WHERE a.is_deleted = FALSE
        ) SELECT id FROM c WHERE id <> :root
    """), {"root": str(root.id)}).fetchall()
    for (aid,) in rows:
        a = get_account(aid)
        if a is None or a.parent_id is None:
            continue
        p = get_account(a.parent_id)
        if p is None:
            continue
        a.path = f"{p.path}.{a.code}"
        a.level = (p.level or 1) + 1
    db.session.flush()


def ensure_entity_access(entity_id: uuid.UUID, tenant_id) -> None:
    """التحقق من انتماء الكيان للمؤسسة (لا تكفي صحة UUID)."""
    from ..models.entity import Entity
    ent = db.session.get(Entity, entity_id)
    if ent is None or ent.is_deleted or str(ent.tenant_id) != str(tenant_id):
        raise ChartError("الكيان خارج نطاق مؤسستك")


def check_postable(acc: Account, posting_date, *, is_manual_entry: bool = True) -> None:
    """فحص موحد لصلاحية الحساب بتاريخ الترحيل (مسودة وترحيل).

    - status يجب أن يكون active وis_active صحيحًا (توحيد معنى الحقلين:
      المشغل القديم يفحص is_active فقط؛ السياسة الجديدة تتطلب الاثنين).
    - is_postable إلزامي دائمًا. allow_manual يُحسم من مسار الخادم
      (is_manual_entry) لا من أي قيمة يرسلها العميل.
    - ملاحظة سياسة موثقة: valid_from/valid_to معلومات تشخيصية (تظهر في
      dry-run) وليست مانع ترحيل — المشغل لا يفحصها، وفرضها بأثر رجعي
      يكسر قيود الافتتاح المؤرخة قبل إنشاء الحساب. أي تشديد مستقبلي
      يتطلب migration + تحديث المشغل مع مراجعة البيانات.
    """
    if acc.is_deleted:
        raise ChartError(f"الحساب {acc.code} محذوف")
    if acc.status != "active" or not acc.is_active:
        raise ChartError(f"الحساب {acc.code} غير نشط (الحالة: {acc.status})")
    if not acc.is_postable:
        raise ChartError(f"الحساب {acc.code} تجميعي ولا يقبل الحركات")
    if is_manual_entry and not acc.allow_manual:
        raise ChartError(f"الحساب {acc.code} رقابي — الترحيل اليدوي ممنوع")


def diagnose(*, tenant_id, entity_id) -> dict:
    """فحص قراءة فقط: صحيح / غير مصنف / خطر — دون أي تغيير."""
    tenant_id, entity_id = str(tenant_id), str(entity_id)
    rows = db.session.execute(text("""
        SELECT id, code, name_ar, parent_id, level, path, is_leaf, account_type,
               control_type, normal_balance, is_postable, allow_manual,
               require_partner, is_active, status, hierarchy_role
        FROM accounts
        WHERE tenant_id = :t AND entity_id = :e AND is_deleted = FALSE
        ORDER BY path
    """), {"t": tenant_id, "e": entity_id}).fetchall()
    by_id = {str(r[0]): r for r in rows}
    healthy, unclassified, risky = [], [], []
    for r in rows:
        (aid, code, name, parent, level, path, leaf, atype, ctype,
         nb, postable, manual, partner, active, status, role) = r
        aid = str(aid)
        problems: list[str] = []
        if parent is not None:
            p = by_id.get(str(parent))
            if p is None:
                problems.append("أب مفقود/محذوف")
            if p is not None and family_of(atype) != family_of(p[7]):
                problems.append("عائلة التصنيف تخالف الأب")
            if p is not None and str(p[0]) == aid:
                problems.append("ربط ذاتي")
        if role is None:
            entry = {"id": aid, "code": code, "name_ar": name, "problems": problems}
            if problems:
                risky.append(entry)
            else:
                unclassified.append(entry)
            continue
        if role not in HIERARCHY_ROLES:
            problems.append(f"دور غير معروف: {role}")
        else:
            need = ROLE_PARENT[role]
            if need is None and parent is not None:
                problems.append("القسم يجب أن يكون بلا أب")
            if need is not None:
                if parent is None:
                    problems.append(f"يتطلب أبًا {ROLE_LABEL_AR[need]}")
                else:
                    p = by_id.get(str(parent))
                    if p is not None and p[15] != need:
                        problems.append(f"الأب ليس {ROLE_LABEL_AR[need]}")
        want_post = (role == "detail")
        if bool(postable) != want_post and role in HIERARCHY_ROLES:
            problems.append("قابلية الترحيل تناقض المستوى")
        if role == "detail" and not leaf:
            problems.append("تفصيلي له أبناء")
        entry = {"id": aid, "code": code, "name_ar": name,
                 "role": role, "problems": problems}
        (risky if problems else healthy).append(entry)
    # كشف الدورات عبر المسارات
    cycles = _find_cycles(by_id)
    for c in cycles:
        risky.append({"id": c, "code": by_id[c][1], "name_ar": by_id[c][2],
                      "problems": ["دورة في السلسلة"]})
    return {"healthy": healthy, "unclassified": unclassified, "risky": risky,
            "counts": {"healthy": len(healthy), "unclassified": len(unclassified),
                       "risky": len(risky), "total": len(rows)}}


def _find_cycles(by_id: dict) -> list[str]:
    found: list[str] = []
    for aid, r in by_id.items():
        seen = set()
        cur = r[3]
        while cur is not None:
            c = str(cur)
            if c == aid or c in seen:
                found.append(aid)
                break
            seen.add(c)
            pr = by_id.get(c)
            cur = pr[3] if pr else None
    return found
