"""Chargement et validation, sur le jeu de CSV pièges (tests/fixtures/pieges/).

Contenu du jeu (18 lignes lues, 9 exclues, 9 gardées) :
- alpha.csv : BOM UTF-8, code NA, illimité > 100 €, prix « 12,50 », espaces autour
  d'un code pays, data_gb ≠ data_display, réseau 3G et recharge « yes ».
- beta.csv : prix 0 / négatif / vide / « abc », devise USD, SKU déjà vu dans alpha,
  pays vide, data_gb vide hors illimité, durée 7,5 j, deux offres identiques.
- gamma.csv : colonne en trop. vide.csv : 0 octet. mauvais_schema.csv : pas de
  colonne price. lisezmoi.txt : pas un CSV.
"""

from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

from dashboard.anomalies import ERROR, WARNING
from dashboard.loader import load_providers, read_csv_as_text
from dashboard.validation import validate

PIEGES = Path(__file__).parent / "fixtures" / "pieges"
HEADER = "sku,provider,product_name,country_code,country_name,data_gb,data_display,validity_days,price,currency,network,top_up"


@pytest.fixture(scope="module")
def result():
    loaded = load_providers(PIEGES)
    validated = validate(loaded.rows)
    return loaded, validated


def rules(anomalies, severity):
    return Counter(a.rule for a in anomalies if a.severity == severity)


# --- Le piège « NA » -------------------------------------------------------


def test_na_country_code_is_kept_not_treated_as_missing(result):
    _, validated = result
    na_rows = validated.clean[validated.clean["country_code"] == "NA"]
    assert list(na_rows["sku"]) == ["alpha-1"]
    assert bool(na_rows["is_region"].iloc[0]) is True


def test_default_pandas_would_have_lost_na_but_our_reader_does_not():
    # Documente le piège : la lecture pandas par défaut transforme « NA » en NaN.
    path = PIEGES / "alpha.csv"
    assert pd.read_csv(path, encoding="utf-8-sig")["country_code"].isna().sum() == 1
    assert (read_csv_as_text(path)["country_code"] == "NA").sum() == 1


# --- Niveau fichier ---------------------------------------------------------


def test_every_csv_is_discovered_and_non_csv_ignored(result):
    loaded, _ = result
    names = [f["file"] for f in loaded.files]
    assert names == ["alpha.csv", "beta.csv", "gamma.csv", "mauvais_schema.csv", "vide.csv"]


def test_broken_files_are_reported_not_crashing(result):
    loaded, _ = result
    by_file = {a.file: a.rule for a in loaded.anomalies if a.severity == ERROR}
    assert by_file == {"vide.csv": "fichier_vide", "mauvais_schema.csv": "colonnes_manquantes"}
    status = {f["file"]: f["status"] for f in loaded.files}
    assert status["vide.csv"] == status["mauvais_schema.csv"] == "ignoré"


def test_extra_column_is_ignored_with_warning(result):
    loaded, validated = result
    assert rules(loaded.anomalies, WARNING) == {"colonnes_en_trop": 1}
    assert "promo" not in validated.clean.columns
    assert "gamma-1" in set(validated.clean["sku"])


def test_bom_does_not_corrupt_first_column(result):
    loaded, _ = result
    assert "sku" in loaded.rows.columns
    assert loaded.rows.loc[loaded.rows["source_file"] == "alpha.csv", "sku"].iloc[0] == "alpha-1"


def test_undecodable_file_is_reported(tmp_path):
    (tmp_path / "latin1.csv").write_bytes((HEADER + "\nx-1,X,eSIM Cor\xe9e,KR,Cor\xe9e,1,1 Go,7,5,EUR,4G,oui\n").encode("latin-1"))
    loaded = load_providers(tmp_path)
    assert [a.rule for a in loaded.anomalies] == ["fichier_illisible"]
    assert loaded.rows.empty


def test_empty_data_dir_does_not_crash(tmp_path):
    loaded = load_providers(tmp_path)
    validated = validate(loaded.rows)
    assert validated.total_rows == 0 and validated.clean.empty


# --- Niveau ligne ------------------------------------------------------------


def test_row_counts(result):
    _, validated = result
    assert validated.total_rows == 18
    assert validated.excluded_rows == 9
    assert len(validated.clean) == 9


def test_errors_exclude_the_right_rows(result):
    _, validated = result
    assert rules(validated.anomalies, ERROR) == {
        "prix_non_positif": 2,  # beta-1 (0), beta-2 (-3)
        "champ_vide": 2,  # beta-3 (price), beta-5 (country_name)
        "devise": 1,  # beta-4 (USD)
        "data_manquante": 1,  # beta-6
        "prix_illisible": 1,  # beta-7
        "duree_invalide": 1,  # beta-8 (7.5 jours)
        "sku_duplique": 1,  # alpha-1 repris dans beta.csv
    }
    kept = set(validated.clean["sku"])
    assert not kept & {f"beta-{i}" for i in range(1, 9)}


def test_duplicate_sku_keeps_first_occurrence(result):
    _, validated = result
    alpha1 = validated.clean[validated.clean["sku"] == "alpha-1"]
    assert len(alpha1) == 1 and alpha1["source_file"].iloc[0] == "alpha.csv"
    dup = next(a for a in validated.anomalies if a.rule == "sku_duplique")
    assert (dup.file, dup.line) == ("beta.csv", 6)
    assert "alpha.csv, ligne 2" in dup.message


def test_warnings_keep_the_rows(result):
    _, validated = result
    assert rules(validated.anomalies, WARNING) == {
        "virgule_decimale": 1,  # alpha-3
        "data_incoherente": 1,  # alpha-5
        "reseau_inconnu": 1,  # alpha-6
        "recharge_inconnue": 1,  # alpha-6
        "doublon_probable": 1,  # beta-10 = beta-9
    }
    assert {"alpha-3", "alpha-5", "alpha-6", "beta-9", "beta-10"} <= set(validated.clean["sku"])


def test_typed_values(result):
    _, validated = result
    clean = validated.clean.set_index("sku")
    assert clean.loc["alpha-3", "price"] == 12.5  # « 12,50 » converti
    assert clean.loc["alpha-4", "country_code"] == "JP"  # espaces retirés
    assert clean.loc["alpha-5", "data_gb"] == 3  # data_gb fait foi sur l'affichage
    assert bool(clean.loc["alpha-2", "is_unlimited"]) and pd.isna(clean.loc["alpha-2", "data_gb"])
    assert clean["validity_days"].dtype.kind == "i"


def test_anomalies_point_to_file_and_line(result):
    _, validated = result
    zero = next(a for a in validated.anomalies if a.sku == "beta-1")
    assert (zero.file, zero.line, zero.rule) == ("beta.csv", 2, "prix_non_positif")


def test_price_outlier_is_flagged_but_kept(tmp_path):
    lines = [HEADER] + [f"o-{i},O,eSIM France 5 Go 7 jours,FR,France,5,5 Go,7,10.00,EUR,4G,oui" for i in range(5)]
    lines.append("o-9,O,eSIM France 5 Go 7 jours,FR,France,5,5 Go,7,99.00,EUR,4G,non")
    (tmp_path / "o.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    validated = validate(load_providers(tmp_path).rows)
    outliers = [a for a in validated.anomalies if a.rule == "prix_aberrant"]
    assert [a.sku for a in outliers] == ["o-9"]
    assert "o-9" in set(validated.clean["sku"])


def test_small_groups_are_not_judged_as_outliers(tmp_path):
    # Moins de 5 produits comparables : pas assez de recul pour parler d'aberration.
    lines = [HEADER, "s-1,S,eSIM France 5 Go 7 jours,FR,France,5,5 Go,7,10.00,EUR,4G,oui",
             "s-2,S,eSIM France 5 Go 7 jours,FR,France,5,5 Go,7,90.00,EUR,4G,non"]
    (tmp_path / "s.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    validated = validate(load_providers(tmp_path).rows)
    assert not [a for a in validated.anomalies if a.rule == "prix_aberrant"]

