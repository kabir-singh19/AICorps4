"""CPU Poisson gradient boosting with log(length * history years) as offset."""
from __future__ import annotations

import copy

import numpy as np
import xgboost as xgb

try:
    from .empirical_bayes import counts, positive
except ImportError:
    from empirical_bayes import counts, positive


class PoissonRiskModel:
    def __init__(self, seed=42, rounds=200, max_depth=3, learning_rate=0.05, threads=2):
        if rounds < 1 or max_depth < 1 or not 0 < learning_rate <= 1 or not 1 <= threads <= 2:
            raise ValueError("invalid CPU boosting parameters")
        self.parameters = {"objective": "count:poisson", "eval_metric": "poisson-nloglik",
                           "tree_method": "hist", "device": "cpu", "nthread": threads,
                           "seed": seed, "max_depth": max_depth, "eta": learning_rate,
                           "subsample": 1.0, "colsample_bytree": 1.0, "base_score": 1.0}
        self.rounds = rounds

    def matrix(self, X, exposure, y=None):
        x, e = np.asarray(X, dtype=float), positive(exposure, "exposure")
        if x.ndim != 2 or e.shape != (len(x),) or not np.isfinite(x).all():
            raise ValueError("invalid boosting inputs")
        return xgb.DMatrix(x, label=y, base_margin=np.log(e), nthread=self.parameters["nthread"])

    def fit(self, X, y, exposure):
        y = counts(y)
        if y.shape != (len(X),) or y.sum() == 0:
            raise ValueError("boosting requires aligned, nonzero total crash history")
        self.booster = xgb.train(self.parameters, self.matrix(X, exposure, y), num_boost_round=self.rounds)
        return self

    def predict(self, X, exposure):
        return positive(self.booster.predict(self.matrix(X, exposure)), "ML predictions")

    def contributions(self, X, exposure):
        # Exact TreeSHAP; final column is the bias including the exposure offset.
        matrix = self.matrix(X, exposure)
        values = self.booster.predict(matrix, pred_contribs=True, approx_contribs=False)
        margin = self.booster.predict(matrix, output_margin=True)
        if not np.allclose(values.sum(axis=1), margin, rtol=1e-5, atol=1e-5):
            raise RuntimeError("SHAP additivity check failed")
        return values

    def out_of_fold_predict(self, X, y, exposure, folds=5):
        """Predict every site from a model that never saw that site's crashes.

        Used to estimate the EB dispersion k: in-sample boosted predictions sit too close to the
        observed counts, which understates k and pushes every EB weight toward 1. Folds are a
        seeded permutation of sites, so the result is reproducible.
        """
        x, y, e = np.asarray(X, dtype=float), counts(y), positive(exposure, "exposure")
        if not 2 <= folds <= len(y):
            raise ValueError("out-of-fold prediction needs 2 <= folds <= number of sites")
        order = np.random.default_rng(self.parameters["seed"]).permutation(len(y))
        predictions = np.empty(len(y))
        for held_out in np.array_split(order, folds):
            train = np.setdiff1d(order, held_out, assume_unique=True)
            if y[train].sum() == 0:
                raise ValueError("an out-of-fold training split has no crashes; use fewer folds")
            fold_model = copy.copy(self).fit(x[train], y[train], e[train])
            predictions[held_out] = fold_model.predict(x[held_out], e[held_out])
        return predictions

    def save(self, path):
        self.booster.save_model(str(path))

    @classmethod
    def load(cls, path, parameters, rounds):
        obj = cls()
        obj.parameters, obj.rounds = parameters, rounds
        obj.booster = xgb.Booster(params={"nthread": parameters["nthread"], "device": "cpu"})
        obj.booster.load_model(str(path))
        return obj
