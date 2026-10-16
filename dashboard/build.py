"""Point d'entrée : data/*.csv -> site statique dans docs/ (pages, assets, stats.json)."""

import json
import os
import shutil
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dashboard import pages, site, stats
from dashboard.dataset import encode_offers
from dashboard.anomalies import ERROR, RULES, WARNING
from dashboard.config import DATA_DIR, DEFAULT_REPOSITORY, EXPECTED_COLUMNS, OUTPUT_DIR, VENDOR_DIR
from dashboard.dataset import decode_offers
from dashboard.loader import load_providers
from dashboard.validation import validate

TIMEZONE = ZoneInfo("Europe/Paris")
TEMPLATES = Path(__file__).parent / "templates"
TEMPLATE = TEMPLATES / "index.html"
PLACEHOLDER = "__STATS_JSON__"
OFFERS_PLACEHOLDER = "__OFFERS_JSON__"

# Fichiers copiés tels quels dans docs/assets/ (tout est servi par le site lui-même).
OWN_ASSETS = ["site.css", "theme.js", "site.js", "analytics.js", "dashboard.js", "favicon.svg"]
VENDOR_ASSETS = {
    "chart.umd.min.js": "vendor/chart.umd.min.js",
    "chartjs-chart-geo.umd.min.js": "vendor/chartjs-chart-geo.umd.min.js",
    "fonts/inter-latin-wght-normal.woff2": "fonts/inter-latin-wght-normal.woff2",
    "fonts/inter-latin-ext-wght-normal.woff2": "fonts/inter-latin-ext-wght-normal.woff2",
    "fonts/OFL.txt": "fonts/OFL.txt",
}
DASHBOARD_SCRIPTS = ("vendor/chart.umd.min.js", "vendor/chartjs-chart-geo.umd.min.js", "vendor/world-110m.js", "analytics.js", "dashboard.js")


def anomaly_report(anomalies, files, total_rows, excluded_rows) -> dict:
    by_rule = Counter((a.severity, a.rule) for a in anomalies)
    return {
        "errors": sum(1 for a in anomalies if a.severity == ERROR),
        "warnings": sum(1 for a in anomalies if a.severity == WARNING),
        "rows_read": total_rows,
        "rows_excluded": excluded_rows,
        "by_rule": [
            {"severity": sev, "rule": rule, "count": count}
            for (sev, rule), count in sorted(by_rule.items(), key=lambda kv: (kv[0][0] != ERROR, -kv[1], kv[0][1]))
        ],
        "checks": [
            {"rule": rule, "severity": sev, "label": label, "count": by_rule.get((sev, rule), 0)}
            for rule, (sev, label) in RULES.items()
        ],
        # Ordre de lecture : fichier, puis ligne (les anomalies de niveau fichier en tête).
        "details": [a.to_dict() for a in sorted(anomalies, key=lambda a: (a.file, a.line or 0, a.severity != ERROR))],
        "files": files,
    }


def build_stats(data_dir: Path, now: datetime | None = None) -> dict:
    return build(data_dir, now)[0]


def build(data_dir: Path, now: datetime | None = None) -> tuple[dict, dict]:
    """Renvoie (statistiques globales, offres valides encodées pour les filtres)."""
    loaded = load_providers(data_dir)
    validated = validate(loaded.rows)
    result = stats.compute(validated.clean)
    result["meta"] = {
        "generated_at": (now or datetime.now(TIMEZONE)).isoformat(timespec="seconds"),
        "files_count": sum(1 for f in loaded.files if f["status"] == "ok"),
        "providers_count": len(result["providers"]),
    }
    result["anomalies"] = anomaly_report(
        loaded.anomalies + validated.anomalies, loaded.files, validated.total_rows, validated.excluded_rows
    )
    return result, encode_offers(validated.clean)


def _embed(data: dict) -> str:
    # Les « < » sont échappés pour qu'aucune valeur (ex. un nom de produit contenant
    # « </script> ») ne puisse fermer la balise et injecter du HTML.
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")


MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
CSV_EXPORT = "offres-esim.csv"


def french_date(d: datetime, with_time: bool = True) -> str:
    text = f"{d.day}{'er' if d.day == 1 else ''} {MONTHS[d.month - 1]} {d.year}"
    return text + (f" à {d:%H:%M}" if with_time else "")


def source_version() -> dict:
    """Dépôt et commit d'où provient la génération (affichés dans le pied de page).

    En CI, GitHub fournit GITHUB_REPOSITORY et GITHUB_SHA ; en local, on interroge git.
    """
    repo = os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPOSITORY
    sha = os.environ.get("GITHUB_SHA", "")
    if not sha:
        try:
            sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10,
                                 cwd=Path(__file__).parent).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            sha = ""
    return {"repo_url": f"https://github.com/{repo}", "sha": sha, "short_sha": sha[:7]}


def page_context(result: dict) -> dict:
    """Informations communes aux pages (pied de page, etc.)."""
    generated = datetime.fromisoformat(result["meta"]["generated_at"])
    return {"generated_text": french_date(generated), "meta": result["meta"], "version": source_version(), "csv_export": CSV_EXPORT}


def offers_csv(offers: dict) -> str:
    """Export complet des offres valides, au format exact des fichiers sources (comme le bouton
    « Exporter CSV » du navigateur) : peut être redéposé dans data/."""
    def cell(v):
        if v is None:
            s = ""
        elif isinstance(v, float):  # même écriture que JavaScript : 10.0 -> « 10 », 17.4 -> « 17.4 »
            s = str(int(v)) if v.is_integer() else repr(v)
        else:
            s = str(v)
        return '"' + s.replace('"', '""') + '"' if any(c in s for c in ',"\n\r') else s
    lines = [",".join(EXPECTED_COLUMNS)]
    for row in decode_offers(offers):
        lines.append(",".join(cell(row[c]) for c in EXPECTED_COLUMNS))
    return "\ufeff" + "\n".join(lines) + "\n"


def render_html(result: dict, offers: dict | None = None) -> str:
    """Tableau de bord. Stats et offres sont intégrées en JSON (données, non exécutées) :
    la page s'ouvre aussi en local (file://), sans serveur."""
    template = TEMPLATE.read_text(encoding="utf-8")
    for marker in (PLACEHOLDER, OFFERS_PLACEHOLDER):
        if template.count(marker) != 1:
            raise ValueError(f"Le gabarit doit contenir {marker} exactement une fois.")
    offers = offers or {"fields": [], "currency": "EUR", "dict": {}, "rows": []}
    html = site.fill(
        template,
        title="Observatoire eSIM · MyBestSim",
        description="Tableau de bord interne du catalogue d'offres eSIM : volumes, prix, data, fournisseurs, destinations et qualité des données.",
        active="index.html",
        scripts=DASHBOARD_SCRIPTS,
        context=page_context(result),
    )
    return html.replace(PLACEHOLDER, _embed(result)).replace(OFFERS_PLACEHOLDER, _embed(offers))


def write_assets(out_dir: Path) -> None:
    """Copie les fichiers du site (CSS, JS, police, librairies) : aucun fichier n'est servi par un tiers."""
    assets = out_dir / "assets"
    (assets / "vendor").mkdir(parents=True, exist_ok=True)
    (assets / "fonts").mkdir(parents=True, exist_ok=True)
    for name in OWN_ASSETS:
        shutil.copyfile(TEMPLATES / name, assets / name)
    for source, target in VENDOR_ASSETS.items():
        shutil.copyfile(VENDOR_DIR / source, assets / target)
    # Fond de carte en script (et non en JSON chargé par fetch, bloqué quand la page
    # est ouverte en local) : window.WORLD_TOPO.
    topo = (VENDOR_DIR / "countries-110m.json").read_text(encoding="utf-8").strip()
    (assets / "vendor" / "world-110m.js").write_text(
        "/* world-atlas 2.0.2, countries-110m (Natural Earth, domaine public) */\nwindow.WORLD_TOPO = " + topo + ";\n", encoding="utf-8"
    )


def write_pages(result: dict, out_dir: Path) -> None:
    """Pages de contenu générées à chaque build."""
    context = page_context(result)
    (out_dir / "mentions-legales.html").write_text(pages.legal_page(context), encoding="utf-8")
    (out_dir / "comment-c-est-construit.html").write_text(pages.built_page(context), encoding="utf-8")


def write_outputs(result: dict, out_dir: Path, offers: dict | None = None) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_assets(out_dir)
    json_path = out_dir / "stats.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    html_path = out_dir / "index.html"
    html_path.write_text(render_html(result, offers), encoding="utf-8")
    (out_dir / CSV_EXPORT).write_text(offers_csv(offers or {"fields": [], "currency": "EUR", "dict": {"country": []}, "rows": []}), encoding="utf-8")
    write_pages(result, out_dir)
    return json_path, html_path


def main(data_dir: Path = DATA_DIR, out_dir: Path = OUTPUT_DIR) -> dict:
    result, offers = build(data_dir)
    json_path, html_path = write_outputs(result, out_dir, offers)
    rep = result["anomalies"]
    print(
        f"{result['headline']['total_offers']} offres valides ({rep['rows_read']} lues, "
        f"{rep['rows_excluded']} exclues) · {rep['errors']} erreur(s), {rep['warnings']} avertissement(s) -> {html_path}, {json_path.name}"
    )
    return result


if __name__ == "__main__":
    main()
