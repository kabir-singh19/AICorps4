"""Citywide count and severity models, ported from crash_risk_colab_v3 (Nov 4 2026).

    SPF+EB    method B: NB2 safety performance function on KABC, HSM empirical Bayes
    ML-EB     method C: Poisson LightGBM on site features (no own history) for total crashes,
              EB blend with the site's own history, times P(KABC|crash) and P(KA|KABC)
    LightGBM  Poisson LightGBM on KABC with own history as features (comparison only)
    LGB-Tot   the same on total crashes, times P(KABC|crash) (comparison only)
    Stack     non-negative blend of the four, weights fit on the last two training years
    Naive     KABC in the last 3 years / 3

Every fitted object is stored as plain parameters (JSON) or LightGBM text, so it reloads
without pickle. Predictions are per site per year.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

try:
    from .empirical_bayes import eb_estimate
    from .panel import CATEGORICAL, TYPE_FLAGS
except ImportError:
    from empirical_bayes import eb_estimate
    from panel import CATEGORICAL, TYPE_FLAGS

STACK_BASE = ["SPF+EB", "LightGBM", "LGB-Tot", "ML-EB"]
MODELS = ["Naive", "SPF+EB", "LightGBM", "LGB-Tot", "ML-EB", "Stack"]
OSM = ["osm_bars_200m", "osm_bus_stops_200m", "osm_crossings_30m", "osm_restaurants_100m",
       "osm_schools_400m", "osm_signalized_intersections_30m"]
BASE = {
    "segment": ["ln_aadt", "aadt_imputed", "func_class", "speed_limit", "num_lanes", "lane_width_ft",
                "median_type", "median_width_ft", "shoulder_inside_ft", "shoulder_outside_ft", "surface_width_ft",
                "access_control", "curb_left", "curb_right", "truck_pct", "curvature_deg_per_mi",
                "dist_to_intersection_m", "length_mi", "state_route", "osm_sidewalk_share", *OSM,
                "nb_tot_3y", "nb_kabc_3y"],
    "intersection": ["ln_aadt_major", "ln_aadt_minor", "aadt_imputed", "legs", "interchange", "signalized",
                     "state_route", *OSM, "nb_tot_3y", "nb_kabc_3y"],
}
OWN_HIST = ["kabc_l1", "kabc_3y", "ka_3y", "tot_3y", "kabc_5y", "ka_5y", "tot_5y", "hist_years",
            *[f"{f}_3y" for f in TYPE_FLAGS]]
MONOTONE_UP = (set(OWN_HIST) - {"hist_years"}) | {"nb_tot_3y", "nb_kabc_3y"}
TRAFFIC = {"ln_aadt", "ln_aadt_major", "ln_aadt_minor"}


# ---------- design matrices ----------
def fc_group(f):
    f = pd.to_numeric(f, errors="coerce")
    return np.select([f <= 2, f == 3, f == 4, f.isin([5, 6])], ["fwy", "pa", "ma", "col"], "loc")


def _const(X):
    X.insert(0, "const", 1.0)
    return X.astype(float)


def spf_design(df, kind):
    X = pd.DataFrame(index=df.index)
    if kind == "segment":
        X["ln_aadt"] = np.log(df["aadt"])
        X["lanes"] = df["num_lanes"].fillna(2).clip(1, 8)
        X["speed10"] = df["speed_limit"].fillna(30) / 10
        X["divided"] = df["divided"]
        X["ln1p_signals"] = np.log1p(df["osm_signalized_intersections_30m"].fillna(0))
        X["ln1p_crossings"] = np.log1p(df["osm_crossings_30m"].fillna(0))
        g = fc_group(df["func_class"])
        for lvl in ("fwy", "pa", "ma", "col"):
            X[f"fc_{lvl}"] = (g == lvl).astype(int)
    else:
        X["ln_aadt_major"] = np.log(df["aadt_major"])
        X["ln_aadt_minor"] = np.log(df["aadt_minor"])
        X["leg4"] = (df["legs"] >= 4).astype(int)
        X["signalized"] = df["signalized"]
        X["ln1p_crossings"] = np.log1p(df["osm_crossings_30m"].fillna(0))
    X["aadt_imputed"] = df["aadt_imputed"]
    X["state_route"] = df["state_route"]
    return _const(X)


def sev_design(df, kind):
    X = pd.DataFrame(index=df.index)
    X["ln_aadt"] = np.log(df["aadt"] if kind == "segment" else df["aadt_major"])
    if kind == "segment":
        X["speed10"] = df["speed_limit"].fillna(30) / 10
        X["lanes"] = df["num_lanes"].fillna(2).clip(1, 8)
        X["divided"] = df["divided"]
    else:
        X["signalized"] = df["signalized"]
        X["leg4"] = (df["legs"] >= 4).astype(int)
    X["any_bar"] = (df["osm_bars_200m"].fillna(0) > 0).astype(int)
    X["state_route"] = df["state_route"]
    for f in TYPE_FLAGS:
        X[f"{f}_share"] = df[f"{f}_3y"] / np.maximum(df["tot_3y"], 1)
    return _const(X)


def _linear(params, X):
    cols = params["cols"]
    return X.reindex(columns=cols, fill_value=0.0).to_numpy() @ np.asarray(params["beta"], float)


# ---------- method B: NB SPF + EB ----------
def fit_spf(train, kind):
    import statsmodels.api as sm
    from scipy.optimize import minimize_scalar
    X = spf_design(train, kind)
    X = X.loc[:, (X.std() > 0) | (X.columns == "const")]
    y = train["y_kabc"].to_numpy(float)
    off = np.log(train["length_mi"].to_numpy()) if kind == "segment" else None
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pois = sm.GLM(y, X, family=sm.families.Poisson(), offset=off).fit()
        start = np.append(pois.params.to_numpy(), 0.5)
        nb = sm.NegativeBinomial(y, X, offset=off, loglike_method="nb2")
        for meth in ("newton", "bfgs"):
            try:
                res = nb.fit(start_params=start, method=meth, maxiter=1000, disp=0)
            except Exception:
                continue
            p = res.params
            if res.mle_retvals.get("converged", False) and np.isfinite(p).all() and 1e-6 < p["alpha"] < 50:
                return {"kind": kind, "cols": list(X.columns), "beta": p.drop("alpha").tolist(),
                        "alpha": float(p["alpha"]), "method": f"NB2 MLE ({meth})"}

        def nll(log_a):
            return -sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=np.exp(log_a)), offset=off).fit().llf
        r = minimize_scalar(nll, bounds=(np.log(1e-3), np.log(20)), method="bounded", options={"xatol": 1e-3})
        alpha = float(np.exp(r.x))
        res = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=alpha), offset=off).fit()
    return {"kind": kind, "cols": list(X.columns), "beta": res.params.tolist(), "alpha": alpha,
            "method": "GLM NB, profile-likelihood alpha"}


def predict_spf(m, df):
    eta = _linear(m, spf_design(df, m["kind"]))
    if m["kind"] == "segment":
        eta = eta + np.log(df["length_mi"].to_numpy())
    return np.exp(eta)


def eb_annual(mu, df, observed_col, k):
    """EB expected count per year from mu per year, history years and observed history."""
    h = df["hist_years"].to_numpy(float)
    res = eb_estimate(np.maximum(h * mu, 1e-9), df[observed_col].to_numpy(float), k)
    return res.expected / h, res.weight


# ---------- LightGBM family ----------
class Encoder:
    """Category codes for LightGBM, fixed at fit time (unseen values become missing)."""

    def __init__(self, levels=None):
        self.levels = levels or {}

    def fit(self, df):
        self.levels = {c: sorted(str(v) for v in df[c].dropna().unique()) for c in CATEGORICAL if c in df}
        return self

    def frame(self, df, feats):
        X = pd.DataFrame(index=df.index)
        if "ln_aadt" in feats:
            X["ln_aadt"] = np.log(df["aadt"])
        if "ln_aadt_major" in feats:
            X["ln_aadt_major"] = np.log(df["aadt_major"])
            X["ln_aadt_minor"] = np.log(df["aadt_minor"])
        for c in feats:
            if c in X:
                continue
            if c in self.levels:
                codes = {v: i for i, v in enumerate(self.levels[c])}
                X[c] = df[c].map(lambda v: codes.get(str(v), np.nan) if pd.notna(v) else np.nan)
            else:
                X[c] = pd.to_numeric(df[c], errors="coerce") if c in df else np.nan
        return X[feats].astype(float)


def lgb_params(cfg, feats, seed):
    p = dict(cfg["lgb_params"], seed=seed, num_threads=cfg["threads"], verbose=-1)
    p["monotone_constraints"] = [1 if f in MONOTONE_UP else 0 for f in feats]
    return p


def fit_lgb(train, kind, cfg, enc, target, feats, n_rounds=None, seeds=None):
    import lightgbm as lgb
    seeds = seeds or cfg["lgb_seeds"]
    X = enc.frame(train, feats)
    cats = [c for c in CATEGORICAL if c in feats]
    init = np.log(train["exposure"].to_numpy())
    y = train[target].to_numpy(float)
    if n_rounds is None and train["year"].nunique() < 2:
        n_rounds = 300  # one year only (inner stacking fit): no year left for early stopping
    if n_rounds is None:
        last = train["year"].max()
        tr, va = (train["year"] < last).to_numpy(), (train["year"] == last).to_numpy()
        dtr = lgb.Dataset(X[tr], y[tr], init_score=init[tr], categorical_feature=cats, free_raw_data=False)
        dva = lgb.Dataset(X[va], y[va], init_score=init[va], categorical_feature=cats, reference=dtr)
        b = lgb.train(lgb_params(cfg, feats, cfg["seed"]), dtr, cfg["lgb_max_rounds"], valid_sets=[dva],
                      callbacks=[lgb.early_stopping(cfg["lgb_early_stop"], verbose=False)])
        n_rounds = max(int(b.best_iteration), 10)
    boosters = [lgb.train(lgb_params(cfg, feats, s), lgb.Dataset(X, y, init_score=init, categorical_feature=cats),
                          n_rounds) for s in seeds]
    return {"kind": kind, "feats": list(feats), "target": target, "n_rounds": n_rounds, "boosters": boosters}


def predict_lgb(m, enc, df):
    X = enc.frame(df, m["feats"])
    raw = np.mean([b.predict(X, raw_score=True) for b in m["boosters"]], axis=0)
    return np.exp(raw + np.log(df["exposure"].to_numpy()))


def lgb_contrib(m, enc, df):
    """TreeSHAP on the log scale, averaged over seeds, with traffic merged with the exposure offset."""
    X = enc.frame(df, m["feats"])
    contrib = np.mean([b.predict(X, pred_contrib=True)[:, :-1] for b in m["boosters"]], axis=0)
    names = list(X.columns)
    tcols = [i for i, n in enumerate(names) if n in TRAFFIC]
    off = np.log(df["exposure"].to_numpy())
    traffic = contrib[:, tcols].sum(1) + (off - off.mean())
    keep = [i for i in range(len(names)) if i not in tcols]
    return np.column_stack([traffic, contrib[:, keep]]), ["traffic"] + [names[i] for i in keep]


def fit_mleb(train, kind, cfg, enc, seeds=None):
    """k from the last training year, out of sample, then a full refit with the same rounds."""
    feats = BASE[kind]
    last = train["year"].max()
    tr, va = train[train["year"] < last], train[train["year"] == last]
    m0 = fit_lgb(tr, kind, cfg, enc, "y_tot", feats, seeds=[cfg["seed"]])
    mu, y = predict_lgb(m0, enc, va), va["y_tot"].to_numpy(float)
    k = float(np.clip(np.sum((y - mu) ** 2 - y) / np.sum(mu ** 2), 1e-3, 10))
    m = fit_lgb(train, kind, cfg, enc, "y_tot", feats, n_rounds=m0["n_rounds"], seeds=seeds)
    m["k"] = k
    return m


# ---------- severity shares ----------
def fit_share(train, kind, num, den, num_h, den_h):
    import statsmodels.api as sm
    t = train[train[den] > 0]
    base = float(t[num].sum() / t[den].sum())
    X = sev_design(t, kind)
    X = X.loc[:, (X.std() > 0) | (X.columns == "const")]
    m = {"kind": kind, "base": base, "cols": list(X.columns), "beta": None, "num_h": num_h, "den_h": den_h,
         "method": "base rate"}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = sm.GLM((t[num] / t[den]).to_numpy(float), X, family=sm.families.Binomial(),
                         var_weights=t[den].to_numpy(float)).fit()
        if np.isfinite(res.params).all():
            m["beta"], m["method"] = res.params.tolist(), "binomial GLM"
    except Exception as exc:  # recorded, then the base rate is used
        m["method"] = f"base rate (GLM failed: {exc})"
    return m


def predict_share(m, df, prior_m):
    from scipy.special import expit
    p = np.full(len(df), m["base"]) if m["beta"] is None else expit(_linear(m, sev_design(df, m["kind"])))
    p = (df[m["num_h"]].to_numpy(float) + prior_m * p) / (df[m["den_h"]].to_numpy(float) + prior_m)
    return np.clip(p, 0, 1)


# ---------- all models ----------
def fit_all(train, kind, cfg, enc, seeds=None):
    return {"kind": kind, "spf": fit_spf(train, kind),
            "lg": fit_lgb(train, kind, cfg, enc, "y_kabc", BASE[kind] + OWN_HIST, seeds=seeds),
            "lt": fit_lgb(train, kind, cfg, enc, "y_tot", BASE[kind] + OWN_HIST, seeds=seeds),
            "me": fit_mleb(train, kind, cfg, enc, seeds=seeds),
            "s1": fit_share(train, kind, "y_kabc", "y_tot", "kabc_5y", "tot_5y"),
            "s2": fit_share(train, kind, "y_ka", "y_kabc", "ka_5y", "kabc_5y")}


def predict_all(F, df, cfg, enc, w=None):
    """{model: dict(kabc, ka, and for B and C the EB pieces)} per site per year."""
    pm = cfg["sev_prior_m"]
    p_ka, p_kabc = predict_share(F["s2"], df, pm), predict_share(F["s1"], df, pm)
    out = {}
    nv = df["kabc_3y"].to_numpy(float) / 3
    out["Naive"] = {"kabc": nv, "ka": nv * p_ka}
    mu_b = predict_spf(F["spf"], df)
    eb_b, w_b = eb_annual(mu_b, df, "kabc_5y", F["spf"]["alpha"])
    out["SPF+EB"] = {"kabc": eb_b, "ka": eb_b * p_ka, "mu": mu_b, "k": F["spf"]["alpha"], "eb_weight": w_b,
                     "n_eb": eb_b, "p_fsi": p_ka, "count_basis": "KABC"}
    lg = predict_lgb(F["lg"], enc, df)
    out["LightGBM"] = {"kabc": lg, "ka": lg * p_ka}
    lt = predict_lgb(F["lt"], enc, df) * p_kabc
    out["LGB-Tot"] = {"kabc": lt, "ka": lt * p_ka}
    mu_c = predict_lgb(F["me"], enc, df)
    eb_c, w_c = eb_annual(mu_c, df, "tot_5y", F["me"]["k"])
    out["ML-EB"] = {"kabc": eb_c * p_kabc, "ka": eb_c * p_kabc * p_ka, "mu": mu_c, "k": F["me"]["k"],
                    "eb_weight": w_c, "n_eb": eb_c, "p_fsi": p_kabc * p_ka, "count_basis": "all crashes"}
    if w is not None:
        out["Stack"] = {t: sum(w[i] * out[m][t] for i, m in enumerate(STACK_BASE)) for t in ("kabc", "ka")}
    return out


def fit_stack_weights(train, kind, cfg, enc):
    """Non-negative weights minimizing Poisson deviance on the last two training years."""
    from scipy.optimize import minimize
    yrs = sorted(train["year"].unique())
    inner, val = train[train["year"] < yrs[-2]], train[train["year"] >= yrs[-2]]
    if inner["year"].nunique() < 2:
        return np.full(len(STACK_BASE), 1 / len(STACK_BASE))
    P = predict_all(fit_all(inner, kind, cfg, enc, seeds=[cfg["seed"]]), val, cfg, enc)
    X = np.column_stack([P[m]["kabc"] for m in STACK_BASE])
    y = val["y_kabc"].to_numpy(float)

    def f(w):
        mu = X @ w + 1e-9
        return float(np.sum(mu - y * np.log(mu))), X.T @ (1 - y / mu)
    r = minimize(f, np.full(X.shape[1], 1 / X.shape[1]), jac=True, method="L-BFGS-B",
                 bounds=[(0, None)] * X.shape[1])
    return r.x


def model_state(F, w):
    """JSON-serializable parameters (boosters are saved separately as LightGBM text)."""
    state = {k: F[k] for k in ("kind", "spf", "s1", "s2")}
    state["stack_weights"] = [float(x) for x in w]
    state["stack_base"] = STACK_BASE
    for name in ("lg", "lt", "me"):
        state[name] = {k: v for k, v in F[name].items() if k != "boosters"}
        state[name]["n_boosters"] = len(F[name]["boosters"])
    return state


def save_boosters(F, directory):
    from pathlib import Path
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    for name in ("lg", "lt", "me"):
        for i, b in enumerate(F[name]["boosters"]):
            b.save_model(str(d / f"lightgbm_{name}_{F['kind']}_seed{i}.txt"))


def load_models(state, directory):
    import lightgbm as lgb
    from pathlib import Path
    F = {k: state[k] for k in ("kind", "spf", "s1", "s2")}
    for name in ("lg", "lt", "me"):
        F[name] = dict(state[name])
        F[name]["boosters"] = [lgb.Booster(model_file=str(Path(directory) / f"lightgbm_{name}_{state['kind']}_seed{i}.txt"))
                               for i in range(state[name]["n_boosters"])]
    return F, np.asarray(state["stack_weights"], float)
