"""Calculs clés, sur un mini-catalogue dont chaque valeur est calculable à la main.

tests/fixtures/calculs/ : 8 offres, 2 fournisseurs.
  a1 FR 1 Go 7 j 5 €  4G oui | b1 FR 1 Go 7 j 5 €  4G oui   (prix min ex æquo)
  a2 FR 10 Go 30 j 20 € 5G non | b2 US 10 Go 30 j 30 € 4G oui
  a3 NA Illimité 30 j 120 € 5G oui | b3 WW Illimité 7 j 100 € 4G non  (100 € pile : pas « > 100 »)
  a4 DE 5 Go 7 j 10 € 4G non | b4 DE 5 Go 7 j 10 € 5G oui
"""

import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from dashboard import fmt, stats
from dashboard.build import build_stats, write_outputs
from dashboard.loader import load_providers
from dashboard.validation import validate

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def df():
    return validate(load_providers(FIXTURES / "calculs").rows).clean


@pytest.fixture(scope="module")
def result(df):
    return stats.compute(df)


# --- Les 6 indicateurs demandés ---------------------------------------------


def test_total_offers(result):
    assert result["headline"]["total_offers"] == 8


def test_expensive_is_strictly_above_100(result):
    exp = result["headline"]["expensive"]
    assert exp["count"] == 1  # a3 (120 €) ; b3 à 100 € pile n'est pas compté
    assert exp["threshold"] == 100 and exp["rule"] == "strictement supérieur"
    assert exp["unlimited_count"] == 1
    assert exp["max_price_limited"] == 30


def test_price_range_reports_ties_and_product(result):
    rng = result["headline"]["price_range"]
    assert rng["min"]["price"] == 5 and rng["min"]["count"] == 2
    assert [p["sku"] for p in rng["min"]["products"]] == ["a1", "b1"]
    assert rng["max"]["price"] == 120 and rng["max"]["products"][0]["sku"] == "a3"


def test_mean_data_excludes_unlimited(result):
    data = result["headline"]["data"]
    assert data["mean_gb"] == pytest.approx(32 / 6, abs=1e-4)  # 1+10+5+1+10+5, sans les 2 illimités
    assert data["median_gb"] == 5
    assert data["offers_with_data"] == 6 and data["unlimited_count"] == 2
    assert data["unlimited_share"] == 0.25


def test_mean_price(result):
    price = result["headline"]["price"]
    assert price["mean"] == 37.5  # 300 / 8
    assert price["mean_limited"] == pytest.approx(80 / 6, abs=1e-4)
    assert price["mean_unlimited"] == 110


def test_by_provider(result):
    providers = {p["provider"]: p for p in result["providers"]}
    a, b = providers["Prov A"], providers["Prov B"]
    assert (a["offers"], b["offers"]) == (4, 4)
    assert a["share"] == 0.5
    assert a["price_per_gb"] == pytest.approx(35 / 16, abs=1e-4)
    assert b["price_per_gb"] == pytest.approx(45 / 16, abs=1e-4)
    assert a["mean_price"] == 38.75 and b["mean_price"] == 36.25
    assert a["unlimited"] == b["unlimited"] == 1
    assert a["source_files"] == ["prov_a.csv"]


# --- Bonus ------------------------------------------------------------------


def test_price_per_gb_total_over_total_vs_ratios(result):
    p = result["pricing"]
    assert p["price_per_gb"] == 2.5  # 80 € / 32 Go
    assert p["price_per_gb_median_of_ratios"] == 2.5  # médiane de 5, 2, 2, 5, 3, 2
    assert p["price_per_gb_mean_of_ratios"] == pytest.approx(19 / 6, abs=1e-4)
    tiers = {t["data_gb"]: t["price_per_gb"] for t in p["by_data_tier"]}
    assert tiers == {1: 5, 5: 2, 10: 2.5}


def test_network_and_top_up(result):
    dist = result["distributions"]
    assert {c["value"]: c["offers"] for c in dist["network"]} == {"4G": 5, "5G": 3}
    assert {c["value"]: c["share"] for c in dist["top_up"]} == {"oui": 0.625, "non": 0.375}


def test_like_for_like_compares_only_comparable_offers(result):
    # Segments avec 4G et 5G : 10 Go/30 j (20/30) et 5 Go/7 j (10/10). Moyenne = (2/3 + 1) / 2.
    assert result["distributions"]["network_like_for_like_5g_vs_4g"] == pytest.approx(5 / 6, abs=1e-4)


def test_price_index_is_relative_to_comparable_offers(result):
    idx = {p["provider"]: p["price_index"] for p in result["providers"]}
    assert idx == {"Prov A": 95.0, "Prov B": 105.0}  # seul a2/b2 diffère : 20 et 30 pour une moyenne de 25


def test_validity_and_data_tiers(result):
    dist = result["distributions"]
    assert {v["validity_days"]: v["offers"] for v in dist["validity"]} == {7: 5, 30: 3}
    assert [t["label"] for t in dist["data_tiers"]] == ["1 Go", "5 Go", "10 Go", "Illimité"]


def test_countries_and_regions_are_separate(result):
    cov = result["coverage"]
    assert cov["countries_count"] == 3  # FR, DE, US
    assert cov["regions_count"] == 2  # NA, WW
    assert [c["code"] for c in cov["top_countries"]] == ["FR", "DE", "US"]
    assert {r["code"]: r["name"] for r in cov["regions"]} == {"NA": "Amérique du Nord", "WW": "Monde"}


def test_insights_are_computed_from_data(result):
    ins = {i["id"]: i for i in result["insights"]}
    assert ins["expensive_all_unlimited"]["highlight"] is True
    assert ins["expensive_all_unlimited"]["title"] == "Le seul produit à plus de 100 € est un forfait illimité"
    assert "30,00 €" in ins["expensive_all_unlimited"]["text"]
    assert ins["volume_discount"]["values"]["from"] == 5 and ins["volume_discount"]["values"]["to"] == 2.5
    # Écart d'indice de 10 points : les fournisseurs ne sont pas jugés homogènes.
    assert ins["cheapest_provider"]["title"] == "Prov A est le fournisseur le moins cher au Go"


def test_expensive_insight_when_not_all_unlimited(df):
    pricey = df.copy()
    pricey.loc[pricey["sku"] == "b2", "price"] = 150.0  # forfait 10 Go à 150 €
    ins = {i["id"]: i for i in stats.compute(pricey)["insights"]}
    assert "expensive_all_unlimited" not in ins
    assert ins["expensive_mix"]["values"] == {"count": 2, "unlimited_count": 1}


# --- Sortie JSON et cas limites ---------------------------------------------


def _no_nan(obj):
    if isinstance(obj, float):
        return math.isfinite(obj)
    if isinstance(obj, dict):
        return all(_no_nan(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_no_nan(v) for v in obj)
    return True


def test_build_writes_valid_json_with_report(tmp_path):
    now = datetime.fromisoformat("2026-10-22T08:00:00+02:00")
    result = build_stats(FIXTURES / "pieges", now=now)
    path = write_outputs(result, tmp_path)
    loaded = json.loads(path.read_text(encoding="utf-8"))  # JSON strict : pas de NaN
    assert _no_nan(loaded)
    assert loaded["meta"]["generated_at"] == "2026-10-22T08:00:00+02:00"
    assert loaded["meta"]["files_count"] == 3  # vide.csv et mauvais_schema.csv ignorés
    rep = loaded["anomalies"]
    assert (rep["rows_read"], rep["rows_excluded"]) == (18, 9)
    assert rep["errors"] == 11 and rep["warnings"] == 6  # 9 lignes + 2 fichiers ; 5 lignes + 1 colonne en trop
    assert rep["by_rule"][0]["severity"] == "erreur"


def test_build_on_empty_folder_does_not_crash(tmp_path):
    result = build_stats(tmp_path)
    assert result["headline"]["total_offers"] == 0
    assert result["insights"] == []
    json.dumps(result, allow_nan=False)


def test_french_formatting():
    assert fmt.number(5056) == "5 056"
    assert fmt.euros(12.5) == "12,50 €"
    assert fmt.percent(0.2208) == "22 %"
    assert fmt.percent(0.009, 1, signed=True) == "+0,9 %"
