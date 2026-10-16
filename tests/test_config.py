"""Garde-fous sur la configuration."""

from dashboard.config import EXPECTED_COLUMNS, REGION_CODES


def test_schema_has_the_twelve_expected_columns():
    assert len(EXPECTED_COLUMNS) == 12 and len(set(EXPECTED_COLUMNS)) == 12


def test_region_codes_include_north_america_na():
    # « NA » est un code légitime (Amérique du Nord), pas une valeur manquante.
    assert REGION_CODES["NA"] == "Amérique du Nord"
