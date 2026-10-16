# Fichiers tiers hébergés localement

Ces fichiers sont copiés dans `docs/assets/` à chaque génération. Ils sont servis par
le site lui-même : aucune requête ne part vers un CDN ou vers Google Fonts, donc
aucune adresse IP de visiteur n'est transmise à un tiers.

Leurs empreintes SHA-384 sont figées dans `dashboard/config.py` (`VENDOR_FILES`) et
vérifiées par `tests/test_site.py` : un fichier modifié ou corrompu fait échouer les tests.

| Fichier | Origine | Version | Licence |
|---|---|---|---|
| `chart.umd.min.js` | npm `chart.js` | 4.4.1 | MIT |
| `chartjs-chart-geo.umd.min.js` | npm `chartjs-chart-geo` | 4.3.6 | MIT |
| `countries-110m.json` | npm `world-atlas` (Natural Earth) | 2.0.2 | ISC (données : domaine public) |
| `fonts/inter-latin-wght-normal.woff2` | npm `@fontsource-variable/inter` | 5.3.0 | SIL OFL 1.1 |
| `fonts/inter-latin-ext-wght-normal.woff2` | npm `@fontsource-variable/inter` | 5.3.0 | SIL OFL 1.1 |
| `fonts/OFL.txt` | licence de la police Inter | — | — |

Sous-ensembles « latin » et « latin étendu » de la police : ils couvrent le français.
