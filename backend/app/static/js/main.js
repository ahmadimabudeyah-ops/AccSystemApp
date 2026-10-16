/* main.js — الثيم، التنبيهات، الاختصارات، أدوات عامة */
(function () {
  const root = document.documentElement;
  try {
    const saved = localStorage.getItem("theme");
    if (saved) root.setAttribute("data-theme", saved);
  } catch (e) { /* ignore */ }

  window.toggleTheme = function () {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) { /* ignore */ }
  };

  window.toast = function (message, type) {
    let stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      document.body.appendChild(stack);
    }
    const el = document.createElement("div");
    el.className = "toast toast-" + (type || "info");
    el.setAttribute("role", "status");
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => el.remove(), 4000);
  };

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      const input = document.querySelector('input[placeholder*="بحث"]');
      if (input) input.focus();
    }
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/static/sw.js").catch(() => {});
    });
  }

  /* تخزين الجلسة: localStorage أولًا (يثبت عبر التبويبات) مع التوافق مع sessionStorage القديم */
  window.__store = {
    get(k) {
      try { const v = localStorage.getItem(k); if (v !== null) return v; } catch (e) { /* ignore */ }
      try { return sessionStorage.getItem(k); } catch (e) { return null; }
    },
    set(k, v) {
      try { localStorage.setItem(k, v); } catch (e) { /* ignore */ }
      try { sessionStorage.setItem(k, v); } catch (e) { /* ignore */ }
    },
    del(k) {
      try { localStorage.removeItem(k); } catch (e) { /* ignore */ }
      try { sessionStorage.removeItem(k); } catch (e) { /* ignore */ }
    },
  };
  try {
    ["access_token", "refresh_token", "tenant_id", "entity_id"].forEach((k) => {
      const s = sessionStorage.getItem(k);
      if (s !== null && localStorage.getItem(k) === null) localStorage.setItem(k, s);
    });
  } catch (e) { /* ignore */ }

  window.apiHeaders = function () {
    const token = window.__store.get("access_token");
    const tenant = window.__store.get("tenant_id");
    const h = { "Content-Type": "application/json" };
    if (token) h.Authorization = "Bearer " + token;
    if (tenant) h["X-Tenant-ID"] = tenant;
    return h;
  };
})();
