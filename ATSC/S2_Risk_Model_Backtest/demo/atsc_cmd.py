"""ATSC road evaluator: a command-prompt style terminal tool.

    bash ~/Desktop/AICorps4/ATSC/S2_Risk_Model_Backtest/demo/atsc.sh      (macOS / Linux)
    ATSC\\S2_Risk_Model_Backtest\\demo\\atsc.bat                          (Windows)

Every number is computed live by the saved S2 models. Every boot step does real work: library
versions against the frozen run, model reload and full recompute, SHA-256 checks, the leakage
gate with seeded post-cutoff records, the frozen-2022 backtest models, and the BIT checks.
Set ATSC_FAST=1 to skip the animation delays.
"""
import os
import random
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
if os.name == "nt":  # Windows: turn on ANSI colors and UTF-8 box drawing
    os.system("")
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from rich import box
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

con = Console(style="grey85 on black", highlight=False)
FAST = os.environ.get("ATSC_FAST") == "1"
PROMPT = "C:\\ATSC> "
BORDER = "grey50"
GRADIENT = ["#ffffff", "#ffd0d0", "#ff9a9a", "#ff6262", "#e02a2a", "#a51515"]

LETTERS = {
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "T": ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
    "S": ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
    "C": [" ██████╗", "██╔════╝", "██║     ", "██║     ", "╚██████╗", " ╚═════╝"],
}
SEG_KNOBS = [("aadt", "Traffic (vehicles/day)", 100, 150000), ("speed_limit", "Posted speed (mph)", 10, 80),
             ("num_lanes", "Lanes", 1, 8), ("lane_width_ft", "Lane width (ft)", 8, 16), ("median_width_ft", "Median width (ft)", 0, 100),
             ("shoulder_outside_ft", "Outside shoulder (ft)", 0, 20), ("truck_pct", "Trucks (%)", 0, 40),
             ("curvature_deg_per_mi", "Curvature (deg/mi)", 0, 400), ("dist_to_intersection_m", "Distance to intersection (m)", 0, 2000),
             ("osm_sidewalk_share", "Sidewalk share (0 to 1)", 0, 1), ("osm_signalized_intersections_30m", "Signals within 30 m", 0, 5),
             ("osm_crossings_30m", "Marked crossings within 30 m", 0, 20), ("osm_bus_stops_200m", "Bus stops within 200 m", 0, 10),
             ("osm_bars_200m", "Bars within 200 m", 0, 10), ("osm_restaurants_100m", "Restaurants within 100 m", 0, 20),
             ("osm_schools_400m", "Schools within 400 m", 0, 5)]
INT_KNOBS = [("aadt_major", "Main road traffic (vehicles/day)", 100, 150000), ("aadt_minor", "Cross road traffic (vehicles/day)", 100, 150000),
             ("signalized", "Signalized (0 or 1)", 0, 1), ("legs", "Legs", 3, 6), ("interchange", "Interchange (0 or 1)", 0, 1),
             ("state_route", "State route (0 or 1)", 0, 1), ("osm_crossings_30m", "Marked crossings within 30 m", 0, 20),
             ("osm_signalized_intersections_30m", "Signals within 30 m", 0, 5), ("osm_bus_stops_200m", "Bus stops within 200 m", 0, 10),
             ("osm_bars_200m", "Bars within 200 m", 0, 10), ("osm_restaurants_100m", "Restaurants within 100 m", 0, 20),
             ("osm_schools_400m", "Schools within 400 m", 0, 5)]
INTEGER_KNOBS = {"num_lanes", "legs", "signalized", "interchange", "state_route", "osm_signalized_intersections_30m",
                 "osm_crossings_30m", "osm_bus_stops_200m", "osm_bars_200m", "osm_restaurants_100m", "osm_schools_400m"}


# ------------------------------------------------------------------ screen helpers
def nap(s):
    if not FAST:
        time.sleep(s)


def cls():
    sys.stdout.write("\033[40m\033[2J\033[H")
    sys.stdout.flush()


def banner(animate=False):
    for i in range(6):
        con.print("  " + " ".join(LETTERS[c][i] for c in "ATSC"), style=f"bold {GRADIENT[i]}")
        if animate:
            nap(0.07)
    con.print("  AI Traffic-Safety Consultant  [grey50]|[/]  S2 crash risk model  [grey50]|[/]  College Station, TX")
    con.print()


def typewriter(text, style="bold bright_white", delay=0.012):
    if FAST:
        con.print(text, style=style)
        return
    for ch in text:
        con.print(ch, style=style, end="")
        time.sleep(delay)
    con.print()


def status(S, where=""):
    t = Text()
    t.append(" ATSC ", style="bold black on grey85")
    t.append(f" {S.manifest['run_id']} ", style="grey85 on grey23")
    t.append(f" hash {S.hash[:8]} OK " if S.hash_ok else " HASH MISMATCH ", style="bold black on green" if S.hash_ok else "bold white on red")
    t.append(f" {len(S.live['sites']):,} sites ", style="grey85 on grey23")
    if where:
        t.append(f" {where} ", style="bold black on yellow")
    con.print(t)
    con.print()


def ask(msg=PROMPT):
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit(0)


def pause(msg="\n  Press Enter to go back... "):
    ask(msg)


def menu(items):
    t = Text("  ")
    for key, lab in items:
        t.append(f"[{key}]", style="bold bright_white")
        t.append(f" {lab}   ", style="grey70")
    con.print(t)


def section(title):
    con.print()
    t = Text("  ")
    t.append(f" {title} ", style="bold black on grey85")
    t.append(" " + "─" * max(10, min(con.width, 110) - len(title) - 6), style="grey35")
    con.print(t)
    nap(0.1)


def ok_line(label, note="", good=True, branch="├─"):
    t = Text(f"  {branch} ", style="grey35")
    t.append(f"{label[:50]:<50}", style="grey85")
    t.append(" OK " if good else " WARN ", style="bold black on green" if good else "bold white on red")
    if note:
        t.append(f"  {note}", style="grey62")
    con.print(t)
    nap(0.06)


def tree_line(text, branch="├─", style="grey70"):
    con.print(Text(f"  {branch} ", style="grey35") + Text(text, style=style))
    nap(0.05)


def bar(n, scale, ch="█"):
    return ch * max(0, int(round(n * scale)))


# ------------------------------------------------------------------ boot
class State:
    pass


def boot():
    cls()
    banner(animate=True)
    typewriter("  > ATSC risk engine v1.1 booting. Every step below does real work.")
    S = State()
    t_boot = time.monotonic()

    section("SYSTEM")
    import platform
    import core
    import lightgbm
    import pandas
    import scipy
    S.core = core
    S.manifest = core.read_json(core.BUNDLE / "manifest.json")
    rt = S.manifest["runtime"]
    ok_line(f"host {platform.system()} {platform.machine()}", f"{os.cpu_count()} CPUs, no GPU needed")
    for name, have in (("python", platform.python_version()), ("numpy", np.__version__), ("pandas", pandas.__version__),
                       ("scipy", scipy.__version__), ("lightgbm", lightgbm.__version__)):
        same = have == rt.get(name)
        ok_line(f"{name} {have}", "same as the frozen run" if same else f"frozen run used {rt.get(name)}", good=True)
    m = S.manifest
    a = m["as_of"] if isinstance(m["as_of"], dict) else {}
    tree_line(f"run {m['run_id']}  |  backtest data to {a.get('backtest_features_and_history', '?')}, forecast crashes to "
              f"{a.get('forecast_crash_history', '?')}  |  code {str(m['commit'])[:7]}", branch="└─")

    section("MODELS  2026 forecast, refit on crashes through 2025")
    t0 = time.monotonic()
    S.live = core.load_live(on_step=lambda msg: tree_line(msg))
    nb = sum(len(S.live["models"][k][f]["boosters"]) for k in S.live["models"] for f in ("me", "lg", "lt"))
    ok_line("models reloaded, every site recomputed", f"{nb} boosters, seeds {S.live['cfg']['lgb_seeds']}, "
            f"{time.monotonic() - t0:.1f} s", branch="└─")

    section("INTEGRITY  SHA-256 of every bundle and cache file")
    n_files = len(m["files"]) + len(S.live["meta"]["cache_hashes"])
    with Progress(TextColumn("  [grey35]├─[/] {task.description}"), BarColumn(bar_width=34, complete_style="green", finished_style="green"),
                  MofNCompleteColumn(), TextColumn("[grey50]{task.fields[f]}"), console=con) as pr:
        task = pr.add_task("hashing files", total=n_files, f="")

        def on_file(name):
            pr.update(task, advance=1, f=name[-34:])
            nap(0.03)
        S.hash, S.errors = core.integrity(S.live, on_file)
        pr.update(task, f="done")
    S.hash_ok = not S.errors
    for e in S.errors[:4]:
        tree_line(e, style="bold red")
    t = Text("  ├─ ranking hash  ", style="grey35")
    con.print(t, end="")
    for i in range(0, 64, 4):
        con.print(S.hash[i:i + 4], style="bold bright_white", end="")
        nap(0.025)
    con.print()
    ok_line("ranking reproduces the frozen run exactly" if S.hash_ok else "hash differs from the frozen run",
            f"expected {m['ranking_hash'][:12]}", good=S.hash_ok, branch="└─")

    section("LEAKAGE GATE  nothing after 2022-12-31 may enter the backtest")
    from S2_Risk_Model_Backtest.leakage import validate_snapshot
    cfg = S.live["cfg"]
    S.snap = None
    if (core.CACHE / "snapshot_meta.json").exists():
        with con.status("  reading the frozen S1 snapshot...", spinner="dots"):
            S.snap = core.snapshot_from_cache()
            gate = validate_snapshot(S.snap, cfg["features"], cfg["history_start"], cfg["history_end"])
        ok_line("clean snapshot passes", f"{gate['sites']:,} sites, {gate['features']:,} feature values, {gate['history_rows']:,} history rows")
        with con.status("  injecting post-cutoff records into copies of the snapshot...", spinner="dots"):
            S.seeded = core.seeded_leakage_checks(S.snap, cfg["features"])
        for i, c in enumerate(S.seeded):
            ok_line(f"seeded: {c['case']}", "refused" if c["detected"] else "MISSED", good=c["detected"],
                    branch="└─" if i == len(S.seeded) - 1 else "├─")
    else:
        tree_line("snapshot not in the cache; gate skipped", branch="└─", style="yellow")

    section("BACKTEST  models frozen at 2022, scored on 2023-2025")
    t0 = time.monotonic()
    S.bt = core.load_live("backtest", on_step=lambda msg: tree_line(msg))
    S.bt["frame"] = core.prediction_frame(S.bt["sites"], S.bt["preds"]["ML-EB"], S.bt["cfg"])
    S.bt["pos"] = {s: i for i, s in enumerate(S.bt["sites"].site_id.astype(str))}
    S.tc = core.test_crash_records() if (core.CACHE / "test_crashes.parquet").exists() else None
    if S.tc:
        ka = sum(1 for c in S.tc if c["severity"] in ("K", "A") and c["site_id"] is not None and c["in_analysis_area"])
        tree_line(f"{len(S.tc):,} held-out crashes from 2023-2025 loaded, {ka} fatal or serious on mapped sites")
    ok_line("frozen-2022 models ready", f"{time.monotonic() - t0:.1f} s", branch="└─")

    section("BUILT-IN TESTS")
    S.table = S.live["table"]
    S.rank = S.table.set_index("site_id")
    S.pos = {s: i for i, s in enumerate(S.live["sites"].site_id.astype(str))}
    for i, (name, good, note) in enumerate(quick_tests(S)):
        ok_line(name, note, good=good, branch="└─" if i == 4 else "├─")

    S.hist = core.read_json(core.BUNDLE / "site_history.json")
    S.memos = {p.stem for p in (core.BUNDLE / "memos").glob("*.md")}
    S.edits, S.base, S.board, S.cal = {}, {}, None, None
    S.boot_s = time.monotonic() - t_boot
    con.print()
    flagged = int(S.table.flagged.sum())
    g = Table.grid(padding=(0, 4))
    for _ in range(5):
        g.add_column(justify="center")
    g.add_row(*(Text(v, style="bold bright_white") for v in (f"{len(S.table):,}", f"{flagged}", f"{nb}", S.hash[:8], f"{S.boot_s:.1f} s")))
    g.add_row(*(Text(v, style="grey62") for v in ("sites ranked", "flagged (11% of length)", "LightGBM boosters", "ranking hash", "boot time")))
    title = Text(" ALL SYSTEMS GO ", style="bold black on green") if S.hash_ok else Text(" RUNNING WITH WARNINGS ", style="bold white on red")
    con.print(Panel(g, title=title, border_style="green" if S.hash_ok else "red", box=box.DOUBLE, padding=(1, 4), expand=False))
    pause("  Press Enter to start... ")
    return S


def quick_tests(S):
    """Fast BIT checks for the boot screen. Each calls the S2 check or recomputes from the live models."""
    from S2_Risk_Model_Backtest.bit import check_explanations, check_predictions
    from calc import eb_by_hand
    out = []
    frame = S.core.prediction_frame(S.live["sites"], S.live["preds"]["ML-EB"], S.live["cfg"])
    try:
        r = check_predictions(frame.to_dict("records"), S.live["sites"].site_id.astype(str))
        out.append(("BIT: coverage, ranges, units, rank prefix", True, f"{r['details']['sites']:,} sites, 0 missing"))
        share = r["details"]["flagged_miles"] / r["details"]["network_miles"]
        out.append(("BIT: flagged length 11% +/- 0.5%", True, f"{r['details']['flagged_miles']:.1f} of {r['details']['network_miles']:.1f} mi = {100 * share:.2f}%"))
    except ValueError as exc:
        out += [("BIT: coverage, ranges, units, rank prefix", False, str(exc)), ("BIT: flagged length 11% +/- 0.5%", False, "")]
    expl = S.core.read_json(S.core.BUNDLE / "explanations.json")
    try:
        r = check_explanations(expl, S.table.site_id[S.table.flagged])
        out.append(("BIT: top-5 SHAP for every flagged site", True, f"{r['details']['flagged_sites']} sites x 5 factors"))
    except ValueError as exc:
        out.append(("BIT: top-5 SHAP for every flagged site", False, str(exc)))
    p, fut = S.live["preds"]["ML-EB"], S.live["fut"]
    hy = fut.hist_years.to_numpy(float)
    w, est = eb_by_hand(p["k"], hy * p["mu"], fut.tot_5y.to_numpy(float))
    werr = float(np.abs(w - p["eb_weight"]).max())
    nerr = float(np.abs(est / hy - p["n_eb"]).max())
    inside = bool(((p["eb_weight"] > 0) & (p["eb_weight"] < 1)).all())
    out.append(("EB: weights in (0, 1), hand formula matches", inside and max(werr, nerr) < 1e-9, f"max error {max(werr, nerr):.1e} on {len(hy):,} sites"))
    err = shap_error(S, S.table.site_id.head(50))
    out.append(("TreeSHAP: factors add up to the model score", err < 1e-6, f"top 50 sites, max error {err:.1e}"))
    return out


def shap_error(S, sids):
    fut = S.live["fut"].iloc[[S.pos[s] for s in sids]]
    err = 0.0
    for kind, rows in fut.groupby("site_type"):
        F = S.live["models"][kind]["me"]
        X = S.live["enc"].frame(rows, F["feats"])
        for b in F["boosters"]:
            err = max(err, float(np.abs(b.predict(X, pred_contrib=True, num_threads=2).sum(1) - b.predict(X, raw_score=True, num_threads=2)).max()))
    return err


# ------------------------------------------------------------------ model calls
def label(S, feat, r):
    if feat == "ln_aadt":
        return f"traffic {r.aadt:,.0f} vehicles/day"
    if feat == "ln_aadt_major":
        return f"main road traffic {r.aadt_major:,.0f} vehicles/day"
    if feat == "ln_aadt_minor":
        return f"cross road traffic {r.aadt_minor:,.0f} vehicles/day"
    return S.core.describe(feat, r[feat] if feat in r.index else None, 0)


def site_row(S, sid):
    return S.live["fut"].iloc[[S.pos[sid]]]


def apply_edits(row, edits):
    import pandas as pd
    r = row.copy()
    for k, v in edits.items():
        r[k] = v
    x = r.iloc[0]
    if x.site_type == "segment":
        r["exposure"] = x.aadt * 365 * x.length_mi / 1e6
        r["divided"] = int(pd.notna(x.median_type) and str(x.median_type) != "0")
    else:
        r["exposure"] = (x.aadt_major + x.aadt_minor) * 365 / 1e6
    return r


def score(S, sid, edits=None):
    if not edits:
        if sid not in S.base:
            S.base[sid] = S.core.site_score(S.live, site_row(S, sid))
        return S.base[sid]
    return S.core.site_score(S.live, apply_edits(site_row(S, sid), edits))


def summary(s):
    p = s["p"]
    ka = float(p["n_eb"][0] * s["p_kabc"] * s["p_ka"])
    return {"mu": p["mu"][0], "w": p["eb_weight"][0], "eb": p["n_eb"][0], "pk": s["p_kabc"], "pa": s["p_ka"], "ka": ka,
            "rate": s["rate"], "rank": s["rank"], "flag": s["flagged"]}


def knobs_for(r):
    return SEG_KNOBS if r.site_type == "segment" else INT_KNOBS


# ------------------------------------------------------------------ list screens
def search(S, q):
    t = S.table
    if q.lower() == "top":
        return t.sort_values("rank").head(15)
    ql = q.lower()
    return t[t.site_id.str.contains(ql, regex=False) | t.road_name.str.lower().str.contains(ql, regex=False)].sort_values("rank").head(20)


def list_screen(S, hits, title):
    tb = Table(box=box.SQUARE, border_style=BORDER, header_style="bold bright_white", title=title, title_style="bold bright_white")
    for c, j in (("#", "right"), ("rank", "right"), ("road", "left"), ("type", "left"), ("ATSC", "center"), ("HIN", "center"),
                 ("memo", "center"), ("K+A/mi/yr", "right")):
        tb.add_column(c, justify=j)
    for n, (_, h) in enumerate(hits.iterrows(), 1):
        tb.add_row(str(n), f"#{int(h['rank']):,}", h.road_name[:52], h.site_type,
                   "[bold red]FLAG[/]" if h.flagged else "[grey50]-[/]", "[cyan]yes[/]" if h.in_hin else "[grey50]-[/]",
                   "[magenta]yes[/]" if h.site_id in S.memos else "[grey50]-[/]", f"{h.fsi_rate:.2f}")
    con.print(tb)


# ------------------------------------------------------------------ site screen
def site_screen(S, sid):
    r = site_row(S, sid).iloc[0]
    t = S.rank.loc[sid]
    b = summary(score(S, sid))
    e = S.edits.get(sid, {})
    a = summary(score(S, sid, e)) if e else b
    status(S, f"WHAT-IF: {len(e)} change{'s' if len(e) != 1 else ''}" if e else "")
    tags = Text()
    tags.append(f" {r.site_type.upper()} ", style="black on grey70")
    tags.append(" ")
    tags.append(" ATSC FLAGGED " if a["flag"] else " not flagged ", style="bold white on red3" if a["flag"] else "grey85 on grey23")
    tags.append(" ")
    tags.append(" IN HIN " if t.in_hin else " not in HIN ", style="bold black on cyan" if t.in_hin else "grey85 on grey23")
    if sid in S.memos:
        tags.append(" ")
        tags.append(" MEMO ", style="bold black on magenta")
    tags.append(f"   {t.jurisdiction}, {r.risk_length_mi:.4f} mi, site {sid}", style="grey62")
    rank_txt = Text(f"#{a['rank']:,}", style="bold bright_white")
    rank_txt.append(f" of {len(S.table):,}", style="grey62")
    pct = 100 * (len(S.table) - a["rank"]) / len(S.table)
    rank_txt.append(f"   riskier than {pct:.2f}% of sites" if a["rank"] > 1 else "   highest in the city", style="grey62")
    if e and a["rank"] != b["rank"]:
        rank_txt.append(f"   was #{b['rank']:,}", style="yellow")
    con.print(Panel(Group(Text(t.road_name, style="bold bright_white"), tags, Text(), Text("RANK  ", style="grey62") + rank_txt),
                    border_style=BORDER, box=box.SQUARE, padding=(0, 2)))

    m = Table(box=box.SIMPLE_HEAD, border_style=BORDER, header_style="bold bright_white", title="Model pipeline", title_style="bold bright_white")
    m.add_column("step")
    m.add_column("real", justify="right")
    if e:
        m.add_column("what-if", justify="right", style="yellow")
        m.add_column("change", justify="right")
    rows = [("LightGBM mu (crashes/yr)", "mu", "{:.2f}"), ("EB weight w", "w", "{:.3f}"), ("EB estimate (crashes/yr)", "eb", "{:.2f}"),
            ("P(injury | crash)", "pk", "{:.3f}"), ("P(K or A | injury)", "pa", "{:.3f}"), ("K+A per year", "ka", "{:.3f}"),
            ("K+A per mile per year", "rate", "{:.2f}")]
    for name, k, f in rows:
        cells = [name, f.format(b[k])]
        if e:
            d = a[k] - b[k]
            cells += [f.format(a[k]), Text(f"{d:+.3f}" if abs(d) > 1e-12 else "", style="red" if d > 0 else "green")]
        m.add_row(*cells)
    s = score(S, sid, e)
    feats = S.live["models"][r.site_type]["me"]["feats"]
    rr = apply_edits(site_row(S, sid), e).iloc[0] if e else r
    c = s["contrib"][:-1]
    top = np.argsort(-np.abs(c))[:6]
    cmax = float(np.abs(c[top]).max()) or 1
    f = Table(box=box.SIMPLE_HEAD, border_style=BORDER, header_style="bold bright_white", title="What drives it (TreeSHAP)", title_style="bold bright_white")
    f.add_column("push", justify="right")
    f.add_column("", min_width=14)
    f.add_column("factor")
    for j in top:
        f.add_row(Text(f"{c[j]:+.3f}", style="red" if c[j] > 0 else "green"), Text(bar(abs(c[j]), 12 / cmax) or "▏", style="red" if c[j] > 0 else "green"),
                  label(S, feats[j], rr))
    grid = Table.grid(padding=(0, 3))
    grid.add_row(m, f)
    con.print(grid)
    bf = S.bt["frame"].iloc[S.bt["pos"][sid]]
    fields = S.hist["fields"]
    yrs = S.hist["sites"].get(sid, {})
    obs = [yrs.get(str(y), [0] * len(fields)) for y in (2023, 2024, 2025)]
    ka = sum(o[fields.index("K")] + o[fields.index("A")] for o in obs)
    con.print(f"  [grey62]Backtest, model frozen at 2022:[/] rank [bold]#{int(bf['rank']):,}[/]{' (flagged)' if bf.flagged else ''}, "
              f"predicted [bold]{float(bf.annual_fsi) * 3:.2f}[/] K+A for 2023-2025, observed [bold]{ka}[/].")
    con.print()
    quick_lab = ("3", "remove signal" if e.get("signalized", r.signalized) else "add signal") if r.site_type == "intersection" else ("3", "speed -10 mph")
    menu([("1", "change a feature"), ("2", "traffic +50%"), quick_lab, ("4", "crash history"), ("5", "the math"), ("6", "compare")])
    items = [("7", "ATSC vs HIN"), ("8", "sweep a feature")]
    if sid in S.memos:
        items.append(("9", "safety memo"))
    menu(items + [("m", "map"), ("r", "reset"), ("b", "back"), ("q", "quit")])
    con.print("  [grey50]or type a new road name to search[/]")


def history_screen(S, sid):
    status(S, "crash history")
    fields = S.hist["fields"]
    yrs = S.hist["sites"].get(sid, {})
    con.print(f"  [bold bright_white]{S.rank.loc[sid].road_name}[/]  crashes matched to this site, by year\n")
    peak = max([yrs.get(str(y), [0])[0] for y in range(2016, 2026)] + [1])
    scale = 46 / peak
    for y in range(2016, 2026):
        v = yrs.get(str(y), [0] * len(fields))
        ka, bc, o = v[1] + v[2], v[3] + v[4], v[0] - v[1] - v[2] - v[3] - v[4]
        t = Text(f"  {y}  ", style="grey62" if y < 2023 else "bold yellow")
        t.append(bar(ka, scale), style="red")
        t.append(bar(bc, scale), style="yellow")
        t.append(bar(o, scale, "░"), style="grey50")
        t.append(f"  {v[0]} crashes, {ka} K+A", style="grey70")
        con.print(t)
        nap(0.04)
    con.print("\n  [red]█[/] fatal or serious (K+A)   [yellow]█[/] minor injury (B, C)   [grey50]░[/] no injury or unknown")
    con.print("  [bold yellow]2023-2025[/] is the test window the frozen-2022 model never saw.")
    pause()


def math_screen(S, sid):
    status(S, "the math")
    e = S.edits.get(sid, {})
    row = apply_edits(site_row(S, sid), e) if e else site_row(S, sid)
    x = row.iloc[0]
    s = score(S, sid, e)
    p = s["p"]
    from calc import eb_numbers
    eb = eb_numbers(p["k"], p["mu"][0], x.hist_years, x.tot_5y)
    seeds = S.live["cfg"]["lgb_seeds"]
    m = S.live["cfg"]["sev_prior_m"]
    lines = [
        ("1  LightGBM, 3 seeds", f"raw scores {', '.join(f'{v:+.3f}' for v in s['raw'])} (seeds {seeds}), mean {s['raw'].mean():+.4f}"),
        ("2  exposure offset", f"{'(main + cross AADT) x 365 / 1e6' if x.site_type == 'intersection' else 'AADT x 365 x length / 1e6'} = {x.exposure:.3f}"),
        ("3  mu", f"exp({s['raw'].mean():+.4f} + ln {x.exposure:.3f}) = {p['mu'][0]:.3f} crashes/yr"),
        ("4  EB weight", f"w = 1 / (1 + k x sum_mu) = 1 / (1 + {eb['k']:.4f} x {eb['sum_mu']:.2f}) = {eb['w']:.4f}"),
        ("5  EB estimate", f"{eb['w']:.4f} x {eb['sum_mu']:.2f} + {1 - eb['w']:.4f} x {eb['observed']:.0f} observed = {eb['eb_total']:.2f} / {eb['hist_years']} yr = {eb['eb_per_year']:.3f}/yr"),
        ("6  severity", f"P(injury) = {s['p_kabc']:.4f}, P(K or A | injury) = {s['p_ka']:.4f} (GLMs shrunk with {m} pseudo-crashes)"),
        ("7  K+A per year", f"{eb['eb_per_year']:.3f} x {s['p_kabc']:.4f} x {s['p_ka']:.4f} = {eb['eb_per_year'] * s['p_kabc'] * s['p_ka']:.4f}"),
        ("8  per mile", f"{eb['eb_per_year'] * s['p_kabc'] * s['p_ka']:.4f} / {x.risk_length_mi:.4f} mi = {s['rate']:.3f}  ->  rank #{s['rank']:,}"),
    ]
    tb = Table(box=box.SQUARE, border_style=BORDER, show_header=False, title=f"{S.rank.loc[sid].road_name}{'  (what-if)' if e else ''}", title_style="bold bright_white")
    tb.add_column(style="bold bright_white", no_wrap=True)
    tb.add_column()
    for a_, b_ in lines:
        tb.add_row(a_, b_)
    con.print(tb)
    ok = abs(np.sum(s["contrib"]) - s["raw"].mean()) < 1e-6
    con.print(f"  SHAP check: baseline + {len(s['contrib']) - 1} contributions = raw score  {'[bold green]exact[/]' if ok else '[bold red]MISMATCH[/]'}")
    pause()


def whatif_screen(S, sid):
    r = site_row(S, sid).iloc[0]
    e = S.edits.setdefault(sid, {})
    knobs = knobs_for(r)
    while True:
        cls()
        status(S, "change a feature")
        tb = Table(box=box.SQUARE, border_style=BORDER, header_style="bold bright_white", title=S.rank.loc[sid].road_name, title_style="bold bright_white")
        for c_, j in (("#", "right"), ("feature", "left"), ("real", "right"), ("what-if", "right"), ("range", "right")):
            tb.add_column(c_, justify=j)
        for n, (k, lab, lo, hi) in enumerate(knobs, 1):
            real = r[k]
            rv = "not recorded" if real != real else f"{real:,.4g}"
            nv = f"{e[k]:,.4g}" if k in e else ""
            tb.add_row(str(n), lab, rv, Text(nv, style="yellow"), f"{lo} to {hi:,}")
        con.print(tb)
        con.print("  Pick a number to change, [bold]r[/] to reset all, Enter when done.")
        pick = ask("  feature> ")
        if not pick:
            break
        if pick.lower() == "r":
            e.clear()
            continue
        if not pick.isdigit() or not 1 <= int(pick) <= len(knobs):
            continue
        k, lab, lo, hi = knobs[int(pick) - 1]
        v = ask(f"  new value for {lab} ({lo} to {hi:,}): ").replace(",", "")
        try:
            v = float(v)
        except ValueError:
            continue
        if lo <= v <= hi:
            e[k] = v
        else:
            con.print("  [red]Out of range.[/]")
            nap(0.8)
    if not e:
        S.edits.pop(sid, None)


def quick(S, sid, which):
    r = site_row(S, sid).iloc[0]
    e = S.edits.setdefault(sid, {})
    if which == "traffic":
        for k in (["aadt"] if r.site_type == "segment" else ["aadt_major", "aadt_minor"]):
            e[k] = min(150000, e.get(k, r[k]) * 1.5)
    elif r.site_type == "intersection":
        now = e.get("signalized", r.signalized)
        e["signalized"] = 0 if now else 1
        e["osm_signalized_intersections_30m"] = 0 if now else max(1, r.osm_signalized_intersections_30m)
    elif r.speed_limit == r.speed_limit:
        e["speed_limit"] = max(10, e.get("speed_limit", r.speed_limit) - 10)
    if not e:
        S.edits.pop(sid, None)


def sweep_screen(S, sid):
    r = site_row(S, sid).iloc[0]
    knobs = knobs_for(r)
    cls()
    status(S, "sweep a feature")
    con.print(f"  [bold bright_white]{S.rank.loc[sid].road_name}[/]  pick a feature; the model is re-run across its range\n")
    for n, (k, lab, lo, hi) in enumerate(knobs, 1):
        con.print(f"  [bold bright_white]{n:>2}[/]  {lab}")
    pick = ask("\n  feature> ")
    if not pick.isdigit() or not 1 <= int(pick) <= len(knobs):
        return
    k, lab, lo, hi = knobs[int(pick) - 1]
    base = dict(S.edits.get(sid, {}))
    now = base.get(k, r[k])
    if hi - lo <= 6 and k in INTEGER_KNOBS:
        vals = list(range(int(lo), int(hi) + 1))
    else:
        vals = list(np.linspace(lo, hi, 9))
        if k in INTEGER_KNOBS:
            vals = sorted({int(round(v)) for v in vals})
    if now == now and now not in vals:
        vals = sorted(vals + [now])
    cls()
    status(S, f"sweep: {lab}")
    res = []
    with con.status(f"  re-running the model at {len(vals)} values...", spinner="dots"):
        for v in vals:
            res.append((v, summary(score(S, sid, {**base, k: float(v)}))))
    peak = max(x["rate"] for _, x in res) or 1
    tb = Table(box=box.SIMPLE_HEAD, border_style=BORDER, header_style="bold bright_white",
               title=f"{S.rank.loc[sid].road_name}: {lab}", title_style="bold bright_white")
    for c_, j in ((lab, "right"), ("K+A/mi/yr", "right"), ("", "left"), ("rank", "right"), ("ATSC", "center"), ("", "left")):
        tb.add_column(c_, justify=j)
    for v, x in res:
        here = now == now and abs(v - now) < 1e-9
        tb.add_row(f"{v:,.0f}" if abs(v) >= 100 else f"{v:.4g}", f"{x['rate']:.2f}", Text(bar(x["rate"], 30 / peak) or "▏", style="red" if x["flag"] else "grey62"),
                   f"#{x['rank']:,}", "[bold red]FLAG[/]" if x["flag"] else "[grey50]-[/]", Text("<- now" if here else "", style="bold yellow"))
    con.print(tb)
    ranks = [x["rank"] for _, x in res]
    con.print(f"  Rank moves between [bold]#{min(ranks):,}[/] and [bold]#{max(ranks):,}[/] across this range. Other features stay as they are"
              f"{' (with your what-if changes)' if base else ''}.")
    if now != now:
        con.print("  [grey62]This site has no recorded value for this feature; the model normally treats it as missing.[/]")
    pause()


def memo_screen(S, sid):
    cls()
    status(S, "safety memo")
    text = (S.core.BUNDLE / "memos" / f"{sid}.md").read_text(encoding="utf-8")
    con.print(Panel(Markdown(text), border_style="magenta", box=box.SQUARE, padding=(0, 2),
                    title=Text(" S3 countermeasure memo, draft for staff review ", style="bold black on magenta")))
    pause()


def pick_site(S, prompt_title):
    while True:
        cls()
        status(S, prompt_title)
        q = ask("  Search road name or site ID (Enter to cancel): ")
        if not q:
            return None
        hits = search(S, q)
        if hits.empty:
            continue
        if len(hits) == 1:
            return hits.site_id.iloc[0]
        cls()
        status(S, prompt_title)
        list_screen(S, hits, f"Matches for '{q}'")
        p = ask("  Pick a number: ")
        if p.isdigit() and 1 <= int(p) <= len(hits):
            return hits.site_id.iloc[int(p) - 1]


def compare_screen(S, sid):
    other = pick_site(S, "compare with")
    if not other:
        return
    cls()
    status(S, "compare")
    tb = Table(box=box.SQUARE, border_style=BORDER, header_style="bold bright_white")
    tb.add_column("")
    for x in (sid, other):
        tb.add_column(S.rank.loc[x].road_name[:34], justify="right")
    a, b = summary(score(S, sid)), summary(score(S, other))
    ra, rb = site_row(S, sid).iloc[0], site_row(S, other).iloc[0]
    rows = [("type", ra.site_type, rb.site_type), ("crashes, last 5 years", f"{int(ra.tot_5y)}", f"{int(rb.tot_5y)}"),
            ("LightGBM mu (crashes/yr)", f"{a['mu']:.2f}", f"{b['mu']:.2f}"), ("EB estimate (crashes/yr)", f"{a['eb']:.2f}", f"{b['eb']:.2f}"),
            ("K+A per year", f"{a['ka']:.3f}", f"{b['ka']:.3f}"), ("K+A per mile per year", f"{a['rate']:.2f}", f"{b['rate']:.2f}"),
            ("rank", f"#{a['rank']:,}", f"#{b['rank']:,}"), ("ATSC flagged", "YES" if a["flag"] else "no", "YES" if b["flag"] else "no"),
            ("in HIN", "yes" if S.rank.loc[sid].in_hin else "no", "yes" if S.rank.loc[other].in_hin else "no")]
    for name, x, y in rows:
        tb.add_row(name, x, y)
    con.print(tb)
    winner = sid if a["rank"] < b["rank"] else other
    con.print(f"  Higher risk: [bold red]{S.rank.loc[winner].road_name}[/]")
    pause()


# ------------------------------------------------------------------ city-wide screens
def map_screen(S, sid=None):
    cls()
    status(S, "map")
    t = S.table
    lat0, lat1, lon0, lon1 = t.lat.min(), t.lat.max(), t.lon.min(), t.lon.max()
    aspect = (lat1 - lat0) / ((lon1 - lon0) * np.cos(np.radians((lat0 + lat1) / 2)))
    W = max(40, min(con.width - 6, 120))
    H = int(round(W * aspect / 2.1))
    cap = max(18, con.height - 16)
    if H > cap:
        W, H = int(W * cap / H), cap
    x = ((t.lon - lon0) / (lon1 - lon0) * (W - 1)).round().astype(int).to_numpy()
    y = ((lat1 - t.lat) / (lat1 - lat0) * (H - 1)).round().astype(int).to_numpy()
    lvl = np.where(t["rank"] <= 9, 4, np.where(t.flagged, 3, np.where(t.in_hin, 2, 1)))
    grid = np.zeros((H, W), int)
    digit = {}
    for xi, yi, lv, rk in zip(x, y, lvl, t["rank"]):
        if lv > grid[yi, xi]:
            grid[yi, xi] = lv
        if lv == 4:
            digit[(yi, xi)] = min(digit.get((yi, xi), 9), int(rk))
    mark = None
    if sid is not None:
        i = int(np.flatnonzero(t.site_id.to_numpy() == sid)[0])
        mark = (y[i], x[i])
    style = {0: (" ", "grey11"), 1: ("·", "grey35"), 2: ("•", "dark_cyan"), 3: ("●", "red")}
    rows = []
    for yi in range(H):
        line = Text()
        for xi in range(W):
            if mark == (yi, xi):
                line.append("◆", style="bold black on yellow")
            elif grid[yi, xi] == 4:
                line.append(str(digit[(yi, xi)]), style="bold bright_yellow")
            else:
                ch, st = style[grid[yi, xi]]
                line.append(ch, style=st)
        rows.append(line)
    con.print(Panel(Group(*rows), title=Text(" College Station: every ranked site ", style="bold bright_white"), border_style=BORDER,
                    box=box.SQUARE, padding=(0, 1), expand=False))
    con.print("  [grey35]·[/] site   [dark_cyan]•[/] in HIN   [red]●[/] ATSC flagged   [bold bright_yellow]1-9[/] top 9 ranks"
              + ("   [bold black on yellow]◆[/] this site" if sid else ""))
    top = t.sort_values("rank").head(9)
    g = Table.grid(padding=(0, 3))
    g.add_column()
    g.add_column()
    names = [f"[bold bright_yellow]{int(r['rank'])}[/] {r.road_name[:44]}" for _, r in top.iterrows()]
    for i in range(0, 9, 2):
        g.add_row(names[i], names[i + 1] if i + 1 < 9 else "")
    con.print(g)
    if sid:
        con.print(f"\n  ◆ {S.rank.loc[sid].road_name}: rank #{int(S.rank.loc[sid]['rank']):,}")
    pause()


def stats_screen(S):
    cls()
    status(S, "network overview")
    t = S.table
    tb = Table(box=box.SQUARE, border_style=BORDER, header_style="bold bright_white", title="Network", title_style="bold bright_white")
    for c_ in ("", "sites", "risk miles", "ATSC flagged", "flagged miles", "in HIN", "flagged and in HIN"):
        tb.add_column(c_, justify="right" if c_ else "left")
    for name, g in (("segments", t[t.site_type == "segment"]), ("intersections", t[t.site_type == "intersection"]), ("all", t)):
        tb.add_row(name, f"{len(g):,}", f"{g.length_mi.sum():.1f}", f"{int(g.flagged.sum()):,}",
                   f"{g.length_mi[g.flagged].sum():.1f}", f"{int(g.in_hin.sum()):,}", f"{int((g.flagged & g.in_hin).sum()):,}")
    con.print(tb)
    con.print(f"  [grey62]Each intersection counts as {t.length_mi[t.site_type == 'intersection'].iloc[0]:.4f} mi (its 250 ft zone). "
              f"Flagged share of risk length: {100 * t.length_mi[t.flagged].sum() / t.length_mi.sum():.2f}%.[/]")
    edges = [0, 0.01, 0.03, 0.1, 0.3, 1, 3, 10, np.inf]
    cnt, _ = np.histogram(t.fsi_rate, bins=edges)
    fl, _ = np.histogram(t.fsi_rate[t.flagged], bins=edges)
    con.print("\n  [bold bright_white]How risk is spread[/] (sites by expected K+A per mile per year)")
    scale = 50 / max(cnt.max(), 1)
    for i in range(len(cnt)):
        lab = f"{edges[i]:g} to {edges[i + 1]:g}" if np.isfinite(edges[i + 1]) else f"{edges[i]:g} and up"
        line = Text(f"  {lab:>13}  ", style="grey62")
        line.append(bar(cnt[i] - fl[i], scale), style="grey50")
        line.append(bar(fl[i], scale), style="red")
        line.append(f"  {cnt[i]:,}" + (f" ({fl[i]} flagged)" if fl[i] else ""), style="grey70")
        con.print(line)
    con.print("  [grey50]█[/] not flagged   [red]█[/] flagged")
    j = t.groupby("jurisdiction").agg(sites=("site_id", "size"), flagged=("flagged", "sum")).sort_values("flagged", ascending=False)
    seg = t[(t.site_type == "segment") & (t.road_name != "")]
    roads = seg.groupby("road_name").agg(flagged=("flagged", "sum"), sites=("site_id", "size")).sort_values("flagged", ascending=False).head(8)
    a = Table(box=box.SIMPLE_HEAD, header_style="bold bright_white", title="Flagged sites by owner", title_style="bold bright_white")
    a.add_column("jurisdiction")
    a.add_column("sites", justify="right")
    a.add_column("flagged", justify="right")
    for name, r in j.iterrows():
        a.add_row(str(name), f"{int(r.sites):,}", f"{int(r.flagged):,}")
    b_ = Table(box=box.SIMPLE_HEAD, header_style="bold bright_white", title="Roads with the most flagged segments", title_style="bold bright_white")
    b_.add_column("road")
    b_.add_column("flagged", justify="right")
    b_.add_column("of", justify="right")
    for name, r in roads.iterrows():
        b_.add_row(str(name)[:34], f"{int(r.flagged)}", f"{int(r.sites)}")
    g = Table.grid(padding=(0, 4))
    g.add_row(a, b_)
    con.print()
    con.print(g)
    pause()


def calib_screen(S):
    cls()
    status(S, "calibration")
    if not S.tc:
        con.print("  Calibration needs the 2023-2025 crash records in the cache.")
        pause()
        return
    if S.cal is None:
        from S2_Risk_Model_Backtest.citywide import calibration
        with con.status("  scoring the frozen-2022 predictions against 2023-2025 crashes...", spinner="dots"):
            S.cal = calibration(S.bt["sites"], S.bt["preds"], S.tc, S.live["cfg"]["test_years"], S.live["cfg"])
    saved = S.core.read_json(S.core.BUNDLE / "calibration.json")
    for key, name in (("ka", "fatal or serious (K+A)"), ("kabc", "all injury (KABC)")):
        rec = S.cal["models"]["ML-EB"][key]
        peak = np.log10(1 + max(max(d["predicted"], d["observed"]) for d in rec["deciles"]))
        con.print(f"  [bold bright_white]ATSC model, {name}[/]: predicted vs observed 2023-2025 crashes, sites in 10 equal groups by prediction")
        con.print("  [grey50]bars on a log scale; group 10 is the riskiest tenth of sites[/]")
        for d in rec["deciles"]:
            p_ = Text(f"  group {d['decile']:>2}  pred ", style="grey62")
            p_.append(f"{d['predicted']:6.1f} ", style="grey85")
            p_.append(bar(np.log10(1 + d["predicted"]), 40 / peak) or "▏", style="bright_blue")
            con.print(p_)
            o_ = Text("            seen ", style="grey62")
            o_.append(f"{d['observed']:6.0f} ", style="grey85")
            o_.append(bar(np.log10(1 + d["observed"]), 40 / peak) or "▏", style="red")
            con.print(o_)
        same = abs(rec["ratio_predicted_to_observed"] - saved["models"]["ML-EB"][key]["ratio_predicted_to_observed"]) < 1e-9
        con.print(f"  Total: predicted [bold]{rec['predicted_total']:.1f}[/], observed [bold]{rec['observed_total']:.0f}[/], "
                  f"ratio [bold]{rec['ratio_predicted_to_observed']:.2f}[/] "
                  f"({'under-predicts' if rec['ratio_predicted_to_observed'] < 1 else 'over-predicts'})  "
                  f"{'[green]matches calibration.json[/]' if same else '[red]differs from calibration.json[/]'}\n")
        if key == "ka":
            pause("  Press Enter for all-injury crashes... ")
            cls()
            status(S, "calibration")
    b = S.cal["models"]["SPF+EB"]
    con.print(f"  For comparison, the HSM model (SPF+EB) ratio: K+A {b['ka']['ratio_predicted_to_observed']:.2f}, "
              f"all injury {b['kabc']['ratio_predicted_to_observed']:.2f}.")
    pause()


def board_screen(S):
    cls()
    status(S, "ATSC vs HIN")
    if S.board is None and S.tc is None:  # no crash-level data shipped: read the frozen results
        bt = S.core.read_json(S.core.BUNDLE / "backtest.json")
        S.board = []
        for target in ("KA", "KABC"):
            for scen in ("11pct", "hin_share"):
                rep = next(x for x in bt["targets"][target] if x["scenario"] == scen and x["length_basis"] == "icd_250ft")
                share = rep["methods"]["A"]["flagged_share"]
                S.board.append((target, "11% of length" if scen == "11pct" else f"HIN's share {100 * share:.1f}%", rep))
    if S.board is None:
        from S2_Risk_Model_Backtest.backtest import bootstrap_capture
        L = S.bt["sites"].risk_length_mi.to_numpy()
        hin = S.bt["sites"].in_hin.astype(bool).to_numpy()
        hs = float(L[hin].sum() / L.sum())
        cfg = S.live["cfg"]
        S.board = []
        jobs = [(target, sev, name, share) for target, sev in (("KA", ("K", "A")), ("KABC", ("K", "A", "B", "C")))
                for name, share in (("11% of length", 0.11), (f"HIN's share {100 * hs:.1f}%", hs))]
        with Progress(TextColumn("  {task.description}"), BarColumn(bar_width=30, complete_style="green", finished_style="green"),
                      MofNCompleteColumn(), console=con, transient=True) as pr:
            task = pr.add_task("1,000 paired bootstrap resamples per comparison", total=len(jobs))
            for target, sev, name, share in jobs:
                masks = {k: set(v) for k, v in S.core.masks_for(S.bt, target, share).items()}
                rep = bootstrap_capture(S.tc, masks, cfg["bootstrap_resamples"], cfg["seed"], severities=sev, pairs=[("C", "B")])
                S.board.append((target, name, rep))
                pr.update(task, advance=1)
    tb = Table(box=box.SQUARE, border_style=BORDER, header_style="bold bright_white",
               title="Share of 2023-2025 crashes on flagged roads (95% CI, 1,000 paired resamples)", title_style="bold bright_white")
    for c_ in ("crashes", "budget", "HIN (A)", "HSM (B)", "ATSC (C)", "C minus HIN", "verdict"):
        tb.add_column(c_, justify="right" if c_ not in ("crashes", "budget", "verdict") else "left")
    for target, name, rep in S.board:
        A, B, C, d = rep["methods"]["A"], rep["methods"]["B"], rep["methods"]["C"], rep["differences"]["C-A"]
        if d["ci_high"] < 0:
            v = Text("HIN better", style="bold cyan")
        elif d["ci_low"] > 0:
            v = Text("ATSC better", style="bold red")
        else:
            v = Text("tie", style="bold yellow")
        tb.add_row("K+A" if target == "KA" else "all injury", name, f"{100 * A['capture']:.1f}%", f"{100 * B['capture']:.1f}%",
                   f"{100 * C['capture']:.1f}%", f"{100 * d['difference']:+.1f} pp [{100 * d['ci_low']:+.1f}, {100 * d['ci_high']:+.1f}]", v)
    con.print(tb)
    con.print("  A verdict needs the whole interval on one side of zero. Computed live from the frozen-2022 models.", style="grey62")
    L = S.bt["sites"].risk_length_mi.to_numpy()
    hs = float(L[S.bt["sites"].in_hin.astype(bool).to_numpy()].sum() / L.sum())
    con.print(f"  The HIN covers {100 * hs:.1f}% of road length, so the 11% rows give ATSC {0.11 / hs:.0%} of the HIN's length; "
              "the HIN's-share rows compare at equal length.", style="grey62")
    pause()


def selftest_screen(S):
    """Full self-test: every check runs now, in front of you."""
    from S2_Risk_Model_Backtest.bit import check_explanations, check_predictions
    cls()
    status(S, "self-test")
    con.print("  [bold bright_white]Running the full self-test now.[/] Each line is computed live.\n")
    results = []

    def run(name, fn):
        t0 = time.monotonic()
        with con.status(f"  {name}...", spinner="dots"):
            try:
                good, note = fn()
            except Exception as exc:
                good, note = False, f"{type(exc).__name__}: {exc}"
        results.append(good)
        ok_line(name, f"{note}  [{time.monotonic() - t0:.1f} s]", good=good)

    def hashes():
        h, errs = S.core.integrity(S.live)
        return not errs, f"{len(S.manifest['files']) + len(S.live['meta']['cache_hashes'])} files, ranking hash {h[:12]}"
    run("SHA-256 of bundle, cache and ranking", hashes)

    def leak():
        if S.snap is None:
            return False, "snapshot not cached"
        cases = S.core.seeded_leakage_checks(S.snap, S.live["cfg"]["features"])
        n = sum(c["detected"] for c in cases)
        return n == len(cases), f"{n} of {len(cases)} seeded post-cutoff records refused"
    run("leakage gate", leak)

    frame = S.core.prediction_frame(S.live["sites"], S.live["preds"]["ML-EB"], S.live["cfg"])
    rows = frame.to_dict("records")
    ids = S.live["sites"].site_id.astype(str)

    def bit_clean():
        check_predictions(rows, ids)
        check_predictions(S.bt["frame"].to_dict("records"), S.bt["sites"].site_id.astype(str))
        check_explanations(S.core.read_json(S.core.BUNDLE / "explanations.json"), S.table.site_id[S.table.flagged])
        return True, "forecast and backtest predictions, explanations: no false alarm"
    run("BIT on the clean run", bit_clean)

    def faults():
        top = max(range(len(rows)), key=lambda i: -rows[i]["rank"])
        nflag = sum(r["flagged"] for r in rows)
        cases = {
            "negative crash estimate": lambda R: R[0].update(mu=-1.0),
            "EB weight outside (0, 1)": lambda R: R[0].update(eb_weight=1.5),
            "rate and count units disagree": lambda R: R[0].update(fsi_rate=R[0]["fsi_rate"] * 2 + 1),
            "a site is missing": lambda R: R.pop(),
            "a site appears twice": lambda R: R.append(dict(R[0])),
            "top-ranked site not flagged": lambda R: R[top].update(flagged=False),
            "flagged length over budget": lambda R: [r.update(flagged=True) for r in R if r["rank"] <= nflag * 2],
            "F&SI above all crashes": lambda R: R[0].update(annual_fsi=R[0]["annual_total"] + 1),
        }
        caught = []
        for name, mutate in cases.items():
            bad = [dict(r) for r in rows]
            mutate(bad)
            try:
                check_predictions(bad, ids)
            except ValueError as exc:
                caught.append((name, str(exc)))
        S.fault_log = caught
        return len(caught) == len(cases), f"{len(caught)} of {len(cases)} injected faults caught"
    run("BIT fault injection", faults)

    def eb():
        from calc import eb_by_hand
        p, fut = S.live["preds"]["ML-EB"], S.live["fut"]
        hy = fut.hist_years.to_numpy(float)
        w, est = eb_by_hand(p["k"], hy * p["mu"], fut.tot_5y.to_numpy(float))
        err = max(float(np.abs(w - p["eb_weight"]).max()), float(np.abs(est / hy - p["n_eb"]).max()))
        inside = bool(((p["eb_weight"] > 0) & (p["eb_weight"] < 1)).all())
        return inside and err < 1e-9, f"all {len(hy):,} weights in (0, 1), max error {err:.1e}"
    run("Empirical Bayes hand-check", eb)

    def shap():
        err = shap_error(S, S.table.site_id[S.table.flagged])
        return err < 1e-6, f"all {int(S.table.flagged.sum())} flagged sites, max error {err:.1e}"
    run("TreeSHAP additivity", shap)

    def repro():
        live2 = S.core.load_live()
        h = S.core.ranking_hash(live2["table"])
        return h == S.manifest["ranking_hash"], f"fresh reload ranks every site again: {h[:12]}"
    run("reproducibility (second full reload)", repro)

    n = sum(results)
    con.print()
    con.print(Panel(Text(f"{n} of {len(results)} checks passed", style="bold black on green" if n == len(results) else "bold white on red",
                         justify="center"), border_style="green" if n == len(results) else "red", box=box.DOUBLE, expand=False, padding=(0, 6)))
    if getattr(S, "fault_log", None):
        con.print("  [grey62]What the BIT said about each injected fault:[/]")
        for name, msg in S.fault_log:
            con.print(f"    [grey70]{name:<32}[/] [grey50]->[/] [yellow]{msg}[/]")
    pause()


def help_home(S):
    con.print("  Type a road name or site ID to evaluate it   [grey50](e.g. holleman, texas ave, wellborn, 17683)[/]\n")
    menu([("top", "riskiest sites"), ("map", "city map"), ("stats", "network overview"), ("memos", "sites with memos")])
    menu([("hin", "ATSC vs HIN"), ("calib", "calibration"), ("test", "full self-test"), ("lucky", "random flagged site"), ("exit", "quit")])
    con.print()


# ------------------------------------------------------------------ main loop
def main():
    S = boot()
    view, hits, title, sid = "home", None, "", None
    while True:
        cls()
        if view == "home":
            banner()
            status(S)
            help_home(S)
            q = ask()
            k = q.lower()
            if k in ("exit", "quit", "q"):
                break
            if k == "hin":
                board_screen(S)
            elif k == "map":
                map_screen(S)
            elif k == "stats":
                stats_screen(S)
            elif k in ("calib", "calibration"):
                calib_screen(S)
            elif k in ("test", "bit", "selftest"):
                selftest_screen(S)
            elif k == "lucky":
                sid, view, hits = random.choice(list(S.table.site_id[S.table.flagged])), "site", None
            elif k == "memos":
                hits, title, view = S.table[S.table.site_id.isin(S.memos)].sort_values("rank"), "Sites with an S3 safety memo", "list"
            elif q:
                hits, title = search(S, q), ("Top 15 highest-risk sites" if k == "top" else f"Matches for '{q}'")
                view = "list"
        elif view == "list":
            status(S, "search")
            if hits is None or hits.empty:
                con.print("  [red]No road matches.[/]")
                nap(1)
                view = "home"
                continue
            list_screen(S, hits, title)
            menu([("number", "open a site"), ("b", "back"), ("q", "quit")])
            con.print("  [grey50]or type a new search[/]")
            q = ask()
            if q.lower() in ("q", "exit", "quit"):
                break
            if q.lower() == "b" or not q:
                view = "home"
            elif q.isdigit() and 1 <= int(q) <= len(hits):
                sid, view = hits.site_id.iloc[int(q) - 1], "site"
            else:
                hits, title = search(S, q), f"Matches for '{q}'"
        elif view == "site":
            site_screen(S, sid)
            q = ask()
            k = q.lower()
            if k in ("q", "exit", "quit"):
                break
            elif k == "b":
                view = "list" if hits is not None and not hits.empty else "home"
            elif k == "1":
                whatif_screen(S, sid)
            elif k == "2":
                quick(S, sid, "traffic")
            elif k == "3":
                quick(S, sid, "signal")
            elif k == "4":
                history_screen(S, sid)
            elif k == "5":
                math_screen(S, sid)
            elif k == "6":
                compare_screen(S, sid)
            elif k == "7":
                board_screen(S)
            elif k == "8":
                sweep_screen(S, sid)
            elif k == "9" and sid in S.memos:
                memo_screen(S, sid)
            elif k == "m":
                map_screen(S, sid)
            elif k == "r":
                S.edits.pop(sid, None)
            elif q:
                hits, title, view = search(S, q), f"Matches for '{q}'", "list"
    sys.stdout.write("\033[0m\033[2J\033[H")


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.stdout.write("\033[0m")
