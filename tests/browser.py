"""Pilotage de Chrome headless pour les tests : sondes chargées comme fichiers (CSP stricte)."""

import json
import re
import shutil
import subprocess
from pathlib import Path

MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME = next(
    (c for c in (shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser"),
                 MAC_CHROME if Path(MAC_CHROME).exists() else None) if c),
    None,
)

# Sondes de test, chargées comme fichiers (la CSP du site interdit tout script en ligne) :
# erreurs JS, violations de CSP, requêtes sortantes, cookies et stockage local.
CATCH = (
    "window.__errs=[];window.__csp=[];addEventListener('error',function(e){__errs.push(String(e.message||e))});"
    "document.addEventListener('securitypolicyviolation',function(e){__csp.push(e.violatedDirective+' '+e.blockedURI)});"
)
PROBE = (
    "addEventListener('load',function(){setTimeout(function(){__ACTION__},300);setTimeout(function(){var d=document.documentElement;"
    "var q=function(id){var e=document.getElementById(id);return e?e.textContent:null};"
    "var ext=performance.getEntriesByType('resource').map(function(r){return r.name}).filter(function(u){return !/^(file|blob|data):/.test(u)});"
    "var st=[];try{st=Object.keys(localStorage)}catch(e){}"
    "var p=document.createElement('pre');p.id='PROBE';p.textContent=JSON.stringify({ready:d.dataset.ready||null,"
    "errors:__errs,csp:__csp,external:ext,cookie:document.cookie,storage:st,overflow:d.scrollWidth>d.clientWidth,"
    "kpis:document.querySelectorAll('#kpis .kpi').length,hero:q('hero-kpis'),result:q('fb-result'),"
    "empty:document.body.classList.contains('is-empty'),search:location.search,extra:window.__extra||null});"
    "document.body.appendChild(p)},1500)})"
)


def instrument(html_path: Path, action: str = "", name: str = "probe.html") -> Path:
    """Copie de la page avec les sondes (fichiers dans assets/) ; renvoie son chemin."""
    assets = html_path.parent / "assets"
    (assets / "_catch.js").write_text(CATCH, encoding="utf-8")
    (assets / "_probe.js").write_text(PROBE.replace("__ACTION__", action), encoding="utf-8")
    prefix = "../" * (len(html_path.relative_to(html_path.parent).parts) - 1)
    html = html_path.read_text(encoding="utf-8")
    html = html.replace("<head>", f'<head>\n<script src="{prefix}assets/_catch.js"></script>', 1)
    html = html.replace("</body>", f'<script src="{prefix}assets/_probe.js"></script>\n</body>', 1)
    page = html_path.parent / name
    page.write_text(html, encoding="utf-8")
    return page


def run_page(page: Path, tmp_path: Path, width: int = 1280, query: str = "", offline: bool = False) -> dict:
    """Ouvre la page instrumentée et renvoie le rapport de la sonde."""
    args = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={tmp_path / 'profile'}",
            f"--window-size={width},900", "--virtual-time-budget=8000"]
    if offline:  # toute résolution DNS échoue : la moindre ressource externe casserait la page
        args.append("--host-resolver-rules=MAP * ~NOTFOUND")
    done = subprocess.run(args + ["--dump-dom", page.as_uri() + query], capture_output=True, text=True, timeout=120)
    m = re.search(r'<pre id="PROBE">(.*?)</pre>', done.stdout, re.S)
    assert m, "la page n'a pas terminé son chargement :\n" + done.stderr[-2000:]
    return json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))
