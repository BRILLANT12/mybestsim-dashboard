// Tableau de bord : rendu, filtres, graphiques, comparateur.
// Les indicateurs sont calculés par analytics.js (même règles que Python, vérifié par les tests).
(function () {
  "use strict";
  var A = window.Analytics;
  var S = JSON.parse(document.getElementById("stats-data").textContent);
  var OFFERS = JSON.parse(document.getElementById("offers-data").textContent);
  var REGION_CODES = Object.keys(S.coverage.region_codes_note);
  var ISO = {};
  S.coverage.countries_price_per_gb.forEach(function (c) { ISO[c.code] = c.iso_numeric; });
  var ALL = A.decodeOffers(OFFERS, REGION_CODES);
  var REDUCED = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  // ---------- Format français ----------
  var nfCache = {};
  function nf(d) { return nfCache[d] || (nfCache[d] = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d })); }
  function num(v, d) { return v == null ? "—" : nf(d || 0).format(v); }
  function eur(v, d) { return v == null ? "—" : nf(d == null ? 2 : d).format(v) + " €"; }
  function pct(v, d) { return v == null ? "—" : nf(d || 0).format(v * 100) + " %"; }
  function gb(v, d) { return v == null ? "—" : nf(d == null ? 2 : d).format(v) + " Go"; }
  function signedPct(v, d) { return v == null ? "—" : (v >= 0 ? "+" : "−") + pct(Math.abs(v), d); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function $(id) { return document.getElementById(id); }
  function plural(n, one, many) { return n > 1 ? many : one; }
  function icon(name) { return '<svg class="icon" aria-hidden="true"><use href="#i-' + name + '"/></svg>'; }
  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  // ---------- Compteurs animés (désactivés si l'utilisateur limite les animations) ----------
  var FORMATS = {
    int: function (v) { return num(Math.round(v)); },
    eur: function (v) { return eur(v); },
    gb: function (v) { return gb(v); },
    pct: function (v) { return pct(v); }
  };
  function counter(value, fmt) {
    return '<span data-count="' + (value == null ? "" : value) + '" data-fmt="' + fmt + '">' + FORMATS[fmt](value) + "</span>";
  }
  function countUp(el, to, format) {
    if (REDUCED || !isFinite(to)) { el.textContent = format(isFinite(to) ? to : null); return; }
    var start = performance.now(), dur = 900, done = false;
    function frame(t) {
      if (done) return;
      var k = Math.min(1, (t - start) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = format(k < 1 ? to * e : to);
      if (k < 1) requestAnimationFrame(frame); else done = true;
    }
    requestAnimationFrame(frame);
    // Filet de sécurité : si le navigateur suspend les animations (onglet en arrière-plan,
    // impression, capture), la valeur finale exacte est tout de même affichée.
    setTimeout(function () { done = true; el.textContent = format(to); }, dur + 100);
  }
  function animateCounters(root) {
    root.querySelectorAll("[data-count]").forEach(function (el) {
      if (el.dataset.count === "") return;
      countUp(el, parseFloat(el.dataset.count), FORMATS[el.dataset.fmt]);
    });
  }

  // ---------- Micro-visualisations (SVG) ----------
  function sparkBars(values) {
    if (!values.length) return "";
    var w = 240, h = 36, n = values.length, max = Math.max.apply(null, values) || 1, gap = 2, bw = (w - gap * (n - 1)) / n;
    return '<svg viewBox="0 0 ' + w + " " + h + '" width="100%" height="' + h + '" preserveAspectRatio="none" aria-hidden="true">' + values.map(function (v, i) {
      var bh = Math.max(2, (v / max) * h);
      return '<rect x="' + (i * (bw + gap)).toFixed(1) + '" y="' + (h - bh).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + bh.toFixed(1) + '" rx="' + Math.min(2, bw / 2).toFixed(1) + '" fill="currentColor" opacity="0.9"/>';
    }).join("") + "</svg>";
  }
  function sparkLine(values) {
    var w = 240, h = 36, pad = 4, n = values.length, max = Math.max.apply(null, values), min = Math.min.apply(null, values);
    var pts = values.map(function (v, i) { return [pad + (i * (w - 2 * pad)) / Math.max(1, n - 1), pad + (1 - (v - min) / ((max - min) || 1)) * (h - 2 * pad)]; });
    var d = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
    var area = d + " L" + pts[n - 1][0].toFixed(1) + " " + h + " L" + pts[0][0].toFixed(1) + " " + h + " Z";
    return '<svg viewBox="0 0 ' + w + " " + h + '" width="100%" height="' + h + '" preserveAspectRatio="none" aria-hidden="true">' +
      '<path d="' + area + '" fill="currentColor" opacity="0.12"/><path d="' + d + '" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>';
  }
  function progress(share, color) {
    var w = Math.max(0, Math.min(100, (share || 0) * 100)).toFixed(1);
    return '<div class="progress" aria-hidden="true"><span style="width:' + w + "%" + (color ? ";background:" + color : "") + '"></span></div>';
  }
  function rangeStrip(min, median, mean, max) {
    // Échelle logarithmique : les prix vont de quelques euros à plus de 150 €.
    var w = 240, lo = Math.log(min), hi = Math.log(max);
    var x = function (v) { return (6 + ((Math.log(v) - lo) / ((hi - lo) || 1)) * (w - 12)).toFixed(1); };
    return '<svg viewBox="0 0 ' + w + ' 26" width="100%" height="26" aria-hidden="true">' +
      '<line x1="6" x2="' + (w - 6) + '" y1="13" y2="13" stroke="currentColor" stroke-width="4" stroke-linecap="round" opacity="0.18"/>' +
      '<circle cx="' + x(min) + '" cy="13" r="5" fill="currentColor"/><circle cx="' + x(max) + '" cy="13" r="5" fill="currentColor"/>' +
      '<line x1="' + x(median) + '" x2="' + x(median) + '" y1="3" y2="23" stroke="currentColor" stroke-width="2.5"/>' +
      '<line x1="' + x(mean) + '" x2="' + x(mean) + '" y1="3" y2="23" stroke="var(--series-2)" stroke-width="2.5"/></svg>';
  }

  function luminance(hex) {
    var n = parseInt(hex.slice(1), 16), c = [n >> 16 & 255, n >> 8 & 255, n & 255].map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function inkOn(hex) { // blanc ou marine : celui qui contraste le plus avec le fond (WCAG)
    var l = luminance(hex), onWhite = 1.05 / (l + 0.05), onNavy = (l + 0.05) / (luminance("#0b1630") + 0.05);
    return onWhite >= onNavy ? "#ffffff" : "#0b1630";
  }
  // ---------- Tableaux ----------
  function table(el, cols, rows, opts) {
    opts = opts || {};
    var caption = el.querySelector("caption");
    var head = "<thead><tr>" + cols.map(function (c, k) {
      var cls = c.n ? ' class="n"' : "";
      return opts.sortable
        ? "<th" + cls + ' scope="col" aria-sort="none" data-k="' + k + '"><button type="button">' + c.label + "</button></th>"
        : "<th" + cls + ' scope="col">' + c.label + "</th>";
    }).join("") + "</tr></thead>";
    function body(list) {
      return "<tbody>" + list.map(function (row) {
        return "<tr" + (opts.rowClass ? ' class="' + opts.rowClass(row) + '"' : "") + ">" + cols.map(function (c) {
          return "<td" + (c.n ? ' class="n"' : c.wrap ? ' class="wrap-cell"' : c.wrapSm ? ' class="wrap-sm"' : "") + ">" + c.fmt(row) + "</td>";
        }).join("") + "</tr>";
      }).join("") + "</tbody>";
    }
    el.innerHTML = (caption ? caption.outerHTML : "") + head + body(rows);
    if (!opts.sortable) return;
    el.querySelectorAll("th").forEach(function (th) {
      th.querySelector("button").addEventListener("click", function () {
        var c = cols[+th.dataset.k];
        var dir = th.getAttribute("aria-sort") === "descending" ? "ascending" : "descending";
        el.querySelectorAll("th").forEach(function (o) { o.setAttribute("aria-sort", "none"); });
        th.setAttribute("aria-sort", dir);
        var sorted = rows.slice().sort(function (a, b) {
          var x = c.key(a), y = c.key(b);
          if (x == null) return 1;
          if (y == null) return -1;
          var r = typeof x === "string" ? x.localeCompare(y, "fr") : x - y;
          return dir === "ascending" ? r : -r;
        });
        el.querySelector("tbody").outerHTML = body(sorted);
      });
    });
  }

  // ---------- Vue : indicateurs recalculés par le moteur (identique à Python, vérifié par les tests) ----------
  var state = { rows: ALL };
  var current = null, byPpg = [], podium = [];

  var genText = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeStyle: "short", timeZone: "Europe/Paris" }).format(new Date(S.meta.generated_at));

  function renderStatic() {
    var Q = S.anomalies, level = Q.errors ? "crit" : Q.warnings ? "warn" : "ok";
    $("hero-date").textContent = "Mis à jour le " + genText + " (heure de Paris)";
    var q = $("hero-quality");
    q.className = "chip" + (level === "ok" ? "" : " " + level);
    q.innerHTML = '<span class="dot" aria-hidden="true"></span>' + (level === "ok"
      ? "Données vérifiées · aucune anomalie"
      : num(Q.errors) + " " + plural(Q.errors, "erreur", "erreurs") + " · " + num(Q.warnings) + " " + plural(Q.warnings, "avertissement", "avertissements"));
    var fills = { threshold: eur(S.headline.expensive.threshold, 0), "mean-gb": gb(S.headline.data.mean_gb), "median-gb": gb(S.headline.data.median_gb, 0) };
    document.querySelectorAll("[data-fill]").forEach(function (el) { el.textContent = fills[el.dataset.fill]; });
    renderInsights();
    renderQuality();
    var names = {};
    ALL.forEach(function (r) { names[r.country_code] = r.country_name; });
    $("zone-hypothesis").innerHTML = S.coverage.zones.map(function (z) {
      return "<li><b>" + esc(z.name) + "</b> (" + esc(z.code) + ") : " + (z.countries === "*" ? "tous les pays" :
        z.countries.map(function (c) { return esc(names[c] || c); }).join(", ")) + ".</li>";
    }).join("");
  }

  function glass(ic, label, value, sub, micro) {
    return '<div class="glass"><div class="glass-top"><span class="ico">' + icon(ic) + "</span>" + label + '</div><div class="glass-value">' + value +
      '</div><div class="glass-sub">' + sub + '</div><div class="micro">' + micro + "</div></div>";
  }
  function renderHero(V) {
    var H = V.headline, C = V.coverage, np = V.providers.length;
    $("hero-sub").textContent = (activeCount() ? "Sélection filtrée : " : "") + num(H.total_offers) + " " + plural(H.total_offers, "offre", "offres") + " de " + num(np) + " " + plural(np, "fournisseur", "fournisseurs") + ", couvrant " +
      num(C.countries_count) + " pays et " + num(C.regions_count) + " " + plural(C.regions_count, "zone régionale", "zones régionales") + ".";
    var hist = V.pricing.histogram.bins.map(function (b) { return b.offers; });
    var tiers = V.distributions.data_tiers.filter(function (t) { return t.label !== "Illimité"; }).map(function (t) { return t.offers; });
    $("hero-kpis").innerHTML = [
      glass("sim", "Cartes eSIM au catalogue", counter(H.total_offers, "int"), "offres valides · <b>" + num(np) + "</b> fournisseurs",
        sparkBars(V.providers.map(function (p) { return p.offers; }))),
      glass("euro", "Prix moyen", counter(H.price.mean, "eur"), "médiane <b>" + eur(H.price.median) + "</b> · répartition des prix", sparkBars(hist)),
      glass("data", "Data moyenne par carte", counter(H.data.mean_gb, "gb"), "médiane <b>" + gb(H.data.median_gb, 0) + "</b> · hors <b>" +
        num(H.data.unlimited_count) + "</b> illimités", sparkBars(tiers))
    ].join("");
  }

  function kpi(ic, label, value, sub, micro, tag) {
    return '<article class="card kpi"><div class="kpi-top"><span class="kpi-ico">' + icon(ic) + "</span>" + label + (tag ? '<span class="tag">' + tag + "</span>" : "") +
      '</div><div class="kpi-value">' + value + '</div><div class="kpi-sub">' + sub + '</div><div class="micro">' + (micro || "") + "</div></article>";
  }
  function ties(ext) {
    if (!ext) return "—";
    if (ext.count === 1) return esc(ext.products[0].provider) + " · " + esc(ext.products[0].product_name);
    return num(ext.count) + " ex æquo : " + ext.by_provider.map(function (x) { return esc(x.provider) + (x.count > 1 ? " (×" + x.count + ")" : ""); }).join(", ");
  }
  function renderKpis(V) {
    var H = V.headline, P = V.pricing, D = V.distributions, e = H.expensive, r = H.price_range;
    var net = {}, top = {};
    D.network.forEach(function (x) { net[x.value] = x; });
    D.top_up.forEach(function (x) { top[x.value] = x; });
    var s5 = net["5G"] ? net["5G"].share : 0, s4 = net["4G"] ? net["4G"].share : 0, sTop = top.oui ? top.oui.share : 0;
    var tierPpg = P.by_data_tier.map(function (t) { return t.price_per_gb; });
    var l4l = D.network_like_for_like_5g_vs_4g, l4lTop = D.top_up_like_for_like_yes_vs_no;
    var expShare = e.count ? e.unlimited_count / e.count : 0;
    $("kpis").innerHTML = [
      kpi("tag", "Produits à plus de " + eur(e.threshold, 0), counter(e.count, "int"),
        "prix <b>strictement supérieur</b> à " + eur(e.threshold, 0) + " · dont <b>" + num(e.unlimited_count) + "</b> illimités",
        e.count ? progress(expShare, "var(--series-2)") + '<div class="micro-legend"><span>Part d\'illimités</span><span>' + pct(expShare) + "</span></div>" : ""),
      kpi("range", "Fourchette de prix", eur(r.min && r.min.price) + " <small>→</small> " + eur(r.max && r.max.price),
        "<b>Min</b> : " + ties(r.min) + "<br><b>Max</b> : " + ties(r.max),
        r.min ? rangeStrip(r.min.price, H.price.median, H.price.mean, r.max.price) +
          '<div class="micro-legend"><span><span class="swatch" style="background:var(--series-1)"></span>médiane ' + eur(H.price.median) +
          '</span><span><span class="swatch" style="background:var(--series-2)"></span>moyenne ' + eur(H.price.mean) + "</span></div>" : ""),
      kpi("gauge", "Prix moyen au Go", counter(P.price_per_gb, "eur") + " <small>/ Go</small>",
        "médiane des forfaits : <b>" + eur(P.price_per_gb_median_of_ratios) + " / Go</b>",
        tierPpg.length > 1 ? sparkLine(tierPpg) + '<div class="micro-legend"><span>' + gb(P.by_data_tier[0].data_gb, 0) + " : " + eur(tierPpg[0]) + "/Go</span><span>" +
          gb(P.by_data_tier[tierPpg.length - 1].data_gb, 0) + " : " + eur(tierPpg[tierPpg.length - 1]) + "/Go</span></div>" : "", "Bonus"),
      kpi("infinity", "Forfaits illimités", counter(H.data.unlimited_count, "int"),
        pct(H.data.unlimited_share) + " du catalogue · <b>" + eur(H.price.mean_unlimited) + "</b> en moyenne",
        progress(H.data.unlimited_share, "var(--series-2)") + '<div class="micro-legend"><span>Part du catalogue</span><span>' + pct(H.data.unlimited_share, 1) + "</span></div>", "Bonus"),
      kpi("signal", "Offres 5G", counter(s5, "pct"),
        num(net["5G"] ? net["5G"].offers : 0) + " offres · <b>" + (l4l == null ? "—" : signedPct(l4l - 1, 1)) + "</b> à offre égale vs 4G",
        progress(s5) + '<div class="micro-legend"><span>4G ' + pct(s4) + "</span><span>5G " + pct(s5) + "</span></div>", "Bonus"),
      kpi("refresh", "Recharge possible", counter(sTop, "pct"),
        num(top.oui ? top.oui.offers : 0) + " offres · <b>" + (l4lTop == null ? "—" : signedPct(l4lTop - 1, 1)) + "</b> à offre égale",
        progress(sTop) + '<div class="micro-legend"><span>Rechargeables</span><span>' + pct(sTop, 1) + "</span></div>", "Bonus")
    ].join("");
    $("ppg-explain").innerHTML = "<b>Pourquoi deux prix au Go ?</b> " + eur(P.price_per_gb) + "/Go divise le total des prix par le total des Go : c'est ce que coûte réellement un Go sur le catalogue. " +
      "La médiane des forfaits (" + eur(P.price_per_gb_median_of_ratios) + "/Go) est plus élevée, car les petits forfaits, chers au Go, y comptent autant que les gros.";
  }

  var INSIGHT_ICONS = { volume_discount: "trend", power_law: "data", "5g_premium": "signal", cheapest_provider: "trophy", expensive_mix: "tag" };
  function renderInsights() {
    var hero = S.insights.filter(function (i) { return i.highlight; })[0];
    var html = "";
    if (hero) {
      var big = hero.values && hero.values.count != null ? num(hero.values.count) : "";
      html += '<article class="insight hero-insight"><div class="big" aria-hidden="true">' + big + '</div><div><div class="kicker">Constat clé</div><h3>' +
        esc(hero.title) + "</h3></div><p>" + esc(hero.text) + "</p></article>";
    }
    html += S.insights.filter(function (i) { return !i.highlight; }).map(function (i) {
      return '<article class="insight"><div class="ico">' + icon(INSIGHT_ICONS[i.id] || "info") + "</div><h3>" + esc(i.title) + "</h3><p>" + esc(i.text) + "</p></article>";
    }).join("");
    $("insights").innerHTML = html;
  }

  var PODIUM_MIN_OFFERS = 10;
  function renderProviders(V) {
    byPpg = V.providers.filter(function (p) { return p.price_per_gb != null; }).sort(function (a, b) { return a.price_per_gb - b.price_per_gb; });
    // Podium réservé aux fournisseurs ayant assez de forfaits limités : sur 3 offres, un classement ne veut rien dire.
    var eligible = byPpg.filter(function (p) { return p.offers - p.unlimited >= PODIUM_MIN_OFFERS; });
    podium = eligible.slice(0, 3).map(function (p) { return p.provider; });
    var tied = eligible.length >= 3 && eligible[2].price_per_gb / eligible[0].price_per_gb - 1 < 0.01;
    var excluded = byPpg.length - eligible.length;
    $("ppg-provider-sub").textContent = !byPpg.length ? "Aucun forfait à volume limité dans la sélection."
      : !podium.length ? "Échantillon trop petit pour un classement (moins de " + PODIUM_MIN_OFFERS + " forfaits limités par fournisseur)."
      : (tied ? "Podium : " + podium.join(", ") + ", quasiment à égalité (moins de 1 % d'écart)." : "Podium du moins cher au Go : " + podium.join(", ") + ".") +
        (excluded ? " " + num(excluded) + " " + plural(excluded, "fournisseur exclu", "fournisseurs exclus") + " du podium (moins de " + PODIUM_MIN_OFFERS + " forfaits limités)." : "");
    var rank = function (name) { return podium.indexOf(name); };
    var maxOffers = Math.max.apply(null, V.providers.map(function (p) { return p.offers; }).concat([1]));
    table($("providers-table"), [
      { label: "Fournisseur", key: function (x) { return x.provider; }, fmt: function (x) {
        var k = rank(x.provider), page = (S.provider_pages || {})[x.provider];
        return (k >= 0 ? '<span class="rank" title="Podium du prix au Go">' + (k + 1) + "</span>" : "") +
          (page ? '<a href="' + esc(page) + '" title="Voir la fiche de ' + esc(x.provider) + '">' + esc(x.provider) + "</a>" : esc(x.provider)); } },
      { label: "Offres", n: true, key: function (x) { return x.offers; }, fmt: function (x) { return '<span class="bar-cell"><i style="width:' + Math.round((x.offers / maxOffers) * 56) + 'px" aria-hidden="true"></i>' + num(x.offers) + "</span>"; } },
      { label: "Part", n: true, key: function (x) { return x.share; }, fmt: function (x) { return pct(x.share, 1); } },
      { label: "Prix moyen", n: true, key: function (x) { return x.mean_price; }, fmt: function (x) { return eur(x.mean_price); } },
      { label: "Prix min", n: true, key: function (x) { return x.min_price; }, fmt: function (x) { return eur(x.min_price); } },
      { label: "Data moy.", n: true, key: function (x) { return x.mean_data_gb; }, fmt: function (x) { return gb(x.mean_data_gb, 1); } },
      { label: "Illimités", n: true, key: function (x) { return x.unlimited; }, fmt: function (x) { return num(x.unlimited); } },
      { label: "€ / Go", n: true, key: function (x) { return x.price_per_gb; }, fmt: function (x) { return eur(x.price_per_gb, 3); } },
      { label: "Indice prix", n: true, key: function (x) { return x.price_index; }, fmt: function (x) { return num(x.price_index, 1); } },
      { label: "5G", n: true, key: function (x) { return x.share_5g; }, fmt: function (x) { return pct(x.share_5g); } },
      { label: "Recharge", n: true, key: function (x) { return x.share_top_up; }, fmt: function (x) { return pct(x.share_top_up); } },
      { label: "Destinations", n: true, key: function (x) { return x.destinations; }, fmt: function (x) { return num(x.destinations); } }
    ], V.providers, { sortable: true, rowClass: function (x) { return rank(x.provider) >= 0 ? "podium" : ""; } });
  }

  function split(el, title, items, labels, note) {
    var colors = ["var(--series-1)", "var(--series-2)"], inks = [inkOn(css("--series-1")), inkOn(css("--series-2"))], order = Object.keys(labels);
    var known = items.filter(function (x) { return labels[x.value]; }).sort(function (a, b) { return order.indexOf(a.value) - order.indexOf(b.value); });
    var other = items.filter(function (x) { return !labels[x.value]; });
    el.innerHTML = '<h3 style="font-size:14px">' + title + "</h3>" +
      (known.length ? '<div class="split" role="img" aria-label="' + esc(title + " : " + known.map(function (x) { return labels[x.value] + " " + pct(x.share); }).join(", ")) + '">' +
        known.map(function (x, k) { return '<span style="flex:' + x.offers + ";background:" + colors[k % 2] + ";color:" + inks[k % 2] + '">' + pct(x.share) + "</span>"; }).join("") + "</div>" : '<p class="sub">Aucune offre.</p>') +
      '<div class="split-legend">' + known.map(function (x, k) {
        return '<div><span class="swatch" style="background:' + colors[k % 2] + '"></span>' + esc(labels[x.value]) + " : <b>" + num(x.offers) + "</b> offres · " + eur(x.mean_price) + " en moyenne</div>";
      }).join("") + "</div>" +
      (other.length ? '<p class="sub">Autres valeurs : ' + other.map(function (x) { return esc(x.value) + " (" + num(x.offers) + ")"; }).join(", ") + "</p>" : "") +
      (note ? '<p class="callout">' + icon("scale") + "<span>" + note + "</span></p>" : "");
  }
  function renderPricing(V) {
    var P = V.pricing, D = V.distributions, H = V.headline;
    table($("table-ppg-tier"), [
      { label: "Volume", fmt: function (x) { return gb(x.data_gb, 0); } },
      { label: "Offres", n: true, fmt: function (x) { return num(x.offers); } },
      { label: "Prix moyen", n: true, fmt: function (x) { return eur(x.mean_price); } },
      { label: "€ / Go", n: true, fmt: function (x) { return eur(x.price_per_gb); } }
    ], P.by_data_tier);
    $("tiers-legend").innerHTML = '<span><span class="swatch" style="background:var(--series-1)"></span>Volume limité</span>' +
      '<span><span class="swatch" style="background:var(--series-2)"></span>Illimité : ' + num(H.data.unlimited_count) + " offres (" + pct(H.data.unlimited_share) + ")</span>";
    table($("table-tiers"), [
      { label: "Volume", fmt: function (x) { return esc(x.label); } },
      { label: "Offres", n: true, fmt: function (x) { return num(x.offers); } }
    ], D.data_tiers);
    var vp = {};
    P.by_validity.forEach(function (v) { vp[v.validity_days] = v.mean_price; });
    table($("table-validity"), [
      { label: "Durée", fmt: function (x) { return num(x.validity_days) + " jours"; } },
      { label: "Offres", n: true, fmt: function (x) { return num(x.offers); } },
      { label: "Part", n: true, fmt: function (x) { return pct(x.share, 1); } },
      { label: "Prix moyen", n: true, fmt: function (x) { return eur(vp[x.validity_days]); } }
    ], D.validity);
    var net = {};
    D.network.forEach(function (x) { net[x.value] = x; });
    var raw = net["5G"] && net["4G"] ? net["5G"].mean_price / net["4G"].mean_price - 1 : null;
    var l4l = D.network_like_for_like_5g_vs_4g, l4lTop = D.top_up_like_for_like_yes_vs_no;
    split($("split-network"), "Réseau 4G / 5G", D.network, { "4G": "4G", "5G": "5G" }, l4l == null ? "" :
      "<b>5G vs 4G :</b> " + (raw == null ? "" : signedPct(raw) + " en moyenne brute, mais ") + "<b>" + signedPct(l4l - 1, 1) +
      "</b> à volume et durée égaux. L'écart brut vient de la composition du catalogue (davantage de gros forfaits en 5G).");
    split($("split-topup"), "Recharge possible", D.top_up, { oui: "Rechargeable", non: "Non rechargeable" }, l4lTop == null ? "" :
      "<b>Surcoût de la recharge à offre égale :</b> " + signedPct(l4lTop - 1, 1) + ". L'option ne se paie pratiquement pas.");
  }

  function renderDestinations(V) {
    var C = V.coverage;
    $("coverage-lead").innerHTML = "<b>" + num(C.countries_count) + "</b> pays et <b>" + num(C.regions_count) + "</b> " +
      plural(C.regions_count, "zone régionale", "zones régionales") + " (Europe, Asie, Amérique du Nord, Monde), comptés séparément.";
    var cols = [
      { label: "Destination", fmt: function (x) { return esc(x.name) + ' <span class="zero">' + esc(x.code) + "</span>"; } },
      { label: "Offres", n: true, fmt: function (x) { return num(x.offers); } },
      { label: "Fournisseurs", n: true, fmt: function (x) { return num(x.providers); } },
      { label: "Dès", n: true, fmt: function (x) { return eur(x.min_price); } }
    ];
    table($("table-countries"), cols, C.top_countries);
    var ranked = C.countries_price_per_gb.filter(function (c) { return c.price_per_gb != null && c.offers >= 10; })
      .sort(function (a, b) { return a.price_per_gb - b.price_per_gb; });
    var ppgCols = [
      { label: "Pays", fmt: function (x) { return esc(x.name); } },
      { label: "€ / Go", n: true, fmt: function (x) { return eur(x.price_per_gb); } }
    ];
    table($("table-cheapest"), [{ label: "Moins chers", fmt: ppgCols[0].fmt }, ppgCols[1]], ranked.slice(0, 5));
    table($("table-dearest"), [{ label: "Plus chers", fmt: ppgCols[0].fmt }, ppgCols[1]], ranked.slice(-5).reverse());
    $("extremes-note").innerHTML = ranked.length > 1 ? icon("scale") + "<span>Écart de <b>" + pct(ranked[ranked.length - 1].price_per_gb / ranked[0].price_per_gb - 1) +
      "</b> entre " + esc(ranked[0].name) + " (" + eur(ranked[0].price_per_gb) + "/Go) et " + esc(ranked[ranked.length - 1].name) + " (" + eur(ranked[ranked.length - 1].price_per_gb) + "/Go).</span>" : "";
  }

  function renderQuality() {
    var Q = S.anomalies, level = Q.errors ? "crit" : Q.warnings ? "warn" : "ok";
    var title = level === "ok" ? "Aucune anomalie détectée"
      : num(Q.errors) + " " + plural(Q.errors, "erreur", "erreurs") + " · " + num(Q.warnings) + " " + plural(Q.warnings, "avertissement", "avertissements");
    $("quality-status").innerHTML = '<div class="status ' + level + '" role="status">' + icon(level === "ok" ? "check" : level === "warn" ? "alert" : "x") +
      "<div><strong>" + title + "</strong><span>" + num(Q.rows_read) + " lignes lues, " +
      (Q.rows_excluded ? num(Q.rows_excluded) + " " + plural(Q.rows_excluded, "exclue", "exclues") : "aucune exclue") + " des calculs, " +
      num(Q.checks.length) + " contrôles appliqués à chaque génération.</span></div></div>";
    var sev = function (s) { return '<span class="sev ' + s + '">' + (s === "erreur" ? "Erreur · exclue" : "Avertissement") + "</span>"; };
    table($("table-checks"), [
      { label: "Contrôle", wrapSm: true, fmt: function (x) { return esc(x.label); } },
      { label: "Niveau", fmt: function (x) { return sev(x.severity); } },
      { label: "Détectées", n: true, fmt: function (x) { return x.count ? '<span class="pos">' + num(x.count) + "</span>" : '<span class="ok-mark" aria-hidden="true">✓</span> <span class="zero">0</span>'; } }
    ], Q.checks.slice().sort(function (a, b) { return b.count - a.count; }));
    table($("table-files"), [
      { label: "Fichier", fmt: function (x) { return "<code>" + esc(x.file) + "</code>"; } },
      { label: "Lignes", n: true, fmt: function (x) { return num(x.rows); } },
      { label: "Statut", fmt: function (x) { return x.status === "ok" ? '<span class="ok-mark" aria-hidden="true">✓</span> lu' : '<span class="sev erreur">' + esc(x.status) + "</span>"; } }
    ], Q.files);
    if (Q.details.length) {
      var MAX = 300;
      $("details-card").hidden = false;
      $("details-sub").textContent = Q.details.length > MAX ? "Les " + num(MAX) + " premières sur " + num(Q.details.length) + " (liste complète dans stats.json)."
        : num(Q.details.length) + " " + plural(Q.details.length, "anomalie", "anomalies") + ", triées par fichier puis par ligne.";
      table($("table-details"), [
        { label: "Niveau", fmt: function (x) { return sev(x.severity); } },
        { label: "Fichier", fmt: function (x) { return "<code>" + esc(x.file) + "</code>"; } },
        { label: "Ligne", n: true, fmt: function (x) { return x.line == null ? "—" : num(x.line); } },
        { label: "SKU", fmt: function (x) { return esc(x.sku || "—"); } },
        { label: "Détail", wrap: true, fmt: function (x) { return esc(x.message); } }
      ], Q.details.slice(0, MAX));
    }
  }

  // ---------- Graphiques Chart.js ----------
  var charts = {};
  function chart(id, config) {
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart($(id), config);
  }
  function tooltipStyle() {
    return { backgroundColor: "#0b1b3a", titleColor: "#ffffff", bodyColor: "#dbe6f7", borderColor: "rgba(255,255,255,.14)", borderWidth: 1,
      padding: 10, cornerRadius: 10, displayColors: false, titleFont: { weight: "600" } };
  }
  function bar(id, labels, values, o) {
    o = o || {};
    var horizontal = !!o.horizontal;
    $(id).parentNode.style.height = (horizontal ? Math.max(160, labels.length * 26 + 44) : 240) + "px";
    var valueAxis = { beginAtZero: true, grid: { color: css("--grid"), drawTicks: false }, border: { display: false },
      ticks: { color: css("--muted"), padding: 8, callback: function (v) { return o.fmt ? o.fmt(v, true) : num(v); } } };
    var catAxis = { grid: { display: false }, border: { color: css("--axis") }, ticks: { color: css("--ink-2"), autoSkip: false, font: { weight: "500" } } };
    chart(id, {
      type: "bar",
      data: { labels: labels, datasets: [{ data: values, backgroundColor: o.colors || css("--series-1"), borderRadius: 4, borderSkipped: "start",
        maxBarThickness: horizontal ? 16 : 44, categoryPercentage: 0.82, barPercentage: 0.9 }] },
      options: {
        indexAxis: horizontal ? "y" : "x", maintainAspectRatio: false, animation: REDUCED || instant ? false : { duration: 450 },
        plugins: { legend: { display: false }, tooltip: Object.assign(tooltipStyle(), { callbacks: { label: function (c) { return o.fmt ? o.fmt(c.raw) : num(c.raw) + " offres"; } } }) },
        scales: horizontal ? { x: valueAxis, y: catAxis } : { x: catAxis, y: valueAxis }
      }
    });
  }
  var instant = false; // pas d'animation des graphiques pendant le filtrage : retour immédiat
  function drawCharts(V, noAnim) {
    instant = !!noAnim;
    if (typeof Chart === "undefined") { document.body.classList.add("no-chart"); return; }
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.font.size = 12;
    var s1 = css("--series-1"), s2 = css("--series-2"), muted = css("--series-muted");
    bar("chart-providers", V.providers.map(function (p) { return p.provider; }), V.providers.map(function (p) { return p.offers; }), { horizontal: true });
    $("ppg-provider-legend").innerHTML = podium.length ? '<span><span class="swatch" style="background:var(--series-1)"></span>Podium (moins chers au Go)</span>' +
      '<span><span class="swatch" style="background:var(--series-muted)"></span>Autres fournisseurs</span>' : "";
    bar("chart-ppg-provider", byPpg.map(function (p) { return p.provider; }), byPpg.map(function (p) { return p.price_per_gb; }), {
      horizontal: true, colors: byPpg.map(function (p) { return podium.indexOf(p.provider) >= 0 ? s1 : muted; }),
      fmt: function (v, axis) { return axis ? eur(v, 1) : eur(v, 3) + " / Go"; } });
    var T = V.pricing.by_data_tier, D = V.distributions;
    bar("chart-ppg-tier", T.map(function (t) { return gb(t.data_gb, 0); }), T.map(function (t) { return t.price_per_gb; }), {
      fmt: function (v, axis) { return axis ? eur(v, 0) : eur(v) + " / Go"; } });
    bar("chart-tiers", D.data_tiers.map(function (t) { return t.label; }), D.data_tiers.map(function (t) { return t.offers; }), {
      colors: D.data_tiers.map(function (t) { return t.label === "Illimité" ? s2 : s1; }) });
    bar("chart-validity", D.validity.map(function (v) { return num(v.validity_days) + " jours"; }), D.validity.map(function (v) { return v.offers; }));
    bar("chart-countries", V.coverage.top_countries.map(function (c) { return c.name; }), V.coverage.top_countries.map(function (c) { return c.offers; }), { horizontal: true });
    drawScatter(V);
    drawHistogram(V);
    drawMap(V);
  }

  // ---------- Filtres ----------
  var KEYS = ["provider", "place", "network", "top_up", "validity_days"];
  var URL_KEYS = { provider: "fournisseur", place: "destination", network: "reseau", top_up: "recharge", validity_days: "duree" };
  var filters = { provider: [], place: [], network: [], top_up: [], validity_days: [] };
  var LABELS = { network: "Réseau", top_up: "Recharge", validity_days: "Durée" };

  function activeCount() { return KEYS.reduce(function (n, k) { return n + (filters[k].length ? 1 : 0); }, 0); }
  function readUrl() {
    var q = new URLSearchParams(location.search);
    KEYS.forEach(function (k) {
      var raw = q.get(URL_KEYS[k]);
      filters[k] = raw ? raw.split(",").filter(Boolean).map(function (v) { return k === "validity_days" ? Number(v) : v; }) : [];
    });
  }
  function writeUrl() {
    var q = new URLSearchParams();
    KEYS.forEach(function (k) { if (filters[k].length) q.set(URL_KEYS[k], filters[k].join(",")); });
    var s = q.toString();
    try { history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash); } catch (e) {}
  }
  function counts(key) {
    var m = {};
    ALL.forEach(function (r) { var v = key === "place" ? r.country_code : r[key]; m[v] = (m[v] || 0) + 1; });
    return m;
  }

  // Menus déroulants à cases à cocher (fournisseur, destination)
  function buildDropdown(key, groups) {
    var panel = $("dd-" + key), btn = $("dd-" + key + "-btn");
    panel.innerHTML = '<input class="dd-search" type="search" placeholder="Rechercher…" aria-label="Rechercher dans la liste">' +
      '<div class="dd-list">' + groups.map(function (g) {
        return (g.title ? "<h4>" + esc(g.title) + "</h4>" : "") + g.items.map(function (it) {
          return '<label data-text="' + esc((it.label + " " + it.value).toLowerCase()) + '"><input type="checkbox" value="' + esc(it.value) + '">' +
            esc(it.label) + '<span class="n">' + num(it.count) + "</span></label>";
        }).join("");
      }).join("") + "</div>" +
      '<div class="dd-foot"><button class="btn ghost" type="button" data-clear>Tout effacer</button><button class="btn primary" type="button" data-close>OK</button></div>';
    var search = panel.querySelector(".dd-search");
    search.addEventListener("input", function () {
      var t = search.value.trim().toLowerCase();
      panel.querySelectorAll(".dd-list label").forEach(function (l) { l.hidden = t && l.dataset.text.indexOf(t) === -1; });
    });
    panel.addEventListener("change", function (e) {
      if (!e.target.matches("input[type=checkbox]")) return;
      filters[key] = Array.prototype.filter.call(panel.querySelectorAll("input[type=checkbox]"), function (c) { return c.checked; }).map(function (c) { return c.value; });
      apply();
    });
    panel.querySelector("[data-clear]").addEventListener("click", function () { filters[key] = []; apply(); });
    panel.querySelector("[data-close]").addEventListener("click", function () { closeAll(true); });
    btn.addEventListener("click", function () {
      var open = btn.getAttribute("aria-expanded") === "true";
      closeAll(false);
      if (!open) { btn.setAttribute("aria-expanded", "true"); panel.hidden = false; search.focus(); }
    });
  }
  function closeAll(restoreFocus) {
    document.querySelectorAll(".dd").forEach(function (dd) {
      var b = dd.querySelector("button[aria-expanded]"), p = dd.querySelector(".dd-panel");
      if (b.getAttribute("aria-expanded") === "true" && restoreFocus) b.focus();
      b.setAttribute("aria-expanded", "false"); p.hidden = true;
    });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    var openDd = document.querySelector(".dd button[aria-expanded=true]");
    if (openDd) closeAll(true); else closePanel(true);
  });
  document.addEventListener("click", function (e) {
    if (!e.target.closest(".dd")) closeAll(false);
    if (!e.target.closest(".filterbar")) closePanel(false);
  });
  // Sous 640 px, les filtres sont rangés dans un panneau ouvert par le bouton « Filtres (n) ».
  function closePanel(focus) {
    var t = $("fb-toggle");
    if (t.getAttribute("aria-expanded") !== "true") return;
    t.setAttribute("aria-expanded", "false");
    $("filterbar").classList.remove("is-open");
    if (focus) t.focus();
  }
  $("fb-toggle").addEventListener("click", function () {
    var open = this.getAttribute("aria-expanded") === "true";
    this.setAttribute("aria-expanded", String(!open));
    $("filterbar").classList.toggle("is-open", !open);
    if (!open) { var first = $("fb-filters").querySelector("button"); if (first) first.focus(); }
  });

  function syncControls() {
    ["provider", "place"].forEach(function (key) {
      var btn = $("dd-" + key + "-btn"), n = filters[key].length;
      btn.innerHTML = (key === "provider" ? "Fournisseur" : "Destination") + (n ? ' <span class="count">' + n + "</span>" : "");
      $("dd-" + key).querySelectorAll("input[type=checkbox]").forEach(function (c) { c.checked = filters[key].indexOf(c.value) !== -1; });
    });
    document.querySelectorAll(".toggle[data-key]").forEach(function (t) {
      var v = t.dataset.key === "validity_days" ? Number(t.dataset.value) : t.dataset.value;
      t.setAttribute("aria-pressed", String(filters[t.dataset.key].indexOf(v) !== -1));
    });
    var active = activeCount(), n = state.rows.length, tc = $("fb-toggle-count");
    tc.hidden = !active; tc.textContent = active;
    $("fb-toggle").setAttribute("aria-label", "Filtres" + (active ? ", " + active + " " + plural(active, "critère actif", "critères actifs") : ""));
    $("fb-reset").disabled = !active;
    $("fb-result").innerHTML = active ? "<b>" + num(n) + "</b> " + plural(n, "offre", "offres") + " sur " + num(ALL.length) : "<b>" + num(ALL.length) + "</b> offres";
    document.body.classList.toggle("is-filtered", active > 0);
    document.body.classList.toggle("is-empty", active > 0 && n === 0);
    $("fb-export").disabled = n === 0;
    document.querySelectorAll("[data-scope]").forEach(function (el) {
      el.textContent = "Filtré · " + num(n) + " " + plural(n, "offre", "offres");
    });
  }

  function apply() {
    state.rows = A.applyFilters(ALL, filters);
    writeUrl();
    syncControls();
    render(false);
  }
  function resetFilters() { KEYS.forEach(function (k) { filters[k] = []; }); closeAll(false); apply(); }

  function initFilters() {
    var pc = counts("provider"), plc = counts("place");
    var providers = Object.keys(pc).sort(function (a, b) { return a.localeCompare(b, "fr"); });
    buildDropdown("provider", [{ items: providers.map(function (p) { return { value: p, label: p, count: pc[p] }; }) }]);
    var names = {};
    ALL.forEach(function (r) { names[r.country_code] = r.country_name; });
    var regions = REGION_CODES.filter(function (c) { return plc[c]; });
    var countries = Object.keys(plc).filter(function (c) { return REGION_CODES.indexOf(c) === -1; }).sort(function (a, b) { return names[a].localeCompare(names[b], "fr"); });
    buildDropdown("place", [
      { title: "Zones régionales", items: regions.map(function (c) { return { value: c, label: names[c], count: plc[c] }; }) },
      { title: "Pays", items: countries.map(function (c) { return { value: c, label: names[c], count: plc[c] }; }) }
    ]);
    var validities = Object.keys(counts("validity_days")).map(Number).sort(function (a, b) { return a - b; });
    $("fb-validity").insertAdjacentHTML("beforeend", validities.map(function (v) {
      return '<button class="toggle" type="button" aria-pressed="false" data-key="validity_days" data-value="' + v + '">' + v + " j</button>";
    }).join(""));
    document.querySelectorAll(".toggle[data-key]").forEach(function (t) {
      t.addEventListener("click", function () {
        var k = t.dataset.key, v = k === "validity_days" ? Number(t.dataset.value) : t.dataset.value, i = filters[k].indexOf(v);
        if (i === -1) filters[k].push(v); else filters[k].splice(i, 1);
        apply();
      });
    });
    $("fb-reset").addEventListener("click", resetFilters);
    document.querySelectorAll("[data-reset]").forEach(function (b) { b.addEventListener("click", resetFilters); });
    $("fb-export").addEventListener("click", exportCsv);
    readUrl();
    state.rows = A.applyFilters(ALL, filters);
    syncControls();
  }

  // ---------- Export CSV (même format que les fichiers sources, redéposable dans data/) ----------
  function exportCsv() {
    var blob = new Blob([A.toCSV(state.rows)], { type: "text/csv;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "offres-esim-" + (activeCount() ? "filtrees" : "toutes") + "-" + S.meta.generated_at.slice(0, 10) + ".csv";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  // ---------- Analyses (lot 5) ----------
  function hash01(s) { // pseudo-aléatoire stable par SKU : l'écartement des points ne bouge pas d'un rendu à l'autre
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return ((h >>> 0) % 10000) / 10000;
  }
  function withAlpha(hex, a) {
    var h = hex.replace("#", ""), n = parseInt(h.length === 3 ? h.replace(/./g, "$&$&") : h, 16);
    return "rgba(" + (n >> 16 & 255) + "," + (n >> 8 & 255) + "," + (n & 255) + "," + a + ")";
  }
  function mix(a, b, t) {
    var pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16), out = 0;
    [16, 8, 0].forEach(function (sh) { out |= Math.round((pa >> sh & 255) + ((pb >> sh & 255) - (pa >> sh & 255)) * t) << sh; });
    return "#" + (out >>> 0).toString(16).padStart(6, "0");
  }
  function isDark() { return css("--page").toLowerCase() !== "#ffffff"; }
  function logTicks(axis, values, fmt) {
    axis.afterBuildTicks = function (scale) { scale.ticks = values.filter(function (v) { return v >= scale.min && v <= scale.max; }).map(function (v) { return { value: v }; }); };
    axis.ticks = Object.assign({}, axis.ticks, { callback: function (v) { return fmt(v); } });
    return axis;
  }

  function drawScatter(V) {
    var rows = state.rows, s1 = css("--series-1"), s2 = css("--series-2"), law = V.pricing.power_law;
    var narrow = $("chart-scatter").parentNode.clientWidth < 480; // moins de graduations sur mobile
    function points(net, unlimited) {
      return rows.filter(function (r) { return r.network === net && r.is_unlimited === unlimited; }).map(function (r) {
        var j = hash01(r.sku);
        return unlimited ? { x: r.validity_days * (1 + (j - 0.5) * 0.36), y: r.price, r: r }
                         : { x: r.data_gb * Math.exp((j - 0.5) * 0.32), y: r.price, r: r };
      });
    }
    var tip = Object.assign(tooltipStyle(), { callbacks: {
      title: function (items) { var r = items[0].raw.r; return r ? r.provider + " · " + r.country_name : ""; },
      label: function (c) {
        var r = c.raw.r;
        return r ? [r.data_display + " · " + r.validity_days + " jours · " + r.network, eur(r.price) + (r.is_unlimited ? "" : " · " + eur(r.price / r.data_gb) + " / Go")]
                 : "Tendance : " + eur(c.raw.y) + " pour " + gb(c.raw.x, 0);
      } } });
    var pointStyle = { pointRadius: 2.6, pointHoverRadius: 6, borderWidth: 0 };
    var datasets = [
      Object.assign({ label: "4G", data: points("4G", false), backgroundColor: withAlpha(s1, 0.38), hoverBackgroundColor: s1 }, pointStyle),
      Object.assign({ label: "5G", data: points("5G", false), backgroundColor: withAlpha(s2, 0.42), hoverBackgroundColor: s2 }, pointStyle)
    ];
    if (law) {
      var trend = [];
      for (var x = 0.8; x <= 62; x *= 1.15) trend.push({ x: x, y: law.coef * Math.pow(x, law.exponent) });
      datasets.push({ type: "line", label: "Tendance", data: trend, borderColor: css("--ink"), borderWidth: 2, borderDash: [6, 4], pointRadius: 0, pointHitRadius: 0, tension: 0 });
    }
    var grid = { color: css("--grid"), drawTicks: false }, ticks = { color: css("--muted"), padding: 6 };
    chart("chart-scatter", {
      type: "scatter", data: { datasets: datasets },
      options: { maintainAspectRatio: false, animation: false, parsing: true,
        plugins: { legend: { display: false }, tooltip: tip },
        scales: {
          x: logTicks({ type: "logarithmic", min: 0.8, max: 62, grid: grid, border: { color: css("--axis") }, ticks: ticks, title: { display: true, text: "Volume de data (Go)", color: css("--muted") } },
            narrow ? [1, 5, 20, 50] : [1, 3, 5, 10, 20, 50], function (v) { return num(v) + " Go"; }),
          y: logTicks({ type: "logarithmic", grid: grid, border: { display: false }, ticks: ticks, title: { display: true, text: "Prix", color: css("--muted") } },
            [5, 10, 20, 50, 100], function (v) { return eur(v, 0); })
        } }
    });
    $("scatter-legend").innerHTML = '<span><span class="swatch" style="background:var(--series-1)"></span>4G</span><span><span class="swatch" style="background:var(--series-2)"></span>5G</span>' +
      (law ? '<span><span class="swatch" style="background:var(--ink);height:2px;vertical-align:3px"></span>Tendance (loi de puissance)</span>' : "");
    $("scatter-note").innerHTML = law ? icon("trend") + "<span>Tendance ajustée sur " + num(law.offers) + " forfaits : quand le volume double, le prix n'est multiplié que par <b>" +
      num(law.doubling_factor, 2) + "</b> (exposant " + num(law.exponent, 2) + ", R² = " + num(law.r2, 2) + "). Le Go devient donc nettement moins cher dans les gros forfaits.</span>" : "";

    var unl = [points("4G", true), points("5G", true)];
    var nUnl = unl[0].length + unl[1].length;
    var validities = V.distributions.validity.map(function (v) { return v.validity_days; });
    chart("chart-unlimited", {
      type: "scatter",
      data: { datasets: [
        Object.assign({ label: "4G", data: unl[0], backgroundColor: withAlpha(s1, 0.5), hoverBackgroundColor: s1 }, pointStyle, { pointRadius: 3 }),
        Object.assign({ label: "5G", data: unl[1], backgroundColor: withAlpha(s2, 0.55), hoverBackgroundColor: s2 }, pointStyle, { pointRadius: 3 })
      ] },
      options: { maintainAspectRatio: false, animation: false,
        plugins: { legend: { display: false }, tooltip: tip },
        scales: {
          x: logTicks({ type: "logarithmic", min: 5.5, max: 40, grid: { display: false }, border: { color: css("--axis") }, ticks: ticks, title: { display: true, text: "Durée", color: css("--muted") } },
            validities, function (v) { return num(v) + " j"; }),
          y: { beginAtZero: true, grid: grid, border: { display: false }, ticks: Object.assign({}, ticks, { callback: function (v) { return eur(v, 0); } }) }
        } }
    });
    var byV = {};
    state.rows.forEach(function (r) { if (r.is_unlimited) (byV[r.validity_days] = byV[r.validity_days] || []).push(r.price); });
    $("unlimited-note").innerHTML = nUnl ? icon("infinity") + "<span>" + num(nUnl) + " forfaits illimités. Prix médian : " + Object.keys(byV).sort(function (a, b) { return a - b; }).map(function (v) {
      return "<b>" + eur(A.median(byV[v])) + "</b> sur " + v + " j";
    }).join(", ") + ".</span>" : "";
  }

  function drawHistogram(V) {
    var Hh = V.pricing.histogram, H = V.headline, bins = Hh.bins, w = Hh.bin_width;
    if (!bins.length) { chart("chart-hist", { type: "bar", data: { labels: [], datasets: [] }, options: { maintainAspectRatio: false } }); $("hist-sub").textContent = "Aucune offre."; $("hist-legend").innerHTML = ""; return; }
    var markers = [
      { v: H.price.median, color: css("--series-1"), label: "Médiane " + eur(H.price.median) },
      { v: H.price.mean, color: css("--series-2"), label: "Moyenne " + eur(H.price.mean) },
      { v: H.expensive.threshold, color: css("--muted"), label: "Seuil " + eur(H.expensive.threshold, 0) }
    ];
    var markerPlugin = { id: "markers", afterDatasetsDraw: function (c) {
      var x = c.scales.x, top = c.chartArea.top, bottom = c.chartArea.bottom, ctx = c.ctx;
      var step = x.getPixelForValue(1) - x.getPixelForValue(0);
      markers.forEach(function (m, k) {
        if (m.v == null) return;
        var px = x.getPixelForValue(0) + (m.v / w - 0.5) * step;
        if (px < c.chartArea.left || px > c.chartArea.right) return;
        ctx.save(); ctx.strokeStyle = m.color; ctx.lineWidth = 2; if (k === 2) ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.moveTo(px, top + 4); ctx.lineTo(px, bottom); ctx.stroke(); ctx.restore();
      });
    } };
    chart("chart-hist", {
      type: "bar", plugins: [markerPlugin],
      data: { labels: bins.map(function (b) { return num(b.from) + "–" + num(b.to) + " €"; }), datasets: [{ data: bins.map(function (b) { return b.offers; }),
        backgroundColor: bins.map(function (b) { return b.from >= H.expensive.threshold ? css("--series-2") : css("--series-1"); }), borderRadius: 3, borderSkipped: "start", categoryPercentage: 0.92, barPercentage: 0.95 }] },
      options: { maintainAspectRatio: false, animation: REDUCED || instant ? false : { duration: 450 },
        plugins: { legend: { display: false }, tooltip: Object.assign(tooltipStyle(), { callbacks: { title: function (i) { return "De " + num(bins[i[0].dataIndex].from) + " à " + num(bins[i[0].dataIndex].to) + " € (exclu)"; }, label: function (c) { return num(c.raw) + " offres"; } } }) },
        scales: { x: { grid: { display: false }, border: { color: css("--axis") }, ticks: { color: css("--muted"), maxRotation: 0, autoSkip: true, autoSkipPadding: 14, callback: function (v) { return num(bins[v].from) + " €"; } } },
                  y: { beginAtZero: true, grid: { color: css("--grid"), drawTicks: false }, border: { display: false }, ticks: { color: css("--muted"), padding: 6 } } } }
    });
    renderQuantiles(H);
    $("hist-sub").textContent = "Nombre d'offres par tranche de " + num(w) + " € · la moitié des offres coûte moins de " + eur(H.price.median) + ".";
    $("hist-legend").innerHTML = markers.map(function (m, k) { return '<span><span class="swatch" style="background:' + m.color + ';height:3px;vertical-align:3px"></span>' + m.label + "</span>"; }).join("") +
      '<span><span class="swatch" style="background:var(--series-2)"></span>Tranches à partir de ' + eur(H.expensive.threshold, 0) + "</span>";
  }

  var quantile = A.quantile; // moteur testé contre pandas
  function renderQuantiles(H) {
    var prices = state.rows.map(function (r) { return r.price; }).sort(function (a, b) { return a - b; });
    var all = prices, lim = state.rows.filter(function (r) { return !r.is_unlimited; }).map(function (r) { return r.price; }).sort(function (a, b) { return a - b; });
    var qs = [["Min", 0], ["1er quartile", 0.25], ["Médiane", 0.5], ["3e quartile", 0.75], ["9e décile", 0.9], ["Max", 1]];
    var rows = [{ label: "Toutes les offres", v: all }, { label: "Hors illimités", v: lim }];
    table($("table-quantiles"), [{ label: "", fmt: function (x) { return x.label; } }].concat(qs.map(function (q) {
      return { label: q[0], n: true, fmt: function (x) { return eur(quantile(x.v, q[1])); } };
    })), rows);
    var q3 = quantile(all, 0.75), q1 = quantile(all, 0.25);
    $("quantiles-note").innerHTML = all.length ? icon("info") + "<span>La moitié centrale des offres coûte entre <b>" + eur(q1) + "</b> et <b>" + eur(q3) +
      "</b>. La moyenne (" + eur(H.price.mean) + ") dépasse la médiane (" + eur(H.price.median) + ") : quelques offres chères, surtout illimitées, tirent la moyenne vers le haut.</span>" : "";
  }

  function drawHeatmap(V) {
    var M = V.provider_validity_index, el = $("heatmap");
    var cheap = isDark() ? "#3a8cf2" : "#0a6cdc", dear = isDark() ? "#e0702a" : "#c2410c", mid = isDark() ? "#1f2b44" : "#eef2f7";
    var cells = {}, maxDev = 0;
    M.cells.forEach(function (c) { cells[c.provider + "|" + c.validity_days] = c; maxDev = Math.max(maxDev, Math.abs(c.index - 100)); });
    var span = Math.max(5, Math.ceil(maxDev)); // échelle symétrique autour de 100, au moins ±5
    function color(idx) { var t = Math.max(-1, Math.min(1, (idx - 100) / span)); return t < 0 ? mix(mid, cheap, -t) : mix(mid, dear, t); }
    function cell(idx, n, extra) {
      if (idx == null) return '<td style="background:var(--card-2)">—</td>';
      var bg = color(idx), thin = n < 5;
      return '<td class="' + (thin ? "thin " : "") + (extra || "") + '" style="background:' + bg + ";color:" + inkOn(bg) + '" title="Indice ' + num(idx, 1) + " · " + num(n) + " " + plural(n, "offre", "offres") + (thin ? " (échantillon faible)" : "") + '">' + num(idx, 0) + "</td>";
    }
    var providers = V.providers.slice().sort(function (a, b) { return a.price_index - b.price_index; });
    el.innerHTML = el.querySelector("caption").outerHTML + "<thead><tr><th></th>" + M.validities.map(function (v) { return '<th scope="col">' + v + " j</th>"; }).join("") + '<th scope="col">Global</th></tr></thead><tbody>' +
      providers.map(function (p) {
        return '<tr><th scope="row">' + esc(p.provider) + "</th>" + M.validities.map(function (v) { var c = cells[p.provider + "|" + v]; return c ? cell(c.index, c.offers) : cell(null); }).join("") + cell(p.price_index, p.offers, "global") + "</tr>";
      }).join("") + "</tbody>";
    $("heat-legend").innerHTML = "<span>Moins cher</span><i style=\"background:linear-gradient(90deg," + cheap + "," + mid + "," + dear + ')"></i><span>Plus cher</span><span>· échelle ' + num(100 - span) + " à " + num(100 + span) + "</span>";
    var lo = providers[0], hi = providers[providers.length - 1];
    $("heat-note").innerHTML = providers.length ? icon("scale") + "<span>" + (maxDev < 5
      ? "Tous les écarts restent sous 5 points : à volume et durée égaux, <b>aucun fournisseur ne se démarque nettement</b>, quelle que soit la durée."
      : "Écarts marqués : de <b>" + num(lo.price_index, 1) + "</b> (" + esc(lo.provider) + ") à <b>" + num(hi.price_index, 1) + "</b> (" + esc(hi.provider) + ").") +
      " Cellules en italique : moins de 5 offres.</span>" : "";
  }

  var WORLD = null, worldState = "idle";
  function loadWorld() {
    if (worldState !== "idle") return;
    worldState = "loading";
    // Fond de carte hébergé localement (assets/vendor/world-110m.js) : aucune requête externe.
    var topo = window.WORLD_TOPO;
    if (!topo) { worldState = "failed"; $("chart-map").parentNode.style.display = "none"; $("map-fallback").style.display = "block"; return; }
    WORLD = ChartGeo.topojson.feature(topo, topo.objects.countries).features.filter(function (f) { return f.id !== "010"; }); // sans l'Antarctique
    worldState = "ready";
    drawMap(current);
  }
  function rampColors() { return isDark() ? ["#2a63ad", "#3a80dc", "#6da7ec", "#9ec5f4", "#cde2fb"] : ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"]; }
  function renderMapSide(V) {
    var C = V.coverage, ppg = C.countries_price_per_gb.filter(function (c) { return c.price_per_gb != null; });
    table($("table-map"), [
      { label: "Pays", fmt: function (x) { return esc(x.name); } },
      { label: "Offres", n: true, fmt: function (x) { return num(x.offers); } },
      { label: "€ / Go", n: true, fmt: function (x) { return eur(x.price_per_gb); } }
    ], ppg.slice().sort(function (a, b) { return a.price_per_gb - b.price_per_gb; }));
    var zones = {};
    state.rows.forEach(function (r) { if (r.is_region) (zones[r.country_code] = zones[r.country_code] || []).push(r); });
    $("zones-list").innerHTML = REGION_CODES.filter(function (z) { return zones[z]; }).map(function (z) {
      var rs = zones[z], lim = rs.filter(function (r) { return !r.is_unlimited; });
      var p = lim.length ? lim.reduce(function (s, r) { return s + r.price; }, 0) / lim.reduce(function (s, r) { return s + r.data_gb; }, 0) : null;
      return "<li><span><b>" + esc(rs[0].country_name) + ' <span class="zero">' + z + "</span></b><small>" + num(rs.length) + " offres · dès " +
        eur(Math.min.apply(null, rs.map(function (r) { return r.price; }))) + '</small></span><span class="v">' + (p == null ? "—" : eur(p) + "<small> / Go</small>") + "</span></li>";
    }).join("") || '<li><span class="zero">Aucune zone dans la sélection.</span></li>';
  }
  function drawMap(V) {
    renderMapSide(V);
    if (typeof ChartGeo === "undefined") { $("chart-map").parentNode.style.display = "none"; $("map-fallback").style.display = "block"; return; }
    if (!WORLD) { loadWorld(); return; }
    var C = V.coverage, byIso = {}, mappedIds = {};
    WORLD.forEach(function (f) { mappedIds[f.id] = true; });
    C.countries_price_per_gb.forEach(function (c) { if (c.iso_numeric && c.price_per_gb != null) byIso[c.iso_numeric] = c; });
    var values = Object.keys(byIso).map(function (k) { return byIso[k].price_per_gb; });
    var min = Math.min.apply(null, values), max = Math.max.apply(null, values), ramp = rampColors();
    function classOf(v) { return max > min ? Math.min(4, Math.floor(((v - min) / (max - min)) * 5)) : 2; }
    chart("chart-map", {
      type: "choropleth",
      data: { labels: WORLD.map(function (f) { return f.properties.name; }), datasets: [{
        outline: WORLD, showOutline: true,
        data: WORLD.map(function (f) { var c = byIso[f.id]; return { feature: f, value: c ? c.price_per_gb : null }; }),
        backgroundColor: function (ctx) { var d = ctx.raw; return d && d.value != null ? ramp[classOf(d.value)] : css("--grid"); },
        borderColor: css("--page"), borderWidth: 0.5, hoverBorderColor: css("--ink"), hoverBorderWidth: 1.2
      }] },
      options: { maintainAspectRatio: false, animation: false, showOutline: true, showGraticule: false,
        plugins: { legend: { display: false }, tooltip: Object.assign(tooltipStyle(), { filter: function (i) { return i.raw && i.raw.value != null; },
          callbacks: { title: function (i) { var c = byIso[i[0].raw.feature.id]; return c ? c.name : ""; }, label: function (i) { var c = byIso[i.raw.feature.id]; return c ? [eur(c.price_per_gb) + " / Go", num(c.offers) + " offres"] : ""; } } }) },
        scales: { projection: { axis: "x", projection: "equalEarth" }, color: { axis: "x", display: false } } }
    });
    var stepW = (max - min) / 5;
    $("map-legend").innerHTML = values.length ? ramp.map(function (col, k) {
      return '<span><span class="swatch" style="background:' + col + '"></span>' + eur(min + k * stepW) + (k < 4 ? "–" + eur(min + (k + 1) * stepW) : " et plus") + "</span>";
    }).join("") + '<span><span class="swatch" style="background:var(--grid)"></span>Hors catalogue</span>' : "";
    var unmapped = C.countries_price_per_gb.filter(function (c) { return !c.iso_numeric || !mappedIds[c.iso_numeric]; });
    $("unmapped").innerHTML = unmapped.length ? "<h4>Trop petits pour la carte</h4><ul class=\"zones\">" + unmapped.map(function (c) {
      return "<li><span><b>" + esc(c.name) + ' <span class="zero">' + esc(c.code) + "</span></b><small>" + num(c.offers) + ' offres</small></span><span class="v">' + (c.price_per_gb == null ? "—" : eur(c.price_per_gb) + "<small> / Go</small>") + "</span></li>";
    }).join("") + "</ul>" : "";
  }

  // ---------- Comparateur (lot 6) ----------
  var ZONES = S.coverage.zones; // hypothèse de couverture (config.ZONE_MEMBERS), documentée dans la Méthodologie
  var ZONE_NAMES = S.coverage.region_codes_note;
  function initComparator() {
    var names = {}, offersBy = {};
    ALL.forEach(function (r) { names[r.country_code] = r.country_name; offersBy[r.country_code] = (offersBy[r.country_code] || 0) + 1; });
    var countries = Object.keys(names).filter(function (c) { return REGION_CODES.indexOf(c) === -1; }).sort(function (a, b) { return names[a].localeCompare(names[b], "fr"); });
    var regions = REGION_CODES.filter(function (c) { return names[c]; });
    $("cmp-place").innerHTML = '<optgroup label="Pays">' + countries.map(function (c) { return '<option value="' + esc(c) + '">' + esc(names[c]) + "</option>"; }).join("") + "</optgroup>" +
      '<optgroup label="Zones régionales">' + regions.map(function (c) { return '<option value="' + esc(c) + '">' + esc(names[c]) + "</option>"; }).join("") + "</optgroup>";
    var gbs = {};
    ALL.forEach(function (r) { if (!r.is_unlimited) gbs[r.data_gb] = true; });
    $("cmp-volume").innerHTML = Object.keys(gbs).map(Number).sort(function (a, b) { return a - b; }).map(function (g) { return '<option value="' + g + '">' + gb(g, g % 1 ? 1 : 0) + "</option>"; }).join("") +
      (ALL.some(function (r) { return r.is_unlimited; }) ? '<option value="unlimited">Illimité</option>' : "");
    var vs = {};
    ALL.forEach(function (r) { vs[r.validity_days] = true; });
    $("cmp-validity").innerHTML = '<option value="">Toutes</option>' + Object.keys(vs).map(Number).sort(function (a, b) { return a - b; }).map(function (v) { return '<option value="' + v + '">' + v + " jours</option>"; }).join("");
    // Valeurs par défaut : la France si elle existe (sinon la destination la plus fournie), 5 Go si disponible.
    var def = names.FR ? "FR" : countries.slice().sort(function (a, b) { return offersBy[b] - offersBy[a]; })[0];
    if (def) $("cmp-place").value = def;
    if (gbs[5]) $("cmp-volume").value = "5";
    ["cmp-place", "cmp-volume", "cmp-validity", "cmp-regional"].forEach(function (id) { $(id).addEventListener("change", function () { cmpExpanded = false; renderComparator(); }); });
    $("cmp-form").addEventListener("submit", function (e) { e.preventDefault(); });
    $("cmp-more").addEventListener("click", function () { cmpExpanded = !cmpExpanded; renderComparator(); });
    renderComparator();
  }
  function coverageLabel(code) { return ZONE_NAMES[code] || code; }
  var cmpExpanded = false;
  function renderComparator() {
    var place = $("cmp-place").value, volume = $("cmp-volume").value, validity = $("cmp-validity").value, regional = $("cmp-regional").checked;
    if (!place) return;
    var res = A.compare(ALL, { place: place, volume: volume, validity_days: validity || null, includeRegional: regional }, ZONES);
    var placeName = $("cmp-place").selectedOptions[0].textContent, volName = $("cmp-volume").selectedOptions[0].textContent;
    if (!res.length) {
      $("cmp-summary").innerHTML = "Aucune offre pour <b>" + esc(placeName) + "</b> en <b>" + esc(volName) + "</b>" + (validity ? " sur " + validity + " jours" : "") + ".";
      $("cmp-best").innerHTML = ""; $("cmp-table").innerHTML = $("cmp-table").querySelector("caption").outerHTML; $("cmp-cards").innerHTML = ""; $("cmp-note").innerHTML = ""; $("cmp-more").hidden = true; return;
    }
    var best = res[0], worst = res[res.length - 1], nReg = res.filter(function (x) { return x.regional; }).length;
    $("cmp-summary").innerHTML = "<b>" + num(res.length) + "</b> " + plural(res.length, "offre", "offres") + " pour <b>" + esc(placeName) + "</b> en <b>" + esc(volName) + "</b>" +
      (validity ? " sur " + validity + " jours" : "") + " · de <b>" + eur(best.offer.price) + "</b> à <b>" + eur(worst.offer.price) + "</b>" +
      (res.length > 1 ? " (écart de " + pct(worst.offer.price / best.offer.price - 1) + ")" : "") + (nReg ? " · dont " + num(nReg) + " " + plural(nReg, "forfait régional", "forfaits régionaux") : "") + ".";
    var bo = best.offer;
    // Étiquette « Meilleur prix » DANS le bloc de texte (sous le trophée sur mobile) : elle ne peut plus déborder.
    $("cmp-best").innerHTML = '<div class="best"><span class="medal">' + icon("trophy") + '</span><div class="best-main"><span class="k">Meilleur prix</span>' +
      '<span class="t">' + esc(bo.provider) + " · " + esc(bo.product_name) + " <small>· " + bo.validity_days + " j · " + esc(bo.network) + " · recharge " + esc(bo.top_up) + "</small>" +
      (best.regional ? ' <span class="badge region">Forfait régional : ' + esc(coverageLabel(bo.country_code)) + "</span>" : "") + "</span></div>" +
      '<div class="p">' + eur(bo.price) + (best.price_per_gb != null ? "<small>" + eur(best.price_per_gb) + " / Go</small>" : "<small>illimité</small>") + "</div></div>";
    var SHORT = 10, MAX = 200, expanded = cmpExpanded && res.length > SHORT;
    var shown = expanded ? res.slice(0, MAX) : res.slice(0, SHORT);
    var more = $("cmp-more");
    more.hidden = res.length <= SHORT;
    more.setAttribute("aria-expanded", String(expanded));
    more.textContent = expanded ? "Afficher seulement les " + SHORT + " moins chères" : "Afficher " + (res.length > MAX ? "les " + MAX + " premières" : "les " + num(res.length) + " offres");
    table($("cmp-table"), [
      { label: "#", n: true, fmt: function (x) { return num(res.indexOf(x) + 1); } },
      { label: "Fournisseur", fmt: function (x) { return esc(x.offer.provider); } },
      { label: "Couverture", fmt: function (x) { return x.regional ? '<span class="badge region">' + esc(coverageLabel(x.offer.country_code)) + "</span>" : '<span class="badge country">' + esc(x.offer.country_name) + "</span>"; } },
      { label: "Durée", n: true, fmt: function (x) { return x.offer.validity_days + " j"; } },
      { label: "Réseau", fmt: function (x) { return esc(x.offer.network); } },
      { label: "Recharge", fmt: function (x) { return esc(x.offer.top_up); } },
      { label: "Prix", n: true, fmt: function (x) { return "<b>" + eur(x.offer.price) + "</b>"; } },
      { label: "€ / Go", n: true, fmt: function (x) { return x.price_per_gb == null ? "—" : eur(x.price_per_gb); } },
      { label: "vs meilleur", n: true, fmt: function (x) { var d = x.offer.price / bo.price - 1; return d === 0 ? '<span class="delta">—</span>' : '<span class="delta">+' + pct(d, d < 0.1 ? 1 : 0) + "</span>"; } },
      { label: "SKU", fmt: function (x) { return '<span class="zero">' + esc(x.offer.sku) + "</span>"; } }
    ], shown, { rowClass: function (x) { return x === best ? "is-best" : ""; } });
    // Sous 640 px, le tableau laisse la place à des cartes compactes : fournisseur, prix et €/Go d'abord,
    // toujours visibles sans défilement horizontal ; couverture, durée, réseau et recharge en petit.
    $("cmp-cards").innerHTML = shown.map(function (x) {
      var o = x.offer, d = o.price / bo.price - 1;
      return '<li class="cmp-card' + (x === best ? " is-best" : "") + '"><div class="cc-top"><span class="cc-rank">' + num(res.indexOf(x) + 1) + '</span><b class="cc-prov">' + esc(o.provider) +
        '</b><span class="cc-price">' + eur(o.price) + "</span></div>" +
        '<div class="cc-sub"><span>' + (x.price_per_gb == null ? "illimité" : eur(x.price_per_gb) + " / Go") + "</span><span>" + (d === 0 ? "meilleur prix" : "+" + pct(d, d < 0.1 ? 1 : 0) + " vs meilleur") + "</span></div>" +
        '<div class="cc-meta">' + (x.regional ? '<span class="badge region">' + esc(coverageLabel(o.country_code)) + "</span>" : '<span class="badge country">' + esc(o.country_name) + "</span>") +
        "<span>" + o.validity_days + " j</span><span>" + esc(o.network) + "</span><span>recharge " + esc(o.top_up) + "</span></div></li>";
    }).join("");
    var zoneTxt = regional && REGION_CODES.indexOf(place) === -1
      ? "Les forfaits régionaux proposés sont ceux des zones supposées couvrir " + esc(placeName) + " (hypothèse détaillée dans la Méthodologie)."
      : regional ? "Les forfaits des zones qui englobent cette zone (ex. Monde) sont aussi proposés." : "Forfaits régionaux exclus.";
    $("cmp-note").innerHTML = icon("info") + "<span>" + (shown.length < res.length ? "Les " + num(shown.length) + " moins chères sur " + num(res.length) + ". " : "") + zoneTxt +
      " À prix égal, l'offre la plus courte puis l'ordre alphabétique départagent.</span>";
  }

  // ---------- Orchestration ----------
  function render(animate) {
    current = A.compute(state.rows, { isoNumeric: ISO });
    renderHero(current);
    renderKpis(current);
    renderProviders(current);
    renderPricing(current);
    renderDestinations(current);
    drawHeatmap(current);
    renderMapSide(current);
    if (animate) { animateCounters($("hero-kpis")); animateCounters($("kpis")); }
    if (window.Chart) drawCharts(current, !animate);
  }

  // ---------- Thème : géré par site.js, qui prévient quand il change ----------
  document.addEventListener("themechange", function () {
    renderPricing(current);
    drawHeatmap(current);
    if (window.Chart) drawCharts(current);
  });

  renderStatic();
  initFilters();
  initComparator();
  render(true);
  window.addEventListener("load", function () {
    if (window.Chart && window.ChartGeo) Chart.register(ChartGeo.ChoroplethController, ChartGeo.GeoFeature, ChartGeo.ColorScale, ChartGeo.ProjectionScale);
    if (window.Chart) drawCharts(current); else { document.body.classList.add("no-chart"); renderMapSide(current); $("map-fallback").style.display = "block"; }
    document.documentElement.dataset.ready = "1"; // repère utilisé par le test de rendu
  });
})();
