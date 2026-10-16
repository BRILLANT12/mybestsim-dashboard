/*
 * Moteur de calcul du dashboard, côté navigateur.
 *
 * Python (dashboard/stats.py) reste la source de vérité : ce moteur recalcule les
 * MÊMES indicateurs, avec les mêmes règles et les mêmes noms de champs, sur les
 * offres filtrées. tests/test_analytics_js.py l'exécute avec Node et vérifie que,
 * sans filtre, il retrouve exactement les chiffres de Python.
 *
 * Règles alignées sur Python : tri des textes par point de code (pas de
 * localeCompare), médiane = moyenne des deux valeurs centrales, classes
 * d'histogramme fermées à gauche, comparaisons « à offre égale » par segment
 * (même volume ou illimité, même durée).
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Analytics = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var EXPENSIVE_THRESHOLD_EUR = 100;
  var HISTOGRAM_BIN_EUR = 5;
  var TOP_DESTINATIONS = 10;
  var MAX_LISTED_PRODUCTS = 5;
  var CSV_COLUMNS = ["sku", "provider", "product_name", "country_code", "country_name", "data_gb",
    "data_display", "validity_days", "price", "currency", "network", "top_up"];

  // ---------- Outils ----------
  function cmp(a, b) { return a < b ? -1 : a > b ? 1 : 0; } // ordre des points de code, comme Python
  function sum(xs) { var s = 0; for (var i = 0; i < xs.length; i++) s += xs[i]; return s; }
  function mean(xs) { return xs.length ? sum(xs) / xs.length : null; }
  function median(xs) {
    if (!xs.length) return null;
    var s = xs.slice().sort(function (a, b) { return a - b; });
    var m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }
  function share(part, total) { return total ? part / total : null; }
  // Quantile par interpolation linéaire (même méthode que pandas.Series.quantile par défaut).
  function quantile(values, q) {
    if (!values.length) return null;
    var s = values.slice().sort(function (a, b) { return a - b; });
    var pos = (s.length - 1) * q, lo = Math.floor(pos), hi = Math.ceil(pos);
    return s[lo] + (s[hi] - s[lo]) * (pos - lo);
  }
  function groupBy(rows, keyFn) {
    var map = new Map();
    rows.forEach(function (r) {
      var k = keyFn(r);
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(r);
    });
    return map;
  }
  function pluck(rows, f) { return rows.map(function (r) { return r[f]; }); }
  function limited(rows) { return rows.filter(function (r) { return !r.is_unlimited; }); }
  function uniqueCount(rows, f) { return new Set(pluck(rows, f)).size; }
  function tierLabel(gb) { return String(gb).replace(".", ",") + " Go"; }
  function segmentKey(r) { return (r.is_unlimited ? "illimité" : String(r.data_gb)) + "|" + r.validity_days; }

  // ---------- Décodage des offres intégrées dans la page ----------
  function decodeOffers(payload, regionCodes) {
    var d = payload.dict, regions = new Set(regionCodes || []);
    return payload.rows.map(function (r) {
      var c = d.country[r[3]];
      return {
        sku: r[0], provider: d.provider[r[1]], product_name: d.product_name[r[2]],
        country_code: c[0], country_name: c[1], data_gb: r[4], data_display: d.data_display[r[5]],
        validity_days: r[6], price: r[7], currency: payload.currency,
        network: d.network[r[8]], top_up: d.top_up[r[9]],
        is_unlimited: r[4] === null, is_region: regions.has(c[0])
      };
    });
  }

  // ---------- Filtres ----------
  // Chaque critère est une liste de valeurs acceptées ; liste vide ou absente = tout.
  function applyFilters(rows, f) {
    f = f || {};
    function ok(list, v) { return !list || !list.length || list.indexOf(v) !== -1; }
    return rows.filter(function (r) {
      return ok(f.provider, r.provider) && ok(f.place, r.country_code) && ok(f.network, r.network) &&
        ok(f.top_up, r.top_up) && ok(f.validity_days, r.validity_days);
    });
  }

  // ---------- Indicateurs ----------
  function pricePerGb(rows) {
    var lim = limited(rows), gb = sum(pluck(lim, "data_gb"));
    return gb > 0 ? sum(pluck(lim, "price")) / gb : null;
  }

  function products(rows) {
    return rows.slice().sort(function (a, b) { return cmp(a.provider, b.provider) || cmp(a.sku, b.sku); })
      .slice(0, MAX_LISTED_PRODUCTS)
      .map(function (r) { return { sku: r.sku, provider: r.provider, product_name: r.product_name, price: r.price }; });
  }

  function extreme(rows, value) {
    var hit = rows.filter(function (r) { return r.price === value; });
    var byProv = Array.from(groupBy(hit, function (r) { return r.provider; }), function (e) { return { provider: e[0], count: e[1].length }; })
      .sort(function (a, b) { return b.count - a.count || cmp(a.provider, b.provider); });
    return { price: value, count: hit.length, products: products(hit), by_provider: byProv };
  }

  function headline(rows) {
    var n = rows.length, lim = limited(rows), unl = rows.filter(function (r) { return r.is_unlimited; });
    var prices = pluck(rows, "price");
    var exp = rows.filter(function (r) { return r.price > EXPENSIVE_THRESHOLD_EUR; }); // strictement supérieur
    return {
      total_offers: n,
      expensive: {
        threshold: EXPENSIVE_THRESHOLD_EUR,
        count: exp.length,
        unlimited_count: exp.filter(function (r) { return r.is_unlimited; }).length,
        validity_days: Array.from(new Set(pluck(exp, "validity_days"))).sort(function (a, b) { return a - b; }),
        max_price_limited: lim.length ? Math.max.apply(null, pluck(lim, "price")) : null
      },
      price_range: {
        min: n ? extreme(rows, Math.min.apply(null, prices)) : null,
        max: n ? extreme(rows, Math.max.apply(null, prices)) : null
      },
      data: {
        mean_gb: mean(pluck(lim, "data_gb")),
        median_gb: median(pluck(lim, "data_gb")),
        offers_with_data: lim.length,
        unlimited_count: unl.length,
        unlimited_share: share(unl.length, n)
      },
      price: {
        mean: mean(prices),
        median: median(prices),
        mean_limited: mean(pluck(lim, "price")),
        mean_unlimited: mean(pluck(unl, "price"))
      }
    };
  }

  // Prix de chaque offre rapporté à la moyenne de son segment (1 = prix moyen des offres comparables).
  function relativePrices(rows) {
    var segMean = new Map();
    groupBy(rows, segmentKey).forEach(function (g, k) { segMean.set(k, mean(pluck(g, "price"))); });
    return rows.map(function (r) { return r.price / segMean.get(segmentKey(r)); });
  }

  function byProvider(rows) {
    var n = rows.length, rel = relativePrices(rows);
    rows.forEach(function (r, i) { r._rel = rel[i]; });
    var out = Array.from(groupBy(rows, function (r) { return r.provider; }), function (e) {
      var d = e[1], lim = limited(d);
      return {
        provider: e[0],
        offers: d.length,
        share: share(d.length, n),
        mean_price: mean(pluck(d, "price")),
        min_price: Math.min.apply(null, pluck(d, "price")),
        mean_data_gb: lim.length ? mean(pluck(lim, "data_gb")) : null,
        unlimited: d.length - lim.length,
        price_per_gb: pricePerGb(d),
        price_index: mean(pluck(d, "_rel")) * 100,
        share_5g: share(d.filter(function (r) { return r.network === "5G"; }).length, d.length),
        share_top_up: share(d.filter(function (r) { return r.top_up === "oui"; }).length, d.length),
        destinations: uniqueCount(d, "country_code")
      };
    });
    rows.forEach(function (r) { delete r._rel; });
    return out.sort(function (a, b) { return b.offers - a.offers || cmp(a.provider, b.provider); });
  }

  function providerValidityIndex(rows) {
    var rel = relativePrices(rows);
    var cells = new Map();
    rows.forEach(function (r, i) {
      var k = r.provider + "\u0000" + r.validity_days;
      if (!cells.has(k)) cells.set(k, { provider: r.provider, validity_days: r.validity_days, rel: [] });
      cells.get(k).rel.push(rel[i]);
    });
    return {
      validities: Array.from(new Set(pluck(rows, "validity_days"))).sort(function (a, b) { return a - b; }),
      cells: Array.from(cells.values()).map(function (c) {
        return { provider: c.provider, validity_days: c.validity_days, index: mean(c.rel) * 100, offers: c.rel.length };
      }).sort(function (a, b) { return cmp(a.provider, b.provider) || a.validity_days - b.validity_days; }) // même ordre que Python
    };
  }

  function powerLaw(rows) {
    var lim = limited(rows);
    if (new Set(pluck(lim, "data_gb")).size < 2) return null;
    var x = lim.map(function (r) { return Math.log(r.data_gb); }), y = lim.map(function (r) { return Math.log(r.price); });
    var mx = mean(x), my = mean(y), sxy = 0, sxx = 0;
    for (var i = 0; i < x.length; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) * (x[i] - mx); }
    var b = sxy / sxx, a = my - b * mx;
    var resid = y.map(function (v, k) { return v - (a + b * x[k]); });
    var variance = function (v) { var m = mean(v); return mean(v.map(function (t) { return (t - m) * (t - m); })); };
    var vy = variance(y);
    return { coef: Math.exp(a), exponent: b, doubling_factor: Math.pow(2, b), r2: vy > 0 ? 1 - variance(resid) / vy : 1, offers: lim.length };
  }

  function priceHistogram(rows, width) {
    width = width || HISTOGRAM_BIN_EUR;
    if (!rows.length) return { bin_width: width, bins: [] };
    var upper = Math.floor(Math.max.apply(null, pluck(rows, "price")) / width) + 1;
    var counts = new Array(upper).fill(0);
    rows.forEach(function (r) { counts[Math.floor(r.price / width)]++; }); // classes [a ; a + largeur[
    return { bin_width: width, bins: counts.map(function (c, k) { return { from: k * width, to: (k + 1) * width, offers: c }; }) };
  }

  function pricing(rows) {
    var lim = limited(rows);
    var ratios = lim.map(function (r) { return r.price / r.data_gb; });
    var tiers = Array.from(groupBy(lim, function (r) { return r.data_gb; }), function (e) {
      return { data_gb: e[0], offers: e[1].length, price_per_gb: pricePerGb(e[1]), mean_price: mean(pluck(e[1], "price")) };
    }).sort(function (a, b) { return a.data_gb - b.data_gb; });
    var byValidity = Array.from(groupBy(rows, function (r) { return r.validity_days; }), function (e) {
      return { validity_days: e[0], offers: e[1].length, mean_price: mean(pluck(e[1], "price")) };
    }).sort(function (a, b) { return a.validity_days - b.validity_days; });
    return {
      power_law: powerLaw(rows),
      histogram: priceHistogram(rows),
      price_per_gb: pricePerGb(rows),
      price_per_gb_median_of_ratios: median(ratios),
      price_per_gb_mean_of_ratios: mean(ratios),
      by_data_tier: tiers,
      by_validity: byValidity
    };
  }

  function categoryCounts(rows, f) {
    var n = rows.length;
    return Array.from(groupBy(rows, function (r) { return String(r[f]); }), function (e) {
      return { value: e[0], offers: e[1].length, share: share(e[1].length, n), mean_price: mean(pluck(e[1], "price")) };
    }).sort(function (a, b) { return b.offers - a.offers || cmp(a.value, b.value); });
  }

  // Écart de prix moyen A/B à volume et durée égaux (moyenne des ratios par segment).
  function likeForLikeRatio(rows, f, a, b) {
    var ratios = [];
    groupBy(rows, segmentKey).forEach(function (seg) {
      var pa = pluck(seg.filter(function (r) { return r[f] === a; }), "price");
      var pb = pluck(seg.filter(function (r) { return r[f] === b; }), "price");
      if (pa.length && pb.length) ratios.push(mean(pa) / mean(pb));
    });
    return ratios.length ? mean(ratios) : null;
  }

  function distributions(rows) {
    var n = rows.length, lim = limited(rows);
    var gbs = Array.from(new Set(pluck(lim, "data_gb"))).sort(function (a, b) { return a - b; });
    var tiers = gbs.map(function (g) { return { label: tierLabel(g), offers: lim.filter(function (r) { return r.data_gb === g; }).length }; });
    if (lim.length < n) tiers.push({ label: "Illimité", offers: n - lim.length });
    return {
      network: categoryCounts(rows, "network"),
      network_like_for_like_5g_vs_4g: likeForLikeRatio(rows, "network", "5G", "4G"),
      top_up: categoryCounts(rows, "top_up"),
      top_up_like_for_like_yes_vs_no: likeForLikeRatio(rows, "top_up", "oui", "non"),
      validity: Array.from(groupBy(rows, function (r) { return r.validity_days; }), function (e) {
        return { validity_days: e[0], offers: e[1].length, share: share(e[1].length, n) };
      }).sort(function (a, b) { return a.validity_days - b.validity_days; }),
      data_tiers: tiers
    };
  }

  function coverage(rows, isoNumeric) {
    isoNumeric = isoNumeric || {};
    var countries = rows.filter(function (r) { return !r.is_region; }), regions = rows.filter(function (r) { return r.is_region; });
    function ranking(d) {
      return Array.from(groupBy(d, function (r) { return r.country_code + "\u0000" + r.country_name; }), function (e) {
        var g = e[1];
        return { code: g[0].country_code, name: g[0].country_name, offers: g.length,
          providers: uniqueCount(g, "provider"), min_price: Math.min.apply(null, pluck(g, "price")) };
      }).sort(function (a, b) { return b.offers - a.offers || cmp(a.name, b.name); });
    }
    var perCountry = Array.from(groupBy(countries, function (r) { return r.country_code + "\u0000" + r.country_name; }), function (e) {
      var g = e[1];
      return { code: g[0].country_code, name: g[0].country_name, iso_numeric: isoNumeric[g[0].country_code] || null,
        offers: g.length, price_per_gb: pricePerGb(g) };
    }).sort(function (a, b) { return cmp(a.name, b.name); });
    return {
      countries_count: uniqueCount(countries, "country_code"),
      regions_count: uniqueCount(regions, "country_code"),
      top_countries: ranking(countries).slice(0, TOP_DESTINATIONS),
      regions: ranking(regions),
      countries_price_per_gb: perCountry
    };
  }

  function compute(rows, ctx) {
    ctx = ctx || {};
    return {
      headline: headline(rows),
      providers: byProvider(rows),
      provider_validity_index: providerValidityIndex(rows),
      pricing: pricing(rows),
      distributions: distributions(rows),
      coverage: coverage(rows, ctx.isoNumeric)
    };
  }

  // ---------- Mini-comparateur ----------
  // Offres pour un pays (ou une zone) et un volume ("unlimited" = illimité), triées du moins
  // cher au plus cher. Avec includeRegional, on ajoute les forfaits des zones qui couvrent le
  // pays, selon l'hypothèse de couverture documentée (zones : [{code, countries: [...] | "*"}]).
  function compare(rows, query, zones) {
    var place = query.place, volume = query.volume;
    var covering = new Set();
    if (query.includeRegional) {
      (zones || []).forEach(function (z) {
        if (z.code !== place && (z.countries === "*" || z.countries.indexOf(place) !== -1)) covering.add(z.code);
      });
    }
    return rows.filter(function (r) {
      var placeOk = r.country_code === place || covering.has(r.country_code);
      var volumeOk = volume === "unlimited" ? r.is_unlimited : (!r.is_unlimited && r.data_gb === Number(volume));
      var validityOk = !query.validity_days || r.validity_days === Number(query.validity_days);
      return placeOk && volumeOk && validityOk;
    }).map(function (r) {
      return { offer: r, regional: r.country_code !== place, price_per_gb: r.is_unlimited ? null : r.price / r.data_gb };
    }).sort(function (a, b) {
      return a.offer.price - b.offer.price || a.offer.validity_days - b.offer.validity_days ||
        cmp(a.offer.provider, b.offer.provider) || cmp(a.offer.sku, b.offer.sku);
    });
  }

  // ---------- Export CSV ----------
  // Même format que les fichiers sources (virgule, point décimal), précédé d'un BOM UTF-8
  // pour qu'Excel affiche correctement les accents. Le fichier peut être redéposé dans data/.
  function csvCell(v) {
    var s = v === null || v === undefined ? "" : String(v);
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function toCSV(rows) {
    var lines = [CSV_COLUMNS.join(",")];
    rows.forEach(function (r) { lines.push(CSV_COLUMNS.map(function (c) { return csvCell(r[c]); }).join(",")); });
    return "﻿" + lines.join("\n") + "\n";
  }

  return {
    EXPENSIVE_THRESHOLD_EUR: EXPENSIVE_THRESHOLD_EUR,
    decodeOffers: decodeOffers, applyFilters: applyFilters, compute: compute,
    compare: compare, toCSV: toCSV, tierLabel: tierLabel, median: median, quantile: quantile
  };
});
