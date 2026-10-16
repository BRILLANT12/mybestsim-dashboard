"""Constantes partagées : chemins, schéma attendu des CSV, seuils métier."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "docs"

# Schéma commun à tous les fournisseurs. Un CSV qui ne le respecte pas est
# signalé dans le rapport d'anomalies au lieu de faire planter la génération.
EXPECTED_COLUMNS = [
    "sku",
    "provider",
    "product_name",
    "country_code",
    "country_name",
    "data_gb",
    "data_display",
    "validity_days",
    "price",
    "currency",
    "network",
    "top_up",
]

EXPECTED_CURRENCY = "EUR"
ALLOWED_NETWORKS = {"4G", "5G"}
ALLOWED_TOP_UP = {"oui", "non"}
UNLIMITED_LABEL = "Illimité"

# Seuil « produits chers » : strictement supérieur (> 100 €, pas ≥).
EXPENSIVE_THRESHOLD_EUR = 100

# Codes de zones régionales propres à ce jeu de données. Attention : en ISO 3166,
# NA = Namibie et AS = Samoa américaines ; ici ils désignent des régions.
REGION_CODES = {
    "EU": "Europe",
    "AS": "Asie",
    "NA": "Amérique du Nord",
    "WW": "Monde",
}
