"""Moteur JS (dashboard/templates/analytics.js), exécuté avec Node.

Le test central vérifie que, sans filtre, le moteur JS retrouve exactement les
chiffres calculés par Python : les deux implémentations ne peuvent pas diverger
sans qu'un test échoue.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dashboard import stats
from dashboard.build import build
from dashboard.config import DATA_DIR, EXPECTED_COLUMNS, REGION_CODES
from dashboard.loader import load_providers
from dashboard.validation import validate

ENGINE = Path(__file__).resolve().parent.parent / "dashboard" / "templates" / "analytics.js"
FIXTURES = Path(__file__).parent / "fixtures"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js est nécessaire pour tester le moteur JS")


def run_js(body: str, payload: dict, tmp_path: Path):
    """Exécute `body` avec A (le moteur) et P (payload) ; la valeur renvoyée est relue en JSON."""
    data = tmp_path / "payload.json"
    data.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    script = (
        f"const A = require({json.dumps(str(ENGINE))});\n"
        f"const P = JSON.parse(require('fs').readFileSync({json.dumps(str(data))}, 'utf8'));\n"
        f"const out = (() => {{ {body} }})();\n"
        "process.stdout.write(JSON.stringify(out));"
    )
    done = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def engine_input(data_dir: Path) -> dict:
    result, offers = build(data_dir)
    iso = {c["code"]: c["iso_numeric"] for c in result["coverage"]["countries_price_per_gb"]}
    return {"offers": offers, "regions": sorted(REGION_CODES), "iso": iso, "zones": result["coverage"]["zones"]}


DECODE = "const rows = A.decodeOffers(P.offers, P.regions);"


def assert_same(js, py, path="racine"):
    """Compare récursivement les champs produits par le JS à ceux de Python (ordre des listes compris)."""
    if isinstance(js, dict):
        assert isinstance(py, dict), path
        for key, value in js.items():
            assert key in py, f"{path}.{key} absent côté Python"
            assert_same(value, py[key], f"{path}.{key}")
    elif isinstance(js, list):
        assert isinstance(py, list) and len(js) == len(py), f"{path} : longueurs {len(js)} / {len(py)}"
        for i, (a, b) in enumerate(zip(js, py)):
            assert_same(a, b, f"{path}[{i}]")
    elif isinstance(js, (int, float)) and not isinstance(js, bool) and py is not None:
        # Python arrondit à 4 décimales (1 pour les indices de prix).
        tol = 0.051 if path.endswith(("price_index", ".index")) else 1e-4
        assert js == pytest.approx(py, abs=tol), path
    else:
        assert js == py, path


# --- Cohérence Python <-> JS ---------------------------------------------------


@pytest.mark.parametrize("data_dir", [FIXTURES / "calculs", FIXTURES / "pieges", DATA_DIR], ids=["calculs", "pieges", "donnees-reelles"])
def test_engine_matches_python_without_filters(data_dir, tmp_path):
    py = stats.compute(validate(load_providers(data_dir).rows).clean)
    js = run_js(DECODE + " return A.compute(rows, { isoNumeric: P.iso });", engine_input(data_dir), tmp_path)
    assert_same(js, py)


def test_decoded_offers_match_validated_rows(tmp_path):
    clean = validate(load_providers(FIXTURES / "calculs").rows).clean
    rows = run_js(DECODE + " return rows;", engine_input(FIXTURES / "calculs"), tmp_path)
    assert [r["sku"] for r in rows] == list(clean["sku"])
    by_sku = {r["sku"]: r for r in rows}
    assert by_sku["a3"]["country_code"] == "NA" and by_sku["a3"]["is_region"] is True
    assert by_sku["a3"]["is_unlimited"] is True and by_sku["a3"]["data_gb"] is None
    assert by_sku["a1"]["is_region"] is False


# --- Filtres -------------------------------------------------------------------


def test_filters_combine_and_recompute(tmp_path):
    out = run_js(
        DECODE
        + """
        const f = (filters) => A.compute(A.applyFilters(rows, filters), {}).headline;
        return {
          all: f({}).total_offers,
          provA: f({ provider: ["Prov A"] }).total_offers,
          provA5g: f({ provider: ["Prov A"], network: ["5G"] }).total_offers,
          fr: f({ place: ["FR"] }).total_offers,
          frde: f({ place: ["FR", "DE"] }).total_offers,
          d30: f({ validity_days: [30] }),
          topUpNo: f({ top_up: ["non"] }).total_offers,
        };""",
        engine_input(FIXTURES / "calculs"),
        tmp_path,
    )
    assert (out["all"], out["provA"], out["provA5g"], out["fr"], out["frde"], out["topUpNo"]) == (8, 4, 2, 3, 5, 3)
    d30 = out["d30"]  # a2 (20 €), a3 (120 €, illimité), b2 (30 €)
    assert d30["total_offers"] == 3 and d30["expensive"]["count"] == 1
    assert d30["price"]["mean"] == pytest.approx(170 / 3)
    assert d30["data"]["mean_gb"] == 10


def test_filter_with_no_result_does_not_crash(tmp_path):
    out = run_js(
        DECODE + " return A.compute(A.applyFilters(rows, { provider: ['Inconnu'] }), {});",
        engine_input(FIXTURES / "calculs"),
        tmp_path,
    )
    h = out["headline"]
    assert h["total_offers"] == 0 and h["price_range"]["min"] is None and h["price"]["mean"] is None
    assert out["providers"] == [] and out["pricing"]["power_law"] is None
    assert out["pricing"]["histogram"]["bins"] == []


# --- Comparateur ---------------------------------------------------------------


def test_comparator_ranks_cheapest_first(tmp_path):
    out = run_js(
        DECODE
        + """
        const pick = (q) => A.compare(rows, q, P.zones).map(x => [x.offer.sku, x.regional]);
        return {
          fr1: pick({ place: "FR", volume: 1 }),
          de5: pick({ place: "DE", volume: "5" }),
          usUnlimited: pick({ place: "US", volume: "unlimited" }),
          usUnlimitedRegional: pick({ place: "US", volume: "unlimited", includeRegional: true }),
          zoneItself: pick({ place: "NA", volume: "unlimited", includeRegional: true }),
          fr1Week: pick({ place: "FR", volume: 1, validity_days: 30 }),
        };""",
        engine_input(FIXTURES / "calculs"),
        tmp_path,
    )
    assert out["fr1"] == [["a1", False], ["b1", False]]  # 5 € chacun : départage par fournisseur
    assert out["de5"] == [["a4", False], ["b4", False]]
    assert out["usUnlimited"] == []  # aucun illimité propre aux États-Unis…
    # … mais Monde (100 €) et Amérique du Nord (120 €) couvrent les États-Unis.
    assert out["usUnlimitedRegional"] == [["b3", True], ["a3", True]]
    assert out["zoneItself"] == [["b3", True], ["a3", False]]  # zone NA choisie : Monde (100 €) la couvre aussi
    assert out["fr1Week"] == []


def test_comparator_respects_zone_hypothesis(tmp_path):
    # Un forfait Europe ne doit pas être proposé pour la Turquie (exclue de l'hypothèse).
    payload = engine_input(FIXTURES / "calculs")
    out = run_js(
        DECODE
        + """
        const eu = Object.assign({}, rows[0], { sku: "eu-1", country_code: "EU", country_name: "Europe", is_region: true });
        return {
          fr: A.compare(rows.concat([eu]), { place: "FR", volume: 1, includeRegional: true }, P.zones).map(x => x.offer.sku),
          tr: A.compare(rows.concat([eu]), { place: "TR", volume: 1, includeRegional: true }, P.zones).map(x => x.offer.sku),
        };""",
        payload,
        tmp_path,
    )
    assert "eu-1" in out["fr"] and "eu-1" not in out["tr"]


# --- Export CSV ----------------------------------------------------------------


def test_csv_export_can_be_dropped_back_into_data(tmp_path):
    csv_text = run_js(DECODE + " return A.toCSV(rows);", engine_input(FIXTURES / "calculs"), tmp_path)
    assert csv_text.startswith("﻿" + ",".join(EXPECTED_COLUMNS) + "\n")

    reimport = tmp_path / "data"
    reimport.mkdir()
    (reimport / "export.csv").write_text(csv_text, encoding="utf-8")
    loaded = load_providers(reimport)
    validated = validate(loaded.rows)
    assert loaded.anomalies == [] and validated.anomalies == []

    original = validate(load_providers(FIXTURES / "calculs").rows).clean
    cols = [c for c in EXPECTED_COLUMNS]
    again = validated.clean[cols].astype(str).to_dict("records")
    before = original[cols].astype(str).to_dict("records")
    assert again == before  # NA conservé, illimités à data_gb vide, prix identiques


def test_csv_quotes_special_characters(tmp_path):
    out = run_js(
        DECODE + ' rows[0].product_name = \'eSIM "Europe", 1 Go\'; return A.toCSV([rows[0]]);',
        engine_input(FIXTURES / "calculs"),
        tmp_path,
    )
    assert '"eSIM ""Europe"", 1 Go"' in out
