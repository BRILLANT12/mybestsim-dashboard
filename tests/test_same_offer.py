"""Contrôle « Même offre, prix différents », sur le jeu piège tests/fixtures/meme_offre/.

Contenu du jeu (17 lignes lues, 2 exclues, 15 gardées) :
- piege.csv (fournisseur « Piège ») :
  - p-1 / p-2 : Argentine 1 Go 30 j à 8,20 € et 7,06 € -> signalée (+16 %) ;
  - p-3 / p-4 / p-5 : Japon, trois lignes, deux prix (10 €, 10 €, 14 €) -> une seule offre signalée
    (et p-4, copie exacte de p-3, en doublon probable) ;
  - p-6 / p-7 : Pérou, même prix -> doublon probable, PAS ce contrôle ;
  - p-8, p-9, p-10 : comme p-1 mais réseau, recharge ou durée différents -> offres distinctes ;
  - p-11 (USD) et p-2 en double SKU : exclues, donc jamais comparées ;
  - p-12 / p-13 : illimité Monde à 96,06 € et 140,24 € -> signalée, plus grand écart (+46 %).
- autre.csv (fournisseur « Autre ») :
  - a-1 : même produit que p-1 mais autre fournisseur -> pas comparé à Piège ;
  - a-2 / a-3 : zone NA à 20 € et 22 € -> signalée (le code NA ne doit pas être perdu).
"""

from pathlib import Path

import pytest

from dashboard import stats
from dashboard.anomalies import RULES, WARNING
from dashboard.build import build
from dashboard.loader import load_providers
from dashboard.validation import validate

MEME_OFFRE = Path(__file__).parent / "fixtures" / "meme_offre"
RULE = "meme_offre_prix_differents"


@pytest.fixture(scope="module")
def validated():
    return validate(load_providers(MEME_OFFRE).rows)


def flagged(v):
    return [a for a in v.anomalies if a.rule == RULE]


def test_rule_is_in_the_catalogue_as_a_warning():
    assert RULES[RULE] == (WARNING, "Même offre, prix différents")


def test_one_warning_per_offer_on_its_first_line(validated):
    found = flagged(validated)
    assert all(a.severity == WARNING for a in found)
    assert sorted((a.file, a.line, a.sku) for a in found) == [
        ("autre.csv", 3, "a-2"),
        ("piege.csv", 2, "p-1"),
        ("piege.csv", 4, "p-3"),
        ("piege.csv", 14, "p-12"),
    ]


def test_rows_are_kept(validated):
    kept = set(validated.clean["sku"])
    assert {"p-1", "p-2", "p-3", "p-4", "p-5", "p-12", "p-13", "a-2", "a-3"} <= kept
    assert (validated.total_rows, validated.excluded_rows) == (17, 2)


def test_different_characteristics_are_not_the_same_offer(validated):
    skus = " ".join(a.message for a in flagged(validated))
    for other in ("p-8", "p-9", "p-10", "a-1"):  # réseau, recharge, durée, fournisseur
        assert f"{other} " not in skus


def test_same_price_duplicates_are_left_to_the_duplicate_check(validated):
    assert not any("p-6" in a.message for a in flagged(validated))
    # p-4 copie aussi p-3 (même prix) : doublon probable, et le Japon reste signalé une fois pour p-5.
    assert [a.sku for a in validated.anomalies if a.rule == "doublon_probable"] == ["p-4", "p-7"]


def test_excluded_rows_are_never_compared(validated):
    # p-11 (USD) et la 2e ligne p-2 (1 €, SKU en double) auraient faussé l'écart de l'Argentine.
    argentine = next(a for a in flagged(validated) if a.sku == "p-1")
    assert "p-11" not in argentine.message and "1.00 €" not in argentine.message
    assert "écart de 16 %" in argentine.message


def test_summary(validated):
    s = validated.same_offer
    assert (s["offers"], s["rows"], s["max_gap"]) == (4, 9, 0.4599)
    assert s["by_provider"] == [
        {"provider": "Piège", "offers": 3, "rows": 7, "max_gap": 0.4599},
        {"provider": "Autre", "offers": 1, "rows": 2, "max_gap": 0.1},
    ]
    worst = s["examples"][0]
    assert (worst["product_name"], worst["min_price"], worst["max_price"]) == ("eSIM Monde Illimité 30 jours", 96.06, 140.24)
    assert [e["gap"] for e in s["examples"]] == sorted((e["gap"] for e in s["examples"]), reverse=True)


def test_kpis_still_use_every_row(validated):
    # Avertissement seulement : aucune ligne n'est retirée ni dédoublonnée.
    h = stats.headline(validated.clean)
    assert h["total_offers"] == len(validated.clean) == 15


def test_report_and_insight():
    result, _ = build(MEME_OFFRE)
    rep = result["anomalies"]
    checks = {c["rule"]: c["count"] for c in rep["checks"]}
    assert checks[RULE] == 4
    assert rep["same_offer"]["offers"] == 4
    insight = {i["id"]: i for i in result["insights"]}["same_offer_price_gap"]
    assert insight["title"] == "4 offres affichées à plusieurs prix chez le même fournisseur"
    assert "46 %" in insight["text"] and "96,06 € ou 140,24 €" in insight["text"]
    assert "selon la ligne retenue" in insight["text"]


def test_clean_catalogue_has_no_insight_and_an_empty_summary(tmp_path):
    result, _ = build(Path(__file__).parent / "fixtures" / "calculs")
    assert "same_offer_price_gap" not in {i["id"] for i in result["insights"]}
    assert result["anomalies"]["same_offer"]["offers"] == 0
