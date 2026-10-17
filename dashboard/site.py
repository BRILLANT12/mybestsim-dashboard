"""Mise en page commune à toutes les pages : <head> (avec la CSP), barre du haut, pied de page.

Chaque page est un gabarit HTML avec trois emplacements, remplis ici :
<!--@HEAD-->, <!--@TOPBAR--> et <!--@FOOTER-->. Les chemins sont relatifs (`root`)
pour que le site fonctionne aussi bien sur GitHub Pages qu'ouvert en double-clic.
"""

from html import escape
from pathlib import Path

from dashboard.config import AUTHOR, CONTENT_SECURITY_POLICY, GITHUB_URL, LINKEDIN_URL

ICONS = (Path(__file__).parent / "templates" / "icons.svg").read_text(encoding="utf-8")

# Menu des pages (chemin depuis la racine du site, libellé).
PAGES = [
    ("index.html", "Tableau de bord"),
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


def _ext(url: str, label: str, icon: str = "") -> str:
    """Lien externe : simple navigation (aucune ressource chargée), sans transmettre la page d'origine."""
    ico = f'<svg class="icon" aria-hidden="true"><use href="#i-{icon}"/></svg>' if icon else ""
    return f'<a href="{escape(url)}" rel="noopener noreferrer">{ico}{escape(label)}</a>'


def footer(root: str, context: dict) -> str:
    """Pied de page commun : projet, données, technique, puis barre légale."""
    meta = context.get("meta", {})
    version = context.get("version", {"repo_url": "", "sha": "", "short_sha": ""})
    repo = version["repo_url"]
    files = meta.get("files_count", 0)
    return f"""<footer class="foot">
  <div class="wrap">
    <div class="foot-grid">
      <section aria-labelledby="f-projet">
        <h2 id="f-projet">Projet</h2>
        <p><b>Observatoire eSIM</b>, réalisé par {escape(AUTHOR)} pour le test de recrutement MyBestSim.</p>
        <ul class="foot-links">
          <li>{_ext(GITHUB_URL, "GitHub", "github")}</li>
          <li>{_ext(LINKEDIN_URL, "LinkedIn", "linkedin")}</li>
        </ul>
      </section>
      <section aria-labelledby="f-donnees">
        <h2 id="f-donnees">Données</h2>
        <p>{files} {"fichier fournisseur" if files == 1 else "fichiers fournisseurs"} · dernière génération le <span id="footer-gen">{escape(context.get("generated_text", ""))}</span> (heure de Paris).</p>
        <ul class="foot-links">
          <li><a href="{root}stats.json" download><svg class="icon" aria-hidden="true"><use href="#i-file"/></svg>stats.json</a></li>
          <li><a href="{root}{context.get("csv_export", "offres-esim.csv")}" download><svg class="icon" aria-hidden="true"><use href="#i-download"/></svg>Export CSV complet</a></li>
        </ul>
      </section>
      <section aria-labelledby="f-technique">
        <h2 id="f-technique">Technique</h2>
        <p>Python, pandas, Chart.js, GitHub Actions</p>
        <ul class="foot-links">
          <li>{_ext(repo, "Code source", "code")}</li>
        </ul>
      </section>
    </div>
    <div class="foot-bottom">
      <a href="{root}mentions-legales.html#cookies"><svg class="icon" aria-hidden="true"><use href="#i-cookie"/></svg>Aucun cookie · aucun traceur</a>
      <span>Outil non officiel, inspiré de l'identité visuelle de mybestsim.com</span>
      <a href="{root}mentions-legales.html">Mentions légales</a>
      <a href="#haut"><svg class="icon" aria-hidden="true"><use href="#i-arrow-up"/></svg>Retour en haut</a>
    </div>
  </div>
</footer>"""


def page(*, title: str, description: str, eyebrow: str, heading: str, lead: str, content: str,
         root: str = "", active: str = "", context: dict | None = None, scripts: tuple[str, ...] = ()) -> str:
    """Page de contenu (mentions légales, fiches…) : même en-tête, même pied de page."""
    template = f"""<!doctype html>
<html lang="fr">
<head>
<!--@HEAD-->
</head>
<body>
<a class="skip" href="#main">Aller au contenu</a>
<header class="hero hero-compact" id="haut">
  <div class="wrap">
<!--@TOPBAR-->
    <div class="hero-head">
      <p class="eyebrow">{eyebrow}</p>
      <h1>{heading}</h1>
      <p class="hero-sub">{lead}</p>
    </div>
  </div>
</header>
<main id="main" class="prose-page">
{content}
</main>
<!--@FOOTER-->
</body>
</html>
"""
    return fill(template, title=title, description=description, root=root, active=active, scripts=scripts, context=context)


def fill(template: str, *, title: str, description: str, root: str = "", active: str = "",
         scripts: tuple[str, ...] = (), context: dict | None = None) -> str:
    context = context or {}
    for marker in ("<!--@HEAD-->", "<!--@TOPBAR-->", "<!--@FOOTER-->"):
        if template.count(marker) != 1:
            raise ValueError(f"Le gabarit doit contenir {marker} exactement une fois.")
    return (template.replace("<!--@HEAD-->", head(title, description, root, scripts))
            .replace("<!--@TOPBAR-->", topbar(root, active))
            .replace("<!--@FOOTER-->", footer(root, context)))
