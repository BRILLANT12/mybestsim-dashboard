"""Validation ligne par ligne des offres.

Deux niveaux :
- ERREUR : la ligne est exclue des calculs (on ne peut pas l'utiliser sans inventer).
- AVERTISSEMENT : la ligne est gardée mais signalée dans le rapport.
"""

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from dashboard.anomalies import ERROR, WARNING, Anomaly
from dashboard.config import (
    ALLOWED_NETWORKS,
    ALLOWED_TOP_UP,
    EXPECTED_CURRENCY,
    REGION_CODES,
    UNLIMITED_LABEL,
)

REQUIRED_FIELDS = [
    "sku",
    "provider",
    "product_name",
    "country_code",
    "country_name",
    "data_display",
    "validity_days",
    "price",
    "currency",
    "network",
    "top_up",
]  # data_gb n'est pas obligatoire : il est vide pour les forfaits illimités

UNLIMITED_ALIASES = {UNLIMITED_LABEL.casefold(), "illimite", "unlimited"}

# Prix aberrant : plus de OUTLIER_FACTOR fois (ou moins de 1/OUTLIER_FACTOR) la
# médiane des produits comparables (même volume, même durée), si le groupe
# compte au moins OUTLIER_MIN_GROUP produits.
OUTLIER_FACTOR = 5
OUTLIER_MIN_GROUP = 5

# « Même offre » : mêmes caractéristiques visibles chez le même fournisseur.
# Deux lignes identiques sur ces colonnes mais de prix différents sont une seule
# offre affichée à deux prix : le prix retenu dépend de la ligne choisie.
SAME_OFFER_KEYS = ["provider", "product_name", "country_code", "data_display", "validity_days", "network", "top_up"]
SAME_OFFER_EXAMPLES = 5

_DISPLAY_RE = re.compile(r"^([\d]+(?:[.,]\d+)?)\s*(go|gb|mo|mb)$", re.IGNORECASE)


@dataclass
class ValidationResult:
    clean: pd.DataFrame
    anomalies: list[Anomaly]
    total_rows: int
    excluded_rows: int
    same_offer: dict | None = None  # synthèse du contrôle « même offre, prix différents »


def is_unlimited(display: str) -> bool:
    return display.casefold() in UNLIMITED_ALIASES


def parse_number(raw: str) -> tuple[float | None, bool]:
    """Convertit un texte en nombre. Renvoie (valeur, virgule_convertie)."""
    if raw == "":
        return None, False
    comma = "," in raw and "." not in raw
    try:
        value = float(raw.replace(",", ".") if comma else raw)
    except ValueError:
        return None, False
    if not np.isfinite(value):
        return None, False
    return value, comma


def parse_display_gb(display: str) -> float | None:
    m = _DISPLAY_RE.match(display.strip())
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    return value / 1000 if m.group(2).lower() in ("mo", "mb") else value


def _check_row(row: dict) -> tuple[dict | None, list[Anomaly]]:
    """Valide une ligne. Renvoie (valeurs typées ou None si exclue, anomalies)."""
    found: list[Anomaly] = []
    sku = row["sku"] or None

    def flag(severity, rule, message):
        found.append(Anomaly(severity, rule, message, row["source_file"], row["line"], sku))

    empty = [f for f in REQUIRED_FIELDS if row[f] == ""]
    if empty:
        flag(ERROR, "champ_vide", f"Champ(s) obligatoire(s) vide(s) : {', '.join(empty)}.")

    price, comma = parse_number(row["price"])
    if row["price"] != "":
        if price is None:
            flag(ERROR, "prix_illisible", f"Prix illisible : « {row['price']} ».")
        elif price <= 0:
            flag(ERROR, "prix_non_positif", f"Prix nul ou négatif : {row['price']}.")
        elif comma:
            flag(WARNING, "virgule_decimale", f"Prix « {row['price']} » : virgule décimale convertie.")

    if row["currency"] != "" and row["currency"].upper() != EXPECTED_CURRENCY:
        flag(ERROR, "devise", f"Devise « {row['currency']} » au lieu de {EXPECTED_CURRENCY} (pas de conversion).")

    validity, _ = parse_number(row["validity_days"])
    if row["validity_days"] != "" and (validity is None or validity <= 0 or validity != int(validity)):
        flag(ERROR, "duree_invalide", f"Durée de validité invalide : « {row['validity_days']} ».")

    unlimited = is_unlimited(row["data_display"])
    data_gb, data_comma = parse_number(row["data_gb"])
    if unlimited:
        if row["data_gb"] != "":
            flag(WARNING, "data_incoherente", f"Forfait « Illimité » avec data_gb = {row['data_gb']} : traité comme illimité.")
        data_gb = None
    elif row["data_gb"] == "":
        if row["data_display"] != "":
            flag(ERROR, "data_manquante", f"data_gb vide alors que le forfait n'est pas illimité (« {row['data_display']} »).")
    elif data_gb is None or data_gb <= 0:
        flag(ERROR, "data_invalide", f"Volume de data invalide : « {row['data_gb']} ».")
    else:
        if data_comma:
            flag(WARNING, "virgule_decimale", f"data_gb « {row['data_gb']} » : virgule décimale convertie.")
        shown = parse_display_gb(row["data_display"])
        if shown is not None and abs(shown - data_gb) > 0.01:
            flag(WARNING, "data_incoherente", f"data_gb = {row['data_gb']} mais data_display = « {row['data_display']} ».")

    if row["network"] != "" and row["network"] not in ALLOWED_NETWORKS:
        flag(WARNING, "reseau_inconnu", f"Réseau inconnu : « {row['network']} ».")
    if row["top_up"] != "" and row["top_up"] not in ALLOWED_TOP_UP:
        flag(WARNING, "recharge_inconnue", f"Valeur de recharge inconnue : « {row['top_up']} ».")
    if row["country_code"] != "" and not re.fullmatch(r"[A-Z]{2}", row["country_code"]):
        flag(WARNING, "code_pays", f"Code pays non conforme (2 majuscules attendues) : « {row['country_code']} ».")

    if any(a.severity == ERROR for a in found):
        return None, found

    typed = dict(row)
    typed.update(
        price=price,
        data_gb=np.nan if data_gb is None else data_gb,
        validity_days=int(validity),
        currency=row["currency"].upper(),
        is_unlimited=unlimited,
        is_region=row["country_code"] in REGION_CODES,
    )
    return typed, found


def _price_outliers(clean: pd.DataFrame) -> list[Anomaly]:
    found = []
    tier = clean["data_gb"].astype(object).where(~clean["is_unlimited"], "illimité")
    for _, group in clean.groupby([tier, clean["validity_days"]]):
        if len(group) < OUTLIER_MIN_GROUP:
            continue
        median = group["price"].median()
        odd = group[(group["price"] > median * OUTLIER_FACTOR) | (group["price"] < median / OUTLIER_FACTOR)]
        for r in odd.itertuples():
            found.append(
                Anomaly(
                    WARNING,
                    "prix_aberrant",
                    f"Prix {r.price:.2f} € très éloigné de la médiane des produits comparables ({median:.2f} €).",
                    r.source_file,
                    r.line,
                    r.sku,
                )
            )
    return found


def same_offer_price_gaps(clean: pd.DataFrame) -> tuple[list[Anomaly], dict]:
    """Offres présentes plusieurs fois chez un fournisseur avec des prix différents.

    Un avertissement par offre (et non par ligne), placé sur sa première ligne ; toutes
    les lignes sont gardées. Renvoie (anomalies, synthèse pour le rapport qualité).
    """
    found, groups = [], []
    if len(clean):
        ordered = clean.sort_values(["source_file", "line"])
        for _, g in ordered.groupby(SAME_OFFER_KEYS, sort=False):
            if g["price"].nunique() < 2:
                continue
            lo, hi = g["price"].min(), g["price"].max()
            first = g.iloc[0]
            listed = ", ".join(f"{r.sku} à {r.price:.2f} €" for r in g.itertuples())
            found.append(Anomaly(
                WARNING,
                "meme_offre_prix_differents",
                f"Même offre sous {len(g)} SKU à des prix différents ({listed}) : écart de {(hi / lo - 1) * 100:.0f} %.",
                first["source_file"],
                int(first["line"]),
                first["sku"],
            ))
            groups.append({
                "provider": first["provider"],
                "product_name": first["product_name"],
                "rows": len(g),
                "min_price": round(float(lo), 2),
                "max_price": round(float(hi), 2),
                "gap": round(float(hi / lo - 1), 4),
                "skus": list(g["sku"]),
            })
    by_provider = {}
    for g in groups:
        p = by_provider.setdefault(g["provider"], {"provider": g["provider"], "offers": 0, "rows": 0, "max_gap": 0.0})
        p["offers"] += 1
        p["rows"] += g["rows"]
        p["max_gap"] = max(p["max_gap"], g["gap"])
    groups.sort(key=lambda g: (-g["gap"], g["provider"], g["product_name"]))
    summary = {
        "offers": len(groups),
        "rows": sum(g["rows"] for g in groups),
        "max_gap": groups[0]["gap"] if groups else None,
        "by_provider": sorted(by_provider.values(), key=lambda p: (-p["offers"], p["provider"])),
        "examples": groups[:SAME_OFFER_EXAMPLES],
    }
    return found, summary


def validate(rows: pd.DataFrame) -> ValidationResult:
    anomalies: list[Anomaly] = []
    kept = []
    for row in rows.to_dict("records"):
        typed, found = _check_row(row)
        anomalies.extend(found)
        if typed is not None:
            kept.append(typed)

    clean = pd.DataFrame(kept, columns=[*rows.columns, "is_unlimited", "is_region"])

    # SKU en double : on garde la première occurrence valide (ordre alphabétique
    # des fichiers puis ordre des lignes), les suivantes sont exclues.
    dup = clean["sku"].duplicated(keep="first")
    first_seen = clean.drop_duplicates("sku").set_index("sku")
    for r in clean[dup].itertuples():
        origin = first_seen.loc[r.sku]
        anomalies.append(
            Anomaly(
                ERROR,
                "sku_duplique",
                f"SKU déjà présent ({origin.source_file}, ligne {origin.line}) : occurrence exclue.",
                r.source_file,
                r.line,
                r.sku,
            )
        )
    clean = clean[~dup].reset_index(drop=True)

    # Même offre sous deux SKU différents : probable doublon, gardé mais signalé.
    content_cols = [c for c in clean.columns if c not in ("sku", "source_file", "line")]
    same = clean.duplicated(subset=content_cols, keep="first")
    for r in clean[same].itertuples():
        anomalies.append(
            Anomaly(WARNING, "doublon_probable", "Offre identique à une autre sous un SKU différent.", r.source_file, r.line, r.sku)
        )

    anomalies.extend(_price_outliers(clean))
    same_offer_found, same_offer = same_offer_price_gaps(clean)
    anomalies.extend(same_offer_found)

    clean = clean.astype({"price": float, "data_gb": float, "validity_days": int, "is_unlimited": bool, "is_region": bool})
    return ValidationResult(
        clean=clean,
        anomalies=anomalies,
        total_rows=len(rows),
        excluded_rows=len(rows) - len(clean),
        same_offer=same_offer,
    )
