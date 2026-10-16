"""Mise en page commune à toutes les pages : <head> (avec la CSP), barre du haut, pied de page.

Chaque page est un gabarit HTML avec trois emplacements, remplis ici :
<!--@HEAD-->, <!--@TOPBAR--> et <!--@FOOTER-->. Les chemins sont relatifs (`root`)
pour que le site fonctionne aussi bien sur GitHub Pages qu'ouvert en double-clic.
"""

from html import escape
from pathlib import Path

from dashboard.config import CONTENT_SECURITY_POLICY

ICONS = (Path(__file__).parent / "templates" / "icons.svg").read_text(encoding="utf-8")

# Menu des pages (chemin depuis la racine du site, libellé).
PAGES = [
    ("index.html", "Tableau de bord"),
    ("comment-c-est-construit.html", "Comment c'est construit"),
    ("mentions-legales.html", "Mentions légales"),
]

THEME_SWITCH = """      <div class="theme-switch" role="group" aria-label="Thème d'affichage">
        <button type="button" data-mode="auto" title="Thème automatique" aria-label="Thème automatique"><svg class="icon" aria-hidden="true"><use href="#i-auto"/></svg></button>
        <button type="button" data-mode="light" title="Thème clair" aria-label="Thème clair"><svg class="icon" aria-hidden="true"><use href="#i-sun"/></svg></button>
        <button type="button" data-mode="dark" title="Thème sombre" aria-label="Thème sombre"><svg class="icon" aria-hidden="true"><use href="#i-moon"/></svg></button>
      </div>"""


def head(title: str, description: str, root: str = "", scripts: tuple[str, ...] = ()) -> str:
    """<head> commun. `scripts` : fichiers de assets/ chargés en différé, dans l'ordre."""
    deferred = "\n".join(f'<script src="{root}assets/{s}" defer></script>' for s in scripts)
    return f"""<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CONTENT_SECURITY_POLICY}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="robots" content="noindex">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<link rel="preload" href="{root}assets/fonts/inter-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{root}assets/site.css">
<script src="{root}assets/theme.js"></script>
<script src="{root}assets/site.js" defer></script>
{deferred}"""


def topbar(root: str = "", active: str = "") -> str:
    """Marque, menu des pages (replié en bouton sur mobile) et choix du thème."""
    links = "\n".join(
        f'          <li><a href="{root}{path}"{" aria-current=\"page\"" if path == active else ""}>{escape(label)}</a></li>'
        for path, label in PAGES
    )
    return ICONS + f"""    <div class="topbar">
      <a class="brand" href="{root}index.html" aria-label="Observatoire MyBestSim, accueil">
        <span class="brand-mark" aria-hidden="true">MB</span>
        <span><b>MyBestSim</b> <span>Observatoire</span></span>
      </a>
      <nav class="sitenav" aria-label="Pages du site">
        <button class="menu-btn" type="button" aria-expanded="false" aria-controls="site-menu"><svg class="icon" aria-hidden="true"><use href="#i-menu"/></svg>Menu</button>
        <ul id="site-menu">
{links}
        </ul>
      </nav>
{THEME_SWITCH}
    </div>"""


def footer(root: str, context: dict) -> str:
    """Pied de page commun (enrichi au lot C)."""
    return f"""<footer class="foot">
  <div class="wrap">
    <p id="footer-gen">Dernière génération : <b>{escape(context.get("generated_text", ""))}</b> (heure de Paris).</p>
    <p>Projet réalisé dans le cadre d'un test de recrutement <b>MyBestSim</b>. Outil non officiel, inspiré de l'identité visuelle de mybestsim.com.</p>
  </div>
</footer>"""


def fill(template: str, *, title: str, description: str, root: str = "", active: str = "",
         scripts: tuple[str, ...] = (), context: dict | None = None) -> str:
    context = context or {}
    for marker in ("<!--@HEAD-->", "<!--@TOPBAR-->", "<!--@FOOTER-->"):
        if template.count(marker) != 1:
            raise ValueError(f"Le gabarit doit contenir {marker} exactement une fois.")
    return (template.replace("<!--@HEAD-->", head(title, description, root, scripts))
            .replace("<!--@TOPBAR-->", topbar(root, active))
            .replace("<!--@FOOTER-->", footer(root, context)))
