"""Lecture de tous les CSV fournisseurs présents dans data/.

Tout fichier *.csv déposé dans le dossier est pris en compte, sans modifier le code.
Un fichier illisible ou mal formé est signalé, jamais bloquant.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from dashboard.anomalies import ERROR, WARNING, Anomaly
from dashboard.config import EXPECTED_COLUMNS


@dataclass
class LoadResult:
    rows: pd.DataFrame  # toutes les lignes brutes (texte), + source_file et line
    anomalies: list[Anomaly] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)  # bilan par fichier


def read_csv_as_text(path: Path) -> pd.DataFrame:
    # keep_default_na=False : sinon pandas transforme le code « NA »
    # (Amérique du Nord) en valeur manquante. Tout est lu en texte, la
    # conversion numérique est faite (et contrôlée) par la validation.
    # utf-8-sig : tolère un BOM en début de fichier (export Excel).
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def load_providers(data_dir: Path) -> LoadResult:
    frames = []
    anomalies: list[Anomaly] = []
    files: list[dict] = []

    for path in sorted(data_dir.glob("*.csv")):
        name = path.name
        status = {"file": name, "rows": 0, "status": "ok"}
        files.append(status)

        try:
            df = read_csv_as_text(path)
        except pd.errors.EmptyDataError:
            anomalies.append(Anomaly(ERROR, "fichier_vide", "Fichier vide, ignoré.", name))
            status["status"] = "ignoré"
            continue
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            anomalies.append(
                Anomaly(ERROR, "fichier_illisible", f"Fichier illisible, ignoré ({type(exc).__name__}).", name)
            )
            status["status"] = "ignoré"
            continue

        df.columns = [c.strip() for c in df.columns]
        missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
        if missing:
            anomalies.append(
                Anomaly(ERROR, "colonnes_manquantes", f"Colonnes manquantes : {', '.join(missing)}. Fichier ignoré.", name)
            )
            status["status"] = "ignoré"
            continue
        extra = [c for c in df.columns if c not in EXPECTED_COLUMNS]
        if extra:
            anomalies.append(
                Anomaly(WARNING, "colonnes_en_trop", f"Colonnes inconnues ignorées : {', '.join(extra)}.", name)
            )
        if df.empty:
            anomalies.append(Anomaly(WARNING, "fichier_sans_ligne", "En-tête présent mais aucune ligne.", name))

        df = df[EXPECTED_COLUMNS].apply(lambda s: s.str.strip())
        df["source_file"] = name
        df["line"] = range(2, len(df) + 2)
        status["rows"] = len(df)
        frames.append(df)

    if frames:
        rows = pd.concat(frames, ignore_index=True)
    else:
        rows = pd.DataFrame(columns=[*EXPECTED_COLUMNS, "source_file", "line"])
    return LoadResult(rows=rows, anomalies=anomalies, files=files)
