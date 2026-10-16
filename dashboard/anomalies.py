"""Modèle d'une anomalie détectée pendant le chargement ou la validation."""

from dataclasses import asdict, dataclass

ERROR = "erreur"  # ligne (ou fichier) exclue des calculs
WARNING = "avertissement"  # ligne conservée mais signalée


@dataclass(frozen=True)
class Anomaly:
    severity: str
    rule: str
    message: str
    file: str
    line: int | None = None  # numéro de ligne physique dans le CSV (en-tête = 1)
    sku: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# Catalogue de tous les contrôles, affiché sur le dashboard même quand tout passe.
RULES = {
    # niveau fichier
    "fichier_vide": (ERROR, "Fichier vide"),
    "fichier_illisible": (ERROR, "Fichier illisible (encodage, format)"),
    "colonnes_manquantes": (ERROR, "Colonnes obligatoires manquantes"),
    "colonnes_en_trop": (WARNING, "Colonnes inconnues (ignorées)"),
    "fichier_sans_ligne": (WARNING, "Fichier sans aucune offre"),
    # niveau ligne : exclusion
    "champ_vide": (ERROR, "Champ obligatoire vide"),
    "prix_illisible": (ERROR, "Prix illisible"),
    "prix_non_positif": (ERROR, "Prix nul ou négatif"),
    "devise": (ERROR, "Devise autre que EUR"),
    "duree_invalide": (ERROR, "Durée de validité invalide"),
    "data_manquante": (ERROR, "Volume de data manquant (hors illimité)"),
    "data_invalide": (ERROR, "Volume de data invalide"),
    "sku_duplique": (ERROR, "SKU en double"),
    # niveau ligne : signalement
    "virgule_decimale": (WARNING, "Virgule décimale convertie"),
    "data_incoherente": (WARNING, "data_gb incohérent avec data_display"),
    "reseau_inconnu": (WARNING, "Réseau autre que 4G/5G"),
    "recharge_inconnue": (WARNING, "Recharge autre que oui/non"),
    "code_pays": (WARNING, "Code pays mal formé"),
    "doublon_probable": (WARNING, "Offre identique sous un autre SKU"),
    "prix_aberrant": (WARNING, "Prix aberrant par rapport aux offres comparables"),
}
