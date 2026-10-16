"""Fiche détaillée de chaque fournisseur (une page générée par fournisseur).

Un nouveau CSV dans data/ = un nouveau fournisseur = une nouvelle fiche, sans toucher au
code. Les indicateurs réutilisent les fonctions de stats.py (mêmes règles que le tableau
de bord) ; l'indice de prix est calculé face à tout le marché, à offre comparable.
"""

import pandas as pd

from dashboard import stats
from dashboard.markdown import slugify

TOP_OFFERS = 5


def page_paths(providers: list[str]) -> dict[str, str]:
    """Chemin de la fiche de chaque fournisseur, unique même si deux noms donnent le même slug."""
    paths, used = {}, set()
    for name in sorted(providers):
        base = slug = slugify(name)
        n = 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        paths[name] = f"fournisseurs/{slug}.html"
    return paths


def _num(v, digits=4):
    return stats._num(v, digits)


def profile(df: pd.DataFrame, provider: str, market: dict) -> dict:
    d = df[df["provider"] == provider]
    lim = stats.limited(d)
    row = next(p for p in market["providers"] if p["provider"] == provider)
    ranked = sorted((p for p in market["providers"] if p["price_per_gb"] is not None), key=lambda p: p["price_per_gb"])
    by_index = sorted(market["providers"], key=lambda p: p["price_index"])

    best = lim.assign(ppg=lim["price"] / lim["data_gb"]).sort_values(["ppg", "price", "sku"]).head(TOP_OFFERS)
    destinations = []
    for (code, name), g in d.groupby(["country_code", "country_name"]):
        destinations.append({
            "code": code, "name": name, "offers": len(g), "is_region": bool(g["is_region"].iloc[0]),
            "min_price": _num(g["price"].min(), 2), "price_per_gb": stats.price_per_gb(g),
        })
    cells = [c for c in market["provider_validity_index"]["cells"] if c["provider"] == provider]
    return {
        "provider": provider,
        "offers": len(d),
        "share": row["share"],
        "mean_price": row["mean_price"],
        "median_price": _num(d["price"].median()),
        "min_price": row["min_price"],
        "max_price": _num(d["price"].max(), 2),
        "mean_data_gb": row["mean_data_gb"],
        "unlimited": row["unlimited"],
        "price_per_gb": row["price_per_gb"],
        "price_index": row["price_index"],
        "share_5g": row["share_5g"],
        "share_top_up": row["share_top_up"],
        "rank_price_per_gb": next((i + 1 for i, p in enumerate(ranked) if p["provider"] == provider), None),
        "rank_index": next(i + 1 for i, p in enumerate(by_index) if p["provider"] == provider),
        "providers_count": len(market["providers"]),
        "countries_count": int(d.loc[~d["is_region"], "country_code"].nunique()),
        "regions_count": int(d.loc[d["is_region"], "country_code"].nunique()),
        "destinations": sorted(destinations, key=lambda x: (x["is_region"], x["name"])),
        "best_offers": [
            {"sku": r.sku, "product_name": r.product_name, "country_name": r.country_name, "data_display": r.data_display,
             "validity_days": int(r.validity_days), "price": _num(r.price, 2), "price_per_gb": _num(r.ppg),
             "network": r.network, "top_up": r.top_up}
            for r in best.itertuples()
        ],
        "index_by_validity": sorted(({"validity_days": c["validity_days"], "index": c["index"], "offers": c["offers"]} for c in cells),
                                    key=lambda c: c["validity_days"]),
        "data_tiers": stats.distributions(d)["data_tiers"],
        "source_files": row["source_files"],
    }


def market_summary(market: dict) -> dict:
    """Repères du marché affichés en face des chiffres du fournisseur."""
    h, dist = market["headline"], market["distributions"]
    share = lambda items, value: next((x["share"] for x in items if x["value"] == value), 0)  # noqa: E731
    return {
        "mean_price": h["price"]["mean"],
        "median_price": h["price"]["median"],
        "price_per_gb": market["pricing"]["price_per_gb"],
        "mean_data_gb": h["data"]["mean_gb"],
        "share_5g": share(dist["network"], "5G"),
        "share_top_up": share(dist["top_up"], "oui"),
    }
