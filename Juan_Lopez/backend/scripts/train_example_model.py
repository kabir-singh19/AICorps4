"""Rebuild a tiny logistic classifier using generated teaching data only.

Run from backend/: .venv/bin/python scripts/train_example_model.py
No traffic records, university service, or third-party ML dependency is used.
"""
import json
import math
import random
from pathlib import Path

FEATURES = [
    {"key": "speed_mph", "label": "Posted speed", "unit": "mph", "min": 20, "max": 65, "step": 1},
    {"key": "daily_vehicles", "label": "Daily vehicle volume", "unit": "vehicles/day", "min": 1000, "max": 60000, "step": 1000},
    {"key": "lanes", "label": "Travel lanes", "unit": "lanes", "min": 2, "max": 8, "step": 1},
    {"key": "crossings_per_mile", "label": "Pedestrian crossing locations", "unit": "per mile", "min": 0, "max": 12, "step": 1},
]


def sigmoid(value):
    return 1 / (1 + math.exp(-value))


def train():
    rng = random.Random(42)
    records = []
    for _ in range(500):
        x = [rng.random() for _ in FEATURES]
        # Invented relationship for demonstration; no empirical traffic meaning.
        chance = sigmoid(-4 + sum(a * b for a, b in zip([2.5, 2, 1.2, 2], x)))
        records.append((x, int(rng.random() < chance)))
    training, holdout = records[:400], records[400:]
    weights, bias = [0.0] * len(FEATURES), 0.0
    for _ in range(1600):
        errors = [(x, sigmoid(bias + sum(w * value for w, value in zip(weights, x))) - y) for x, y in training]
        bias -= 0.4 * sum(error for _, error in errors) / len(training)
        weights = [w - 0.4 * sum(error * x[j] for x, error in errors) / len(training) for j, w in enumerate(weights)]
    correct = sum((sigmoid(bias + sum(w * v for w, v in zip(weights, x))) >= 0.5) == bool(y) for x, y in holdout)
    return {"model_id": "synthetic-logistic-v1", "name": "Synthetic traffic screening classifier", "algorithm": "Logistic regression", "is_demo": True, "training_source": "500 computer-generated records; labels generated from an invented relationship. No real crash or roadway records.", "training_records": len(training), "holdout_records": len(holdout), "synthetic_holdout_accuracy": correct / len(holdout), "random_seed": 42, "features": FEATURES, "weights": weights, "intercept": bias, "threshold": 0.5, "output": "Score for a synthetic review label; not a crash probability or F&SI rate."}


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "app" / "data" / "example-model.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(train(), indent=2) + "\n")
    print(f"Saved {target.name} (synthetic teaching model only)")
