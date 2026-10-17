"""Pages de contenu générées : mentions légales et fiches fournisseurs."""

from datetime import date
from html import escape

from dashboard import site
from dashboard.config import AUTHOR, GITHUB_URL, HOST, LEGAL_UPDATED, LINKEDIN_URL

NBSP = "\u202f"


def _n(v, d=0):
    if v is None:
        return "—"
    return f"{v:,.{d}f}".replace(",", NBSP).replace(".", ",")


def _eur(v, d=2):
    return "—" if v is None else f"{_n(v, d)}{NBSP}€"


def _pct(v, d=0):
    return "—" if v is None else f"{_n(v * 100, d)}{NBSP}%"


def _points(share, reference):
    """Écart entre deux parts, en points (38 % contre 35 % : +3 points, et non « 9 % de plus »)."""
    if share is None or reference is None:
        return ""
    pts = round((share - reference) * 100)
    gap = "au niveau du marché" if pts == 0 else f"{'+' if pts > 0 else '−'}{abs(pts)} point{'s' if abs(pts) > 1 else ''} par rapport au marché"
    return f'<span class="delta">{gap} ({_pct(reference)})</span>'


def _delta(value, reference, fmt, lower_is_better=True):
    """« 3 % moins cher que le marché » : écart relatif lisible, avec le sens."""
    if value is None or not reference:
        return ""
    gap = value / reference - 1
    if abs(gap) < 0.005:
        return '<span class="delta">au niveau du marché</span>'
    good = (gap < 0) == lower_is_better
    word = ("moins" if gap < 0 else "plus") + (" cher" if lower_is_better else "")
    return f'<span class="delta {"good" if good else "bad"}">{_pct(abs(gap))} {word} que le marché ({fmt(reference)})</span>'


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




def provider_page(p: dict, market: dict, context: dict, neighbours: tuple[str | None, str | None], paths: dict) -> str:
    """Fiche d'un fournisseur (page dans fournisseurs/, d'où le préfixe ../)."""
    root = "../"
    prev_name, next_name = neighbours
    link = lambda name: f'<a href="{root}{paths[name]}">{escape(name)}</a>'  # noqa: E731

    def kpi(label, value, sub):
        return f'<article class="card kpi"><div class="kpi-top">{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></article>'

    rank_ppg = f"{p['rank_price_per_gb']}<sup>e</sup> sur {p['providers_count']}" if p["rank_price_per_gb"] else "—"
    rank_ppg = rank_ppg.replace("1<sup>e</sup>", "1<sup>er</sup>", 1) if p["rank_price_per_gb"] == 1 else rank_ppg
    index = p["price_index"]
    index_txt = ("au prix moyen du marché" if abs(index - 100) < 0.5 else
                 f"{_n(abs(index - 100), 1)} % {'moins cher' if index < 100 else 'plus cher'} que le marché, à offre comparable")
    kpis = "".join([
        kpi("Offres", _n(p["offers"]), f"{_pct(p['share'], 1)} du catalogue · dont {_n(p['unlimited'])} illimités"),
        kpi("Prix moyen", _eur(p["mean_price"]), _delta(p["mean_price"], market["mean_price"], _eur)),
        kpi("Prix au Go", _eur(p["price_per_gb"], 3), f"{rank_ppg} · " + _delta(p["price_per_gb"], market["price_per_gb"], _eur)),
        kpi("Indice de prix", _n(index, 1), index_txt),
        kpi("Offres 5G", _pct(p["share_5g"]), _points(p["share_5g"], market["share_5g"])),
        kpi("Recharge possible", _pct(p["share_top_up"]), _points(p["share_top_up"], market["share_top_up"])),
    ])
    best_rows = "".join(
        f"<tr><td class=\"n\">{i}</td><td class=\"wrap-sm\">{escape(o['product_name'])}</td><td>{escape(o['data_display'])}</td>"
        f"<td class=\"n\">{o['validity_days']} j</td><td>{escape(o['network'])}</td><td>{escape(o['top_up'])}</td>"
        f"<td class=\"n\"><b>{_eur(o['price'])}</b></td><td class=\"n\">{_eur(o['price_per_gb'], 3)}</td></tr>"
        for i, o in enumerate(p["best_offers"], 1)
    )
    dest_rows = "".join(
        f"<tr><td>{escape(d['name'])} <span class=\"zero\">{escape(d['code'])}</span>{' <span class=\"badge region\">zone</span>' if d['is_region'] else ''}</td>"
        f"<td class=\"n\">{_n(d['offers'])}</td><td class=\"n\">{_eur(d['min_price'])}</td><td class=\"n\">{_eur(d['price_per_gb'])}</td></tr>"
        for d in p["destinations"]
    )
    max_tier = max([t["offers"] for t in p["data_tiers"]] + [1])
    tiers = "".join(
        f'<li><span>{escape(t["label"])}</span><i style="width:{t["offers"] / max_tier * 100:.1f}%"></i><b>{_n(t["offers"])}</b></li>'
        for t in p["data_tiers"]
    )
    by_validity = " · ".join(f"{c['validity_days']} j : <b>{_n(c['index'], 1)}</b>" for c in p["index_by_validity"])
    nav = " · ".join(x for x in [
        f"← {link(prev_name)}" if prev_name else "",
        f'<a href="{root}index.html#fournisseurs">Tous les fournisseurs</a>',
        f"{link(next_name)} →" if next_name else "",
    ] if x)
    content = f"""
<div class="wrap">
  <p class="crumbs">{nav}</p>
  <div class="kpis">{kpis}</div>

  <div class="grid" style="margin-top:24px">
    <section class="card" aria-labelledby="meilleures">
      <h2 id="meilleures" class="card-title">Les {len(p['best_offers'])} meilleures offres au Go</h2>
      <p class="sub">Forfaits à volume limité, classés par prix au Go</p>
      <div class="table-wrap"><table>
        <thead><tr><th class="n">#</th><th>Offre</th><th>Data</th><th class="n">Durée</th><th>Réseau</th><th>Recharge</th><th class="n">Prix</th><th class="n">€ / Go</th></tr></thead>
        <tbody>{best_rows}</tbody>
      </table></div>
    </section>
    <section class="card" aria-labelledby="volumes">
      <h2 id="volumes" class="card-title">Volumes proposés</h2>
      <p class="sub">Nombre d'offres par palier · indice de prix par durée : {by_validity}</p>
      <ul class="hbars">{tiers}</ul>
      <p class="note">Indice : 100 = prix moyen des offres comparables de tout le marché (même volume, même durée). Source : {", ".join(f"<code>{escape(f)}</code>" for f in p["source_files"])}.</p>
    </section>
  </div>

  <section class="card" style="margin-top:16px" aria-labelledby="destinations">
    <h2 id="destinations" class="card-title">Destinations couvertes</h2>
    <p class="sub">{p['countries_count']} pays et {p['regions_count']} zones régionales</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Destination</th><th class="n">Offres</th><th class="n">Dès</th><th class="n">€ / Go</th></tr></thead>
      <tbody>{dest_rows}</tbody>
    </table></div>
  </section>
</div>
"""
    return site.page(
        title=f"{p['provider']} · Fiche fournisseur · Observatoire eSIM",
        description=f"Fiche du fournisseur eSIM {p['provider']} : offres, prix, prix au Go, indice de prix, destinations.",
        eyebrow="Fiche fournisseur",
        heading=escape(p["provider"]),
        lead=f"{_n(p['offers'])} offres · {p['countries_count']} pays et {p['regions_count']} zones · prix au Go {_eur(p['price_per_gb'])}",
        content=content,
        root=root,
        context=context,
    )
