"""Pages de contenu générées : mentions légales (et, au lot D, « Comment c'est construit »
et les fiches fournisseurs)."""

from datetime import date
from html import escape

from dashboard import site
from dashboard.config import AUTHOR, GITHUB_URL, HOST, LEGAL_UPDATED, LINKEDIN_URL


def _french_day(iso: str) -> str:
    months = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    d = date.fromisoformat(iso)
    return f"{d.day}{'er' if d.day == 1 else ''} {months[d.month - 1]} {d.year}"


def legal_page(context: dict) -> str:
    repo = context["version"]["repo_url"]
    link = lambda url, label: f'<a href="{escape(url)}" rel="noopener noreferrer">{escape(label)}</a>'  # noqa: E731
    content = f"""
<div class="wrap prose">
  <section aria-labelledby="editeur">
    <h2 id="editeur">Éditeur du site</h2>
    <p><b>{escape(AUTHOR)}</b>, étudiant ingénieur. Site personnel, non commercial, réalisé dans le cadre d'un test de recrutement.</p>
    <p>Contact : uniquement via {link(GITHUB_URL, "GitHub")} ou {link(LINKEDIN_URL, "LinkedIn")}. Conformément à l'article 6-III-2 de la loi n° 2004-575 du 21 juin 2004 pour la confiance dans l'économie numérique (LCEN), l'éditeur, personne physique agissant à titre non professionnel, ne publie pas son adresse ; ses coordonnées ont été communiquées à l'hébergeur.</p>
  </section>

  <section aria-labelledby="directeur">
    <h2 id="directeur">Directeur de la publication</h2>
    <p>{escape(AUTHOR)}.</p>
  </section>

  <section aria-labelledby="hebergeur">
    <h2 id="hebergeur">Hébergeur</h2>
    <p><b>{escape(HOST["name"])}</b><br>{escape(HOST["address"])}</p>
    <p>GitHub ne publie pas de numéro de téléphone ; contact via son {link(HOST["contact"], "formulaire d'assistance")}. Adresse vérifiée le 16 octobre 2026 dans la {link(HOST["source"], "déclaration de confidentialité de GitHub")}.</p>
  </section>

  <section aria-labelledby="propriete">
    <h2 id="propriete">Propriété intellectuelle</h2>
    <ul>
      <li>Cet outil est <b>non officiel</b> : il n'est ni édité ni validé par MyBestSim.</li>
      <li>Le nom « MyBestSim » et son identité visuelle appartiennent à leur propriétaire ; le site s'en inspire sans reprendre le logo.</li>
      <li>Les données sont les <b>fichiers de test fournis par MyBestSim</b> pour le recrutement.</li>
      <li>Le code source est publié sous <b>licence MIT</b> ({link(repo + "/blob/main/LICENSE", "fichier LICENSE")}). La police Inter est sous licence SIL OFL 1.1, Chart.js et chartjs-chart-geo sous licence MIT, le fond de carte world-atlas sous licence ISC (données Natural Earth, domaine public).</li>
    </ul>
  </section>

  <section aria-labelledby="donnees">
    <h2 id="donnees">Données personnelles</h2>
    <p><b>Aucune donnée personnelle n'est collectée.</b> Le site n'a ni formulaire, ni compte, ni mesure d'audience, ni publicité. Il ne transmet rien à aucun service tiers : la police, les librairies et le fond de carte sont hébergés sur le site lui-même.</p>
    <p>Comme pour tout site, l'hébergeur peut journaliser des données techniques de connexion (adresse IP, date, page demandée) pour la sécurité de son service ; ce traitement relève de GitHub et de sa {link(HOST["source"], "politique de confidentialité")}.</p>
  </section>

  <section aria-labelledby="cookies">
    <h2 id="cookies">Cookies et traceurs</h2>
    <p><b>Ce site ne dépose aucun cookie et n'utilise aucun traceur.</b> C'est pourquoi il n'affiche pas de bandeau de consentement.</p>
    <p>Une seule information peut être enregistrée dans votre navigateur, et seulement si vous la choisissez : votre <b>préférence de thème</b> (clair ou sombre), dans le stockage local (<code>localStorage</code>) sous la clé <code>theme</code>, avec la valeur <code>light</code> ou <code>dark</code>. Elle n'est jamais transmise et sert uniquement à afficher le thème que vous avez demandé. Ce stockage, strictement nécessaire à un service que vous demandez expressément, est exempté de consentement selon les recommandations de la CNIL.</p>
    <p>Pour l'effacer : choisissez le thème « automatique » (icône d'écran dans l'en-tête), utilisez le bouton ci-dessous, ou effacez les données du site dans les réglages de votre navigateur.</p>
    <p><button class="btn" type="button" id="clear-theme"><svg class="icon" aria-hidden="true"><use href="#i-x"/></svg>Effacer ma préférence de thème</button> <span class="sub" id="clear-theme-status" role="status" aria-live="polite"></span></p>
    <p>Mesures techniques : une politique de sécurité du contenu (CSP) stricte interdit à chaque page de charger une ressource externe ou d'ouvrir une connexion réseau. Un test automatique vérifie, page par page, qu'aucun cookie n'est déposé et qu'aucun domaine externe n'est contacté.</p>
  </section>

  <p class="updated">Dernière mise à jour de cette page : {_french_day(LEGAL_UPDATED)}.</p>
</div>
"""
    return site.page(
        title="Mentions légales · Observatoire eSIM",
        description="Mentions légales, données personnelles, cookies et traceurs de l'Observatoire eSIM.",
        eyebrow="Informations légales",
        heading="Mentions légales",
        lead="Éditeur, hébergeur, propriété intellectuelle, données personnelles, cookies et traceurs.",
        content=content,
        active="mentions-legales.html",
        context=context,
    )


def built_page(context: dict, notes_html: str = "") -> str:
    """« Comment c'est construit » (version courte, complétée au lot D)."""
    content = """
<div class="wrap prose">
  <section aria-labelledby="pipeline">
    <h2 id="pipeline">Le pipeline</h2>
    <p>Les fichiers CSV des fournisseurs sont validés et agrégés en Python, testés, puis publiés en site statique par une GitHub Action.</p>
  </section>
</div>
"""
    return site.page(
        title="Comment c'est construit · Observatoire eSIM",
        description="Pipeline, choix techniques, sécurité et journal de construction de l'Observatoire eSIM.",
        eyebrow="Coulisses",
        heading="Comment c'est construit",
        lead="Du fichier CSV à la page publiée : pipeline, choix techniques, sécurité et journal de travail avec l'IA.",
        content=content,
        active="comment-c-est-construit.html",
        context=context,
    )
