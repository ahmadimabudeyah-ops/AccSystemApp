/* charts.js — رسوم Chart.js بتوجه RTL وألوان دافئة */
(function () {
  function ready(fn) {
    if (typeof Chart === "undefined") return;
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }
  ready(function () {
    Chart.defaults.font.family = "Tajawal, sans-serif";
    Chart.defaults.font.size = 13;
    const sales = document.getElementById("sales-chart");
    if (sales) {
      const draw = (labels, values) => new Chart(sales, {
        type: "line",
        data: {
          labels: labels,
          datasets: [{
            label: "المبيعات (د.أ)",
            data: values,
            borderColor: "#A67B5B", backgroundColor: "rgba(166,123,91,.15)",
            fill: true, tension: 0.4,
          }],
        },
        options: {
          plugins: { legend: { position: "top", rtl: true } },
          scales: { x: { reverse: true }, y: { position: "left" } },
        },
      });
      if (window.__dash && window.__dash.months && window.__dash.months.length) {
        draw(window.__dash.months, window.__dash.monthly_revenue);
      } else {
        const chart = draw(["لا بيانات بعد"], [0]);
        document.addEventListener("dash:ready", () => {
          const m = (window.__dash && window.__dash.months) || [];
          const v = (window.__dash && window.__dash.monthly_revenue) || [];
          if (m.length) { chart.data.labels = m; chart.data.datasets[0].data = v; chart.update(); }
        });
      }
    }
    const rev = document.getElementById("revenue-chart");
    if (rev) {
      const mix0 = window.__dash && window.__dash.revenue_mix;
      const chart2 = new Chart(rev, {
        type: "doughnut",
        data: {
          labels: (mix0 && mix0.labels) || ["لا إيرادات بعد"],
          datasets: [{
            data: (mix0 && mix0.values) || [0],
            backgroundColor: ["#A67B5B", "#C9A961", "#E5D5C5", "#8a7a68"],
          }],
        },
        options: { plugins: { legend: { position: "bottom", rtl: true } } },
      });
      document.addEventListener("dash:ready", () => {
        const mix = window.__dash && window.__dash.revenue_mix;
        if (mix && mix.labels && mix.labels.length) {
          chart2.data.labels = mix.labels;
          chart2.data.datasets[0].data = mix.values;
          chart2.update();
        }
      });
    }
  });
})();
