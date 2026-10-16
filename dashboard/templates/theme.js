// Thème appliqué avant le premier rendu (pas de flash) : auto, clair ou sombre.
// Seule donnée stockée par le site : la clé localStorage « theme » ("light" ou "dark"),
// enregistrée uniquement quand le visiteur choisit un thème (aucun cookie).
(function () {
  try {
    var t = localStorage.getItem("theme");
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  } catch (e) {}
})();
