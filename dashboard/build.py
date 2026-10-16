"""Point d'entrée : data/*.csv -> docs/stats.json + docs/index.html."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dashboard import stats
from dashboard.anomalies import ERROR, RULES, WARNING
from dashboard.config import DATA_DIR, OUTPUT_DIR
from dashboard.loader import load_providers
from dashboard.validation import validate

TIMEZONE = ZoneInfo("Europe/Paris")
TEMPLATE = Path(__file__).parent / "templates" / "index.html"
PLACEHOLDER = "__STATS_JSON__"


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
    return result


def render_html(result: dict) -> str:
    """Intègre les stats dans la page : elle s'ouvre aussi en local (file://), sans serveur.

    Les « < » sont échappés pour qu'aucune valeur (ex. un nom de produit contenant
    « </script> ») ne puisse fermer la balise et injecter du HTML.
    """
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise ValueError(f"Le gabarit doit contenir {PLACEHOLDER} exactement une fois.")
    payload = json.dumps(result, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    return template.replace(PLACEHOLDER, payload)


def write_outputs(result: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "stats.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    html_path = out_dir / "index.html"
    html_path.write_text(render_html(result), encoding="utf-8")
    return json_path, html_path


def main(data_dir: Path = DATA_DIR, out_dir: Path = OUTPUT_DIR) -> dict:
    result = build_stats(data_dir)
    json_path, html_path = write_outputs(result, out_dir)
    rep = result["anomalies"]
    print(
        f"{result['headline']['total_offers']} offres valides ({rep['rows_read']} lues, "
        f"{rep['rows_excluded']} exclues) · {rep['errors']} erreur(s), {rep['warnings']} avertissement(s) -> {html_path}, {json_path.name}"
    )
    return result


if __name__ == "__main__":
    main()
