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
from dashboard.config import DATA_DIR as DATA_DIR_REAL

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


# --- Accessibilité (lot 6) : contrastes du texte mesurés dans le navigateur --------

# Pour chaque élément portant du texte visible : couleur du texte et du fond réellement
# rendues (transparences composées), ratio WCAG, seuil 4,5:1 (3:1 pour le grand texte).
# Les zones à fond dégradé (hero, bandeau des constats) sont vérifiées à part, dans
# leurs couleurs les plus défavorables (test_gradient_areas_contrast).
CONTRAST_AUDIT = r"""
function parse(c){var m=c.match(/rgba?\(([^)]+)\)/);if(m){var p=m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);return[p[0],p[1],p[2],p.length>3?p[3]:1];}
 m=c.match(/color\(srgb ([^)]+)\)/);if(m){var q=m[1].split(/[ \/]+/).filter(Boolean).map(Number);return[q[0]*255,q[1]*255,q[2]*255,q.length>3?q[3]:1];}return[0,0,0,0];}
function over(a,b){var t=a[3];return[a[0]*t+b[0]*(1-t),a[1]*t+b[1]*(1-t),a[2]*t+b[2]*(1-t),1];}
function lum(c){var v=c.slice(0,3).map(function(x){x/=255;return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4)});return 0.2126*v[0]+0.7152*v[1]+0.0722*v[2];}
function ratio(a,b){var x=lum(a),y=lum(b);return(Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);}
function bgOf(el){var layers=[];for(var e=el;e;e=e.parentElement){var cs=getComputedStyle(e);if(cs.backgroundImage!=='none')return null;var c=parse(cs.backgroundColor);if(c[3]>0){layers.push(c);if(c[3]>=1)break;}}
 var b=[255,255,255,1];for(var i=layers.length-1;i>=0;i--)b=over(layers[i],b);return b;}
var fails=[],checked=0;
document.querySelectorAll('body *').forEach(function(el){
 if(el.closest('.hero,.band-dark,svg,canvas,.sr-only,[hidden],script,style'))return;
 var own=Array.prototype.some.call(el.childNodes,function(n){return n.nodeType===3&&n.textContent.trim();});if(!own)return;
 var r=el.getBoundingClientRect();if(!r.width||!r.height)return;var cs=getComputedStyle(el);if(cs.visibility==='hidden'||+cs.opacity===0)return;
 var bg=bgOf(el);if(!bg)return;var fg=over(parse(cs.color),bg);var size=parseFloat(cs.fontSize),bold=+cs.fontWeight>=700;
 var need=(size>=24||(size>=18.66&&bold))?3:4.5;
 if(el.closest('.thin'))return; /* cellules « échantillon faible », volontairement estompées et doublées d'une infobulle */
 checked++;var k=ratio(fg,bg);if(k<need)fails.push(el.textContent.trim().slice(0,40)+' | '+k.toFixed(2)+' < '+need);});
window.__extra=JSON.stringify({checked:checked,fails:fails.slice(0,20),n:fails.length});
"""


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_text_contrast_meets_wcag_aa(theme, tmp_path):
    # Changement de thème par le vrai bouton (comme un utilisateur), puis audit.
    action = f"document.querySelector('.theme-switch button[data-mode={theme}]').click();setTimeout(function(){{{CONTRAST_AUDIT}}},400);"
    probe = render(DATA_DIR_REAL, tmp_path, action=action)
    audit = json.loads(probe["extra"])
    assert audit["checked"] > 300, audit
    assert audit["n"] == 0, audit["fails"]


def test_gradient_areas_contrast():
    # Hero et bandeau des constats : textes clairs sur dégradés marine/bleu ; on vérifie
    # chaque couleur de texte sur la couleur de fond la plus claire du dégradé.
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def ratio(a, b):
        x, y = sorted([lum(a), lum(b)], reverse=True)
        return (x + 0.05) / (y + 0.05)

    lightest_backgrounds = ["#0b3a86", "#0c2756", "#1b4a96"]  # dernier : verre (blanc 6 %) sur #0b3a86
    for ink in ["#ffffff", "#c3d2ec", "#b4c6e6", "#dbe6f7", "#ffd84d"]:
        for bg in lightest_backgrounds:
            assert ratio(ink, bg) >= 4.5, (ink, bg)


# --- Comparateur et clavier (lot 6) -----------------------------------------------


def test_comparator_ranks_regional_offers(tmp_path):
    # États-Unis, illimité : aucune offre propre, mais Monde (100 €) et Amérique du Nord (120 €) couvrent le pays.
    action = ("var p=document.getElementById('cmp-place');p.value='US';var v=document.getElementById('cmp-volume');v.value='unlimited';"
              "v.dispatchEvent(new Event('change'));setTimeout(function(){window.__extra=[document.querySelectorAll('#cmp-table tbody tr').length,"
              "document.querySelector('#cmp-best .p').textContent,document.querySelectorAll('#cmp-table .badge.region').length].join('|')},100);")
    probe = render(FIXTURES / "calculs", tmp_path, action=action)
    rows, best, regional = probe["extra"].split("|")
    assert probe["errors"] == []
    assert rows == "2" and best.startswith("100,00") and regional == "2"


def test_dropdown_is_keyboard_operable(tmp_path):
    action = ("var b=document.getElementById('dd-provider-btn');b.click();var r=[document.activeElement.className,"
              "document.getElementById('dd-provider').hidden];document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));"
              "r.push(document.getElementById('dd-provider').hidden,document.activeElement===b);window.__extra=r.join('|');")
    probe = render(FIXTURES / "calculs", tmp_path, action=action)
    # ouvert -> focus dans la recherche ; Échap -> fermé et focus rendu au bouton
    assert probe["extra"] == "dd-search|false|true|true"


def test_comparator_shows_top_ten_then_all(tmp_path):
    action = ("var n=function(){return document.querySelectorAll('#cmp-table tbody tr').length};var a=n();"
              "document.getElementById('cmp-more').click();window.__extra=[a,n(),document.getElementById('cmp-more').getAttribute('aria-expanded')].join('|');")
    probe = render(DATA_DIR_REAL, tmp_path, action=action)
    shown, expanded, aria = probe["extra"].split("|")
    assert shown == "10" and int(expanded) > 10 and aria == "true"
