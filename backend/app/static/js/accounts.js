/* accounts.js — نموذج دليل الحسابات: قوائم متتالية + تحقق + حفظ */
(function () {
  function sGet(k) {
    try { if (window.__store) return window.__store.get(k); } catch (e) { /* ignore */ }
    try { return sessionStorage.getItem(k); } catch (e) { return null; }
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }
  const SUGGEST = { asset: "debit", expense: "debit", contra_liability: "debit", contra_equity: "debit", contra_income: "debit",
    liability: "credit", equity: "credit", income: "credit", contra_asset: "credit", contra_expense: "credit" };
  const ROLE_HINT = { section: "تجميعي — بلا أب ولا حركات", general: "تجميعي — أبوه قسم ولا يقبل الحركات",
    subsidiary: "تجميعي — أبوه أستاذ عام ولا يقبل الحركات", detail: "يقبل الحركات — أبوه أستاذ مساعد وبلا أبناء" };
  const NEED = { general: ["section"], subsidiary: ["section", "general"], detail: ["section", "general", "subsidiary"] };

  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("account-form");
    if (!form) return;
    const role = document.getElementById("acc-role");
    const badge = document.getElementById("postable-badge");
    const hint = document.getElementById("role-hint");
    const alertBox = document.getElementById("acc-alert");
    const submitBtn = document.getElementById("acc-submit");
    const sels = { section: document.getElementById("sel-section"), general: document.getElementById("sel-general"), subsidiary: document.getElementById("sel-subsidiary") };
    const seq = { section: 0, general: 0, subsidiary: 0 };
    const editId = form.dataset.account || null;
    let balTouched = false;
    let loadedVersion = null;

    function note(msg, kind) {
      alertBox.innerHTML = msg ? `<div class="alert alert-${kind || "warn"}">${esc(msg)}</div>` : "";
    }
    function entity() { return sGet("entity_id"); }
    function needLogin() {
      if (!sGet("access_token")) { note("انتهت الجلسة — سجّل الدخول أولًا", "error"); return true; }
      if (!entity()) { note("لا يوجد كيان محدد — أعد تسجيل الدخول", "error"); return true; }
      return false;
    }
    function updateBadge() {
      const r = role.value;
      if (r === "__legacy") {
        badge.textContent = "غير مصنف (قديم)";
        hint.textContent = "علاقاته الحالية محفوظة كما هي حتى المواءمة";
      } else {
        badge.textContent = r === "detail" ? "يقبل الحركات" : (r ? "تجميعي — لا يقبل الحركات" : "—");
        hint.textContent = ROLE_HINT[r] || "";
      }
      Object.entries(sels).forEach(([k]) => {
        const wrap = document.querySelector(`[data-anc="${k}"]`);
        if (wrap) wrap.hidden = !(NEED[r] || []).includes(k);
      });
    }
    async function api(path) {
      const res = await fetch(path, { headers: window.apiHeaders() });
      if (res.status === 401) {
        note("انتهت الجلسة — سجّل الدخول مجددًا", "error");
        setTimeout(() => { window.location.href = "/login"; }, 800);
        throw new Error("API 401");
      }
      if (!res.ok) throw new Error("API " + res.status);
      const j = await res.json();
      return (j && typeof j === "object" && "data" in j) ? j.data : j;
    }
    async function loadRole(r, parentId, preset) {
      const my = ++seq[r];
      const sel = sels[r];
      sel.innerHTML = `<option value="">جارٍ التحميل…</option>`;
      try {
        let url = `/api/v1/accounts?entity_id=${encodeURIComponent(entity())}&role=${r}&page=1`;
        if (parentId) url += `&parent_id=${encodeURIComponent(parentId)}`;
        const d = await api(url);
        if (my !== seq[r]) return; // استجابة قديمة — تُتجاهل (منع السباق)
        const list = (d && d.data) || d || [];
        sel.innerHTML = `<option value="">اختر…</option>` +
          list.map((a) => `<option value="${esc(a.id)}">${esc(a.code)} — ${esc(a.name_ar)}</option>`).join("");
        if (preset) {
          if (![...sel.options].some((o) => o.value === preset)) {
            const extra = (await fetchPreset(r, preset));
            if (extra) sel.insertAdjacentHTML("beforeend",
              `<option value="${esc(extra.id)}">${esc(extra.code)} — ${esc(extra.name_ar)}</option>`);
          }
          sel.value = preset;
        }
      } catch (e) { if (my === seq[r]) sel.innerHTML = `<option value="">تعذر التحميل</option>`; }
    }
    async function fetchPreset(r, id) {
      try { return await api(`/api/v1/accounts/${encodeURIComponent(id)}`); }
      catch (e) { return null; }
    }
    async function searchRole(r, q) {
      const my = ++seq[r];
      const sel = sels[r];
      try {
        const list = await api(`/api/v1/accounts/search?entity_id=${encodeURIComponent(entity())}&q=${encodeURIComponent(q)}`);
        if (my !== seq[r]) return;
        const items = (Array.isArray(list) ? list : []).filter((a) => a.hierarchy_role === r);
        sel.innerHTML = `<option value="">اختر…</option>` +
          items.map((a) => `<option value="${esc(a.id)}">${esc(a.code)} — ${esc(a.name_ar)}</option>`).join("");
      } catch (e) { /* ignore */ }
    }
    function parentFor(roleValue) {
      if (roleValue === "section") return null;
      if (roleValue === "general") return sels.section.value || null;
      if (roleValue === "subsidiary") return sels.general.value || null;
      if (roleValue === "detail") return sels.subsidiary.value || null;
      return undefined;
    }
    role.addEventListener("change", () => {
      updateBadge(); note("");
      const r = role.value;
      Object.values(sels).forEach((s) => { s.innerHTML = `<option value="">اختر…</option>`; });
      if ((NEED[r] || []).includes("section")) loadRole("section", null);
    });
    sels.section.addEventListener("change", () => {
      sels.general.innerHTML = `<option value="">اختر…</option>`;
      sels.subsidiary.innerHTML = `<option value="">اختر…</option>`;
      if (sels.section.value && (NEED[role.value] || []).includes("general")) loadRole("general", sels.section.value);
    });
    sels.general.addEventListener("change", () => {
      sels.subsidiary.innerHTML = `<option value="">اختر…</option>`;
      if (sels.general.value && (NEED[role.value] || []).includes("subsidiary")) loadRole("subsidiary", sels.general.value);
    });
    ["section", "general", "subsidiary"].forEach((r) => {
      const q = document.getElementById("q-" + r);
      if (q) q.addEventListener("input", () => {
        const v = q.value.trim();
        if (v.length < 2) return;
        searchRole(r, v);
      });
    });
    document.getElementById("f-type").addEventListener("change", (e) => {
      if (!balTouched && SUGGEST[e.target.value]) document.getElementById("f-bal").value = SUGGEST[e.target.value];
    });
    document.getElementById("f-bal").addEventListener("change", () => { balTouched = true; });

    // تعبئة التعديل: الحساب ثم سلسلة الآباء ثم الخيارات
    // إنشاء تابع مسبق: ?parent=<id> يثبت الدور المناسب والأب
    const CHILD_OF = { section: "general", general: "subsidiary", subsidiary: "detail" };
    (async function presetParent() {
      if (editId) return;
      let pid = null;
      try { pid = new URLSearchParams(window.location.search).get("parent"); } catch (e) { /* ignore */ }
      if (!pid || !sGet("access_token")) return;
      try {
        const p = await api(`/api/v1/accounts/${encodeURIComponent(pid)}`);
        if (!p || p.is_deleted) return;
        if (p.hierarchy_role === "detail") {
          note("الحساب التفصيلي لا يقبل أبناء — اختر أبًا تجميعيًا", "error");
          return;
        }
        if (!p.hierarchy_role) {
          note("الأب المختار قديم غير مصنف — اختر المستوى والأب يدويًا", "warn");
          return;
        }
        role.value = CHILD_OF[p.hierarchy_role];
        role.disabled = true;
        updateBadge();
        const anc = p.ancestors || [];
        const byRole = {};
        anc.forEach((a) => { if (a.hierarchy_role) byRole[a.hierarchy_role] = a.id; });
        byRole[p.hierarchy_role] = p.id;
        if (byRole.section) await loadRole("section", null, byRole.section);
        if (role.value !== "section" && byRole.general) await loadRole("general", byRole.section, byRole.general);
        if (role.value === "detail" && byRole.subsidiary) await loadRole("subsidiary", byRole.general, byRole.subsidiary);
        note(`إضافة تابع تحت: ${p.code} — ${p.name_ar}`, "warn");
      } catch (e) { /* ignore */ }
    })();
    (async function prefill() {
      updateBadge();
      if (!editId || !sGet("access_token")) return;
      try {
        const d = await api(`/api/v1/accounts/${encodeURIComponent(editId)}`);
        loadedVersion = d.version;
        document.getElementById("f-code").value = d.code || "";
        document.getElementById("f-name").value = d.name_ar || "";
        document.getElementById("f-name-en").value = d.name_en || "";
        document.getElementById("f-type").value = d.account_type || "";
        document.getElementById("f-bal").value = d.normal_balance || "";
        balTouched = true;
        if (document.getElementById("f-status")) document.getElementById("f-status").value = d.status || "active";
        document.getElementById("f-ctl").value = d.control_type || "general";
        document.getElementById("f-cur").value = d.currency_restriction || "";
        document.getElementById("f-manual").checked = d.allow_manual !== false;
        document.getElementById("f-partner").checked = d.require_partner === true;
        document.getElementById("f-notes").value = d.notes || "";
        const anc = d.ancestors || [];
        if (!d.hierarchy_role) {
          document.getElementById("wrap-legacy").hidden = false;
          document.getElementById("legacy-note").textContent =
            "حساب قديم غير مصنف — علاقاته الحالية: " +
            (anc.length ? anc.map((a) => `${a.code} ${a.name_ar}`).join(" ← ") : "بلا أب") +
            ". اختر مستوى لمواءمته (قد يرفض الخادم التغيير الهيكلي لحساب مستخدم).";
          role.insertAdjacentHTML("beforeend", `<option value="__legacy" selected>غير مصنف (قديم)</option>`);
          updateBadge();
        } else {
          role.value = d.hierarchy_role;
          updateBadge();
          const byRole = {};
          anc.forEach((a) => { if (a.hierarchy_role) byRole[a.hierarchy_role] = a.id; });
          if (byRole.section) { await loadRole("section", null, byRole.section); }
          if (role.value !== "section" && byRole.general) { await loadRole("general", byRole.section, byRole.general); }
          if (role.value === "detail" && byRole.subsidiary) { await loadRole("subsidiary", byRole.general, byRole.subsidiary); }
          else if ((NEED[role.value] || []).includes("section") && !byRole.section) loadRole("section", null);
        }
        try {
          const b = await api(`/api/v1/accounts/${encodeURIComponent(editId)}/balance?mode=direct`);
          if ((b.debit || 0) + (b.credit || 0) > 0) {
            note("تنبيه: للحساب حركات مرحلة — الرمز والتصنيف والمستوى مقفلة تغييرها دون مسار مواءمة.", "warn");
            document.getElementById("f-code").setAttribute("aria-readonly", "true");
          }
        } catch (e) { /* ignore */ }
      } catch (e) { note("تعذر تحميل بيانات الحساب", "error"); }
    })();

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (form.dataset.busy === "1") return;
      note("");
      if (needLogin()) return;
      const r = role.value;
      if (!r) { note("اختر مستوى الحساب", "error"); role.focus(); return; }
      const keepingLegacy = editId && r === "__legacy";
      const roleToSend = keepingLegacy ? null : r;
      const pid = keepingLegacy ? null : parentFor(r);
      if (pid === undefined) { note("اختر مستوى الحساب", "error"); return; }
      if (roleToSend !== null && r !== "section" && !pid) { note("اختر الأب المطلوب للمستوى", "error"); return; }
      for (const id of ["f-name", "f-type", "f-bal"]) {
        const el = document.getElementById(id);
        if (!String(el.value || "").trim()) { note("أكمل الحقول المطلوبة (بعلامة *)", "error"); el.focus(); return; }
      }
      const payload = { entity_id: entity(),
        name_ar: document.getElementById("f-name").value.trim(),
        name_en: document.getElementById("f-name-en").value.trim() || null,
        account_type: document.getElementById("f-type").value,
        normal_balance: document.getElementById("f-bal").value,
        control_type: document.getElementById("f-ctl").value,
        currency_restriction: document.getElementById("f-cur").value || null,
        allow_manual: document.getElementById("f-manual").checked,
        require_partner: document.getElementById("f-partner").checked,
        notes: document.getElementById("f-notes").value.trim() || null };
      const codeVal = document.getElementById("f-code").value.trim();
      if (codeVal) payload.code = codeVal;
      if (roleToSend) payload.hierarchy_role = roleToSend;
      if (pid) payload.parent_id = pid;
      if (editId) {
        payload.status = document.getElementById("f-status").value;
        if (loadedVersion !== null && loadedVersion !== undefined) payload.version = loadedVersion;
        if (keepingLegacy) { /* إبقاء العلاقة القديمة: لا دور ولا أب */ }
        else if (r === "section") payload.parent_id = null;
      }
      form.dataset.busy = "1";
      submitBtn.disabled = true;
      try {
        const res = await fetch(form.dataset.apiPost, { method: form.dataset.method || "POST",
          headers: window.apiHeaders(), body: JSON.stringify(payload) });
        const data = await res.json().catch(() => ({}));
        if (res.status === 201 || res.ok) {
          window.toast("تم الحفظ بنجاح", "success");
          const id = data.data && data.data.id;
          setTimeout(() => { window.location.href = (form.dataset.redirect || "/accounts") + (id && !editId ? `/${id}` : (editId ? `/${editId}` : "")); }, 300);
        } else if (res.status === 401) { note("انتهت الجلسة — سجّل الدخول مجددًا", "error"); }
        else if (res.status === 409) { note((data.error && (data.error.message || data.error.code)) || "تعارض — راجع البيانات", "error"); }
        else note((data.error && (data.error.message || data.error.code)) || "تعذر الحفظ", "error");
      } catch (err) { note("تعذر الاتصال بالخادم — لم يُحفظ شيء", "error"); }
      finally { form.dataset.busy = "0"; submitBtn.disabled = false; }
    });
  });
})();
