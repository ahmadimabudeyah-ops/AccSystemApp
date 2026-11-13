/* charts.js — رسوم Chart.js بتوجه RTL وألوان دافئة */
(function () {
  function ready(fn) {
    if (typeof Chart === "undefined") return;
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }
  function fmtMoney(v, cur) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "—";
    return new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2, maximumFractionDigits: 2,
    }).format(n) + (cur ? " " + cur : "");
  }
  function monthLabel(key) {
    const parts = String(key || "").split("-").map(Number);
    if (parts.length !== 2 || !parts[0] || !parts[1]) return key;
    return new Date(parts[0], parts[1] - 1, 1)
      .toLocaleDateString("ar-EG", { month: "short", year: "numeric" });
  }
  function themeColor(name, fallback) {
    try {
      const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return v || fallback;
    } catch (e) { return fallback; }
  }

  ready(function () {
    Chart.defaults.font.family = "Tajawal, sans-serif";
    Chart.defaults.font.size = 13;
    Chart.defaults.color = themeColor("--text-soft", "#78716C");
    const charts = [];

    const sales = document.getElementById("sales-chart");
    if (sales) {
      const chart = new Chart(sales, {
        type: "line",
        data: {
          labels: ["لا بيانات بعد"],
          datasets: [{
            label: "صافي الإيرادات",
            data: [0],
            borderColor: "#A67B5B",
            backgroundColor: "rgba(166,123,91,.15)",
            pointBackgroundColor: "#C9A961",
            pointBorderColor: "#FFFFFF",
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.4,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { position: "top", rtl: true },
            tooltip: {
              rtl: true,
              callbacks: {
                label: (ctx) => fmtMoney(ctx.parsed.y, (window.__dash || {}).functional_currency || "JOD"),
              },
            },
          },
          scales: {
            x: { reverse: true, grid: { display: false } },
            y: {
              position: "left",
              grid: { color: "rgba(166,123,91,.12)" },
              ticks: {
                callback: (v) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v),
              },
            },
          },
        },
      });
      charts.push(chart);

      const applySales = () => {
        const d = window.__dash || {};
        const months = d.months || [];
        const values = d.monthly_revenue || [];
        const cur = d.functional_currency || "JOD";
        chart.data.labels = months.length ? months.map(monthLabel) : ["لا بيانات بعد"];
        chart.data.datasets[0].data = months.length ? values : [0];
        chart.data.datasets[0].label = `صافي الإيرادات (${cur})`;
        chart.update();
      };
      applySales();
      document.addEventListener("dash:ready", applySales);
    }

    const rev = document.getElementById("revenue-chart");
    if (rev) {
      const chart2 = new Chart(rev, {
        type: "doughnut",
        data: {
          labels: ["لا إيرادات بعد"],
          datasets: [{
            data: [0],
            backgroundColor: ["#A67B5B", "#C9A961", "#E5D5C5", "#8a7a68"],
            borderColor: "rgba(255,255,255,.85)",
            borderWidth: 2,
            hoverOffset: 6,
          }],
        },
        options: {
          responsive: true,
          cutout: "62%",
          plugins: {
            legend: { position: "bottom", rtl: true },
            tooltip: {
              rtl: true,
              callbacks: {
                label: (ctx) => {
                  const values = (ctx.dataset.data || []).map(Number);
                  const total = values.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0);
                  const pct = total ? (Number(ctx.parsed) / total * 100).toFixed(1) : "0";
                  return `${fmtMoney(ctx.parsed, (window.__dash || {}).functional_currency || "JOD")} (${pct}%)`;
                },
              },
            },
          },
        },
      });
      charts.push(chart2);

      const applyMix = () => {
        const mix = (window.__dash && window.__dash.revenue_mix) || {};
        const labels = mix.labels || [];
        const values = mix.values || [];
        chart2.data.labels = labels.length ? labels : ["لا إيرادات بعد"];
        chart2.data.datasets[0].data = labels.length ? values : [0];
        chart2.update();
      };
      applyMix();
      document.addEventListener("dash:ready", applyMix);
    }

    // تحديث ألوان النصوص عند تبديل الوضع الفاتح/الداكن دون إعادة تحميل.
    try {
      const observer = new MutationObserver(() => {
        Chart.defaults.color = themeColor("--text-soft", "#78716C");
        charts.forEach((c) => c.update("none"));
      });
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    } catch (e) { /* ignore */ }
  });
})();