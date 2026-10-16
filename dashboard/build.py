"""Point d'entrée : data/*.csv -> docs/stats.json (et docs/index.html à l'étape 4)."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dashboard import stats
from dashboard.anomalies import ERROR, WARNING
from dashboard.config import DATA_DIR, OUTPUT_DIR
from dashboard.loader import load_providers
from dashboard.validation import validate

TIMEZONE = ZoneInfo("Europe/Paris")


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
        "details": [a.to_dict() for a in anomalies],
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


def write_outputs(result: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "stats.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(data_dir: Path = DATA_DIR, out_dir: Path = OUTPUT_DIR) -> dict:
    result = build_stats(data_dir)
    path = write_outputs(result, out_dir)
    rep = result["anomalies"]
    print(
        f"{result['headline']['total_offers']} offres valides ({rep['rows_read']} lues, "
        f"{rep['rows_excluded']} exclues) · {rep['errors']} erreur(s), {rep['warnings']} avertissement(s) -> {path}"
    )
    return result


if __name__ == "__main__":
    main()
