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
from tests.browser import instrument, needs_chrome, run_page

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


# --- Pied de page, mentions légales, liens (lot C) ------------------------------------

from dashboard.build import offers_csv, source_version  # noqa: E402
from dashboard.config import AUTHOR, GITHUB_URL, HOST, LEGAL_UPDATED, LINKEDIN_URL  # noqa: E402


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])


def parse_links(page: Path) -> Links:
    p = Links()
    p.feed(page.read_text(encoding="utf-8"))
    return p


def test_footer_is_on_every_page_with_all_links(site):
    for page in pages(site):
        html = page.read_text(encoding="utf-8")
        hrefs = parse_links(page).hrefs
        name = page.relative_to(site)
        for needed in (GITHUB_URL, LINKEDIN_URL):
            assert needed in hrefs, f"{name} : lien {needed} absent"
        assert any(h.endswith("stats.json") for h in hrefs) and any(h.endswith("offres-esim.csv") for h in hrefs), name
        assert not any("NOTES_" + "IA" in h for h in hrefs), f"{name} : lien vers le journal (privé)"
        assert "Python, pandas, Chart.js, GitHub Actions" in html and 'id="f-methode"' not in html, name
        assert "/commit/" not in html, f"{name} : numéro de commit affiché"
        assert any(h.endswith("mentions-legales.html#cookies") for h in hrefs) and "#haut" in hrefs, name
        assert f"réalisé par {AUTHOR}" in html and "Aucun cookie · aucun traceur" in html, name
        assert "Outil non officiel, inspiré de l'identité visuelle de mybestsim.com" in html, name


def test_no_email_or_phone_number_anywhere(site):
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    phone = re.compile(r"(?:\+33|\b0[1-9])(?:[ .-]?\d{2}){4}\b|\+1[ (]*\d{3}")
    for page in pages(site):
        text = page.read_text(encoding="utf-8")
        assert not email.search(text), f"{page.name} : adresse e-mail"
        assert not phone.search(text), f"{page.name} : numéro de téléphone"


def test_internal_links_and_anchors_resolve(site):
    parsed = {p.resolve(): parse_links(p) for p in pages(site)}
    for page, links in parsed.items():
        for href in links.hrefs:
            if re.match(r"^(https?:|mailto:|tel:)", href):
                continue
            path, _, anchor = href.partition("#")
            target = (page.parent / path).resolve() if path else page
            assert target.exists(), f"{page.name} : lien cassé {href}"
            if anchor and target.suffix == ".html":
                ids = parsed[target].ids if target in parsed else parse_links(target).ids
                assert anchor in ids, f"{page.name} : ancre absente {href}"


def test_legal_page_content(site):
    html = (site / "mentions-legales.html").read_text(encoding="utf-8")
    for section in ("editeur", "directeur", "hebergeur", "propriete", "donnees", "cookies"):
        assert f'id="{section}"' in html
    assert HOST["address"] in html and "6-III-2" in html and "licence MIT" in html
    assert "<code>theme</code>" in html and "<code>localStorage</code>" in html
    assert "16 octobre 2026" in html and LEGAL_UPDATED == "2026-10-16"
    assert "Aucune donnée personnelle n'est collectée" in html


def test_version_comes_from_ci_variables(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "someone/repo")
    monkeypatch.setenv("GITHUB_SHA", "0123456789abcdef")
    assert source_version() == {"repo_url": "https://github.com/someone/repo", "sha": "0123456789abcdef", "short_sha": "0123456"}


def test_full_csv_export_is_written_and_reimportable(site, tmp_path):
    from dashboard.loader import load_providers
    from dashboard.validation import validate

    data = tmp_path / "data"
    data.mkdir()
    (data / "export.csv").write_bytes((site / "offres-esim.csv").read_bytes())
    validated = validate(load_providers(data).rows)
    assert validated.anomalies == [] and len(validated.clean) == 8


@needs_chrome
def test_clear_theme_button_on_legal_page(site, tmp_path):
    action = ("document.querySelector('.theme-switch [data-mode=dark]').click();var before=Object.keys(localStorage).join(',');"
              "document.getElementById('clear-theme').click();window.__extra=before+'|'+Object.keys(localStorage).length+'|'+"
              "(document.documentElement.getAttribute('data-theme')||'auto');")
    probe = run_page(instrument(site / "mentions-legales.html", action), tmp_path, offline=True)
    assert probe["extra"] == "theme|0|auto" and probe["csp"] == []


# --- Contrastes sur toutes les pages (vérification finale) ------------------------------


@needs_chrome
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_text_contrast_on_every_page(site, theme, tmp_path):
    import json

    from tests.test_render import CONTRAST_AUDIT

    action = f"document.querySelector('.theme-switch button[data-mode={theme}]').click();setTimeout(function(){{{CONTRAST_AUDIT}}},400);"
    for page in pages(site):
        probe = run_page(instrument(page, action), tmp_path)
        audit = json.loads(probe["extra"])
        assert audit["checked"] > 20, (page.name, audit)
        assert audit["n"] == 0, (page.relative_to(site), theme, audit["fails"])


def test_readme_mentions_test_data_and_its_images_exist():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "données de test fournies par MyBestSim pour le recrutement" in readme
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
    assert len(images) == 3 and all(Path(i).exists() for i in images)


def test_site_presents_the_product_not_its_making(site):
    assert not (site / "comment-c-est-construit.html").exists()
    for page in pages(site):
        html = page.read_text(encoding="utf-8")
        for banned in ("NOTES_" + "IA", "Journal de construction", "comment-c-est-construit", "Clau" + "de"):
            assert banned not in html, f"{page.name} : « {banned} »"
        assert not re.search(r"\bIA\b", html), f"{page.name} : « IA »"


def test_no_local_path_or_email_in_tracked_files():
    """Garde-fou sur le contenu public du dépôt : aucun chemin de la machine de développement,
    aucune adresse e-mail. (Volontairement générique : aucun nom n'est écrit ici en clair.)"""
    import subprocess

    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split()
    # Classes d'un caractère ([s], [r], [o]) : le motif détecte les dossiers personnels et temporaires
    # (macOS, Linux, Windows) sans se détecter lui-même.
    local_path = re.compile(r"/U[s]ers/[^/\s]+|/p[r]ivate/(?:tmp|var)/|/h[o]me/[a-z][\w-]*/|[A-Z]:\\U[s]ers\\")
    email = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}")
    for name in files:
        path = Path(name)
        if not path.exists() or path.suffix in (".woff2", ".png", ".bundle") or path.parts[:2] == ("dashboard", "vendor"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.parts[0] == "docs" and path.parts[1:2] == ("assets",) and "vendor" in path.parts:
            continue
        assert not local_path.search(text), f"{name} : chemin local"
        assert not email.search(text), f"{name} : adresse e-mail"
