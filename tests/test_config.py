"""Garde-fous sur le socle : le schéma déclaré correspond bien aux vraies données."""

import csv

from dashboard.config import DATA_DIR, EXPECTED_COLUMNS, REGION_CODES


def test_real_csv_headers_match_expected_schema():
    files = sorted(DATA_DIR.glob("*.csv"))
    assert files, "aucun CSV trouvé dans data/"
    for path in files:
        with path.open(encoding="utf-8", newline="") as f:
            header = next(csv.reader(f))
        assert header == EXPECTED_COLUMNS, path.name


def test_region_codes_include_north_america_na():
    # « NA » est un code légitime (Amérique du Nord), pas une valeur manquante.
    assert REGION_CODES["NA"] == "Amérique du Nord"
