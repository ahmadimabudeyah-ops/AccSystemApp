/* tables.js — تصدير الجداول + مساعدات الشجرة */
(function () {
  window.exportTable = function (tableId) {
    const table = document.getElementById(tableId);
    if (!table) { window.toast("لا يوجد جدول للتصدير", "error"); return; }
    const rows = [];
    table.querySelectorAll("tr").forEach((tr) => {
      const cells = [];
      tr.querySelectorAll("th,td").forEach((td) => cells.push('"' + td.innerText.trim() + '"'));
      rows.push(cells.join(","));
    });
    const blob = new Blob(["\ufeff" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = tableId + ".csv";
    a.click();
    window.toast("تم التصدير بنجاح", "success");
  };

  window.toggleTree = function (el) {
    const node = el.closest(".tree-node");
    if (!node) return;
    const children = node.querySelector(":scope > .tree-children");
    if (children) children.hidden = !children.hidden;
    el.classList.toggle("collapsed");
  };
})();
