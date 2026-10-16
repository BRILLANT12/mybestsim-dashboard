"""Fiches fournisseurs : chiffres, noms de fichiers, génération automatique."""

import shutil
from pathlib import Path

import pytest

from dashboard import profiles, stats
from dashboard.build import build, offers_frame, write_outputs
from dashboard.loader import load_providers
from dashboard.validation import validate

FIXTURES = Path(__file__).parent / "fixtures"
HEADER = "sku,provider,product_name,country_code,country_name,data_gb,data_display,validity_days,price,currency,network,top_up"


def test_page_paths_are_unique_and_readable():
    paths = profiles.page_paths(["Maya Mobile", "4S eSIM", "aloSIM", "A-b", "A b"])
    assert paths["Maya Mobile"] == "fournisseurs/maya-mobile.html"
    assert paths["4S eSIM"] == "fournisseurs/4s-esim.html"
    assert paths["aloSIM"] == "fournisseurs/alosim.html"
    assert sorted([paths["A-b"], paths["A b"]]) == ["fournisseurs/a-b-2.html", "fournisseurs/a-b.html"]


@pytest.fixture(scope="module")
def market():
    clean = validate(load_providers(FIXTURES / "calculs").rows).clean
    return clean, stats.compute(clean)


def test_profile_figures_computed_by_hand(market):
    clean, result = market
    p = profiles.profile(clean, "Prov A", result)
    assert p["offers"] == 4 and p["share"] == 0.5
    assert p["price_per_gb"] == pytest.approx(35 / 16, abs=1e-4)
    assert p["price_index"] == 95.0 and p["rank_index"] == 1 and p["rank_price_per_gb"] == 1
    # Meilleures offres au Go : a4 (10 € / 5 Go) et a2 (20 € / 10 Go) à 2 €/Go (départage par prix), puis a1 (5 €/Go)
    assert [o["sku"] for o in p["best_offers"]] == ["a4", "a2", "a1"]
    assert (p["countries_count"], p["regions_count"]) == (2, 1)  # FR, DE + NA
    assert [d["code"] for d in p["destinations"]] == ["DE", "FR", "NA"]  # pays d'abord, puis zones
    assert {c["validity_days"]: c["index"] for c in p["index_by_validity"]} == {7: 100.0, 30: 90.0}


def test_profile_from_decoded_offers_matches_validated_rows(market):
    clean, result = market
    _, offers = build(FIXTURES / "calculs")
    rebuilt = offers_frame(offers)
    for name in ("Prov A", "Prov B"):
        a, b = profiles.profile(clean, name, result), profiles.profile(rebuilt, name, result)
        a.pop("source_files"), b.pop("source_files")
        assert a == b


def test_market_summary(market):
    _, result = market
    m = profiles.market_summary(result)
    assert m["mean_price"] == 37.5 and m["price_per_gb"] == 2.5 and m["share_5g"] == 0.375


def _data_dir(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    shutil.copytree(FIXTURES / "calculs", data)
    return data


def test_new_csv_creates_a_new_page_and_removed_csv_removes_it(tmp_path):
    data, out = _data_dir(tmp_path), tmp_path / "site"
    result, offers = build(data)
    write_outputs(result, out, offers)
    assert sorted(p.name for p in (out / "fournisseurs").glob("*.html")) == ["prov-a.html", "prov-b.html"]

    (data / "nouveau.csv").write_text(HEADER + "\nn1,Nouveau Fournisseur,eSIM France 5 Go 7 jours,FR,France,5,5 Go,7,9.00,EUR,5G,oui\n", encoding="utf-8")
    result, offers = build(data)
    write_outputs(result, out, offers)
    page = out / "fournisseurs" / "nouveau-fournisseur.html"
    assert page.exists() and "Nouveau Fournisseur" in page.read_text(encoding="utf-8")
    assert result["provider_pages"]["Nouveau Fournisseur"] == "fournisseurs/nouveau-fournisseur.html"

    (data / "nouveau.csv").unlink()
    result, offers = build(data)
    write_outputs(result, out, offers)
    assert not page.exists()
    assert sorted(p.name for p in (out / "fournisseurs").glob("*.html")) == ["prov-a.html", "prov-b.html"]
    assert (out / "index.html").exists() and (out / "assets" / "site.css").exists()  # rien d'autre n'est supprimé


def test_provider_page_content(tmp_path):
    out = tmp_path / "site"
    result, offers = build(FIXTURES / "calculs")
    write_outputs(result, out, offers)
    html = (out / "fournisseurs" / "prov-a.html").read_text(encoding="utf-8")
    assert "<h1>Prov A</h1>" in html
    assert "2,188 €" in html  # prix au Go (3 décimales)
    assert "Les 3 meilleures offres au Go" in html and "eSIM Allemagne 5 Go 7 jours" in html
    assert '<a href="../fournisseurs/prov-b.html">Prov B</a> →' in html  # navigation vers la fiche suivante
    assert 'href="../index.html#fournisseurs"' in html


def test_share_gaps_are_in_points():
    from dashboard.pages import _points

    assert "+3 points par rapport au marché" in _points(0.38, 0.35)
    assert "−1 point par rapport au marché" in _points(0.34, 0.35)
    assert "au niveau du marché" in _points(0.351, 0.35)
