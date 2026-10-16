"""Encodage compact des offres validées, intégrées dans la page pour les filtres en direct.

Les colonnes très répétitives (fournisseur, pays, libellés…) sont remplacées par
un index dans un dictionnaire : la charge utile passe d'environ 430 Ko à environ
255 Ko (la page entière pèse environ 75 Ko une fois compressée par le serveur). Seules les lignes VALIDES sont
encodées : les filtres ne peuvent pas faire réapparaître une ligne rejetée.
"""

import math

import pandas as pd

from dashboard.config import EXPECTED_CURRENCY

# Ordre des champs dans chaque ligne encodée.
FIELDS = ["sku", "provider", "product_name", "country", "data_gb", "data_display", "validity_days", "price", "network", "top_up"]
DICTIONARY_FIELDS = ["provider", "product_name", "data_display", "network", "top_up"]


def encode_offers(clean: pd.DataFrame) -> dict:
    dicts = {f: sorted(clean[f].unique().tolist()) for f in DICTIONARY_FIELDS}
    countries = sorted(set(zip(clean["country_code"], clean["country_name"])))
    lookup = {f: {v: i for i, v in enumerate(values)} for f, values in dicts.items()}
    country_index = {c: i for i, c in enumerate(countries)}

    rows = []
    for r in clean.itertuples(index=False):
        gb = None if (r.data_gb is None or (isinstance(r.data_gb, float) and math.isnan(r.data_gb))) else r.data_gb
        rows.append([
            r.sku,
            lookup["provider"][r.provider],
            lookup["product_name"][r.product_name],
            country_index[(r.country_code, r.country_name)],
            int(gb) if gb is not None and float(gb).is_integer() else gb,
            lookup["data_display"][r.data_display],
            int(r.validity_days),
            round(float(r.price), 2),
            lookup["network"][r.network],
            lookup["top_up"][r.top_up],
        ])
    return {
        "fields": FIELDS,
        "currency": EXPECTED_CURRENCY,
        "dict": {**dicts, "country": [list(c) for c in countries]},
        "rows": rows,
    }


def decode_offers(payload: dict) -> list[dict]:
    """Inverse d'encode_offers (utilisé par les tests ; le navigateur a son équivalent JS)."""
    d = payload["dict"]
    out = []
    for sku, prov, name, country, gb, display, validity, price, network, top_up in payload["rows"]:
        code, country_name = d["country"][country]
        out.append({
            "sku": sku,
            "provider": d["provider"][prov],
            "product_name": d["product_name"][name],
            "country_code": code,
            "country_name": country_name,
            "data_gb": gb,
            "data_display": d["data_display"][display],
            "validity_days": validity,
            "price": price,
            "currency": payload["currency"],
            "network": d["network"][network],
            "top_up": d["top_up"][top_up],
        })
    return out
