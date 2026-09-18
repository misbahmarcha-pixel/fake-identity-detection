(function () {
  const root = document.documentElement;
  const stored = localStorage.getItem("theme") || "dark";
  root.setAttribute("data-theme", stored);

  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const current = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", current);
      localStorage.setItem("theme", current);
    });
  });
})();
