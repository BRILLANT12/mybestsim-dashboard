"""Rendu réel de la page dans Chrome headless : aucune erreur JS, rendu complet.

Ignoré si aucun Chrome/Chromium n'est trouvé (Chrome est préinstallé sur les
machines GitHub Actions).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from dashboard.build import build, write_outputs

FIXTURES = Path(__file__).parent / "fixtures"
MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME = next(
    (c for c in (shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser"),
                 MAC_CHROME if Path(MAC_CHROME).exists() else None) if c),
    None,
)
pytestmark = pytest.mark.skipif(CHROME is None, reason="Chrome/Chromium introuvable : test de rendu ignoré")

# Collecte des erreurs JS dès le début, puis rapport après le chargement.
CATCH = "<script>window.__errs=[];addEventListener('error',function(e){__errs.push(String(e.message||e))});</script>"
PROBE = (
    "<script>addEventListener('load',function(){setTimeout(function(){__ACTION__},300);setTimeout(function(){var d=document.documentElement;"
    "var p=document.createElement('pre');p.id='PROBE';p.textContent=JSON.stringify({ready:d.dataset.ready||null,"
    "errors:__errs,overflow:d.scrollWidth>d.clientWidth,kpis:document.querySelectorAll('#kpis .kpi').length,"
    "hero:document.getElementById('hero-kpis').textContent,result:document.getElementById('fb-result').textContent,"
    "empty:document.body.classList.contains('is-empty'),search:location.search,extra:window.__extra||null});"
    "document.body.appendChild(p)},1500)})</script>"
)


def render(data_dir: Path, tmp_path: Path, width: int = 1280, query: str = "", action: str = "") -> dict:
    result, offers = build(data_dir)
    _, html_path = write_outputs(result, tmp_path, offers)
    html = html_path.read_text(encoding="utf-8").replace("<head>", "<head>" + CATCH, 1).replace("</body>", PROBE.replace("__ACTION__", action) + "</body>", 1)
    page = tmp_path / "probe.html"
    page.write_text(html, encoding="utf-8")
    done = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={tmp_path / 'profile'}",
         f"--window-size={width},900", "--virtual-time-budget=8000", "--dump-dom", page.as_uri() + query],
        capture_output=True, text=True, timeout=120,
    )
    m = re.search(r'<pre id="PROBE">(.*?)</pre>', done.stdout, re.S)
    assert m, "la page n'a pas terminé son chargement :\n" + done.stderr[-2000:]
    return json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&"))


@pytest.mark.parametrize("data_dir", [FIXTURES / "calculs", FIXTURES / "pieges"], ids=["calculs", "pieges"])
def test_page_renders_without_js_errors(data_dir, tmp_path):
    probe = render(data_dir, tmp_path)
    assert probe["errors"] == []
    assert probe["ready"] == "1"
    assert probe["kpis"] == 6
    # Valeur finale (et non une valeur d'animation) : 8 offres valides dans « calculs », 9 dans « pieges ».
    expected = {"calculs": "8", "pieges": "9"}[data_dir.name]
    assert f"Cartes eSIM au catalogue{expected}offres valides" in probe["hero"]


def test_no_horizontal_overflow_on_mobile_width(tmp_path):
    # Chrome headless impose une fenêtre d'au moins 500 px : on vérifie à cette largeur
    # (les captures à 375 px réels sont faites dans une iframe, hors tests).
    probe = render(FIXTURES / "calculs", tmp_path, width=500)
    assert probe["errors"] == [] and probe["overflow"] is False


# --- Filtres (lot 4) -----------------------------------------------------------


def test_filters_are_read_from_the_url(tmp_path):
    probe = render(FIXTURES / "calculs", tmp_path, query="?fournisseur=Prov%20A&reseau=4G")
    assert probe["errors"] == []
    assert "Cartes eSIM au catalogue2offres valides" in probe["hero"]  # a1 et a4
    assert probe["result"] == "2 offres sur 8"


def test_filter_without_result_shows_empty_state(tmp_path):
    probe = render(FIXTURES / "calculs", tmp_path, query="?fournisseur=Inconnu")
    assert probe["errors"] == [] and probe["empty"] is True
    assert "Cartes eSIM au catalogue0offres valides" in probe["hero"]


def test_clicking_a_toggle_recomputes_and_updates_url(tmp_path):
    action = "document.querySelector('.toggle[data-key=network][data-value=\\'5G\\']').click();"
    probe = render(FIXTURES / "calculs", tmp_path, action=action)
    assert probe["errors"] == []
    assert "Cartes eSIM au catalogue3offres valides" in probe["hero"]  # a2, a3, b4
    assert probe["search"] == "?reseau=5G"


def test_export_contains_the_filtered_rows(tmp_path):
    # On intercepte le téléchargement pour lire le CSV produit par le bouton.
    action = ("URL.createObjectURL=function(b){b.text().then(function(t){window.__extra=t});return 'blob:x'};"
              "HTMLAnchorElement.prototype.click=function(){};document.getElementById('fb-export').click();")
    probe = render(FIXTURES / "calculs", tmp_path, query="?destination=FR", action=action)
    lines = probe["extra"].lstrip("\ufeff").strip().split("\n")
    assert lines[0].startswith("sku,provider,product_name,country_code")
    assert sorted(line.split(",")[0] for line in lines[1:]) == ["a1", "a2", "b1"]


def test_podium_requires_a_minimum_sample(tmp_path):
    # Dans « calculs », chaque fournisseur n'a que 3 forfaits limités : pas de podium.
    action = "window.__extra=document.getElementById('ppg-provider-sub').textContent+'|'+document.querySelectorAll('#providers-table .rank').length;"
    probe = render(FIXTURES / "calculs", tmp_path, action=action)
    sub, ranks = probe["extra"].split("|")
    assert sub.startswith("Échantillon trop petit pour un classement") and ranks == "0"


# --- Analyses (lot 5) ----------------------------------------------------------


def test_heatmap_and_zones_follow_the_data(tmp_path):
    action = ("window.__extra=[document.querySelectorAll('#heatmap tbody tr').length,"
              "document.querySelectorAll('#zones-list li').length,"
              "document.querySelectorAll('#table-quantiles tbody tr').length].join('|');")
    probe = render(FIXTURES / "calculs", tmp_path, action=action)
    assert probe["errors"] == []
    assert probe["extra"] == "2|2|2"  # 2 fournisseurs, 2 zones (NA, WW), 2 lignes de quantiles
