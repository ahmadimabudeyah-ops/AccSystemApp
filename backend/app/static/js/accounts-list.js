/* accounts-list.js — بطاقات + فلاتر + تحديد + إجراءات جماعية (تعطيل/تفعيل فقط) */
(function () {
  function sGet(k) {
    try { if (window.__store) return window.__store.get(k); } catch (e) { /* ignore */ }
    try { return sessionStorage.getItem(k); } catch (e) { return null; }
  }
  document.addEventListener("DOMContentLoaded", () => {
    const tbody = document.querySelector('tbody[data-api="accounts"]');
    if (!tbody) return;
    const qs = new URLSearchParams(window.location.search);
    const setFilter = (id, param) => {
      const el = document.getElementById(id);
      if (el && qs.get(param)) el.value = qs.get(param);
      if (el) el.addEventListener("change", () => {
        const nq = new URLSearchParams(window.location.search);
        if (el.value) nq.set(param, el.value); else nq.delete(param);
        nq.delete("page");
        window.location.search = nq.toString();
      });
    };
    setFilter("flt-role", "role");
    setFilter("flt-type", "type");
    setFilter("flt-bal", "bal");
    setFilter("flt-status", "status");
    const clearer = document.getElementById("flt-clear");
    if (clearer) clearer.addEventListener("click", () => { window.location.search = ""; });
    const size = document.getElementById("page-size");
    if (size) {
      if (qs.get("size")) size.value = qs.get("size");
      size.addEventListener("change", () => {
        const nq = new URLSearchParams(window.location.search);
        nq.set("size", size.value);
        nq.delete("page");
        window.location.search = nq.toString();
      });
    }
    // البطاقات
    (async () => {
      try {
        const eid = sGet("entity_id");
        if (!eid || !sGet("access_token")) return;
        const res = await fetch(`/api/v1/accounts/stats?entity_id=${encodeURIComponent(eid)}`,
          { headers: window.apiHeaders() });
        if (!res.ok) return;
        const d = (await res.json()).data || {};
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        set("st-total", d.total);
        set("st-sections", d.sections);
        set("st-generals", d.generals);
        set("st-details", d.details);
      } catch (e) { /* ignore */ }
    })();
    // التحديد
    const countEl = document.getElementById("sel-count");
    const updateCount = () => {
      const n = tbody.querySelectorAll('input[type="checkbox"][data-id]:checked').length;
      if (countEl) countEl.textContent = n;
    };
    tbody.addEventListener("change", (e) => {
      if (e.target.matches('input[type="checkbox"][data-id]')) updateCount();
    });
    const syncAll = (master) => {
      if (!master) return;
      master.addEventListener("change", () => {
        tbody.querySelectorAll('input[type="checkbox"][data-id]').forEach((c) => { c.checked = master.checked; });
        const other = master.id === "sel-all"
          ? document.getElementById("sel-all-2") : document.getElementById("sel-all");
        if (other) other.checked = master.checked;
        updateCount();
      });
    };
    syncAll(document.getElementById("sel-all"));
    syncAll(document.getElementById("sel-all-2"));
    const bulk = async (active) => {
      const ids = [...tbody.querySelectorAll('input[type="checkbox"][data-id]:checked')]
        .map((c) => c.dataset.id);
      if (!ids.length) { window.toast("حدد حسابًا واحدًا على الأقل", "error"); return; }
      if (!confirm(`تأكيد ${active ? "تفعيل" : "تعطيل"} ${ids.length} حسابًا؟ (التعطيل لا يمحو التاريخ)`)) return;
      try {
        const res = await fetch("/api/v1/accounts/bulk-status", { method: "POST",
          headers: window.apiHeaders(),
          body: JSON.stringify({ ids, is_active: active, status: active ? "active" : "inactive" }) });
        const d = await res.json().catch(() => ({}));
        if (res.ok) {
          window.toast(`تم: ${d.data.ok} — فشل: ${d.data.failed}`, d.data.failed ? "error" : "success");
          setTimeout(() => window.location.reload(), 600);
        } else window.toast((d.error && (d.error.message || d.error.code)) || "تعذر التنفيذ", "error");
      } catch (e) { window.toast("تعذر الاتصال", "error"); }
    };
    const bd = document.getElementById("bulk-deactivate");
    const ba = document.getElementById("bulk-activate");
    if (bd) bd.addEventListener("click", () => bulk(false));
    if (ba) ba.addEventListener("click", () => bulk(true));
  });
})();
