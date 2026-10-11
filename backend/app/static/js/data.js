/* data.js — تحميل البيانات الحية من الـ API وعرضها في الجداول والبطاقات */
(function () {
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }
  async function api(path) {
    const res = await fetch(path, { headers: window.apiHeaders() });
    if (!res.ok) throw new Error("API " + res.status);
    const j = await res.json();
    return (j && typeof j === "object" && "data" in j) ? j.data : j;
  }
  async function getEntity() {
    let eid = sessionStorage.getItem("entity_id");
    if (eid) return eid;
    const tid = sessionStorage.getItem("tenant_id");
    if (!tid) return null;
    const res = await api("/api/v1/tenants/" + tid + "/entities");
    const list = (res && res.data) || res;
    if (list && list.length) {
      sessionStorage.setItem("entity_id", list[0].id);
      return list[0].id;
    }
    return null;
  }
  function badge(status) {
    const map = { posted: "posted", paid: "posted", active: "posted", done: "posted",
      approved: "approved", sent: "approved", draft: "draft", pending: "pending",
      partially_paid: "partial", cancelled: "cancelled", rejected: "cancelled", overdue: "cancelled" };
    const safe = String(status == null ? "" : status).replace(/[<>&"']/g, "");
    return '<span class="badge badge-' + (map[status] || "draft") + '">' + safe + "</span>";
  }
  const renderers = {
    accounts: (r) => [`<a href="/accounts/${r.id}">${r.code}</a>`, r.name_ar, r.account_type, r.normal_balance],
    entries: (r) => [`<a href="/journal-entries/${r.id}">${r.official_number || "—"}</a>`,
      r.posting_date, r.description || "", `<span class="num">${r.total_debit}</span>`,
      `<span class="num">${r.total_credit}</span>`, badge(r.status)],
    users: (r) => [`<a href="/settings/users/${r.id}">${r.username}</a>`, `<span dir="ltr">${r.email}</span>`,
      badge(r.is_active ? "active" : "cancelled")],
  };
  const endpoints = {
    accounts: async () => `/api/v1/accounts?entity_id=${await getEntity()}`,
    entries: async () => `/api/v1/journal-entries?limit=50`,
    users: async () => "/api/v1/users",
    branches: async () => `/api/v1/tenants/entities/${await getEntity()}/branches`,
  };
  async function loadTable(tbody) {
    const src = tbody.dataset.src;
    const kind = tbody.dataset.api || tbody.dataset.src;
    if ((!src && !kind) || !sessionStorage.getItem("access_token")) return;
    try {
      const url = (src && src.startsWith("/")) ? src : await endpoints[kind]();
      const res = await api(url);
      const raw = (res && res.data) || res;
      const list = Array.isArray(raw) ? raw : [];
      if (!list.length) return; // keep server empty-state
      const table = tbody.closest("table");
      const keys = table ? [...table.querySelectorAll("thead th[data-key]")].map((th) => ({
        key: th.dataset.key, num: th.hasAttribute("data-num"), badge: th.hasAttribute("data-badge") })) : [];
      const detail = tbody.dataset.detail;
      tbody.innerHTML = list.map((r) => {
        let tds;
        if (keys.length) {
          tds = keys.map((c, i) => {
            let v = r[c.key];
            if (v === null || v === undefined) v = "—";
            else if (c.badge) v = badge(v);
            else if (c.num) v = `<span class="num">${v}</span>`;
            if (i === 0 && detail && r.id) v = `<a href="${detail}/${r.id}">${v}</a>`;
            return `<td>${v}</td>`;
          }).join("");
        } else {
          tds = renderers[kind](r).map((c) => `<td>${c}</td>`).join("");
          if (detail && r.id) tds += `<td><a href="${detail}/${r.id}" aria-label="عرض">عرض</a></td>`;
        }
        return `<tr>${tds}</tr>`;
      }).join("");
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="8">تعذر تحميل البيانات — <button type="button" class="btn btn-link" onclick="location.reload()">إعادة المحاولة</button></td></tr>`;
    }
  }
  async function loadDashboard() {
    if (!sessionStorage.getItem("access_token")) return;
    try {
      const eid = await getEntity();
      if (!eid) return;
      const s = await api(`/api/v1/reports/dashboard-summary?entity_id=${eid}`);
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
      set("stat-revenue", s.revenue + " د.أ");
      set("stat-expenses", s.expenses + " د.أ");
      set("stat-profit", s.profit + " د.أ");
      set("stat-drafts", s.pending_drafts);
      set("stat-overdue", s.overdue_invoices);
      try {
        const payload = JSON.parse(atob(sessionStorage.getItem("access_token").split(".")[1]));
        const perms = payload.permissions || [];
        document.querySelectorAll("[data-requires]").forEach((el) => {
          if (!perms.includes(el.dataset.requires) && !perms.includes("admin.*")) el.style.display = "none";
        });
      } catch (e) { /* ignore */ }
      window.__dash = s;
      document.dispatchEvent(new CustomEvent("dash:ready"));
    } catch (e) { /* demo numbers remain */ }
  }
  async function loadRecentEntries() {
    const tb = document.getElementById("recent-entries");
    if (!tb || !sessionStorage.getItem("access_token")) return;
    try {
      const res = await api("/api/v1/journal-entries");
      const raw = (res && res.data) || res || [];
      const list = (Array.isArray(raw) ? raw : []).slice(0, 5);
      if (!list.length) return;
      tb.innerHTML = list.map((r) =>
        `<tr><td>${r.official_number || "—"}</td><td>${(r.description || "").slice(0, 40)}</td>` +
        `<td><span class="num">${r.total_debit}</span></td><td>${badge(r.status)}</td></tr>`).join("");
    } catch (e) { /* ignore */ }
  }
  async function loadEntryDetail() {
    const root = document.getElementById("entry-detail");
    if (!root || !sessionStorage.getItem("access_token")) return;
    const eid = root.dataset.entry;
    try {
      const e = await api(`/api/v1/journal-entries/${eid}`);
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
      set("e-no", e.official_number || "—");
      set("e-status", e.status);
      set("e-date", e.posting_date);
      set("e-total", e.total_debit);
      const lines = await api(`/api/v1/journal-entries/${eid}/lines`);
      const lt = document.getElementById("e-lines");
      if (lt) lt.innerHTML = lines.map((l) =>
        `<tr><td>${l.line_number}</td><td class="ltr">${l.account_id.slice(0, 8)}</td>` +
        `<td><span class="num">${l.debit}</span></td><td><span class="num">${l.credit}</span></td></tr>`).join("");
      const appr = await api(`/api/v1/journal-entries/${eid}/approvals`);
      const at = document.getElementById("e-approvals");
      if (at) at.innerHTML = appr.length ? appr.map((a) => `<div>${badge(a.status)} <span dir="ltr">${a.approver_id.slice(0, 8)}</span></div>`).join("") : "لا اعتمادات بعد";
      const com = await api(`/api/v1/journal-entries/${eid}/comments`);
      const ct = document.getElementById("e-comments");
      if (ct) ct.innerHTML = com.length ? com.map((c) => `<div class="toast">${c.comment}</div>`).join("") : "لا تعليقات";
    } catch (e) { /* ignore */ }
  }
  async function loadAccountDetail() {
    const root = document.getElementById("account-detail");
    if (!root || !root.dataset.account || !sessionStorage.getItem("access_token")) return;
    const aid = root.dataset.account;
    try {
      const b = await api(`/api/v1/reports/account-balance?account_id=${aid}`);
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
      set("a-debit", b.debit); set("a-credit", b.credit); set("a-balance", b.balance);
    } catch (e) { /* ignore */ }
  }
  async function loadTree() {
    const root = document.getElementById("accounts-tree");
    if (!root || !sessionStorage.getItem("access_token")) return;
    try {
      const eid = await getEntity();
      const res = await api(`/api/v1/accounts?entity_id=${eid}`);
      const list = (res && res.data) || res || [];
      const byParent = {};
      list.forEach((a) => {
        const k = a.parent_id || "root";
        (byParent[k] = byParent[k] || []).push(a);
      });
      const cls = { asset: "type-asset", liability: "type-liability", equity: "type-equity", income: "type-income", expense: "type-expense" };
      const build = (pid) => (byParent[pid] || []).map((a) =>
        `<div class="tree-node"><div class="tree-row" onclick="toggleTree(this)">` +
        `<span class="${cls[a.account_type] || ""}">${esc(a.code)} — ${esc(a.name_ar)}</span>` +
        `<a href="/accounts/${esc(a.id)}" class="ms-auto" aria-label="عرض">عرض</a></div>` +
        `<div class="tree-children">${build(a.id)}</div></div>`).join("");
      root.innerHTML = build("root") || "لا حسابات";
    } catch (e) { /* ignore */ }
  }
  async function populateEntryForm() {
    const form = document.getElementById("entry-form");
    if (!form || !sessionStorage.getItem("access_token")) return;
    try {
      const eid = await getEntity();
      const js = await api("/api/v1/journals");
      const accs = await api(`/api/v1/accounts?entity_id=${eid}`);
      const jsList = (js && js.data) || js || [];
      const accList = (accs && accs.data) || accs || [];
      const jOpts = jsList.map((j) => `<option value="${esc(j.id)}">${esc(j.code)}</option>`).join("");
      const aOpts = accList.filter((a) => a.is_postable)
        .map((a) => `<option value="${esc(a.id)}">${esc(a.code)} — ${esc(a.name_ar)}</option>`).join("");
      form.querySelectorAll('select[name="journal_id"]').forEach((s) => { s.innerHTML = `<option value="">اختر…</option>` + jOpts; });
      form.querySelectorAll('select[name="account"]').forEach((s) => { s.innerHTML = aOpts; });
    } catch (e) { /* ignore */ }
  }
  window.loadReport = async function () {
    const f = document.getElementById("report-filter");
    if (!f || !sessionStorage.getItem("access_token")) { window.toast("سجّل الدخول أولًا", "error"); return; }
    const name = f.dataset.report;
    const pidEl = document.getElementById("rep-period");
    const pid = pidEl ? pidEl.value : "";
    const needPeriod = ["trial-balance", "balance-sheet", "income-statement", "ledger"].includes(name);
    if (!pid && needPeriod) { window.toast("اختر الفترة", "error"); return; }
    const head = document.getElementById("rep-head");
    const body = document.getElementById("rep-body");
    try {
      if (name === "trial-balance") {
        const tb = await api(`/api/v1/reports/trial-balance?period_id=${pid}`);
        head.innerHTML = "<th>الحساب</th><th class='num'>مدين</th><th class='num'>دائن</th>";
        body.innerHTML = tb.lines.map((l) =>
          `<tr><td class="ltr">${esc(l.account_id).slice(0, 8)}</td><td class="num">${esc(l.debit)}</td><td class="num">${esc(l.credit)}</td></tr>`).join("") +
          `<tr><th>الإجمالي</th><th class="num">${esc(tb.total_debit)}</th><th class="num">${esc(tb.total_credit)}</th></tr>`;
      } else if (name === "balance-sheet" || name === "income-statement") {
        const st = await api(`/api/v1/reports/${name}?period_id=${pid}`);
        head.innerHTML = "<th>البند</th><th class='num'>المبلغ</th>";
        body.innerHTML = st.lines.map((l) =>
          `<tr><td>${esc(l.line_code)}</td><td class="num">${esc(l.amount)}</td></tr>`).join("") +
          `<tr><th>الإجمالي</th><th class="num">${esc(st.total)}</th></tr>`;
      } else if (name === "cash-flow") {
        const eid = await getEntity();
        const cf = await api(`/api/v1/reports/cash-flow?entity_id=${eid}`);
        head.innerHTML = "<th>الشهر</th><th class='num'>الصافي</th>";
        body.innerHTML = (cf.months || []).map((m) =>
          `<tr><td class="ltr">${esc(m.month)}</td><td class="num">${esc(m.net)}</td></tr>`).join("") +
          `<tr><th>الإجمالي</th><th class="num">${esc(cf.total)}</th></tr>`;
      } else if (name === "ledger") {
        const accSel = document.getElementById("rep-account");
        const aid = accSel ? accSel.value : "";
        if (!aid) { window.toast("اختر الحساب", "error"); return; }
        const per = await api(`/api/v1/reports/fiscal-periods?entity_id=${await getEntity()}`);
        const plist = (per && per.data) || per || [];
        const p = plist.find((x) => String(x.id) === String(pid));
        if (!p || !p.starts_on || !p.ends_on) { window.toast("الفترة بلا تواريخ — اختر فترة أخرى", "error"); return; }
        const lg = await api(`/api/v1/reports/ledger?account_id=${aid}&from=${p.starts_on}&to=${p.ends_on}`);
        const rows = (lg && lg.lines) || lg || [];
        head.innerHTML = "<th>التاريخ</th><th>البيان</th><th class='num'>مدين</th><th class='num'>دائن</th>";
        body.innerHTML = (Array.isArray(rows) ? rows : []).map((l) =>
          `<tr><td class="ltr">${esc(l.posting_date || "")}</td><td>${esc(l.description || "")}</td><td class="num">${esc(l.debit)}</td><td class="num">${esc(l.credit)}</td></tr>`).join("") || "<tr><td colspan='4'>لا حركات</td></tr>";
      } else if (name === "aging-receivables" || name === "aging-payables") {
        const eid = await getEntity();
        const ag = await api(`/api/v1/reports/${name}?entity_id=${eid}`);
        head.innerHTML = "<th>المستند</th><th>الاستحقاق</th><th class='num'>المتبقي</th><th class='num'>أيام التأخير</th>";
        body.innerHTML = (ag.lines || []).map((l) =>
          `<tr><td class="ltr">${esc(l.doc_number)}</td><td class="ltr">${esc(l.due_on)}</td><td class="num">${esc(l.remaining)}</td><td class="num">${esc(l.overdue_days)}</td></tr>`).join("") +
          `<tr><th>الإجمالي</th><th></th><th class="num">${esc((ag.buckets || {}).total)}</th><th></th></tr>`;
      } else if (name === "inventory") {
        const eid = await getEntity();
        const ir = await api(`/api/v1/reports/inventory?entity_id=${eid}`);
        head.innerHTML = "<th>الصنف</th><th>الموقع</th><th class='num'>الكمية</th><th class='num'>التكلفة</th><th class='num'>القيمة</th>";
        body.innerHTML = (ir.lines || []).map((l) =>
          `<tr><td>${esc(l.product_code)} — ${esc(l.product_name)}</td><td class="ltr">${esc(l.location)}</td><td class="num">${esc(l.qty)}</td><td class="num">${esc(l.avg_cost)}</td><td class="num">${esc(l.value)}</td></tr>`).join("") +
          `<tr><th colspan="4">إجمالي القيمة</th><th class="num">${esc(ir.total_value)}</th></tr>`;
      } else if (name === "assets") {
        const eid = await getEntity();
        const ar = await api(`/api/v1/reports/assets?entity_id=${eid}`);
        head.innerHTML = "<th>الأصل</th><th>الحالة</th><th class='num'>الكلفة</th><th class='num'>المجمع</th><th class='num'>الصافي</th>";
        body.innerHTML = (ar.lines || []).map((l) =>
          `<tr><td>${esc(l.code)} — ${esc(l.name_ar)}</td><td>${esc(l.status)}</td><td class="num">${esc(l.cost)}</td><td class="num">${esc(l.accum)}</td><td class="num">${esc(l.net)}</td></tr>`).join("") +
          `<tr><th colspan="4">إجمالي الصافي</th><th class="num">${esc(ar.total_net)}</th></tr>`;
      } else if (name === "tax") {
        const eid = await getEntity();
        const tr = await api(`/api/v1/reports/tax?entity_id=${eid}`);
        head.innerHTML = "<th>البيان</th><th class='num'>المبلغ</th>";
        body.innerHTML =
          `<tr><td>ضريبة المخرجات (${esc(tr.sales_invoices)} فاتورة مرحّلة)</td><td class="num">${esc(tr.output_vat)}</td></tr>` +
          `<tr><td>ضريبة المدخلات (${esc(tr.purchase_bills)} فاتورة مرحّلة)</td><td class="num">${esc(tr.input_vat)}</td></tr>` +
          `<tr><th>الصافي المستحق</th><th class="num">${esc(tr.net_payable)}</th></tr>`;
      } else if (name === "budget") {
        const eid = await getEntity();
        const br = await api(`/api/v1/reports/budget?entity_id=${eid}`);
        head.innerHTML = "<th>الحساب</th><th class='num'>المخطط</th><th class='num'>الفعلي</th><th class='num'>الانحراف</th>";
        body.innerHTML = (br.lines || []).map((l) =>
          `<tr><td>${esc(l.account_code)} — ${esc(l.account_name)}</td><td class="num">${esc(l.planned)}</td><td class="num">${esc(l.actual)}</td><td class="num">${esc(l.variance)}</td></tr>`).join("") +
          `<tr><th>الإجمالي (${esc(br.budget || "—")})</th><th class="num">${esc(br.total_planned)}</th><th class="num">${esc(br.total_actual)}</th><th></th></tr>`;
      } else {
        body.innerHTML = "<tr><td colspan='5'>هذا التقرير غير مدعوم بعد — لا يوجد endpoint له</td></tr>";
      }
    } catch (e) { window.toast("تعذر تحميل التقرير", "error"); }
  };
  async function initReportFilter() {
    const f = document.getElementById("report-filter");
    if (!f || !sessionStorage.getItem("access_token")) return;
    if (["ledger", "aging-receivables", "aging-payables"].includes(f.dataset.report)) {
      const w = document.getElementById("rep-account-wrap");
      if (w) w.hidden = false;
    }
    try {
      const eid = await getEntity();
      const psRaw = await api(`/api/v1/reports/fiscal-periods?entity_id=${eid}`);
      const ps = (psRaw && psRaw.data) || psRaw || [];
      const sel = document.getElementById("rep-period");
      if (!sel) return;
      sel.innerHTML = `<option value="">اختر…</option>` +
        ps.map((p) => `<option value="${esc(p.id)}">${esc(p.code)} (${esc(p.status)})</option>`).join("");
      const accSel = document.getElementById("rep-account");
      if (accSel && f.dataset.report === "ledger") {
        try {
          const accRaw = await api(`/api/v1/accounts?entity_id=${eid}`);
          const accList = ((accRaw && accRaw.data) || accRaw || []).filter((a) => a.is_postable);
          accSel.innerHTML = `<option value="">اختر…</option>` +
            accList.map((a) => `<option value="${esc(a.id)}">${esc(a.code)} — ${esc(a.name_ar)}</option>`).join("");
        } catch (e) { /* ignore */ }
      }
    } catch (e) { /* ignore */ }
  }
  async function loadDocDetail() {
    const root = document.getElementById("doc-detail");
    if (!root || !sessionStorage.getItem("access_token")) return;
    const urls = { invoice: (id) => `/api/v1/sales/invoices/${id}`,
                   bill: (id) => `/api/v1/purchases/bills/${id}`,
                   asset: (id) => `/api/v1/assets/${id}`,
                   quotation: (id) => `/api/v1/sales/quotations/${id}`,
                   sales_order: (id) => `/api/v1/sales/orders/${id}`,
                   delivery: (id) => `/api/v1/sales/deliveries/${id}`,
                   purchase_request: (id) => `/api/v1/purchases/requests/${id}`,
                   purchase_order: (id) => `/api/v1/purchases/orders/${id}`,
                   receipt: (id) => `/api/v1/purchases/receipts/${id}`,
                   credit_note: (id) => `/api/v1/sales/credit-notes/${id}`,
                   return: (id) => `/api/v1/sales/returns/${id}`,
                   vendor_return: (id) => `/api/v1/purchases/returns/${id}`,
                   account: (id) => `/api/v1/accounts/${id}`,
                   party: (id) => `/api/v1/parties/${id}`,
                   product: (id) => `/api/v1/products/${id}`,
                   employee: (id) => `/api/v1/hr/employees/${id}`,
                   payroll_run: (id) => `/api/v1/hr/payroll-runs/${id}`,
                   project: (id) => `/api/v1/projects/${id}`,
                   journal: (id) => `/api/v1/journals/${id}`,
                   cash_box: (id) => `/api/v1/treasury/cash-boxes/${id}`,
                   check: (id) => `/api/v1/treasury/checks/${id}`,
                   fee_contract: (id) => `/api/v1/education/fee-contracts/${id}`,
                   user: (id) => `/api/v1/users/${id}`,
                   role: (id) => `/api/v1/roles/${id}` };
    const url = (urls[root.dataset.kind] || (() => null))(root.dataset.id);
    if (!url) return;
    try {
      const d = await api(url);
      const set = (id, v) => { const el = document.getElementById(id);
        if (el) el.textContent = (v == null || v === "") ? "—" : v; };
      set("d-no", d.doc_number || d.code || d.id);
      set("d-status", d.status);
      set("d-sub", d.subtotal);
      set("d-tax", d.tax_total);
      set("d-grand", d.grand_total);
      set("d-rem", d.remaining_amount);
      set("d-cost", d.acquisition_cost);
      set("d-accum", d.accumulated_depreciation);
      set("d-net", d.net);
      set("d-debit", d.debit_balance || d.current_debit);
      set("d-credit", d.credit_balance || d.current_credit);
      set("d-balance", d.balance);
      const lt = document.getElementById("d-lines");
      if (lt) lt.innerHTML = (d.lines || []).map((l, i) => {
        const q = l.qty ?? l.ordered_qty ?? l.requested_qty ?? l.received_qty ?? l.delivered_qty ?? "";
        const p = l.unit_price ?? l.unit_cost ?? "";
        const t = l.line_total ?? ((q !== "" && p !== "") ? (parseFloat(q) * parseFloat(p)).toFixed(3) : "");
        const desc = l.description || (l.product_id ? `صنف ${l.product_id.slice(0, 8)}` : "");
        return `<tr><td>${i + 1}</td><td>${esc(desc)}</td>` +
          `<td class="num">${esc(q)}</td><td class="num">${esc(p)}</td>` +
          `<td class="num">${esc(t)}</td></tr>`;
      }).join("") || `<tr><td colspan="5">لا بنود</td></tr>`;
      const ft = document.getElementById("d-fields");
      if (ft) {
        const fields = [
          ["الرمز", d.code], ["الاسم", d.name_ar || d.name], ["النوع", d.type || d.account_type],
          ["العملة", d.currency_id], ["الرصيد", d.balance], ["مدين", d.debit_balance || d.current_debit],
          ["دائن", d.credit_balance || d.current_credit], ["الحالة", d.status], ["نشط", d.is_active ? "نعم" : "لا"],
          ["العميل/المورد", d.customer_name || d.supplier_name], ["المعرف", d.id]
        ].filter(([k, v]) => v != null && v !== "");
        ft.innerHTML = fields.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("");
      }
      const acts = document.getElementById("d-actions");
      if (acts && d.status === "draft" && !acts.querySelector("button, a, form")) {
        const bases = { invoice: "/api/v1/sales/invoices/", bill: "/api/v1/purchases/bills/",
                        credit_note: "/api/v1/sales/credit-notes/", return: "/api/v1/sales/returns/",
                        vendor_return: "/api/v1/purchases/returns/" };
        const base = bases[root.dataset.kind];
        if (!base) return;
        acts.innerHTML = `<button class="btn btn-primary" id="d-post">ترحيل</button>`;
        document.getElementById("d-post").addEventListener("click", async () => {
          const res = await fetch(base + root.dataset.id + "/post",
            { method: "POST", headers: window.apiHeaders() });
          if (res.ok) window.location.reload();
          else window.toast("تعذر الترحيل", "error");
        });
      }
    } catch (e) { /* ignore */ }
  }
  async function loadNotifications() {
    const box = document.getElementById("notif-list");
    if (!box || !sessionStorage.getItem("access_token")) return;
    try {
      const res = await api("/api/v1/notifications?unread=1");
      const nlist = (res && res.data) || res || [];
      if (nlist.length) box.innerHTML = nlist.map((n) => `<div class="toast">${esc(n.title)}</div>`).join("");
    } catch (e) { /* ignore */ }
  }
  async function populateSelects() {
    if (!sessionStorage.getItem("access_token")) return;
    const eid = await getEntity().catch(() => null);
    const sources = {
      customers: "/api/v1/parties?type=customer",
      suppliers: "/api/v1/parties?type=supplier",
      products: eid ? `/api/v1/products?entity_id=${eid}` : null,
      taxes: "/api/v1/taxes",
      boxes: "/api/v1/treasury/cash-boxes",
      journals: "/api/v1/journals",
      accounts: eid ? `/api/v1/accounts?entity_id=${eid}` : null,
      categories: "/api/v1/product-categories",
      students: "/api/v1/education/students",
      periods: eid ? `/api/v1/fiscal-periods?entity_id=${eid}` : null,
      sales_orders: "/api/v1/sales/orders",
      purchase_orders: "/api/v1/purchases/orders",
      warehouses: "/api/v1/warehouses",
      quotations: "/api/v1/sales/quotations",
      sales_invoices: "/api/v1/sales/invoices",
      purchase_bills: "/api/v1/purchases/bills",
      purchase_requests: "/api/v1/purchases/requests",
      banks: "/api/v1/treasury/banks",
      bank_accounts: "/api/v1/treasury/bank-accounts",
      fiscal_years: "/api/v1/tenants/fiscal-years",
      asset_categories: "/api/v1/asset-categories",
      roles: "/api/v1/roles",
      uoms: "/api/v1/uoms",
      product_categories: "/api/v1/product-categories",
      employees: "/api/v1/hr/employees",
    };
    const label = (r) => r.name_ar || r.full_name_ar || r.name || r.doc_number || r.check_no || r.student_no || r.employee_no || r.code || "?";
    for (const sel of document.querySelectorAll("select[data-source]")) {
      const url = sources[sel.dataset.source];
      if (!url) continue;
      try {
        const res = await api(url);
        const list = ((res && res.data) || res || []);
        let items = Array.isArray(list) ? list : [];
        if (sel.dataset.source === "accounts" && sel.hasAttribute("data-postable"))
          items = items.filter((a) => a.is_postable);
        const codeOf = (r) => r.code || r.doc_number || r.student_no || r.employee_no || r.check_no || "";
        sel.innerHTML = `<option value="">اختر…</option>` +
          items.map((r) => `<option value="${esc(r.id)}">${esc(codeOf(r) ? codeOf(r) + " — " : "")}${esc(label(r))}</option>`).join("");
      } catch (e) { sel.innerHTML = `<option value="">تعذر التحميل — أعد المحاولة</option>`; }
    }
    for (const wh of document.querySelectorAll("select[data-warehouse-for]")) {
      const targets = wh.dataset.warehouseFor.split(",").map((s) => s.trim())
        .map((n) => document.querySelector(`select[name="${n}"]`)).filter(Boolean);
      if (!targets.length) continue;
      const load = async () => {
        if (!wh.value) {
          targets.forEach((t) => { t.innerHTML = `<option value="">اختر المستودع أولًا</option>`; });
          return;
        }
        try {
          const res = await api(`/api/v1/warehouses/${encodeURIComponent(wh.value)}/locations`);
          const locList = ((res && res.data) || res || []);
          const opts = `<option value="">اختر…</option>` +
            locList.map((l) => `<option value="${esc(l.id)}">${esc(l.code)} — ${esc(l.name_ar)}</option>`).join("");
          targets.forEach((t) => { t.innerHTML = opts; });
        } catch (e) { /* ignore */ }
      };
      wh.addEventListener("change", load);
      await load();
    }
  }
  document.addEventListener("DOMContentLoaded", () => {
    initReportFilter();
    loadDocDetail();
    populateSelects();
    loadNotifications();
    document.querySelectorAll("[data-docaction]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("تأكيد " + btn.textContent.trim() + "؟")) return;
        try {
          const res = await fetch(`${btn.dataset.base}/${btn.dataset.id}/${btn.dataset.docaction}`, {
            method: "POST", headers: Object.assign(window.apiHeaders(), { "Content-Type": "application/json" }),
            body: "{}" });
          const data = await res.json().catch(() => ({}));
          if (res.ok) window.location.reload();
          else window.toast((data.error && data.error.code) || "تعذر التنفيذ", "error");
        } catch (e) { window.toast("تعذر الاتصال", "error"); }
      });
    });
    document.querySelectorAll("[data-do]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const root = document.getElementById("entry-detail");
        if (!root) return;
        const eid = root.dataset.entry;
        try {
          const res = await fetch(`/api/v1/journal-entries/${eid}/${btn.dataset.do}`, {
            method: "POST", headers: window.apiHeaders() });
          const data = await res.json();
          if (res.ok) window.location.reload();
          else window.toast((data.error && data.error.code) || "تعذر التنفيذ", "error");
        } catch (e) { window.toast("تعذر الاتصال", "error"); }
      });
    });
    document.querySelectorAll("tbody[data-api], tbody[data-src]").forEach(loadTable);
    if (document.getElementById("stat-revenue")) loadDashboard();
    loadRecentEntries();
    loadEntryDetail();
    loadAccountDetail();
    loadTree();
    populateEntryForm();
  });
})();
