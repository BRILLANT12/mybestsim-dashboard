"""Vie privée et sécurité du site généré : aucun cookie, aucun traceur, aucun tiers.

Ces tests portent sur TOUTES les pages générées (une page ajoutée est couverte d'office).
"""

import base64
import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from dashboard.build import build, write_outputs
from dashboard.config import CONTENT_SECURITY_POLICY, VENDOR_DIR, VENDOR_FILES
from tests.browser import CHROME, instrument, run_page

FIXTURES = Path(__file__).parent / "fixtures"
OWN_JS = ["theme.js", "site.js", "analytics.js", "dashboard.js"]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    result, offers = build(FIXTURES / "calculs")
    write_outputs(result, out, offers)
    return out


def pages(site_dir: Path) -> list[Path]:
    found = sorted(p for p in site_dir.rglob("*.html") if not p.name.startswith(("probe", "_")))
    assert found, "aucune page générée"
    return found


class Inspector(HTMLParser):
    """Relève les ressources chargées, les scripts en ligne et les gestionnaires on…= d'une page."""

    def __init__(self):
        super().__init__()
        self.loads, self.inline_scripts, self.handlers, self.csp = [], [], [], []
        self._in_script = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.handlers += [k for k in a if k.startswith("on")]
        if tag == "meta" and a.get("http-equiv", "").lower() == "content-security-policy":
            self.csp.append(a.get("content"))
        if tag in ("script", "img", "iframe", "audio", "video", "source", "embed") and a.get("src"):
            self.loads.append(a["src"])
        if tag == "link" and a.get("href") and a.get("rel") in ("stylesheet", "icon", "preload", "manifest", "prefetch", "preconnect", "dns-prefetch"):
            self.loads.append(a["href"])
        if tag == "script" and not a.get("src"):
            self._in_script = a.get("type", "")

    def handle_data(self, data):
        if self._in_script is not None and data.strip():
            self.inline_scripts.append(self._in_script)

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = None


# --- Fichiers tiers ------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(VENDOR_FILES))
def test_vendored_files_match_pinned_hashes(name):
    digest = base64.b64encode(hashlib.sha384((VENDOR_DIR / name).read_bytes()).digest()).decode()
    assert f"sha384-{digest}" == VENDOR_FILES[name]


# --- Analyse statique des pages --------------------------------------------------


def test_every_page_has_the_strict_csp_and_no_third_party(site):
    for page in pages(site):
        doc = Inspector()
        doc.feed(page.read_text(encoding="utf-8"))
        name = page.relative_to(site)
        assert doc.csp == [CONTENT_SECURITY_POLICY], name
        assert "script-src 'self'" in CONTENT_SECURITY_POLICY and "unsafe-inline' ;" not in CONTENT_SECURITY_POLICY
        assert all(t == "application/json" for t in doc.inline_scripts), f"{name} : script exécutable en ligne"
        assert doc.handlers == [], f"{name} : gestionnaires en ligne {doc.handlers}"
        external = [u for u in doc.loads if re.match(r"^(https?:)?//", u)]
        assert external == [], f"{name} : ressources externes {external}"
        for u in doc.loads:  # toute ressource locale référencée existe bien
            assert (page.parent / u).resolve().exists(), f"{name} : fichier manquant {u}"


def test_css_and_own_scripts_never_reach_out(site):
    css = (site / "assets" / "site.css").read_text(encoding="utf-8")
    assert re.findall(r"url\(\s*['\"]?(https?:)?//", css) == []
    assert "@import" not in css
    for name in OWN_JS:
        code = (site / "assets" / name).read_text(encoding="utf-8")
        for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource", "document.cookie", "http://", "https://"):
            assert forbidden not in code, f"{name} contient {forbidden}"


def test_only_storage_is_the_theme_key():
    # Une seule écriture de stockage dans tout le code maison : la clé « theme ».
    code = "".join((Path("dashboard/templates") / n).read_text(encoding="utf-8") for n in OWN_JS)
    assert re.findall(r"(?:localStorage|sessionStorage)\.setItem\(\s*\"([^\"]+)\"", code) == ["theme"]
    assert "sessionStorage" not in code and "indexedDB" not in code


# --- En conditions réelles, réseau externe coupé --------------------------------------


needs_chrome = pytest.mark.skipif(CHROME is None, reason="Chrome/Chromium introuvable")


@needs_chrome
def test_pages_work_offline_without_cookie_or_external_request(site, tmp_path):
    for page in pages(site):
        probe = run_page(instrument(page, "window.__extra=document.fonts.check('16px Inter')+'|'+document.fonts.status;"), tmp_path, offline=True)
        name = page.relative_to(site)
        assert probe["errors"] == [], name
        assert probe["csp"] == [], f"{name} : violations de CSP {probe['csp']}"
        assert probe["external"] == [], f"{name} : requêtes externes {probe['external']}"
        assert probe["cookie"] == "" and probe["storage"] == [], name
        assert probe["extra"].startswith("true"), f"{name} : police Inter non chargée localement"


@needs_chrome
def test_theme_choice_is_the_only_thing_stored(site, tmp_path):
    index = site / "index.html"
    dark = run_page(instrument(index, "document.querySelector('.theme-switch [data-mode=dark]').click();"), tmp_path, offline=True)
    assert dark["storage"] == ["theme"] and dark["cookie"] == ""
    back = run_page(instrument(index, "document.querySelector('.theme-switch [data-mode=dark]').click();"
                                      "document.querySelector('.theme-switch [data-mode=auto]').click();"), tmp_path, offline=True)
    assert back["storage"] == []  # revenir à « auto » efface la préférence
