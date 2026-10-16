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

# Pays couverts par chaque zone régionale : HYPOTHÈSE (les CSV ne le précisent pas).
# Utilisée par le comparateur pour proposer aussi les forfaits régionaux couvrant
# un pays. Choix prudents : on n'inclut un pays que s'il est couvert sans
# ambiguïté par les forfaits de la zone chez la plupart des fournisseurs.
# - Turquie : exclue de l'Europe (incluse chez certains fournisseurs seulement).
# - Moyen-Orient (AE, IL, JO, QA, SA) : exclu de l'Asie (zone souvent vendue à part).
# - Mexique : inclus dans l'Amérique du Nord ; Rép. dominicaine (Caraïbes) : exclue.
# - Monde (WW) : couvre tous les pays.
ZONE_MEMBERS = {
    "EU": ["AT", "BE", "CH", "CZ", "DE", "ES", "FR", "GB", "GR", "HR", "IE", "IT", "NL", "NO", "PL", "PT", "SE"],
    "AS": ["CN", "ID", "IN", "JP", "KR", "MY", "PH", "SG", "TH", "VN"],
    "NA": ["CA", "MX", "US"],
}
WORLD_ZONE = "WW"

# Codes ISO 3166-1 alpha-2 -> numérique (identifiants du fond de carte world-atlas).
# Source : github.com/lukes/ISO-3166-Countries-with-Regional-Codes, recoupée à la main
# pour les 50 pays du catalogue.
ISO_NUMERIC_FILE = ROOT_DIR / "dashboard" / "reference" / "iso3166_numeric.json"
