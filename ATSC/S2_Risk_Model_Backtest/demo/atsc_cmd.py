"""ATSC road evaluator: a command-prompt style terminal tool.

    bash ~/Desktop/AICorps4/ATSC/S2_Risk_Model_Backtest/demo/atsc.sh

Every number is computed live by the saved S2 models; boot steps are real (model reload, full
recompute of all sites, ranking-hash check against the frozen run).
"""
import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
if os.name == "nt":  # Windows: turn on ANSI colors and UTF-8 box drawing
    os.system("")
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

con = Console(style="grey85 on black", highlight=False)
PROMPT = "C:\\ATSC> "
BORDER = "grey50"

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


# ------------------------------------------------------------------ screen helpers
def cls():
    sys.stdout.write("\033[40m\033[2J\033[H")
    sys.stdout.flush()


def banner():
    for i in range(6):
        con.print("  " + " ".join(LETTERS[c][i] for c in "ATSC"), style="bold bright_white")
    con.print("  AI Traffic-Safety Consultant  [grey50]|[/]  S2 crash risk model  [grey50]|[/]  College Station, TX")
    con.print()


def status(S, where=""):
    t = Text()
    t.append(f" ATSC ", style="bold black on grey85")
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


def pause():
    ask("\n  Press Enter to go back... ")


def menu(items):
    t = Text("  ")
    for key, lab in items:
        t.append(f"[{key}]", style="bold bright_white")
        t.append(f" {lab}   ", style="grey70")
    con.print(t)


# ------------------------------------------------------------------ boot
class State:
    pass


def boot():
    cls()
    banner()
    con.print("  Initializing ATSC risk engine...", style="bright_white")
    con.print()
    S = State()

    def step(label, fn):
        con.print(f"  {label:<46}", end="")
        for _ in range(3):
            con.print(".", end="")
            time.sleep(0.1)
        t0 = time.monotonic()
        try:
            note = fn()
        except Exception as exc:
            con.print(f" [bold red]FAILED[/]  {exc}")
            raise SystemExit(1)
        bad = "MISMATCH" in note
        con.print(f" {'[bold red]WARN[/]' if bad else '[bold green]OK[/]'}  [grey62]{note} ({time.monotonic() - t0:.1f} s)[/]")

    def libs():
        import core
        S.core = core
        return "numpy, pandas, lightgbm, S2 package"

    def bundle():
        S.manifest = S.core.read_json(S.core.BUNDLE / "manifest.json")
        return S.manifest["run_id"]

    def models():
        S.live = S.core.load_live()
        n = sum(len(S.live["models"][k][f]["boosters"]) for k in S.live["models"] for f in ("me", "lg", "lt"))
        return f"{n} LightGBM boosters, seeds {S.live['cfg']['lgb_seeds']}"

    def verify():
        S.hash, S.errors = S.core.integrity(S.live)
        S.hash_ok = not S.errors
        if S.errors:
            return "[bold red]MISMATCH[/] " + "; ".join(S.errors)[:300]
        return f"ranking hash {S.hash[:12]} matches the frozen run"

    def backtest():
        c = S.core
        S.bt = c.load_live("backtest")
        S.bt["frame"] = c.prediction_frame(S.bt["sites"], S.bt["preds"]["ML-EB"], S.bt["cfg"])
        S.bt["pos"] = {s: i for i, s in enumerate(S.bt["sites"].site_id.astype(str))}
        S.tc = c.test_crash_records() if (c.CACHE / "test_crashes.parquet").exists() else None
        return "frozen at 2022-12-31, 2023-2025 held out"

    for label, fn in (("Loading libraries", libs), ("Opening frozen run bundle", bundle),
                      ("Reloading models, recomputing all sites", models), ("Verifying ranking hash", verify),
                      ("Loading frozen-2022 backtest models", backtest)):
        step(label, fn)
    S.table = S.live["table"]
    S.rank = S.table.set_index("site_id")
    S.pos = {s: i for i, s in enumerate(S.live["sites"].site_id.astype(str))}
    S.hist = S.core.read_json(S.core.BUNDLE / "site_history.json")
    S.edits = {}
    S.base = {}
    S.board = None
    con.print()
    con.print(f"  [bold green]Ready.[/] {len(S.table):,} sites ranked, {int(S.table.flagged.sum())} flagged (11% of road length).")
    time.sleep(0.8)
    return S


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


# ------------------------------------------------------------------ screens
def search(S, q):
    t = S.table
    if q.lower() == "top":
        return t.sort_values("rank").head(15)
    ql = q.lower()
    return t[t.site_id.str.contains(ql, regex=False) | t.road_name.str.lower().str.contains(ql, regex=False)].sort_values("rank").head(20)


def list_screen(S, hits, title):
    tb = Table(box=box.SQUARE, border_style=BORDER, header_style="bold bright_white", title=title, title_style="bold bright_white")
    for c, j in (("#", "right"), ("rank", "right"), ("road", "left"), ("type", "left"), ("ATSC", "center"), ("HIN", "center"), ("K+A/mi/yr", "right")):
        tb.add_column(c, justify=j)
    for n, (_, h) in enumerate(hits.iterrows(), 1):
        tb.add_row(str(n), f"#{int(h['rank']):,}", h.road_name[:52], h.site_type,
                   "[bold red]FLAG[/]" if h.flagged else "[grey50]-[/]", "[cyan]yes[/]" if h.in_hin else "[grey50]-[/]", f"{h.fsi_rate:.2f}")
    con.print(tb)


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
    tags.append(f"   {t.jurisdiction}, {r.risk_length_mi:.4f} mi, site {sid}", style="grey62")
    rank_txt = Text(f"#{a['rank']:,}", style="bold bright_white")
    rank_txt.append(f" of {len(S.table):,}", style="grey62")
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
    import numpy as np
    c = s["contrib"][:-1]
    top = np.argsort(-np.abs(c))[:6]
    cmax = float(np.abs(c[top]).max()) or 1
    f = Table(box=box.SIMPLE_HEAD, border_style=BORDER, header_style="bold bright_white", title="What drives it (TreeSHAP)", title_style="bold bright_white")
    f.add_column("push", justify="right")
    f.add_column("", min_width=14)
    f.add_column("factor")
    for j in top:
        bar = "█" * max(1, int(round(12 * abs(c[j]) / cmax)))
        f.add_row(Text(f"{c[j]:+.3f}", style="red" if c[j] > 0 else "green"), Text(bar, style="red" if c[j] > 0 else "green"), label(S, feats[j], rr))
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
    quick = ("3", "remove signal" if e.get("signalized", r.signalized) else "add signal") if r.site_type == "intersection" else ("3", "speed -10 mph")
    menu([("1", "change a feature"), ("2", "traffic +50%"), quick, ("4", "crash history"), ("5", "the math")])
    menu([("6", "compare with another road"), ("7", "ATSC vs HIN"), ("r", "reset changes"), ("b", "back"), ("q", "quit")])
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
        t.append("█" * round(ka * scale), style="red")
        t.append("█" * round(bc * scale), style="yellow")
        t.append("░" * round(o * scale), style="grey50")
        t.append(f"  {v[0]} crashes, {ka} K+A", style="grey70")
        con.print(t)
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
    import numpy as np
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
    knobs = SEG_KNOBS if r.site_type == "segment" else INT_KNOBS
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
            con.print(f"  [red]Out of range.[/]")
            time.sleep(0.8)
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
        con.print("  Re-running 1,000 paired bootstrap resamples on the 2023-2025 crashes...", style="grey70")
        from S2_Risk_Model_Backtest.backtest import bootstrap_capture
        L = S.bt["sites"].risk_length_mi.to_numpy()
        hin = S.bt["sites"].in_hin.astype(bool).to_numpy()
        hs = float(L[hin].sum() / L.sum())
        cfg = S.live["cfg"]
        S.board = []
        for target, sev in (("KA", ("K", "A")), ("KABC", ("K", "A", "B", "C"))):
            for name, share in (("11% of length", 0.11), (f"HIN's share {100 * hs:.1f}%", hs)):
                masks = {k: set(v) for k, v in S.core.masks_for(S.bt, target, share).items()}
                rep = bootstrap_capture(S.tc, masks, cfg["bootstrap_resamples"], cfg["seed"], severities=sev, pairs=[("C", "B")])
                S.board.append((target, name, rep))
        cls()
        status(S, "ATSC vs HIN")
    tb = Table(box=box.SQUARE, border_style=BORDER, header_style="bold bright_white",
               title="Share of 2023-2025 crashes on flagged roads (95% CI, 1,000 paired resamples)", title_style="bold bright_white")
    for c_ in ("crashes", "budget", "HIN (A)", "ATSC (C)", "C minus HIN", "verdict"):
        tb.add_column(c_, justify="right" if c_ not in ("crashes", "budget", "verdict") else "left")
    for target, name, rep in S.board:
        A, C, d = rep["methods"]["A"], rep["methods"]["C"], rep["differences"]["C-A"]
        if d["ci_high"] < 0:
            v = Text("HIN better", style="bold cyan")
        elif d["ci_low"] > 0:
            v = Text("ATSC better", style="bold red")
        else:
            v = Text("tie", style="bold yellow")
        tb.add_row("K+A" if target == "KA" else "all injury", name, f"{100 * A['capture']:.1f}%", f"{100 * C['capture']:.1f}%",
                   f"{100 * d['difference']:+.1f} pp [{100 * d['ci_low']:+.1f}, {100 * d['ci_high']:+.1f}]", v)
    con.print(tb)
    con.print("  A verdict needs the whole interval on one side of zero. Computed live from the frozen-2022 models.", style="grey62")
    pause()


def help_home(S):
    con.print("  Type a road name or site ID to evaluate it   [grey50](e.g. holleman, texas ave, 17683)[/]")
    menu([("top", "highest-risk sites"), ("hin", "ATSC vs HIN"), ("exit", "quit")])
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
            if q.lower() in ("exit", "quit", "q"):
                break
            if q.lower() == "hin":
                board_screen(S)
            elif q:
                hits, title = search(S, q), ("Top 15 highest-risk sites" if q.lower() == "top" else f"Matches for '{q}'")
                view = "list"
        elif view == "list":
            status(S, "search")
            if hits is None or hits.empty:
                con.print(f"  [red]No road matches.[/]")
                time.sleep(1)
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
