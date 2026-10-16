// Comportements communs à toutes les pages : thème (auto / clair / sombre) et menu compact.
(function () {
  "use strict";
  var root = document.documentElement;

  // ---------- Thème ----------
  // Seule donnée stockée : la clé localStorage « theme », uniquement si le visiteur choisit
  // « clair » ou « sombre » (supprimée s'il revient à « auto »). Aucun cookie.
  var buttons = document.querySelectorAll(".theme-switch button");
  function mode() { return root.getAttribute("data-theme") || "auto"; }
  function sync() { buttons.forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.mode === mode())); }); }
  function announce() { document.dispatchEvent(new CustomEvent("themechange", { detail: { mode: mode() } })); }
  buttons.forEach(function (b) {
    b.addEventListener("click", function () {
      var m = b.dataset.mode;
      if (m === "auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", m);
      try { if (m === "auto") localStorage.removeItem("theme"); else localStorage.setItem("theme", m); } catch (e) {}
      sync();
      announce();
    });
  });
  sync();
  if (window.matchMedia) {
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    if (mq.addEventListener) mq.addEventListener("change", function () { if (mode() === "auto") announce(); });
  }

  // ---------- Menu des pages : replié derrière un bouton sur petit écran ----------
  var toggle = document.querySelector(".menu-btn"), menu = document.getElementById("site-menu");
  if (toggle && menu) {
    function close(focus) {
      if (toggle.getAttribute("aria-expanded") !== "true") return;
      toggle.setAttribute("aria-expanded", "false");
      if (focus) toggle.focus();
    }
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      if (!open) { var first = menu.querySelector("a"); if (first) first.focus(); }
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(true); });
    document.addEventListener("click", function (e) { if (!e.target.closest(".sitenav")) close(false); });
  }
})();
