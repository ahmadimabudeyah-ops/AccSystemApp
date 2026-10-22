/* forms.js — تحقق النماذج بالعربية + إرسال القيد والدخول */
(function () {
  function escAttr(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function showError(input, message) {
    input.classList.add("invalid");
    let err = input.parentElement.querySelector(".form-error");
    if (!err) {
      err = document.createElement("div");
      err.className = "form-error";
      input.parentElement.appendChild(err);
    }
    err.textContent = message;
    err.hidden = false;
  }
  function clearError(input) {
    input.classList.remove("invalid");
    const err = input.parentElement.querySelector(".form-error");
    if (err) err.hidden = true;
  }
  window.validateEmail = function (value) {
    return /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(value || "");
  };

  document.addEventListener("DOMContentLoaded", () => {
    /* ملاحظة: الدخول يُدار حصريًا من سكربت مضمّن في login.html (يعمل بلا ملفات خارجية) */

    const entryForm = document.getElementById("entry-form");
    if (entryForm) {
      entryForm.addEventListener("input", updateDiff);
      entryForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const diff = document.getElementById("entry-diff").textContent;
        if (diff !== "0.000" && diff !== "0") { window.toast("القيد غير متوازن — راجع المجاميع", "error"); return; }
        const fd = new FormData(entryForm);
        const lines = [];
        document.querySelectorAll("#entry-lines tbody tr").forEach((tr) => {
          const acc = tr.querySelector('select[name="account"]').value;
          const d = parseFloat(tr.querySelector('input[name="debit"]').value || 0);
          const c = parseFloat(tr.querySelector('input[name="credit"]').value || 0);
          if (acc && (d > 0 || c > 0)) lines.push({ account_id: acc, debit: d, credit: c });
        });
        try {
          const res = await fetch("/api/v1/journal-entries", {
            method: "POST", headers: Object.assign(window.apiHeaders(), {
              "Idempotency-Key": (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())) }),
            body: JSON.stringify({
              entity_id: storeGet("entity_id"),
              journal_id: fd.get("journal_id"), posting_date: fd.get("posting_date"),
              document_date: fd.get("posting_date"), description: fd.get("description"), lines }),
          });
          const data = await res.json();
          if (res.status === 201) { window.location.href = "/journal-entries/" + data.data.id; }
          else window.toast((data.error && data.error.code) || "تعذر الحفظ", "error");
        } catch (err) { window.toast("تعذر الاتصال بالخادم", "error"); }
      });
    }
  });

  window.addLine = function () {
    const tbody = document.querySelector("#entry-lines tbody");
    const row = tbody.rows[0].cloneNode(true);
    row.querySelectorAll("input").forEach((i) => { i.value = i.type === "number" ? 0 : ""; });
    tbody.appendChild(row);
  };
  window.removeLine = function (btn) {
    const tbody = btn.closest("tbody");
    if (tbody.rows.length > 2 || true) {
      if (tbody.rows.length === 1) { window.toast("يجب أن يحوي القيد سطرين على الأقل", "error"); return; }
      btn.closest("tr").remove();
      updateDiff();
    }
  };
  function updateDiff() {
    let d = 0, c = 0;
    document.querySelectorAll("#entry-lines tbody tr").forEach((tr) => {
      d += parseFloat(tr.querySelector('input[name="debit"]').value || 0);
      c += parseFloat(tr.querySelector('input[name="credit"]').value || 0);
    });
    document.getElementById("entry-diff").textContent = (d - c).toFixed(3);
  }

  /* ---- document forms: sales invoices + purchase bills with lines ---- */
  window.addInvLine = function () {
    const tbody = document.querySelector("#inv-lines tbody");
    const clone = tbody.rows[0].cloneNode(true);
    clone.querySelectorAll("input").forEach((i) => { i.value = i.name === "qty" ? 1 : 0; });
    clone.querySelectorAll("select").forEach((s) => { s.selectedIndex = 0; });
    tbody.appendChild(clone);
    invTotal();
  };
  window.invTotal = function () {
    let t = 0;
    document.querySelectorAll("#inv-lines tbody tr").forEach((tr) => {
      const q = parseFloat(tr.querySelector('input[name="qty"]')?.value || 0);
      const p = parseFloat(tr.querySelector('input[name="price"]')?.value || 0);
      const d = parseFloat(tr.querySelector('input[name="disc"]')?.value || 0);
      let rate = 0;
      const taxSel = tr.querySelector('select[name="tax"]');
      if (taxSel && taxSel.selectedOptions.length) {
        rate = parseFloat(taxSel.selectedOptions[0].dataset.rate || 0);
      }
      const net = q * p * (1 - d / 100);
      t += net * (1 + rate / 100);
    });
    const el = document.getElementById("inv-total");
    if (el) el.textContent = t.toFixed(3);
  };
  async function fillDocOptions(form) {
    const eid = storeGet("entity_id");
    const get = async (url) => (await (await fetch(url, { headers: window.apiHeaders() })).json()).data || [];
    const getAll = async (base, maxPages) => {
      const out = [];
      const sep = base.includes("?") ? "&" : "?";
      for (let p = 1; p <= (maxPages || 10); p++) {
        const env = await (await fetch(`${base}${sep}page=${p}`, { headers: window.apiHeaders() })).json().catch(() => ({}));
        const rows = (env && env.data) || [];
        out.push(...rows);
        if (env.total == null || out.length >= env.total || !rows.length) break;
      }
      return out;
    };
    const kind = form.dataset.kind;
    const partyUrl = kind === "sales" ? "/api/v1/parties?type=customer" : "/api/v1/parties?type=supplier";
    const [parties, products, taxes] = await Promise.all([
      getAll(partyUrl), getAll(`/api/v1/products?entity_id=${eid}`), get("/api/v1/taxes").catch(() => []),
    ]);
    const pSel = form.querySelector('select[name="customer_id"]');
    const quickLabel = kind === "sales" ? "+ عميل جديد…" : "+ مورد جديد…";
    if (pSel) {
      pSel.innerHTML = `<option value="">اختر…</option>` +
        parties.map((p) => `<option value="${p.id}">${p.code} — ${p.name_ar}</option>`).join("") +
        `<option value="__new__">${quickLabel}</option>`;
      pSel.addEventListener("change", async () => {
        if (pSel.value !== "__new__") return;
        const name = window.prompt(kind === "sales" ? "اسم العميل الجديد:" : "اسم المورد الجديد:");
        if (!name || !name.trim()) { pSel.value = ""; return; }
        try {
          const res = await fetch("/api/v1/parties", {
            method: "POST", headers: window.apiHeaders(),
            body: JSON.stringify({ entity_id: eid, name_ar: name.trim(),
              party_type: kind === "sales" ? "customer" : "supplier" }),
          });
          const d = await res.json().catch(() => ({}));
          if (res.ok && d.data) {
            pSel.insertAdjacentHTML("beforeend",
              `<option value="${escAttr(d.data.id)}">${escAttr(d.data.code)} — ${escAttr(d.data.name_ar)}</option>`);
            pSel.value = d.data.id;
            window.toast("تمت إضافة الطرف بنجاح", "success");
          } else {
            window.toast((d.error && (d.error.message || d.error.code)) || "تعذر إضافة الطرف", "error");
            pSel.value = "";
          }
        } catch (err) { window.toast("تعذر الاتصال بالخادم", "error"); pSel.value = ""; }
      });
    }
    const pOpts = products.map((p) => `<option value="${p.id}">${p.code} — ${p.name_ar}</option>`).join("");
    form.querySelectorAll('select[name="product"]').forEach((s) => { s.innerHTML = pOpts; });
    const tOpts = `<option value="" data-rate="0">بلا</option>` +
      (taxes.map ? taxes.map((t) => `<option value="${t.id}" data-rate="${t.rate || 0}">${t.code} ${t.rate}%</option>`).join("") : "");
    form.querySelectorAll('select[name="tax"]').forEach((s) => { s.innerHTML = tOpts; });
  }
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("invoice-form");
    if (!form || !storeGet("access_token")) return;
    fillDocOptions(form);
    form.addEventListener("input", invTotal);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const kind = form.dataset.kind;
      const fd = new FormData(form);
      const lines = [];
      document.querySelectorAll("#inv-lines tbody tr").forEach((tr) => {
        const pid = tr.querySelector('select[name="product"]').value;
        const qty = parseFloat(tr.querySelector('input[name="qty"]').value || 0);
        const price = parseFloat(tr.querySelector('input[name="price"]').value || 0);
        if (!pid || qty <= 0) return;
        const line = { product_id: pid, qty, unit_price: price };
        const disc = tr.querySelector('input[name="disc"]');
        const tax = tr.querySelector('select[name="tax"]');
        if (disc) line.discount_pct = parseFloat(disc.value || 0);
        if (tax && tax.value) line.tax_id = tax.value;
        lines.push(line);
      });
      if (!lines.length) { window.toast("أضف بندًا واحدًا على الأقل", "error"); return; }
      const base = kind === "sales" ? "/api/v1/sales" : "/api/v1/purchases";
      const termInput = form.querySelector('input[name="payment_term_days"], select[name="payment_term_days"]');
      const curInput = form.querySelector('select[name="currency_id"], input[name="currency_id"]');
      const fxInput = form.querySelector('input[name="exchange_rate"]');
      const currency_id = curInput && curInput.value ? curInput.value : "JOD";
      const exchange_rate = fxInput && fxInput.value ? parseFloat(fxInput.value) : 1;
      const payload = kind === "sales"
        ? { entity_id: sessionStorage.getItem("entity_id"), customer_id: fd.get("customer_id"),
            invoice_date: fd.get("invoice_date"),
            payment_term_days: termInput ? parseInt(termInput.value || 30, 10) : (parseInt(fd.get("payment_term_days") || 30, 10)),
            currency_id, exchange_rate, lines }
        : { entity_id: sessionStorage.getItem("entity_id"), supplier_id: fd.get("customer_id"),
            bill_date: fd.get("invoice_date"), supplier_ref: fd.get("supplier_ref"),
            currency_id, exchange_rate, lines };
      const url = kind === "sales" ? `${base}/invoices` : `${base}/bills`;
      const res = await fetch(url, { method: "POST",
        headers: Object.assign(window.apiHeaders(), {
          "Idempotency-Key": crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) }),
        body: JSON.stringify(payload) });
      const data = await res.json();
      if (res.status === 201) {
        window.location.href = kind === "sales"
          ? `/sales/invoices/${data.data.id}` : `/purchases/bills/${data.data.id}`;
      } else window.toast((data.error && data.error.code) || "تعذر الحفظ", "error");
    });
  });
  /* Generic API forms: <form data-api-post="/api/..." data-redirect="/..." data-method="POST|PUT"> */
  function storeGet(k) {
    try {
      if (window.__store) return window.__store.get(k);
    } catch (e) { /* ignore */ }
    try { return sessionStorage.getItem(k); } catch (e) { return null; }
  }
  function errText(data, fallback) {
    if (data && data.error) {
      return data.error.message ? `${data.error.code}: ${data.error.message}` : (data.error.code || fallback);
    }
    return fallback;
  }
  function isUuid(s) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s || "");
  }
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("form[data-api-post]").forEach((form) => {
      const pre = form.dataset.prefill;
      if (pre && storeGet("access_token")) {
        api_prefill(form, pre);
      }
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (form.dataset.busy === "1") return;
        if (!storeGet("access_token")) {
          window.toast("انتهت الجلسة — سجّل الدخول أولًا", "error");
          window.location.href = "/login";
          return;
        }
        // تحقق عميل سريع: الحقول المطلوبة (الصفحة تستخدم novalidate)
        const missing = [];
        form.querySelectorAll("[required]").forEach((el) => {
          if (!String(el.value == null ? "" : el.value).trim()) {
            missing.push(el);
            el.classList.add("invalid");
          } else el.classList.remove("invalid");
        });
        if (missing.length) {
          window.toast("أكمل الحقول المطلوبة (بعلامة *)", "error");
          missing[0].focus();
          return;
        }
        const eid = storeGet("entity_id");
        if (!eid && (form.dataset.method || "POST").toUpperCase() === "POST"
            && !String(form.dataset.apiPost || "").includes("/users")
            && !String(form.dataset.apiPost || "").includes("/roles")
            && !String(form.dataset.apiPost || "").includes("/settings")) {
          window.toast("لا يوجد كيان محدد — أعد تسجيل الدخول", "error");
          return;
        }
        const fd = new FormData(form);
        const payload = {};
        if (eid) payload.entity_id = eid;
        fd.forEach((v, k) => { if (v !== "" && v !== null) payload[k] = v; });
        ["amount", "price", "sale_price", "standard_cost", "credit_limit", "rate",
         "planned_amount", "budget_total", "total_fees", "discount_pct",
         "opening_balance", "max_users", "max_entities", "qty", "ordered_qty",
         "returned_qty", "received_qty", "unit_price", "valid_days", "installments",
         "acquisition_cost", "residual_value", "useful_life_years", "installment",
         "basic_salary", "discount", "limit_value"].forEach((k) => {
          if (payload[k] !== undefined && payload[k] !== "") payload[k] = parseFloat(payload[k]);
        });
        if (form.dataset.singleLine !== undefined) {
          const line = {};
          ["product_id", "qty", "ordered_qty", "returned_qty", "received_qty",
           "unit_price", "discount_pct"].forEach((k) => {
            if (payload[k] !== undefined) line[k] = k === "product_id" ? payload[k] : parseFloat(payload[k]);
          });
          if (line.qty !== undefined) {
            if (line.ordered_qty === undefined) line.ordered_qty = line.qty;
            if (line.returned_qty === undefined) line.returned_qty = line.qty;
          }
          if (line.ordered_qty !== undefined && line.qty === undefined) line.qty = line.ordered_qty;
          payload.lines = [line];
          ["product_id", "qty", "ordered_qty", "returned_qty", "received_qty",
           "unit_price", "discount_pct"].forEach((k) => delete payload[k]);
        }
        form.dataset.busy = "1";
        const btn = form.querySelector('button[type="submit"]');
        if (btn) btn.disabled = true;
        try {
          const res = await fetch(form.dataset.apiPost, {
            method: form.dataset.method || "POST",
            headers: window.apiHeaders(), body: JSON.stringify(payload) });
          const data = await res.json().catch(() => ({}));
          if (res.status === 201 || res.ok) {
            window.toast("تم الحفظ بنجاح", "info");
            const base = form.dataset.redirect || "";
            const noAppend = form.dataset.appendId === "0";
            const field = form.dataset.redirectField || "id";
            const rid = data.data && (data.data[field] || data.data.id);
            let target = base;
            if (rid && !noAppend) {
              const parts = String(base).split("/").filter(Boolean);
              const endsWithUuid = parts.some(isUuid);
              if (!endsWithUuid) target = `${base}/${rid}`;
            }
            setTimeout(() => { window.location.href = target || "/dashboard"; }, 300);
          } else if (res.status === 401) {
            window.toast("انتهت الجلسة — سجّل الدخول أولًا", "error");
            window.location.href = "/login";
          } else window.toast(errText(data, "تعذر الحفظ"), "error");
        } catch (err) { window.toast("تعذر الاتصال بالخادم", "error"); }
        finally {
          form.dataset.busy = "0";
          if (btn) btn.disabled = false;
        }
      });
    });
  });
  async function api_prefill(form, url) {
    try {
      const res = await fetch(url, { headers: window.apiHeaders() });
      const d = (await res.json()).data || {};
      const pending = [];
      Object.entries(d).forEach(([k, v]) => {
        if (v === null || typeof v === "object") return;
        const el = form.querySelector(`[name="${k}"]`);
        if (!el) return;
        if (el.tagName === "SELECT" && !el.querySelector(`option[value="${v}"]`)) {
          pending.push([el, v]);
        } else el.value = v;
      });
      let tries = 0;
      const timer = setInterval(() => {
        tries++;
        for (let i = pending.length - 1; i >= 0; i--) {
          const [el, v] = pending[i];
          if (el.querySelector(`option[value="${v}"]`)) { el.value = v; pending.splice(i, 1); }
        }
        if (!pending.length || tries > 30) clearInterval(timer);
      }, 300);
    } catch (e) { /* ignore */ }
  }
})();
