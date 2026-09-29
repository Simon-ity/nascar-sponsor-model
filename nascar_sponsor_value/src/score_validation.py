"""Score a hand-coded broadcast sample against the coverage model.

Usage: python src/score_validation.py data/validation/<file>.csv <race_id>

The CSV has one row per 5-second checkpoint: segment, timestamp, shot_type,
cars_visible (car numbers separated by ';' or 'none'), coder_pass (1 or 2).
Pass 2 rows, if present, are used only for inter-coder agreement.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_SEC = 5


def load(path):
    df = pd.read_csv(path, dtype=str).fillna("none")
    df["cars"] = df["cars_visible"].apply(lambda s: [] if s.strip().lower() == "none" else [c.strip() for c in s.split(";") if c.strip()])
    df["coder_pass"] = df.get("coder_pass", "1").astype(int)
    return df


def kappa(p1, p2, cars):
    """Mean per-car Cohen's kappa on 'visible at checkpoint' across cars seen by either pass."""
    m = p1.merge(p2, on=["segment", "timestamp"], suffixes=("_1", "_2"))
    ks = []
    for c in cars:
        a = m["cars_1"].apply(lambda x: c in x).astype(int)
        b = m["cars_2"].apply(lambda x: c in x).astype(int)
        po = (a == b).mean()
        pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
        if pe < 1:
            ks.append((po - pe) / (1 - pe))
    return float(np.mean(ks)) if ks else float("nan"), len(m)


def main(path, race_id):
    coded = load(path)
    p1, p2 = coded[coded.coder_pass == 1], coded[coded.coder_pass == 2]
    model = pd.read_csv(ROOT / "data/processed/car_race_value.csv", dtype={"car_number": str})
    model = model[model.race_id == int(race_id)].copy()
    if model.empty:
        sys.exit(f"race_id {race_id} not in model output")
    model["rank"] = model.avg_ps.rank(method="first")

    counts = pd.Series([c for cars in p1.cars for c in cars]).value_counts()
    model["coded_appearances"] = model.car_number.map(counts).fillna(0)
    total = model.coded_appearances.sum()
    unknown = sorted(set(counts.index) - set(model.car_number))

    top10 = model.loc[model["rank"] <= 10, "coded_appearances"].sum() / total if total else float("nan")
    rho, pval = spearmanr(model.coded_appearances, model.share_p50)
    q75 = model["rank"] > len(model) * 0.75
    seg_minutes = len(p1) * CHECKPOINT_SEC / 60

    print(f"Race {race_id}: {len(p1)} checkpoints ({seg_minutes:.0f} min coded), {int(total)} car appearances")
    print(f"Top-10 share of appearances: {top10:.1%}   (model assumes 45-55%)")
    print(f"Spearman rank correlation, coded vs model share: {rho:.2f} (p={pval:.3f})")
    print(f"Bottom-quarter cars: {model.loc[q75,'coded_appearances'].sum()/total:.1%} of appearances; "
          f"model share {model.loc[q75,'share_p50'].sum():.1%}")
    shots = p1.shot_type.str.lower().value_counts(normalize=True)
    car_shot = shots.reindex(["wide", "tight", "in-car"]).fillna(0).sum()
    with_cars = p1[p1.cars.str.len() > 0]
    print(f"Car shots: {car_shot:.0%} of checkpoints (model assumes 55-80%); "
          f"cars per car shot: {with_cars.cars.str.len().mean():.1f} (model assumes 1.5-2.5)")
    if unknown:
        print(f"Car numbers not in this race's field (check for typos): {unknown}")
    if len(p2):
        k, n = kappa(p1, p2, list(counts.index))
        print(f"Inter-coder agreement: mean per-car Cohen's kappa {k:.2f} over {n} double-coded checkpoints")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
