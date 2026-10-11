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

  window.apiHeaders = function () {
    const token = sessionStorage.getItem("access_token");
    const tenant = sessionStorage.getItem("tenant_id");
    const h = { "Content-Type": "application/json" };
    if (token) h.Authorization = "Bearer " + token;
    if (tenant) h["X-Tenant-ID"] = tenant;
    return h;
  };
})();
