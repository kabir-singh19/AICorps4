"""Progress figures for S1, drawn from the live database (every number comes from a query).

    .venv/bin/python make_figures.py                      # writes figures/*.png
    .venv/bin/python make_figures.py --network v0_2019

Needs the database running with crashes, network, matching and features already built
(see the README quickstart). Colors: categorical slots 1-3 and the blue sequential ramp of
the reference data-viz palette; slots 1-3 are validated colorblind-safe as a set.
"""
import argparse
import json
import math
import os

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

import ingest  # noqa: E402

# --- palette (reference instance, light mode) --------------------------------------------
SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, CONTEXT = "#e1e0d9", "#c3c2b7", "#d9d8d2"
CORRIDOR_COLOR = {"BS0006R": "#2a78d6", "FM0060": "#eb6834", "FM2154": "#1baf7a"}
CORRIDOR_NAME = {"BS0006R": "Texas Ave", "FM0060": "University Dr", "FM2154": "Wellborn Rd"}
SERIES = "#2a78d6"

SOURCE = ("Source: TxDOT CRIS crash records 2016–2025 (City of College Station); "
          "TxDOT Roadway Inventory 2019. TASC S1 database, network {net}.")

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10, "text.color": INK, "axes.labelcolor": INK_2,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "grid.color": GRID, "grid.linewidth": 0.6,
})


def q(cur, sql, params=None):
    cur.execute(sql, params or {})
    return cur.fetchall()


OSM_SOURCE = ("Source: © OpenStreetMap contributors (ODbL), history via ohsome API (HeiGIT), within 600 m "
              "of network {net}; TxDOT Roadway Inventory 2019. TASC S1 database.")


def finish(fig, path, title, subtitle, net, source=SOURCE):
    # Place title and subtitle a fixed distance (in inches) from the top, whatever the figure height.
    h = fig.get_figheight()
    fig.text(0.012, 1 - 0.18 / h, title, ha="left", va="top", fontsize=14, fontweight="bold")
    fig.text(0.012, 1 - 0.50 / h, subtitle, ha="left", va="top", fontsize=10, color=INK_2)
    fig.text(0.012, 0.012, source.format(net=net), ha="left", fontsize=7.5, color=MUTED)
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print("wrote", path)


def lines_from_geojson(rows):
    """rows of (geojson, ...) -> list of (xs, ys, rest)."""
    out = []
    for g, *rest in rows:
        geom = json.loads(g)
        parts = [geom["coordinates"]] if geom["type"] == "LineString" else geom["coordinates"]
        for part in parts:
            out.append(([p[0] for p in part], [p[1] for p in part], rest))
    return out


def map_axes(fig, rect):
    ax = fig.add_axes(rect)
    ax.set_aspect(1 / math.cos(math.radians(30.61)))
    ax.set_axis_off()
    return ax


def draw_context(ax, cur):
    rows = q(cur, """SELECT ST_AsGeoJSON(ST_Transform(geom, 4326)) FROM tasc.road
                     WHERE roadbed = 'KG' AND city_code = 9050""")
    for xs, ys, _ in lines_from_geojson(rows):
        ax.plot(xs, ys, color=CONTEXT, lw=0.5, zorder=1, solid_capstyle="round")


def segments(cur, net):
    return q(cur, """SELECT ST_AsGeoJSON(ST_Transform(s.geom, 4326)), r.route_name, r.speed_limit
                     FROM tasc.site s JOIN tasc.road r USING (road_id)
                     WHERE s.network_version = %(net)s AND s.site_type = 'segment'""", {"net": net})


# Where each corridor's direct label goes: order its segments along an axis, take the segment at
# this fraction, and offset the label to one side, clear of the intersections.
LABEL_RULE = {
    "BS0006R": ("lat", 0.45, (16, 0), "left"),       # Texas Ave: middle, to the right
    "FM0060": ("lon", 0.15, (-10, 14), "right"),     # University Dr: west end, above-left
    "FM2154": ("lat", 0.55, (-16, 0), "right"),      # Wellborn Rd: middle, to the left
}


def label_corridors(cur, net):
    """Anchor point, text offset and alignment for each corridor's direct label."""
    found = {}
    for route, (axis, frac, offset, ha) in LABEL_RULE.items():
        rows = q(cur, f"""SELECT ST_X(p), ST_Y(p) FROM (
                            SELECT ST_Transform(ST_LineInterpolatePoint(s.geom, 0.5), 4326) p
                            FROM tasc.site s JOIN tasc.road r USING (road_id)
                            WHERE s.network_version = %(net)s AND s.site_type = 'segment' AND r.route_name = %(r)s) t
                          ORDER BY ST_{'Y' if axis == 'lat' else 'X'}(p)""", {"net": net, "r": route})
        found[route] = (rows[int(frac * (len(rows) - 1))], offset, ha)
    return found


def zoom_to_network(ax, cur, net, pad=0.006):
    xmin, ymin, xmax, ymax = q(cur, """SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e) FROM (
                                         SELECT ST_Extent(ST_Transform(geom, 4326))::geometry e FROM tasc.site
                                         WHERE network_version = %(net)s) t""", {"net": net})[0]
    ax.set_xlim(xmin - pad * 1.6, xmax + pad * 1.6)
    ax.set_ylim(ymin - pad, ymax + pad)


# --- figure 1: network and crashes --------------------------------------------------------
def fig_network(cur, net, out):
    fig = plt.figure(figsize=(10, 8.6))
    ax = map_axes(fig, [0.01, 0.05, 0.98, 0.83])
    draw_context(ax, cur)
    for xs, ys, (route, _) in lines_from_geojson(segments(cur, net)):
        ax.plot(xs, ys, color=CORRIDOR_COLOR[route], lw=3.2, zorder=3, solid_capstyle="butt")
    crashes = q(cur, """SELECT c.lon, c.lat, c.is_fsi FROM tasc.crash_match m JOIN tasc.crash c USING (crash_id)
                        WHERE m.network_version = %(net)s AND m.status = 'matched'""", {"net": net})
    other = [(x, y) for x, y, f in crashes if not f]
    fsi = [(x, y) for x, y, f in crashes if f]
    ax.scatter(*zip(*other), s=4, color=INK_2, alpha=0.25, lw=0, zorder=4)
    ax.scatter(*zip(*fsi), s=16, color=INK, edgecolor=SURFACE, linewidth=0.8, zorder=6)
    inter = q(cur, """SELECT ST_X(ST_Transform(geom, 4326)), ST_Y(ST_Transform(geom, 4326)) FROM tasc.site
                      WHERE network_version = %(net)s AND site_type = 'intersection'""", {"net": net})
    ax.scatter(*zip(*inter), s=150, facecolor="none", edgecolor=INK, linewidth=1.6, zorder=7)

    stats = {r[0]: r[1:] for r in q(cur, """
        SELECT r.route_name, count(DISTINCT s.site_id), sum(DISTINCT s.length_m) FILTER (WHERE true)
        FROM tasc.site s JOIN tasc.road r USING (road_id)
        WHERE s.network_version = %(net)s AND s.site_type = 'segment' GROUP BY 1""", {"net": net})}
    miles = {r[0]: r[1] for r in q(cur, """
        SELECT r.route_name, sum(s.length_m) / 1609.344 FROM tasc.site s JOIN tasc.road r USING (road_id)
        WHERE s.network_version = %(net)s AND s.site_type = 'segment' GROUP BY 1""", {"net": net})}
    for route, ((x, y), offset, ha) in label_corridors(cur, net).items():
        ax.annotate(f"{CORRIDOR_NAME[route]}\n{miles[route]:.1f} mi · {stats[route][0]} segments",
                    (x, y), xytext=offset, textcoords="offset points", fontsize=9.5,
                    fontweight="bold", color=INK, va="center", ha=ha,
                    bbox=dict(boxstyle="round,pad=0.3", fc=SURFACE, ec=CORRIDOR_COLOR[route], lw=1.4), zorder=8)
    zoom_to_network(ax, cur, net)

    n_seg = sum(v[0] for v in stats.values())
    handles = [Line2D([], [], color=CORRIDOR_COLOR[r], lw=3.2, label=CORRIDOR_NAME[r]) for r in CORRIDOR_NAME]
    handles += [
        Line2D([], [], color=CONTEXT, lw=1.2, label="Other College Station roads"),
        Line2D([], [], marker="o", ls="", color=INK_2, alpha=0.5, ms=3, label=f"Crash ({len(other):,})"),
        Line2D([], [], marker="o", ls="", color=INK, mec=SURFACE, ms=6.5, label=f"Fatal or serious injury ({len(fsi)})"),
        Line2D([], [], marker="o", ls="", mfc="none", mec=INK, ms=10, label=f"Intersection ({len(inter)})"),
    ]
    ax.legend(handles=handles, loc="lower left", frameon=True, facecolor=SURFACE, edgecolor=GRID, fontsize=9)
    finish(fig, os.path.join(out, "fig1_network_and_crashes.png"),
           "Three-corridor road network with matched crashes",
           f"{sum(miles.values()):.1f} miles cut into {n_seg} segments of about 0.1 mi; "
           f"{len(crashes):,} crashes from 2016–2025 placed on the network.", net)


# --- figure 2: crashes per year -----------------------------------------------------------
def fig_by_year(cur, net, out):
    rows = q(cur, """SELECT c.crash_year, count(*), count(*) FILTER (WHERE c.is_fsi)
                     FROM tasc.crash c JOIN tasc.corridor_street cs ON cs.street_name = upper(trim(c.street_name))
                     GROUP BY 1 ORDER BY 1""")
    years = [r[0] for r in rows]
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.6), sharex=True,
                             gridspec_kw=dict(height_ratios=[1.4, 1], hspace=0.35))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.82, bottom=0.1)
    for ax, idx, label in ((axes[0], 1, "All crashes on the three corridors"),
                           (axes[1], 2, "Fatal or serious injury (K + A)")):
        vals = [r[idx] for r in rows]
        ax.axvspan(2022.5, max(years) + 0.5, color="#f0efec", zorder=0)
        ax.bar(years, vals, width=0.72, color=SERIES, zorder=2)
        ax.set_title(label, color=INK, pad=8)
        ax.yaxis.grid(True, zorder=1)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        for y, v in zip(years, vals):
            ax.text(y, v, f"{v:,}", ha="center", va="bottom", fontsize=8, color=INK_2,
                    transform=ax.transData, clip_on=False).set_y(v + max(vals) * 0.015)
        ax.set_ylim(0, max(vals) * 1.15)
    axes[0].text(2019.5, axes[0].get_ylim()[1], "Training: 2016–2022", ha="center", va="top", fontsize=9, color=INK_2)
    axes[0].text(2024, axes[0].get_ylim()[1], "Backtest test window: 2023–2025", ha="center", va="top",
                 fontsize=9, color=INK_2)
    axes[1].set_xticks(years)
    train = sum(r[2] for r in rows if r[0] <= 2022)
    test = sum(r[2] for r in rows if r[0] >= 2023)
    test_geo = q(cur, """SELECT count(*) FROM tasc.crash c
                         JOIN tasc.corridor_street cs ON cs.street_name = upper(trim(c.street_name))
                         WHERE c.is_fsi AND c.crash_year >= 2023 AND c.geom IS NOT NULL""")[0][0]
    finish(fig, os.path.join(out, "fig2_crashes_by_year.png"),
           "Corridor crashes per year, 2016–2025",
           f"{sum(r[1] for r in rows):,} crashes on Texas Ave, University Dr and Wellborn Rd; "
           f"{train} fatal or serious in training years, {test} in the backtest window ({test_geo} with coordinates). "
           f"The 2020 dip coincides with COVID-19.", net)


# --- figure 3: map-matching evidence ------------------------------------------------------
def fig_matching(cur, net, out):
    rates = q(cur, """
        SELECT p, count(*) FILTER (WHERE c.is_fsi AND m.status = 'matched'),
                  count(*) FILTER (WHERE c.is_fsi AND c.geom IS NOT NULL)
        FROM tasc.crash_match m JOIN tasc.crash c USING (crash_id)
        CROSS JOIN LATERAL (VALUES (CASE WHEN c.crash_year <= 2022 THEN '2016–2022\n(training)'
                                         ELSE '2023–2025\n(backtest)' END), ('All years')) v(p)
        WHERE m.network_version = %(net)s AND m.reason IS DISTINCT FROM 'off_corridor'
        GROUP BY p ORDER BY p""", {"net": net})
    # Only crashes measured against a segment: inside an intersection zone the distance is to the
    # intersection point, not to the road line, so it says nothing about how close CRIS puts a crash.
    dist = sorted(max(r[0], 0.01) for r in q(cur, """
        SELECT m.distance_m FROM tasc.crash_match m JOIN tasc.site s ON s.site_id = m.nearest_site_id
        WHERE m.network_version = %(net)s AND m.distance_m IS NOT NULL AND s.site_type = 'segment'
          AND m.reason IS DISTINCT FROM 'off_corridor'""", {"net": net}))
    tol = q(cur, "SELECT max(tolerance_m) FROM tasc.crash_match WHERE network_version = %(net)s", {"net": net})[0][0]

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 5.2), gridspec_kw=dict(width_ratios=[1, 1.35], wspace=0.28))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.8, bottom=0.14)

    labels = [r[0] for r in rates]
    pct = [100 * r[1] / r[2] for r in rates]
    a.bar(labels, pct, width=0.6, color=SERIES, zorder=2)
    a.axhline(95, color=INK, lw=1.2, ls=(0, (4, 3)), zorder=3)
    a.text(-0.42, 95.25, "FSR target 95%", ha="left", va="bottom", fontsize=9, color=INK,
           bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec="none"), zorder=4)
    for i, r in enumerate(rates):
        a.text(i, pct[i] + 0.3, f"{pct[i]:.1f}%\n{r[1]}/{r[2]}", ha="center", va="bottom", fontsize=9, color=INK)
    a.set_ylim(85, 102)
    a.set_ylabel("Fatal + serious crashes matched (%)")
    a.set_title("Match rate vs the FSR target", pad=10)
    a.yaxis.grid(True, zorder=1)
    a.set_axisbelow(True)

    n = len(dist)
    share = [100 * (i + 1) / n for i in range(n)]
    b.plot(dist, share, color=SERIES, lw=2, zorder=3)
    b.set_xscale("log")
    b.set_xlim(0.05, 2000)
    b.set_ylim(0, 102)
    med = dist[n // 2]
    p95 = dist[int(0.95 * (n - 1))]
    b.axvline(med, color=MUTED, lw=0.8, zorder=2)
    b.text(med / 1.12, 8, f"median\n{med:.1f} m", fontsize=9, color=INK_2, ha="right")
    b.axvline(p95, color=MUTED, lw=0.8, zorder=2)
    b.text(p95 * 1.12, 8, f"95% within\n{p95:.1f} m", fontsize=9, color=INK_2, ha="left")
    b.axvline(tol, color=INK, lw=1.2, ls=(0, (4, 3)), zorder=2)
    b.text(tol * 1.12, 40, f"match tolerance\n{tol:.1f} m (150 ft)", fontsize=9, color=INK)
    b.set_xlabel("Distance from crash to its nearest corridor site (m, log scale)")
    b.set_ylabel("Corridor crashes within that distance (%)")
    b.set_title("How close CRIS places corridor crashes to the road", pad=10)
    b.grid(True, which="major", zorder=1)
    b.set_axisbelow(True)
    finish(fig, os.path.join(out, "fig3_map_matching.png"),
           "Map-matching meets the 95% requirement",
           f"Left: fatal and serious crashes CRIS records on a corridor, matched to that corridor's sites. "
           f"Right: all {n:,} geocoded corridor crashes outside the intersection zones.", net)


# --- figure 4: speed limit (feature table) ------------------------------------------------
def fig_speed(cur, net, out):
    rows = q(cur, """SELECT ST_AsGeoJSON(ST_Transform(s.geom, 4326)), f.value_num
                     FROM tasc.site s JOIN tasc.site_feature f USING (site_id)
                     WHERE s.network_version = %(net)s AND f.feature_set = 'backtest_2022'
                       AND f.feature_name = 'speed_limit'""", {"net": net})
    # Four bands, so each shade is easy to tell apart (steps 250 / 400 / 550 / 700 of the blue ramp).
    bands = [(35, 40, "#86b6ef"), (45, 50, "#3987e5"), (55, 60, "#1c5cab"), (65, 70, "#0d366b")]

    def band(sp):
        return next(b for b in bands if b[0] <= sp <= b[1])

    fig = plt.figure(figsize=(10, 8.6))
    ax = map_axes(fig, [0.01, 0.05, 0.98, 0.83])
    draw_context(ax, cur)
    for xs, ys, (sp,) in lines_from_geojson(rows):
        ax.plot(xs, ys, color=band(int(sp))[2], lw=4, zorder=3, solid_capstyle="butt")
    for route, ((x, y), offset, ha) in label_corridors(cur, net).items():
        ax.annotate(CORRIDOR_NAME[route], (x, y), xytext=offset, textcoords="offset points", fontsize=9.5,
                    fontweight="bold", color=INK, va="center", ha=ha,
                    bbox=dict(boxstyle="round,pad=0.3", fc=SURFACE, ec=GRID, lw=1), zorder=8)
    zoom_to_network(ax, cur, net)
    handles = []
    for lo, hi, c in bands:
        n = sum(1 for r in rows if lo <= int(r[1]) <= hi)
        handles.append(Line2D([], [], color=c, lw=4, label=f"{lo}–{hi} mph  ({n} segments)"))
    ax.legend(handles=handles, title="Posted speed limit", loc="lower left", frameon=True,
              facecolor=SURFACE, edgecolor=GRID, fontsize=9, title_fontsize=9.5)
    n_feat, n_vals, as_of = q(cur, """
        SELECT count(DISTINCT f.feature_name), count(*), max(f.as_of_date)
        FROM tasc.site_feature f JOIN tasc.site s USING (site_id)
        WHERE s.network_version = %(net)s AND f.feature_set = 'backtest_2022' AND s.site_type = 'segment'""",
        {"net": net})[0]
    finish(fig, os.path.join(out, "fig4_speed_limit_feature.png"),
           "Feature table: posted speed limit on each segment",
           f"Speed limit is one of {n_feat} features stored for every segment ({n_vals:,} values), "
           f"all dated {as_of} and checked against the 2022 leakage cutoff.", net)


# --- figure 5: data funnel ----------------------------------------------------------------
def fig_funnel(cur, net, out):
    r = q(cur, """
        SELECT count(*), count(*) FILTER (WHERE m.reason IS DISTINCT FROM 'off_corridor'),
               count(*) FILTER (WHERE m.reason IS DISTINCT FROM 'off_corridor' AND c.geom IS NOT NULL),
               count(*) FILTER (WHERE m.status = 'matched'),
               count(*) FILTER (WHERE c.is_fsi),
               count(*) FILTER (WHERE c.is_fsi AND m.reason IS DISTINCT FROM 'off_corridor'),
               count(*) FILTER (WHERE c.is_fsi AND m.reason IS DISTINCT FROM 'off_corridor' AND c.geom IS NOT NULL),
               count(*) FILTER (WHERE c.is_fsi AND m.status = 'matched')
        FROM tasc.crash_match m JOIN tasc.crash c USING (crash_id) WHERE m.network_version = %(net)s""",
          {"net": net})[0]
    stages = ["Loaded from CRIS\n(College Station, 2016–2025)", "Recorded on the\nthree corridors",
              "With coordinates", "Matched to a site"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True, gridspec_kw=dict(wspace=0.12))
    fig.subplots_adjust(left=0.2, right=0.97, top=0.76, bottom=0.12)
    for ax, vals, title in ((axes[0], r[0:4], "All crashes"), (axes[1], r[4:8], "Fatal or serious injury")):
        y = list(range(len(stages)))[::-1]
        ax.barh(y, vals, height=0.62, color=SERIES, zorder=2)
        for yi, v in zip(y, vals):
            ax.text(v + max(vals) * 0.015, yi, f"{v:,}", va="center", fontsize=9.5, color=INK)
        ax.set_xlim(0, max(vals) * 1.18)
        ax.xaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
        ax.set_title(title, pad=8)
        ax.xaxis.grid(True, zorder=1)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(range(len(stages))[::-1], stages)
    finish(fig, os.path.join(out, "fig5_data_funnel.png"),
           "From raw CRIS records to crashes on the network",
           "Every crash keeps a row with a reason: off corridor, no coordinates, or outside the match tolerance.",
           net)


# --- figure 6: OSM growth near the corridors, 2022 vs latest -------------------------------
OSM_GROUP_LABEL = {"crossing": "Marked crossings", "major_road": "Major-road pieces", "sidewalk": "Sidewalk lines",
                   "restaurant": "Restaurants / cafés", "signalized_intersection": "Signalized intersections",
                   "bus_stop": "Bus stops",
                   "street_lamp": "Street lamps", "bar": "Bars / pubs", "school": "Schools"}
OLD, NEW = "#86b6ef", "#1c5cab"      # blue ramp steps 250 and 550: earlier lighter, later darker


def signal_intersections(cur, source):
    """Traffic-signal points merged within 50 m: one per signalized intersection (as in 06_osm_features.sql)."""
    return q(cur, """SELECT count(DISTINCT cid) FROM (
                         SELECT ST_ClusterDBSCAN(geom, 50, 1) OVER () AS cid FROM tasc.osm_feature
                         WHERE source = %(s)s AND grp = 'traffic_signals') t""", {"s": source})[0][0]


def osm_dates(cur):
    return {s: d.isoformat() for s, d in q(cur, "SELECT source, max(snapshot_date) FROM tasc.osm_feature GROUP BY 1")}


def fig_osm_growth(cur, net, out):
    rows = q(cur, """SELECT grp, count(*) FILTER (WHERE source = 'osm_2022-12-31'),
                            count(*) FILTER (WHERE source = 'osm_latest')
                     FROM tasc.osm_feature GROUP BY grp""")
    # Signals: count intersections, not points (OSM often draws one point per approach).
    rows = [("signalized_intersection", signal_intersections(cur, "osm_2022-12-31"),
             signal_intersections(cur, "osm_latest")) if r[0] == "traffic_signals" else r for r in rows]
    rows.sort(key=lambda r: -r[2])
    dates = osm_dates(cur)
    old_d, new_d = dates["osm_2022-12-31"], dates["osm_latest"]
    labels = [OSM_GROUP_LABEL.get(r[0], r[0]) for r in rows][::-1]
    a = [r[1] for r in rows][::-1]
    b = [r[2] for r in rows][::-1]
    fig, ax = plt.subplots(figsize=(10, 6.2))
    fig.subplots_adjust(left=0.2, right=0.95, top=0.8, bottom=0.12)
    y = range(len(rows))
    h = 0.36
    ax.barh([i + h / 2 + 0.02 for i in y], a, height=h, color=OLD, label=f"As of {old_d} (backtest)", zorder=2)
    ax.barh([i - h / 2 - 0.02 for i in y], b, height=h, color=NEW, label=f"As of {new_d} (latest)", zorder=2)
    for i, (va, vb) in enumerate(zip(a, b)):
        ax.text(va + 8, i + h / 2 + 0.02, f"{va:,}", va="center", fontsize=8.5, color=INK_2)
        growth = f"  ({vb / va:.1f}×)" if va else ""
        ax.text(vb + 8, i - h / 2 - 0.02, f"{vb:,}{growth}", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(list(y), labels)
    ax.set_xlim(0, max(b) * 1.22)
    ax.xaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
    ax.xaxis.grid(True, zorder=1)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("OSM features within 600 m of the corridors")
    ax.legend(loc="lower right", frameon=False, fontsize=9.5)
    tot_a, tot_b = sum(a), sum(b)
    finish(fig, os.path.join(out, "fig6_osm_2022_vs_latest.png"),
           "OpenStreetMap near the corridors grew a lot after 2022",
           f"{tot_a:,} features mapped by {old_d} vs {tot_b:,} by {new_d}. The backtest may only use the "
           f"{old_d[:4]} map, so many of its zeros mean 'not mapped yet'.", net, OSM_SOURCE)


# --- figure 7: OSM sidewalks, crossings and signals on the map, 2022 vs latest ----------------
def fig_osm_maps(cur, net, out):
    dates = osm_dates(cur)
    fig = plt.figure(figsize=(13, 7.6))
    panels = (("osm_2022-12-31", [0.005, 0.07, 0.49, 0.75]), ("osm_latest", [0.505, 0.07, 0.49, 0.75]))
    styles = {"sidewalk": ("#2a78d6", "Sidewalk line"), "crossing": ("#eb6834", "Marked crossing"),
              "traffic_signals": (INK, "Traffic signal")}
    for source, rect in panels:
        ax = map_axes(fig, rect)
        draw_context(ax, cur)
        for xs, ys, _ in lines_from_geojson(segments(cur, net)):
            ax.plot(xs, ys, color="#9a9890", lw=2.2, zorder=2, solid_capstyle="butt")
        sw = q(cur, """SELECT ST_AsGeoJSON(ST_Transform(geom, 4326)) FROM tasc.osm_feature
                       WHERE source = %(s)s AND grp = 'sidewalk'""", {"s": source})
        for xs, ys, _ in lines_from_geojson(sw):
            ax.plot(xs, ys, color=styles["sidewalk"][0], lw=0.9, zorder=3)
        counts = {"sidewalk": len(sw)}
        for grp, size in (("crossing", 9), ("traffic_signals", 14)):
            pts = q(cur, """SELECT ST_X(ST_Transform(geom, 4326)), ST_Y(ST_Transform(geom, 4326))
                            FROM tasc.osm_feature WHERE source = %(s)s AND grp = %(g)s""", {"s": source, "g": grp})
            counts[grp] = len(pts)
            if pts:
                ax.scatter(*zip(*pts), s=size, color=styles[grp][0], edgecolor=SURFACE, linewidth=0.5,
                           zorder=5 if grp == "traffic_signals" else 4)
        zoom_to_network(ax, cur, net)
        ax.set_title(f"As of {dates[source]}" + (" (backtest)" if source != "osm_latest" else " (latest)"),
                     loc="left", fontsize=12, pad=4)
        handles = [Line2D([], [], color=styles["sidewalk"][0], lw=1.5, label=f"Sidewalk lines ({counts['sidewalk']})"),
                   Line2D([], [], marker="o", ls="", color=styles["crossing"][0], ms=4,
                          label=f"Marked crossings ({counts['crossing']})"),
                   Line2D([], [], marker="o", ls="", color=INK, mec=SURFACE, ms=5,
                          label=f"Traffic signal points ({counts['traffic_signals']}) = "
                                f"{signal_intersections(cur, source)} intersections"),
                   Line2D([], [], color="#9a9890", lw=2.2, label="Corridor network")]
        ax.legend(handles=handles, loc="lower left", frameon=True, facecolor=SURFACE, edgecolor=GRID, fontsize=8.5)
    finish(fig, os.path.join(out, "fig7_osm_maps_2022_vs_latest.png"),
           "Pedestrian infrastructure mapped in OpenStreetMap, then and now",
           "The same 600 m band around Texas Ave, University Dr and Wellborn Rd. "
           "Left feeds the backtest features; right feeds the live ranking.", net, OSM_SOURCE)


# --- figure 8: crash conditions (new CRIS columns) ------------------------------------------
def fig_conditions(cur, net, out):
    base = """FROM tasc.crash c JOIN tasc.crash_match m USING (crash_id)
              WHERE m.network_version = %(net)s AND m.status = 'matched'"""
    panels = [
        ("Weather", "regexp_replace(c.weather_condition, '^[0-9]+ - ', '')"),
        ("Road surface", "regexp_replace(c.surface_condition, '^[0-9]+ - ', '')"),
        ("Location", "initcap(lower(c.intersection_related))"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13, 5.4), gridspec_kw=dict(wspace=0.55))
    fig.subplots_adjust(left=0.1, right=0.98, top=0.76, bottom=0.12)
    n_all, n_fsi = q(cur, f"SELECT count(*), count(*) FILTER (WHERE c.is_fsi) {base}", {"net": net})[0]
    for ax, (title, expr) in zip(axes, panels):
        rows = q(cur, f"""SELECT {expr} AS v, count(*), count(*) FILTER (WHERE c.is_fsi) {base}
                          GROUP BY 1 ORDER BY 2 DESC""", {"net": net})
        top = rows[:4]
        if len(rows) > 4:     # fold the rest into "Other" rather than add more bars
            top.append(("Other / unknown", sum(r[1] for r in rows[4:]), sum(r[2] for r in rows[4:])))
        labels = [str(r[0]).capitalize() if r[0] else "Not recorded" for r in top][::-1]
        pa = [100 * r[1] / n_all for r in top][::-1]
        pf = [100 * r[2] / n_fsi for r in top][::-1]
        y = range(len(top))
        h = 0.36
        ax.barh([i + h / 2 + 0.02 for i in y], pa, height=h, color="#2a78d6", label=f"All crashes ({n_all:,})", zorder=2)
        ax.barh([i - h / 2 - 0.02 for i in y], pf, height=h, color="#eb6834",
                label=f"Fatal or serious ({n_fsi})", zorder=2)
        for i, (a, f) in enumerate(zip(pa, pf)):
            ax.text(a + 1, i + h / 2 + 0.02, f"{a:.0f}%", va="center", fontsize=8.5, color=INK_2)
            ax.text(f + 1, i - h / 2 - 0.02, f"{f:.0f}%", va="center", fontsize=8.5, color=INK)
        ax.set_yticks(list(y), labels)
        ax.set_xlim(0, 100)
        ax.set_title(title, pad=8)
        ax.xaxis.grid(True, zorder=1)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.set_xlabel("Share of crashes (%)")
    axes[0].legend(loc="lower right", frameon=False, fontsize=9)
    finish(fig, os.path.join(out, "fig8_crash_conditions.png"),
           "Conditions at the time of crash, from the new CRIS columns",
           f"Crashes matched to the three corridors, 2016–2025. Stored on each crash (not as road features): "
           f"weather, surface and location type.", net)


# --- figure 9: officer-recorded speed vs TxDOT speed (data cross-check) -----------------------
def fig_speed_check(cur, net, out):
    rows = q(cur, """SELECT r.speed_limit, c.speed_limit_reported, count(*)
                     FROM tasc.crash c JOIN tasc.crash_match m USING (crash_id)
                     JOIN tasc.site s ON s.site_id = m.site_id JOIN tasc.road r ON r.road_id = s.road_id
                     WHERE m.network_version = %(net)s AND m.status = 'matched' AND s.site_type = 'segment'
                       AND c.speed_limit_reported IS NOT NULL
                     GROUP BY 1, 2""", {"net": net})
    txdot = sorted({r[0] for r in rows})
    reported = sorted({r[1] for r in rows if r[1] >= 25})        # below 25 mph: a handful of oddities
    grid = {(r[0], r[1]): r[2] for r in rows}
    total = sum(r[2] for r in rows)
    same = sum(v for (a, b), v in grid.items() if a == b)
    within5 = sum(v for (a, b), v in grid.items() if abs(a - b) <= 5)
    shown = sum(grid.get((a, b), 0) for a in txdot for b in reported)

    fig, ax = plt.subplots(figsize=(9, 7.4))
    fig.subplots_adjust(left=0.13, right=0.97, top=0.82, bottom=0.11)
    vmax = max(grid.values())
    ramp = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
    for xi, a in enumerate(txdot):
        for yi, b in enumerate(reported):
            v = grid.get((a, b), 0)
            if not v:
                continue
            color = ramp[min(len(ramp) - 1, int(len(ramp) * math.log1p(v) / math.log1p(vmax)))]
            ax.add_patch(plt.Rectangle((xi - 0.46, yi - 0.46), 0.92, 0.92, color=color, zorder=2,
                                       ec=INK if a == b else "none", lw=1.4 if a == b else 0))
            ax.text(xi, yi, f"{v:,}", ha="center", va="center", fontsize=8,
                    color=SURFACE if ramp.index(color) >= 3 else INK, zorder=3)
    ax.set_xlim(-0.6, len(txdot) - 0.4)
    ax.set_ylim(-0.6, len(reported) - 0.4)
    ax.set_xticks(range(len(txdot)), [f"{s}" for s in txdot])
    ax.set_yticks(range(len(reported)), [f"{s}" for s in reported])
    ax.set_xlabel("TxDOT 2019 inventory speed limit on the segment (mph)")
    ax.set_ylabel("Speed limit the officer recorded (mph)")
    ax.tick_params(length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.text(len(txdot) - 0.45, -0.55, "outlined cells: the two sources agree", ha="right", va="bottom",
            fontsize=8.5, color=INK_2)
    finish(fig, os.path.join(out, "fig9_speed_cross_check.png"),
           "Cross-check: officer-recorded speed vs TxDOT speed",
           f"{100 * same / total:.1f}% of {total:,} matched segment crashes agree exactly, "
           f"{100 * within5 / total:.0f}% within 5 mph. Grid shows {shown:,} (reported speeds of 25 mph and up).", net)


# --- figure 10: what the model sees, mile by mile along each corridor ------------------------
STRIP_ROWS = [  # (label, feature name or history key, format of the range text)
    ("Speed limit (mph)",                 "speed_limit",                       "{:.0f}"),
    ("Lanes",                             "num_lanes",                         "{:.0f}"),
    ("Traffic (AADT, vehicles/day)",      "aadt",                              "{:,.0f}"),
    ("Marked crossings, 30 m",            "osm_crossings_30m",                 "{:.0f}"),
    ("Signalized intersections, 30 m",    "osm_signalized_intersections_30m",  "{:.0f}"),
    ("Sidewalk share",                    "osm_sidewalk_share",                "{:.0%}"),
    ("Schools, 400 m",                    "osm_schools_400m",                  "{:.0f}"),
    ("Restaurants / cafés, 100 m",        "osm_restaurants_100m",              "{:.0f}"),
    ("Bars / pubs, 200 m",                "osm_bars_200m",                     "{:.0f}"),
    ("Crashes 2016–2022",                 "hist_crashes",                      "{:.0f}"),
    ("Fatal + serious 2016–2022",         "hist_fsi",                          "{:.0f}"),
]
# Travel order per corridor: University Dr west to east; Texas Ave and Wellborn Rd north to south.
STRIP_ORDER = {"FM0060": ("x", 1), "BS0006R": ("y", -1), "FM2154": ("y", -1)}


def corridor_strips(cur, net):
    """Per route: segments in travel order with position (mi), length (mi) and a value per row."""
    import numpy as np
    rows = q(cur, """
        SELECT s.site_id, r.route_name, s.length_m,
               ST_X(ST_LineInterpolatePoint(s.geom, 0.5)), ST_Y(ST_LineInterpolatePoint(s.geom, 0.5))
        FROM tasc.site s JOIN tasc.road r USING (road_id)
        WHERE s.network_version = %(net)s AND s.site_type = 'segment'""", {"net": net})
    values = {}
    for sid, name, v in q(cur, """
            SELECT f.site_id, f.feature_name, f.value_num FROM tasc.site_feature f JOIN tasc.site s USING (site_id)
            WHERE s.network_version = %(net)s AND f.feature_set = 'backtest_2022' AND f.value_num IS NOT NULL""",
            {"net": net}):
        values[(sid, name)] = v
    for sid, n, fsi in q(cur, """
            SELECT m.site_id, count(*), count(*) FILTER (WHERE c.is_fsi)
            FROM tasc.crash_match m JOIN tasc.crash c USING (crash_id)
            WHERE m.network_version = %(net)s AND m.status = 'matched' AND c.crash_year BETWEEN 2016 AND 2022
            GROUP BY 1""", {"net": net}):
        values[(sid, "hist_crashes")], values[(sid, "hist_fsi")] = n, fsi
    strips = {}
    for route, (axis, sign) in STRIP_ORDER.items():
        segs = sorted((r for r in rows if r[1] == route), key=lambda r: sign * (r[3] if axis == "x" else r[4]))
        out, pos = [], 0.0
        for i, (sid, _, length_m, x, y) in enumerate(segs):
            if i:   # keep real gaps (Wellborn has a short stretch outside the city): midpoint distance minus half-lengths
                px, py, plen = segs[i - 1][3], segs[i - 1][4], segs[i - 1][2]
                gap = math.hypot(x - px, y - py) - (plen + length_m) / 2
                pos += max(gap, 0) / 1609.344 if gap > 50 else 0
            row_vals = {key: values.get((sid, key), 0 if key.startswith("hist") else None) for _, key, _ in STRIP_ROWS}
            out.append((sid, pos, length_m / 1609.344, row_vals, (x, y)))
            pos += length_m / 1609.344
        strips[route] = out
    return strips


def fig_feature_strips(cur, net, out):
    from matplotlib.colors import LinearSegmentedColormap
    strips = corridor_strips(cur, net)
    cmap = LinearSegmentedColormap.from_list("seq", ["#eef4fc", "#9ec5f4", "#3987e5", "#184f95", "#0d366b"])
    ranges = {}
    for _, key, _ in STRIP_ROWS:
        vals = [s[3][key] for segs in strips.values() for s in segs if s[3][key] is not None]
        ranges[key] = (min(vals), max(vals))
    inter = q(cur, """SELECT ST_X(geom), ST_Y(geom) FROM tasc.site
                      WHERE network_version = %(net)s AND site_type = 'intersection'""", {"net": net})
    max_len = max(segs[-1][1] + segs[-1][2] for segs in strips.values())

    n_rows = len(STRIP_ROWS)
    fig, axes = plt.subplots(3, 1, figsize=(13, 13.5), gridspec_kw=dict(hspace=0.42))
    fig.subplots_adjust(left=0.2, right=0.9, top=0.89, bottom=0.07)
    for ax, (route, segs) in zip(axes, strips.items()):
        for r, (label, key, fmt) in enumerate(STRIP_ROWS):
            lo, hi = ranges[key]
            y = n_rows - 1 - r
            for _, pos, length, vals, _ in segs:
                v = vals[key]
                color = "#f0efec" if v is None else cmap(0 if hi == lo else (v - lo) / (hi - lo))
                ax.add_patch(plt.Rectangle((pos, y - 0.42), length, 0.84, color=color, lw=0, zorder=2))
            if ax is axes[0]:
                ax.text(max_len * 1.01, y, f"{fmt.format(lo)}–{fmt.format(hi)}", va="center", fontsize=8,
                        color=MUTED, clip_on=False)
        # Light divider between the road/OSM inputs and the crash history rows.
        ax.axhline(1.5, color=SURFACE, lw=3, zorder=3)
        for ix, iy in inter:   # where another corridor crosses this one
            near = min(segs, key=lambda s: math.hypot(s[4][0] - ix, s[4][1] - iy))
            if math.hypot(near[4][0] - ix, near[4][1] - iy) < 200:
                x = near[1] + near[2] / 2
                ax.axvline(x, color=INK, lw=1, ls=(0, (3, 2)), zorder=4)
                others = [n for r2, n in CORRIDOR_NAME.items() if r2 != route and
                          any(math.hypot(s[4][0] - ix, s[4][1] - iy) < 200 for s in strips[r2])]
                ax.text(x, n_rows - 0.35, " × " + " & ".join(others), fontsize=8.5, color=INK, va="bottom", zorder=5)
        length = sum(sg[2] for sg in segs)        # road length only; drawn gaps are not road
        ends = {"FM0060": ("west", "east"), "BS0006R": ("north", "south"), "FM2154": ("north", "south")}[route]
        gap_note = ", gap = stretch outside city limits" if segs[-1][1] + segs[-1][2] - length > 0.05 else ""
        ax.set_title(f"{CORRIDOR_NAME[route]}  ·  {len(segs)} segments, {length:.1f} mi "
                     f"({ends[0]} to {ends[1]}{gap_note})", pad=16)
        ax.set_xlim(0, max_len)
        ax.set_ylim(-0.6, n_rows - 0.4)
        ax.set_yticks(range(n_rows), [lab for lab, _, _ in STRIP_ROWS][::-1], fontsize=9)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.set_xlabel("Miles along the corridor", fontsize=9)
    axes[0].text(max_len * 1.01, n_rows - 0.4, "range\n(all corridors)", fontsize=8, color=MUTED, va="bottom",
                 clip_on=False)
    finish(fig, os.path.join(out, "fig10_feature_strips.png"),
           "What the model sees: every input, segment by segment",
           "Each cell is one 0.1-mile segment; darker = higher, on one scale per row shared by all three corridors. "
           "Inputs are dated by 2022-12-31 (feature set backtest_2022); grey = not recorded.", net,
           "Source: TxDOT Roadway Inventory 2019; © OpenStreetMap contributors as of 2022-12-31 (ohsome API); "
           "TxDOT CRIS 2016–2022. TASC S1 database, network {net}.")


# --- figure 11: data lineage, from sources to what other subsystems read ---------------------
def fig_lineage(cur, net, out):
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    one = lambda sql: q(cur, sql, {"net": net})[0][0]   # noqa: E731
    n = {
        "crash": one("SELECT count(*) FROM tasc.crash"),
        "fsi": one("SELECT count(*) FROM tasc.crash WHERE is_fsi"),
        "road": one("SELECT count(*) FROM tasc.road"),
        "osm22": one("SELECT count(*) FROM tasc.osm_feature WHERE source = 'osm_2022-12-31'"),
        "osm_new": one("SELECT count(*) FROM tasc.osm_feature WHERE source = 'osm_latest'"),
        "seg": one("SELECT count(*) FROM tasc.site WHERE network_version = %(net)s AND site_type = 'segment'"),
        "int": one("SELECT count(*) FROM tasc.site WHERE network_version = %(net)s AND site_type = 'intersection'"),
        "miles": one("SELECT sum(length_m) / 1609.344 FROM tasc.site WHERE network_version = %(net)s"),
        "matched": one("SELECT count(*) FROM tasc.crash_match WHERE network_version = %(net)s AND status = 'matched'"),
        "match_pct": one("SELECT fsi_match_pct FROM tasc.match_rate WHERE network_version = %(net)s"),
        "feat_bt": one("""SELECT count(DISTINCT feature_name) FROM tasc.site_feature f JOIN tasc.site s USING (site_id)
                          WHERE s.network_version = %(net)s AND f.feature_set = 'backtest_2022'"""),
        "feat_vals": one("""SELECT count(*) FROM tasc.site_feature f JOIN tasc.site s USING (site_id)
                            WHERE s.network_version = %(net)s AND f.feature_set = 'backtest_2022'"""),
        "feat_cur": one("""SELECT count(DISTINCT feature_name) FROM tasc.site_feature f JOIN tasc.site s USING (site_id)
                           WHERE s.network_version = %(net)s AND f.feature_set = 'current'"""),
        "osm22_date": one("SELECT max(snapshot_date) FROM tasc.osm_feature WHERE source = 'osm_2022-12-31'"),
        "osm_new_date": one("SELECT max(snapshot_date) FROM tasc.osm_feature WHERE source = 'osm_latest'"),
    }

    fig = plt.figure(figsize=(15, 9.6))
    ax = fig.add_axes([0.01, 0.05, 0.98, 0.83])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_axis_off()
    SRC, STEP, TAB, OUT = "#e6f0fb", "#fcfcfb", "#f0efec", "#fdeee6"

    def box(x, y, w, h, title, body, fill, edge=AXIS, lw=1.0):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                    fc=fill, ec=edge, lw=lw, zorder=2))
        ax.text(x + 1, y + h - 1.2, title, fontsize=9.5, fontweight="bold", va="top", zorder=3)
        ax.text(x + 1, y + h - 4.6, body, fontsize=8.2, color=INK_2, va="top", zorder=3, linespacing=1.35)
        return (x, y, w, h)

    def arrow(a, b, color=MUTED):
        (ax_, ay, aw, ah), (bx, by, bw, bh) = a, b
        ax.add_patch(FancyArrowPatch((ax_ + aw + 0.6, ay + ah / 2), (bx - 0.6, by + bh / 2),
                                     arrowstyle="-|>", mutation_scale=11, color=color, lw=1.1, zorder=1,
                                     connectionstyle="arc3,rad=0"))

    for x, label in ((1, "1  Sources"), (27, "2  Checks and steps"), (53, "3  Database tables (PostGIS)"),
                     (79, "4  What others read")):
        ax.text(x, 99, label, fontsize=11, fontweight="bold", color=INK, va="top")

    # Column 1: sources, each with its date.
    s_cris = box(1, 76, 22, 17, "TxDOT CRIS crash records",
                 "College Station, 2016–2025\n2 exports per year (columns)\nDownloaded Oct 2026", SRC)
    s_road = box(1, 54, 22, 17, "TxDOT Roadway Inventory 2019",
                 "Snapshot dated 2019-12-31\nPublished 2021-08-06\nfetch_roads.py", SRC)
    s_osm = box(1, 32, 22, 17, "OpenStreetMap (ohsome)",
                f"As of {n['osm22_date']}  (backtest)\nAs of {n['osm_new_date']}  (live)\nfetch_osm.py, 600 m band", SRC)
    s_cor = box(1, 13, 22, 14, "corridors.py",
                "3 corridors, 26 CRIS\nstreet-name spellings", SRC)

    # Column 2: steps.
    p_cr = box(27, 76, 22, 17, "ingest.py crashes / crash-details",
               "Stops a file at >2% bad rows\nDuplicates, dates, coordinates,\nseverity checked; every reject logged", STEP)
    p_rd = box(27, 54, 22, 17, "ingest.py roads + 02_build_network",
               "Centerlines (KG), College Station\nCut into ~0.1-mi segments;\n3+ legs = intersection", STEP)
    p_osm = box(27, 32, 22, 17, "ingest.py osm + 06_osm_features",
                "Counts near each site; signals\nmerged within 50 m; features with\nno variation dropped", STEP)
    p_mm = box(27, 13, 22, 14, "03_map_match + 04_features",
               "Crash -> site of its own corridor\nRoad attributes -> site features", STEP)

    # Column 3: tables with live counts.
    t_crash = box(53, 76, 22, 17, "crash  ·  crash_match",
                  f"{n['crash']:,} crashes ({n['fsi']} fatal/serious)\n{n['matched']:,} matched to sites\n"
                  f"F&SI match rate {n['match_pct']}%", TAB)
    t_site = box(53, 54, 22, 17, "road  ·  site",
                 f"{n['road']:,} road records\n{n['seg']} segments + {n['int']} intersections\n{n['miles']:.1f} miles",
                 TAB)
    t_osm = box(53, 32, 22, 17, "osm_feature",
                f"{n['osm22']:,} features as of {n['osm22_date']}\n{n['osm_new']:,} features as of {n['osm_new_date']}",
                TAB)
    t_feat = box(53, 6, 22, 21, "site_feature  (leakage trigger)",
                 f"backtest_2022: {n['feat_bt'] - 1} segment features\n+ intersection legs, {n['feat_vals']:,} values\n"
                 f"current: {n['feat_cur']} OSM features (live)\nAny value dated after 2022-12-31\n"
                 "is REFUSED from backtest_2022", TAB, edge=INK, lw=1.6)

    # Column 4: consumers.
    o_s2 = box(79, 54, 20, 39, "S2 risk model (Param)",
               "Read-only role s2_reader\nViews: s2_site_scope,\ns2_crash_scope,\ns2_source_registry\n\n"
               "Trains on 2016–2022,\ntests on 2023–2025\n(M2 run: Oct 20)", OUT)
    o_fig = box(79, 32, 20, 17, "Figures and dump",
                "make_figures.py (this figure)\ndumps/ for teammates", OUT)
    o_tests = box(79, 13, 20, 14, "Tests",
                  "Validator + leakage +\nS2-view contract tests", OUT)

    for a, b in ((s_cris, p_cr), (s_road, p_rd), (s_osm, p_osm), (p_cr, t_crash), (p_rd, t_site),
                 (p_osm, t_osm), (t_crash, o_s2), (t_site, o_s2), (t_osm, o_fig), (t_feat, o_tests)):
        arrow(a, b)
    # Diagonal links: corridors drive matching; tables feed the feature/matching steps.
    for (x0, y0), (x1, y1) in (((23.6, 20), (26.4, 20)), ((64, 31.4), (64, 27.6)), ((75.6, 16), (78.4, 64))):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=11, color=MUTED,
                                     lw=1.1, zorder=1))
    ax.add_patch(FancyArrowPatch((49.6, 20), (52.4, 16), arrowstyle="-|>", mutation_scale=11, color=MUTED, lw=1.1))

    ax.text(1, 3, "Cutoff rule: everything the model uses for training and the backtest must be dated, and publicly "
                  "available, by 2022-12-31. The 2026 OSM snapshot feeds only the live ranking ('current').",
            fontsize=9, color=INK, va="bottom")
    finish(fig, os.path.join(out, "fig11_data_lineage.png"),
           "S1 data lineage: from public sources to what the model reads",
           "Every number in the boxes is queried live from the database when this figure is drawn.", net,
           "TASC S1 (Kabir Singh). Sources: TxDOT CRIS; TxDOT Roadway Inventory; © OpenStreetMap contributors via "
           "ohsome API. Network {net}.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Draw S1 progress figures from the database")
    parser.add_argument("--network", default="v0_2019")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures"))
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    with ingest.connect() as conn, conn.cursor() as cur:
        for fn in (fig_network, fig_by_year, fig_matching, fig_speed, fig_funnel,
                   fig_osm_growth, fig_osm_maps, fig_conditions, fig_speed_check,
                   fig_feature_strips, fig_lineage):
            fn(cur, args.network, args.out)


if __name__ == "__main__":
    main()
