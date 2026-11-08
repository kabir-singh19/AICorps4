"""Site-year panels for the citywide models (port of crash_risk_colab_v3 build_panel).

One row per site and label year t. Labels count crashes in year t; history windows end on
31 Dec of t-1, so a row never sees its own year or anything later. Static site features come
from the frozen IF-09 snapshot (TxDOT 2019, OSM and network as of 2022-12-31).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TYPE_FLAGS = ("angle", "rear_end", "single_vehicle", "opposite_direction", "night", "wet")
CATEGORICAL = ("median_type", "access_control", "curb_left", "curb_right")
STATE_JURISDICTIONS = ("TxDOT", "City/TxDOT")
MI_PER_M = 1 / 1609.344


def static_frame(snapshot, context):
    """Wide table of site features plus derived exposure inputs, one row per site."""
    sites = pd.DataFrame(snapshot["sites"])
    sites["site_id"] = sites["site_id"].astype(str)
    feats = pd.DataFrame(snapshot["features"])
    wide = feats.pivot(index="site_id", columns="feature_name", values="value").reindex(sites.site_id)
    ctx = pd.DataFrame(context["context"]).set_index("site_id").reindex(sites.site_id)
    if ctx["site_type"].isna().any():
        raise ValueError("site context view misses sites in the snapshot")
    df = sites.set_index("site_id").join(wide).join(ctx.drop(columns=["site_type"]))
    for c in df.columns:
        if c in CATEGORICAL or c in ("site_type", "road_name", "jurisdiction", "route_name", "geojson", "as_of_date"):
            continue
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # TxDOT records an unknown speed limit as 0.
    if "speed_limit" in df:
        df.loc[df["speed_limit"] <= 0, "speed_limit"] = np.nan
    df["length_mi"] = df["risk_length_mi"].astype(float)
    df["state_route"] = df["jurisdiction"].isin(STATE_JURISDICTIONS).astype(int)
    seg = df.site_type == "segment"
    # AADT: segments use their own TxDOT 2019 count; missing ones (OSM-only streets) take the
    # median of their functional class. Intersections use the largest and smallest approach.
    fc = df["func_class"]
    med_by_fc = df.loc[seg & df.aadt.notna()].groupby("func_class")["aadt"].median()
    overall = float(df.loc[seg, "aadt"].median())
    df["aadt_imputed"] = 0
    miss = seg & df.aadt.isna()
    df.loc[miss, "aadt"] = fc[miss].map(med_by_fc).fillna(overall)
    df.loc[miss, "aadt_imputed"] = 1
    inter = ~seg
    for col in ("aadt_major", "aadt_minor"):
        m = inter & df[col].isna()
        df.loc[m, col] = float(df.loc[inter, col].median())
        df.loc[m, "aadt_imputed"] = 1
    df["signalized"] = (df.get("osm_signalized_intersections_30m", 0) > 0).astype(int)
    df["divided"] = (df["median_type"].fillna("0") != "0").astype(int)
    df["exposure"] = np.where(seg, df.aadt * 365 * df.length_mi / 1e6,
                              (df.aadt_major + df.aadt_minor) * 365 / 1e6)
    if not (df.exposure > 0).all():
        raise ValueError("every site needs positive exposure")
    for c in CATEGORICAL:
        if c in df:
            df[c] = df[c].astype("object")
    return df.reset_index()


def neighbor_matrix(static, radius_m):
    """Sparse 0/1 matrix of site pairs whose centers are within radius_m (self excluded)."""
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    xy = static[["x_m", "y_m"]].to_numpy(float)
    pairs = cKDTree(xy).query_pairs(radius_m, output_type="ndarray")
    n = len(static)
    i, j = np.concatenate([pairs[:, 0], pairs[:, 1]]), np.concatenate([pairs[:, 1], pairs[:, 0]])
    return coo_matrix((np.ones(len(i)), (i, j)), shape=(n, n)).tocsr(), len(pairs)


def crash_frame(context):
    c = pd.DataFrame(context["crashes"])
    if c.empty:
        raise ValueError("no matched crashes")
    c["site_id"] = c["site_id"].astype(str)
    c["date"] = pd.to_datetime(c["crash_date"])
    c["year"] = c["crash_year"].astype(int)
    c["tot"] = 1
    c["kabc"] = c["severity"].isin(["K", "A", "B", "C"]).astype(int)
    c["ka"] = c["severity"].isin(["K", "A"]).astype(int)
    c["known"] = (c["severity"] != "U").astype(int)
    for f in TYPE_FLAGS:
        c[f] = c[f].astype(bool).astype(int)
    return c


def build_panel(static, crashes, years, history_start, long_years, nb, last_crash_date):
    """Rows for every site and year in `years`. Label columns are zero for years after the data."""
    last = pd.Timestamp(last_crash_date)
    if crashes["date"].max() > last:
        raise ValueError("leakage: crash records after the stated last crash date")
    ids = static["site_id"].to_numpy()
    cols = ["tot", "kabc", "ka", "known", *TYPE_FLAGS]
    by_year = crashes.groupby(["site_id", "year"])[cols].sum()
    rows = []
    for t in years:
        start5 = max(t - long_years, history_start)
        window = crashes[(crashes.year >= start5) & (crashes.year < t)]
        if len(window) and window["date"].max() >= pd.Timestamp(t, 1, 1):
            raise ValueError(f"leakage: history for label year {t} reaches into {t}")
        g5 = window.groupby("site_id")[cols].sum().reindex(ids, fill_value=0)
        g3 = window[window.year >= t - 3].groupby("site_id")[cols].sum().reindex(ids, fill_value=0)
        g1 = window[window.year == t - 1].groupby("site_id")["kabc"].sum().reindex(ids, fill_value=0)
        p = pd.DataFrame({"site_id": ids, "year": t})
        if pd.Timestamp(t, 12, 31) <= last:
            cur = by_year.xs(t, level="year") if t in by_year.index.get_level_values("year") else by_year.iloc[:0].droplevel(1)
            cur = cur.reindex(ids, fill_value=0)
            p["y_tot"], p["y_kabc"], p["y_ka"], p["y_known"] = (cur[c].to_numpy() for c in ("tot", "kabc", "ka", "known"))
            p["labeled"] = True
        else:
            p["y_tot"] = p["y_kabc"] = p["y_ka"] = p["y_known"] = 0
            p["labeled"] = False
        for c in ("tot", "kabc", "ka", "known"):
            p[f"{c}_3y"] = g3[c].to_numpy()
            p[f"{c}_5y"] = g5[c].to_numpy()
        for f in TYPE_FLAGS:
            p[f"{f}_3y"] = g3[f].to_numpy()
        p["kabc_l1"] = g1.to_numpy()
        p["hist_years"] = t - start5
        p["nb_tot_3y"] = nb @ g3["tot"].to_numpy(float)
        p["nb_kabc_3y"] = nb @ g3["kabc"].to_numpy(float)
        p["hist_max_date"] = window["date"].max() if len(window) else pd.NaT
        rows.append(p)
    panel = pd.concat(rows, ignore_index=True)
    panel = panel.merge(static, on="site_id", how="left")
    if not ((panel.y_ka <= panel.y_kabc) & (panel.y_kabc <= panel.y_tot)).all():
        raise ValueError("labels must satisfy KA <= KABC <= total")
    return panel
