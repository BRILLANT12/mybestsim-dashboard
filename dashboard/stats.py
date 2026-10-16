"""Calcul des indicateurs du dashboard à partir des offres validées.

Toutes les fonctions prennent le DataFrame « clean » produit par validation.py
(price float, data_gb float avec NaN pour les illimités, is_unlimited, is_region).
Les valeurs sont renvoyées brutes (non formatées) : le formatage français est
fait à l'affichage.
"""

import json
import math

import numpy as np
import pandas as pd

from dashboard import fmt
from dashboard.config import EXPENSIVE_THRESHOLD_EUR, ISO_NUMERIC_FILE, REGION_CODES, WORLD_ZONE, ZONE_MEMBERS

MAX_LISTED_PRODUCTS = 5  # produits ex æquo listés pour le prix min / max
TOP_DESTINATIONS = 10
HISTOGRAM_BIN_EUR = 5  # largeur des classes de l'histogramme des prix
# Écart d'indice (en points) sous lequel on considère les fournisseurs au même prix.
HOMOGENEOUS_INDEX_SPREAD = 5
# « Moins cher au Go » : on montre un podium, déclaré à égalité si l'écart 1er/dernier < 1 %.
CHEAPEST_TOP_N = 3
TIE_TOLERANCE = 0.01


def _num(value, digits=4):
    """Nombre JSON-compatible (NaN/inf -> None), arrondi."""
    if value is None:
        return None
    value = float(value)
    return None if not math.isfinite(value) else round(value, digits)


def _share(part, total):
    return _num(part / total) if total else None


def _products(rows: pd.DataFrame) -> list[dict]:
    return [
        {"sku": r.sku, "provider": r.provider, "product_name": r.product_name, "price": _num(r.price, 2)}
        for r in rows.sort_values(["provider", "sku"]).head(MAX_LISTED_PRODUCTS).itertuples()
    ]


def segment(df: pd.DataFrame) -> pd.Series:
    """Segment « produits comparables » : même volume (ou illimité) et même durée."""
    tier = df["data_gb"].astype(object).where(~df["is_unlimited"], "illimité")
    return tier.astype(str) + "|" + df["validity_days"].astype(str)


def limited(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["is_unlimited"]]


def price_per_gb(df: pd.DataFrame) -> float | None:
    """Prix au Go = total des prix / total des Go (forfaits limités uniquement).

    C'est le coût réel d'un Go sur l'ensemble du catalogue. La moyenne des ratios
    individuels donnerait le même poids à un forfait de 1 Go qu'à un de 50 Go et
    serait tirée vers le haut par les petits forfaits, chers au Go.
    """
    lim = limited(df)
    total_gb = lim["data_gb"].sum()
    return _num(lim["price"].sum() / total_gb) if total_gb > 0 else None


def like_for_like_ratio(df: pd.DataFrame, column: str, value_a, value_b) -> float | None:
    """Écart de prix moyen A/B à produits comparables.

    Pour chaque segment (volume, durée) contenant les deux valeurs, on calcule
    prix moyen A / prix moyen B, puis on fait la moyenne de ces ratios. Cela
    neutralise l'effet de composition (ex. : plus de gros forfaits en 5G).
    """
    means = df.groupby([segment(df), df[column]])["price"].mean().unstack()
    if value_a not in means or value_b not in means:
        return None
    ratios = (means[value_a] / means[value_b]).dropna()
    return _num(ratios.mean()) if len(ratios) else None


def power_law(df: pd.DataFrame) -> dict | None:
    """Ajuste prix = coef × Go^exposant sur les forfaits limités (régression log-log).

    Exposant < 1 : le prix augmente moins vite que le volume (dégressivité).
    doubling_factor = 2^exposant : ce que devient le prix quand on double le volume.
    """
    lim = limited(df)
    if lim["data_gb"].nunique() < 2:
        return None
    x, y = np.log(lim["data_gb"].to_numpy()), np.log(lim["price"].to_numpy())
    exponent, intercept = np.polyfit(x, y, 1)
    residuals = y - (intercept + exponent * x)
    r2 = 1 - residuals.var() / y.var() if y.var() > 0 else 1.0
    return {
        "coef": _num(math.exp(intercept)),
        "exponent": _num(exponent),
        "doubling_factor": _num(2**exponent),
        "r2": _num(r2),
        "offers": len(lim),
    }


def price_histogram(df: pd.DataFrame, width: float = HISTOGRAM_BIN_EUR) -> dict:
    """Classes de prix [a ; a + largeur[ ; un prix de 100 € tombe dans [100 ; 105[."""
    if df.empty:
        return {"bin_width": width, "bins": []}
    upper = math.floor(df["price"].max() / width) + 1
    idx = np.floor(df["price"] / width).astype(int)
    counts = idx.value_counts()
    return {
        "bin_width": width,
        "bins": [{"from": _num(k * width, 2), "to": _num((k + 1) * width, 2), "offers": int(counts.get(k, 0))} for k in range(upper)],
    }


def provider_validity_index(df: pd.DataFrame) -> dict:
    """Indice de prix (100 = moyenne des offres comparables) par fournisseur et par durée."""
    relative = df["price"] / df.groupby(segment(df))["price"].transform("mean")
    grouped = relative.groupby([df["provider"], df["validity_days"]])
    cells = [
        {"provider": prov, "validity_days": int(v), "index": _num(r.mean() * 100, 1), "offers": len(r)}
        for (prov, v), r in grouped
    ]
    return {"validities": sorted(int(v) for v in df["validity_days"].unique()), "cells": cells}


def _iso_numeric() -> dict:
    return json.loads(ISO_NUMERIC_FILE.read_text(encoding="utf-8"))


def countries_price_per_gb(df: pd.DataFrame) -> list[dict]:
    """Prix au Go (total / total, forfaits limités) par pays, pour la carte."""
    iso = _iso_numeric()
    out = []
    for (code, name), d in df[~df["is_region"]].groupby(["country_code", "country_name"]):
        out.append({
            "code": code,
            "name": name,
            "iso_numeric": iso.get(code),  # None : pays absent de la table, non cartographié
            "offers": len(d),
            "price_per_gb": price_per_gb(d),
        })
    return sorted(out, key=lambda c: c["name"])


def zones() -> list[dict]:
    """Hypothèse de couverture des zones (voir config.ZONE_MEMBERS)."""
    out = [{"code": code, "name": REGION_CODES[code], "countries": sorted(members)} for code, members in ZONE_MEMBERS.items()]
    out.append({"code": WORLD_ZONE, "name": REGION_CODES[WORLD_ZONE], "countries": "*"})
    return out


def headline(df: pd.DataFrame) -> dict:
    n = len(df)
    lim = limited(df)
    unl = df[df["is_unlimited"]]
    expensive = df[df["price"] > EXPENSIVE_THRESHOLD_EUR]

    def extreme(value):
        rows = df[df["price"] == value]
        per_provider = rows.groupby("provider").size().reset_index(name="count")
        per_provider = per_provider.sort_values(["count", "provider"], ascending=[False, True])
        return {
            "price": _num(value, 2),
            "count": len(rows),
            "products": _products(rows),
            # « eSIMX (×2) » plutôt que « eSIMX, eSIMX » quand un fournisseur a plusieurs ex æquo.
            "by_provider": [{"provider": r.provider, "count": int(r.count)} for r in per_provider.itertuples()],
        }

    return {
        "total_offers": n,
        "expensive": {
            "threshold": EXPENSIVE_THRESHOLD_EUR,
            "rule": "strictement supérieur",
            "count": len(expensive),
            "unlimited_count": int(expensive["is_unlimited"].sum()),
            "validity_days": sorted(int(v) for v in expensive["validity_days"].unique()),
            "max_price_limited": _num(lim["price"].max(), 2) if len(lim) else None,
        },
        "price_range": {
            "min": extreme(df["price"].min()) if n else None,
            "max": extreme(df["price"].max()) if n else None,
        },
        "data": {
            "mean_gb": _num(lim["data_gb"].mean()) if len(lim) else None,
            "median_gb": _num(lim["data_gb"].median()) if len(lim) else None,
            "offers_with_data": len(lim),
            "unlimited_count": len(unl),
            "unlimited_share": _share(len(unl), n),
        },
        "price": {
            "mean": _num(df["price"].mean()) if n else None,
            "median": _num(df["price"].median()) if n else None,
            "mean_limited": _num(lim["price"].mean()) if len(lim) else None,
            "mean_unlimited": _num(unl["price"].mean()) if len(unl) else None,
        },
    }


def by_provider(df: pd.DataFrame) -> list[dict]:
    n = len(df)
    seg_mean = df.groupby(segment(df))["price"].transform("mean")
    relative = df["price"] / seg_mean  # 1 = prix moyen des produits comparables
    out = []
    for provider, d in df.groupby("provider"):
        out.append(
            {
                "provider": provider,
                "offers": len(d),
                "share": _share(len(d), n),
                "mean_price": _num(d["price"].mean()),
                "min_price": _num(d["price"].min(), 2),
                "mean_data_gb": _num(limited(d)["data_gb"].mean()) if len(limited(d)) else None,
                "unlimited": int(d["is_unlimited"].sum()),
                "price_per_gb": price_per_gb(d),
                # Indice 100 = prix moyen du marché à volume et durée égaux (< 100 : moins cher).
                "price_index": _num(relative[d.index].mean() * 100, 1),
                "share_5g": _share((d["network"] == "5G").sum(), len(d)),
                "share_top_up": _share((d["top_up"] == "oui").sum(), len(d)),
                "destinations": int(d["country_code"].nunique()),
                "source_files": sorted(d["source_file"].unique()),
            }
        )
    return sorted(out, key=lambda p: (-p["offers"], p["provider"]))


def pricing(df: pd.DataFrame) -> dict:
    lim = limited(df)
    ratios = lim["price"] / lim["data_gb"]
    tiers = []
    for gb, d in lim.groupby("data_gb"):
        tiers.append({"data_gb": _num(gb), "offers": len(d), "price_per_gb": price_per_gb(d), "mean_price": _num(d["price"].mean())})
    by_validity = [
        {"validity_days": int(v), "offers": len(d), "mean_price": _num(d["price"].mean())}
        for v, d in df.groupby("validity_days")
    ]
    return {
        "power_law": power_law(df),
        "histogram": price_histogram(df),
        "price_per_gb": price_per_gb(df),
        "price_per_gb_median_of_ratios": _num(ratios.median()) if len(ratios) else None,
        "price_per_gb_mean_of_ratios": _num(ratios.mean()) if len(ratios) else None,
        "by_data_tier": tiers,
        "by_validity": by_validity,
    }


def _category_counts(df: pd.DataFrame, column: str) -> list[dict]:
    n = len(df)
    return [
        {"value": str(value), "offers": len(d), "share": _share(len(d), n), "mean_price": _num(d["price"].mean())}
        for value, d in sorted(df.groupby(column), key=lambda kv: (-len(kv[1]), str(kv[0])))
    ]


def distributions(df: pd.DataFrame) -> dict:
    data_tier = df["data_gb"].map(lambda g: f"{g:g} Go").where(~df["is_unlimited"], "Illimité")
    order = {f"{g:g} Go": g for g in sorted(limited(df)["data_gb"].unique())}
    tier_counts = data_tier.value_counts()
    return {
        "network": _category_counts(df, "network"),
        "network_like_for_like_5g_vs_4g": like_for_like_ratio(df, "network", "5G", "4G"),
        "top_up": _category_counts(df, "top_up"),
        "top_up_like_for_like_yes_vs_no": like_for_like_ratio(df, "top_up", "oui", "non"),
        "validity": [
            {"validity_days": int(v), "offers": int(c), "share": _share(c, len(df))}
            for v, c in df["validity_days"].value_counts().sort_index().items()
        ],
        "data_tiers": [
            {"label": label, "offers": int(tier_counts.get(label, 0))}
            for label in [*sorted(order, key=order.get), *(["Illimité"] if "Illimité" in tier_counts else [])]
        ],
    }


def coverage(df: pd.DataFrame) -> dict:
    countries = df[~df["is_region"]]
    regions = df[df["is_region"]]

    def ranking(d):
        counts = d.groupby(["country_code", "country_name"]).agg(
            offers=("sku", "size"), providers=("provider", "nunique"), min_price=("price", "min")
        )
        counts = counts.reset_index().sort_values(["offers", "country_name"], ascending=[False, True])
        return [
            {"code": r.country_code, "name": r.country_name, "offers": int(r.offers),
             "providers": int(r.providers), "min_price": _num(r.min_price, 2)}
            for r in counts.itertuples()
        ]

    return {
        "countries_count": int(countries["country_code"].nunique()),
        "regions_count": int(regions["country_code"].nunique()),
        "top_countries": ranking(countries)[:TOP_DESTINATIONS],
        "regions": ranking(regions),
        "region_codes_note": {code: name for code, name in REGION_CODES.items()},
        "countries_price_per_gb": countries_price_per_gb(df),
        "zones": zones(),
    }


def insights(h: dict, providers: list[dict], p: dict, dist: dict) -> list[dict]:
    """Constats calculés (jamais écrits en dur) : chaque texte dépend des données."""
    out = []
    exp = h["expensive"]
    if exp["count"]:
        threshold = fmt.euros(exp["threshold"], 0)
        if exp["unlimited_count"] == exp["count"]:
            days = " ou ".join(f"{d} jours" for d in exp["validity_days"])
            out.append({
                "id": "expensive_all_unlimited", "highlight": True,
                "title": (f"Les {fmt.number(exp['count'])} produits à plus de {threshold} sont tous des forfaits illimités"
                          if exp["count"] > 1 else f"Le seul produit à plus de {threshold} est un forfait illimité"),
                "text": f"{'Tous' if exp['count'] > 1 else 'Il est'} sur {days}. Le forfait à volume limité le plus cher coûte "
                        f"{fmt.euros(exp['max_price_limited'])} : au-delà de {threshold}, on ne trouve que de l'illimité.",
                "values": {"count": exp["count"], "max_price_limited": exp["max_price_limited"]},
            })
        else:
            out.append({
                "id": "expensive_mix", "highlight": True,
                "title": f"{fmt.number(exp['unlimited_count'])} des {fmt.number(exp['count'])} produits "
                         f"à plus de {threshold} sont des forfaits illimités",
                "text": "Les autres sont des forfaits à volume limité.",
                "values": {"count": exp["count"], "unlimited_count": exp["unlimited_count"]},
            })

    tiers = [t for t in p["by_data_tier"] if t["price_per_gb"]]
    if len(tiers) >= 2:
        lo, hi = tiers[0], tiers[-1]
        out.append({
            "id": "volume_discount", "highlight": False,
            "title": "Le prix au Go baisse fortement avec le volume",
            "text": f"{fmt.euros(lo['price_per_gb'])}/Go pour les forfaits de {fmt.number(lo['data_gb'])} Go, "
                    f"contre {fmt.euros(hi['price_per_gb'])}/Go pour ceux de {fmt.number(hi['data_gb'])} Go, "
                    f"soit {fmt.number(lo['price_per_gb'] / hi['price_per_gb'], 1)} fois moins cher.",
            "values": {"from_gb": lo["data_gb"], "from": lo["price_per_gb"], "to_gb": hi["data_gb"], "to": hi["price_per_gb"]},
        })

    law = p.get("power_law")
    if law and law["exponent"] is not None and law["exponent"] < 1:
        out.append({
            "id": "power_law", "highlight": False,
            "title": "Doubler le volume ne double pas le prix",
            "text": f"Le prix suit environ {fmt.number(law['coef'], 2)} € × Go^{fmt.number(law['exponent'], 2)} : "
                    f"quand le volume double, le prix n'est multiplié que par {fmt.number(law['doubling_factor'], 2)} "
                    f"(+{fmt.percent(law['doubling_factor'] - 1)}).",
            "values": law,
        })

    net = {c["value"]: c for c in dist["network"]}
    l4l = dist["network_like_for_like_5g_vs_4g"]
    if "4G" in net and "5G" in net and l4l is not None:
        raw = net["5G"]["mean_price"] / net["4G"]["mean_price"] - 1
        out.append({
            "id": "5g_premium", "highlight": False,
            "title": "À offre égale, la 5G coûte presque le même prix que la 4G",
            "text": f"En moyenne brute, la 5G paraît {fmt.percent(raw)} plus chère. Mais à volume et "
                    f"durée égaux, l'écart n'est que de {fmt.percent(l4l - 1, 1, signed=True)} : la différence brute "
                    "vient surtout de ce que les offres 5G comptent davantage de gros forfaits.",
            "values": {"raw": _num(raw), "like_for_like": _num(l4l - 1)},
        })

    ranked = sorted((pr for pr in providers if pr["price_per_gb"] is not None), key=lambda pr: pr["price_per_gb"])
    if len(ranked) >= 2:
        top = ranked[:CHEAPEST_TOP_N]
        worst = ranked[-1]
        names = [pr["provider"] for pr in top]
        # 3 décimales : à 2 décimales, le podium affiche trois fois « 1,63 € » et paraît arbitraire.
        listed = ", ".join(f"{pr['provider']} ({fmt.euros(pr['price_per_gb'], 3)}/Go)" for pr in top[:-1])
        listed += f" et {top[-1]['provider']} ({fmt.euros(top[-1]['price_per_gb'], 3)}/Go)"
        tied = top[-1]["price_per_gb"] / top[0]["price_per_gb"] - 1 < TIE_TOLERANCE
        joined = ", ".join(names[:-1]) + f" et {names[-1]}"
        if tied:
            title = f"Moins chers au Go : {joined}, quasiment à égalité"
            lead = (f"{listed} sont quasiment à égalité en tête : moins de "
                    f"{fmt.percent(TIE_TOLERANCE)} d'écart entre eux.")
        else:
            title = f"Moins chers au Go : {joined}"
            lead = f"En tête : {listed}."
        indices = [pr["price_index"] for pr in providers if pr["price_index"] is not None]
        lo_idx, hi_idx = min(indices), max(indices)
        by_index = min(providers, key=lambda pr: pr["price_index"])
        spread = f"entre {fmt.number(lo_idx, 1)} et {fmt.number(hi_idx, 1)} (100 = prix moyen du marché)"
        if hi_idx - lo_idx < HOMOGENEOUS_INDEX_SPREAD:
            check = (f"À volume et durée égaux, tous les fournisseurs ont un indice de prix {spread} : l'écart "
                     "au Go vient surtout de la part de gros forfaits dans leur catalogue, pas de tarifs différents.")
        else:
            check = (f"À volume et durée égaux, les indices de prix vont {spread} ; "
                     f"le plus bas est celui de {by_index['provider']}.")
        out.append({
            "id": "cheapest_provider", "highlight": False,
            "title": title,
            "text": f"{lead} Le plus cher au Go est {worst['provider']} ({fmt.euros(worst['price_per_gb'])}/Go). {check}",
            "values": {"top": [{"provider": pr["provider"], "price_per_gb": pr["price_per_gb"]} for pr in top],
                       "tied": tied, "worst": worst["provider"], "best_by_index": by_index["provider"],
                       "index_min": lo_idx, "index_max": hi_idx},
        })
    return out


def compute(df: pd.DataFrame) -> dict:
    h = headline(df)
    providers = by_provider(df)
    p = pricing(df)
    dist = distributions(df)
    return {
        "headline": h,
        "providers": providers,
        "provider_validity_index": provider_validity_index(df),
        "pricing": p,
        "distributions": dist,
        "coverage": coverage(df),
        "insights": insights(h, providers, p, dist),
    }
