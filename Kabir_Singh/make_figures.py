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


def finish(fig, path, title, subtitle, net):
    # Place title and subtitle a fixed distance (in inches) from the top, whatever the figure height.
    h = fig.get_figheight()
    fig.text(0.012, 1 - 0.18 / h, title, ha="left", va="top", fontsize=14, fontweight="bold")
    fig.text(0.012, 1 - 0.50 / h, subtitle, ha="left", va="top", fontsize=10, color=INK_2)
    fig.text(0.012, 0.012, SOURCE.format(net=net), ha="left", fontsize=7.5, color=MUTED)
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Draw S1 progress figures from the database")
    parser.add_argument("--network", default="v0_2019")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures"))
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    with ingest.connect() as conn, conn.cursor() as cur:
        for fn in (fig_network, fig_by_year, fig_matching, fig_speed, fig_funnel):
            fn(cur, args.network, args.out)


if __name__ == "__main__":
    main()
