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
from dashboard.build import PLACEHOLDER, build_stats, render_html, write_outputs
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
    # Seulement 2 fournisseurs (podium tronqué), 2,19 vs 2,81 €/Go : pas d'égalité.
    cheapest = ins["cheapest_provider"]
    assert cheapest["title"] == "Moins chers au Go : Prov A et Prov B"
    assert [t["provider"] for t in cheapest["values"]["top"]] == ["Prov A", "Prov B"]
    assert cheapest["values"]["tied"] is False


def test_cheapest_podium_declares_tie_when_close(df):
    close = df.copy()
    close.loc[close["sku"] == "b2", "price"] = 20.1  # B : 35,10 € / 16 Go, à 0,3 % de A
    cheapest = {i["id"]: i for i in stats.compute(close)["insights"]}["cheapest_provider"]
    assert cheapest["values"]["tied"] is True
    assert cheapest["title"] == "Moins chers au Go : Prov A et Prov B, quasiment à égalité"
    assert "2,19\u202f€/Go" in cheapest["text"]


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
    json_path, html_path = write_outputs(result, tmp_path)
    loaded = json.loads(json_path.read_text(encoding="utf-8"))  # JSON strict : pas de NaN
    assert _no_nan(loaded)
    assert loaded["meta"]["generated_at"] == "2026-10-22T08:00:00+02:00"
    assert loaded["meta"]["files_count"] == 3  # vide.csv et mauvais_schema.csv ignorés
    rep = loaded["anomalies"]
    assert (rep["rows_read"], rep["rows_excluded"]) == (18, 9)
    assert rep["errors"] == 11 and rep["warnings"] == 6  # 9 lignes + 2 fichiers ; 5 lignes + 1 colonne en trop
    assert rep["by_rule"][0]["severity"] == "erreur"
    # Chaque règle déclenchée dans le code figure au catalogue affiché sur le dashboard.
    checks = {c["rule"]: c["count"] for c in rep["checks"]}
    assert {r["rule"] for r in rep["by_rule"]} <= set(checks)
    assert checks["prix_non_positif"] == 2 and checks["prix_aberrant"] == 0


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


def test_html_embeds_the_stats_and_escapes_script_tags(df):
    hostile = df.copy()
    hostile.loc[hostile["sku"] == "b2", "price"] = 0.5  # devient le prix min, donc listé dans la page
    hostile.loc[hostile["sku"] == "b2", "product_name"] = "</script><script>alert(1)</script>"
    result = stats.compute(hostile)
    result.update(meta={"generated_at": "2026-10-22T08:00:00+02:00", "files_count": 1, "providers_count": 2},
                  anomalies={"details": []})
    html = render_html(result)
    assert PLACEHOLDER not in html
    assert "alert(1)" in html and "</script><script>alert" not in html
    embedded = html.split('<script id="stats-data" type="application/json">')[1].split("</script>")[0]
    assert json.loads(embedded)["headline"]["price_range"]["min"]["products"][0]["product_name"].startswith("</script>")


# --- Lot 1 de la refonte : corrections et nouveaux calculs --------------------


def test_price_range_groups_ties_by_provider(df):
    tie = df.copy()
    tie.loc[tie["sku"] == "a4", "price"] = 5.0  # Prov A a désormais 2 produits au prix min
    rng = stats.compute(tie)["headline"]["price_range"]["min"]
    assert rng["count"] == 3
    assert rng["by_provider"] == [{"provider": "Prov A", "count": 2}, {"provider": "Prov B", "count": 1}]


def test_cheapest_podium_uses_three_decimals(df):
    close = df.copy()
    close.loc[close["sku"] == "b2", "price"] = 20.1
    cheapest = {i["id"]: i for i in stats.compute(close)["insights"]}["cheapest_provider"]
    assert "Prov A (2,188 €/Go)" in cheapest["text"]  # 35 / 16 = 2,1875
    assert "Prov B (2,194 €/Go)" in cheapest["text"]  # 35,1 / 16 = 2,19375


def test_power_law_recovers_exact_exponent():
    import pandas as pd

    gb = [1.0, 2.0, 4.0, 8.0, 16.0]
    exact = pd.DataFrame({"data_gb": gb, "price": [3 * g**0.5 for g in gb], "is_unlimited": [False] * 5})
    law = stats.power_law(exact)
    assert law["coef"] == pytest.approx(3) and law["exponent"] == pytest.approx(0.5)
    assert law["doubling_factor"] == pytest.approx(2**0.5, abs=1e-4) and law["r2"] == pytest.approx(1)


def test_power_law_needs_two_volumes(df):
    one_volume = df[df["data_gb"] == 1]
    assert stats.power_law(one_volume) is None


def test_price_histogram_bins_are_left_closed(result):
    hist = result["pricing"]["histogram"]
    assert hist["bin_width"] == 5
    filled = {b["from"]: b["offers"] for b in hist["bins"] if b["offers"]}
    # 5, 5 | 10, 10 | 20 | 30 | 100 (100 € tombe dans [100 ; 105[) | 120
    assert filled == {5: 2, 10: 2, 20: 1, 30: 1, 100: 1, 120: 1}
    assert sum(b["offers"] for b in hist["bins"]) == 8
    assert hist["bins"][-1]["to"] == 125


def test_provider_validity_index_matrix(result):
    cells = {(c["provider"], c["validity_days"]): c["index"] for c in result["provider_validity_index"]["cells"]}
    # Seule la paire a2 (20 €) / b2 (30 €) sur 10 Go / 30 j s'écarte de la moyenne de son segment (25 €).
    assert cells == {("Prov A", 7): 100.0, ("Prov A", 30): 90.0, ("Prov B", 7): 100.0, ("Prov B", 30): 120.0}
    assert result["provider_validity_index"]["validities"] == [7, 30]


def test_countries_price_per_gb_for_the_map(result):
    countries = {c["code"]: c for c in result["coverage"]["countries_price_per_gb"]}
    assert set(countries) == {"FR", "DE", "US"}  # les zones NA et WW n'y sont pas
    assert countries["FR"]["price_per_gb"] == 2.5  # (5 + 20 + 5) / (1 + 10 + 1)
    assert countries["DE"]["price_per_gb"] == 2.0
    assert countries["US"]["iso_numeric"] == "840"


def test_zone_hypothesis_is_exported(result):
    zones = {z["code"]: z["countries"] for z in result["coverage"]["zones"]}
    assert zones["WW"] == "*"
    assert "FR" in zones["EU"] and "TR" not in zones["EU"]
    assert "US" in zones["NA"]


def test_power_law_insight(df):
    ins = {i["id"]: i for i in stats.compute(df)["insights"]}
    assert ins["power_law"]["values"]["exponent"] < 1
