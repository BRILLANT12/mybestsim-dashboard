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

# Fichiers tiers hébergés localement (voir dashboard/vendor/README.md) et leur
# empreinte SHA-384 : vérifiée par les tests, toute modification est détectée.
VENDOR_DIR = ROOT_DIR / "dashboard" / "vendor"
VENDOR_FILES = {
    "chart.umd.min.js": "sha384-9nhczxUqK87bcKHh20fSQcTGD4qq5GhayNYSYWqwBkINBhOfQLg/P5HG5lF1urn4",
    "chartjs-chart-geo.umd.min.js": "sha384-EW6qTcZh7bPyECHRcIzVvefbUO37nGjPkmDFEdcdAe7ex44EjBA0GWnoleczHbC/",
    "countries-110m.json": "sha384-yOCJ+8ShBm8UDqtAVtAvxTDDf4gXo5edxl/YG0FmVC5OTmqVLl7utuVGBDEeZWHf",
    "fonts/inter-latin-wght-normal.woff2": "sha384-l0ql7Q1zqvX5klAVRwYjcMVCkCxg5dMTdghsIlC3pYkX6wwEHerh2bP/4yAao3Im",
    "fonts/inter-latin-ext-wght-normal.woff2": "sha384-r0EoKgCx3XyQjhJdTJ6FDE+8mEZrV95dM7cWvqLDUVdqzM44cq76qdOaYiA3sebS",
    "fonts/OFL.txt": "sha384-kj3ws+qnzjazxsLTzPAVaXquIFuyNRYVaSXX024NG79Z2vDskAWFDhnsJYazAo0C",
}

# Politique de sécurité du contenu, identique sur toutes les pages : aucun script en
# ligne, aucune ressource externe, aucune connexion réseau. Seule exception assumée :
# les attributs style="" générés (largeurs de barres, couleurs), qui ne peuvent pas
# exécuter de code.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; "
    "img-src 'self'; font-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
)

# Éditeur du site (aucun e-mail ni téléphone : contact via GitHub ou LinkedIn uniquement).
AUTHOR = "Jean Bonheur NGUEMA"
GITHUB_URL = "https://github.com/BRILLANT12"
LINKEDIN_URL = "https://www.linkedin.com/in/jean-bonheur-nguema-097044346"
# Dépôt du code source. En CI, GitHub fournit le nom exact (GITHUB_REPOSITORY), qui prime.
DEFAULT_REPOSITORY = "BRILLANT12/mybestsim-dashboard"

# Hébergeur. Adresse vérifiée le 16/10/2026 dans la « GitHub General Privacy Statement »
# (en vigueur au 27/04/2026). GitHub ne publie pas de numéro de téléphone (« We do not
# offer telephone support », GitHub Terms of Service) : contact via son formulaire.
HOST = {
    "name": "GitHub, Inc. (service GitHub Pages)",
    "address": "88 Colin P. Kelly Jr. St., San Francisco, CA 94107, États-Unis",
    "contact": "https://support.github.com/contact",
    "source": "https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
}
LEGAL_UPDATED = "2026-10-16"  # date de dernière modification du contenu des mentions légales
