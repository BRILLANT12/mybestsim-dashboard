"""Offres encodées pour la page : compactes et fidèles aux lignes validées."""

import json
from pathlib import Path

from dashboard.build import build, render_html
from dashboard.config import EXPECTED_COLUMNS, ISO_NUMERIC_FILE, REGION_CODES, ZONE_MEMBERS
from dashboard.dataset import decode_offers, encode_offers
from dashboard.loader import load_providers
from dashboard.validation import validate

FIXTURES = Path(__file__).parent / "fixtures"


def test_roundtrip_is_lossless():
    clean = validate(load_providers(FIXTURES / "calculs").rows).clean
    decoded = decode_offers(encode_offers(clean))
    assert len(decoded) == len(clean)
    original = clean[EXPECTED_COLUMNS].to_dict("records")
    for got, exp in zip(decoded, original):
        assert list(got) == EXPECTED_COLUMNS
        for key in EXPECTED_COLUMNS:
            if key == "data_gb" and exp[key] != exp[key]:  # NaN = illimité
                assert got[key] is None
            else:
                assert got[key] == exp[key], key


def test_rejected_rows_are_not_embedded():
    _, offers = build(FIXTURES / "pieges")
    skus = [r[0] for r in offers["rows"]]
    assert "beta-1" not in skus and "beta-4" not in skus  # prix 0, devise USD
    assert skus.count("alpha-1") == 1  # SKU en double : une seule occurrence
    na = [c for c in offers["dict"]["country"] if c[0] == "NA"]
    assert na == [["NA", "Amérique du Nord"]]


def test_offers_are_embedded_in_html():
    result, offers = build(FIXTURES / "calculs")
    html = render_html(result, offers)
    embedded = html.split('<script id="offers-data" type="application/json">')[1].split("</script>")[0]
    assert len(json.loads(embedded)["rows"]) == 8


def test_zone_members_are_consistent():
    iso = json.loads(ISO_NUMERIC_FILE.read_text(encoding="utf-8"))
    for zone, members in ZONE_MEMBERS.items():
        assert zone in REGION_CODES
        assert all(code in iso for code in members), zone
        assert not set(members) & set(REGION_CODES)
