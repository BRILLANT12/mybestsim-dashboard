"""Formatage des nombres à la française pour les textes générés côté Python.

Espace fine insécable (U+202F) pour les milliers et avant « % » / « € »,
comme le fait Intl.NumberFormat("fr-FR") côté navigateur.
"""

NNBSP = " "


def number(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"  # 5,056.50
    return text.replace(",", NNBSP).replace(".", ",")


def euros(value: float, decimals: int = 2) -> str:
    return f"{number(value, decimals)}{NNBSP}€"


def percent(ratio: float, decimals: int = 0, signed: bool = False) -> str:
    text = number(abs(ratio) * 100, decimals)
    sign = ("+" if ratio >= 0 else "−") if signed else ("−" if ratio < 0 else "")
    return f"{sign}{text}{NNBSP}%"
