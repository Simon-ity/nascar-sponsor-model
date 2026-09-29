"""Broadcast exposure value model for 2025 NASCAR Cup sponsors.

The model estimates how much logo-on-screen value each car delivered in each race,
with the uncertainty carried through a Monte Carlo simulation.

1. Attention allocation (who the cameras show)
   A share phi of car-focused coverage follows the race leader, split by laps led.
   The rest decays with average running position: weight = exp(-alpha * (avg_ps - 1)).
   Cars that crashed out get a small bonus (replays, caution coverage).
   alpha is solved per draw so the top 10 cars take ~50% of coverage, the
   benchmark Relo Metrics reports for NASCAR broadcasts. The leader-follow term
   reflects Rotthoff, Depken & Groothuis (2014), who found laps led, not wins,
   drives time on camera.

2. Seconds on screen
   race coverage seconds x (1 - ad load) x share of shots showing cars
   x cars per shot x share of that time the logos are clear.

3. Dollar value (ad-equivalent)
   seconds / 30 x cost of a 30-second spot, where cost = CPM x viewers / 1000.
   Daytona 500 CPM anchored to reported 2025 FOX spot prices; other races drawn
   from an assumed range. The primary sponsor gets primary_share of the car's value.

4. Qualification risk
   Open (non-chartered) cars can miss the race. In 2025 that happened only at the
   two oversubscribed races, the Daytona 500 and the Chicago street race (Grant
   Park 165). P(qualify) at the Daytona 500 is Beta-distributed from the 2025 outcome.

All assumptions live in PARAMS with their basis, and sensitivity() in analysis.py
shows which ones move the answer.
"""
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "nascar_2025.duckdb"
OUT = ROOT / "data" / "processed"
RNG_SEED = 2025
N_DRAWS = 2000

# name: (low, high, basis) — each is drawn uniformly per Monte Carlo draw
PARAMS = {
    "coverage_min":   (150, 200, "Assumption: green-to-checkered coverage minutes for a Cup race"),
    "ad_load":        (0.20, 0.30, "Assumption: share of race coverage in national commercial breaks"),
    "car_shot_share": (0.55, 0.80, "Assumption: share of race coverage showing cars (vs booth, pit, crowd, graphics)"),
    "cars_per_shot":  (1.5, 2.5, "Assumption: average number of cars identifiable per shot"),
    "clear_share":    (0.25, 0.50, "Assumption: share of on-screen time a car's primary logos are clear and in focus; Relo Metrics reports ~20% of NASCAR frames are blurry"),
    "phi":            (0.10, 0.25, "Assumption: share of car coverage that follows the leader (Rotthoff et al. 2014: laps led drive exposure)"),
    "top10_target":   (0.45, 0.55, "Relo Metrics: cameras focus on the top 10 for about half of each race"),
    "crash_bonus":    (0.005, 0.02, "Assumption: extra share of coverage for each car that crashes out (replays)"),
    "cpm":            (25.0, 55.0, "Assumption: CPM for a regular Cup race; below the Daytona 500 anchor"),
    "cpm_daytona500": (59.0, 74.0, "SBJ via Awful Announcing: 2025 Daytona 500 spots mostly $400-450K, some $500K+, 6.761M viewers"),
    "primary_share":  (0.60, 0.80, "Assumption: primary sponsor's share of a car's logo exposure (hood + quarter panels)"),
}
DAYTONA_500 = 5546
OPEN_SPOTS = 4  # 40-car field, 36 charters


def draw_params(n: int, rng: np.random.Generator) -> pd.DataFrame:
    return pd.DataFrame({k: rng.uniform(lo, hi, n) for k, (lo, hi, _) in PARAMS.items()})


def load_starters() -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute("""
        SELECT race_id, race_name, track_name, track_type, race_date, broadcaster, network_group,
               over_the_air, total_laps, car_number, driver, team_name, sponsor, is_ny_racing,
               avg_ps, lead_laps, top15_laps, finish, status
        FROM starters ORDER BY race_date, finish
    """).df()
    con.close()
    views = pd.read_csv(ROOT / "data" / "raw" / "viewership_2025.csv")[["race_id", "viewers_m"]]
    return df.merge(views, on="race_id", how="left")


def _shares(avg_ps, lead_frac, crashed, race_idx, n_races, alpha, phi, crash_bonus):
    """Coverage share per car for one parameter draw. Arrays are aligned per car-race."""
    w = np.exp(-alpha * (avg_ps - 1.0))
    wsum = np.bincount(race_idx, w, n_races)
    base = w / wsum[race_idx]
    s = (1 - phi) * base + phi * lead_frac
    s = s + crash_bonus * crashed
    return s / np.bincount(race_idx, s, n_races)[race_idx]


def solve_alpha(df, race_idx, n_races, top10, phi, crash_bonus, target):
    """Bisection on alpha so the mean top-10 coverage share across races hits target."""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        s = _shares(df.avg_ps.values, df.lead_frac.values, df.crashed.values,
                    race_idx, n_races, mid, phi, crash_bonus)
        got = np.bincount(race_idx, s * top10, n_races).mean()
        lo, hi = (mid, hi) if got < target else (lo, mid)
    return (lo + hi) / 2


def prepare(df: pd.DataFrame):
    df = df.copy()
    df["lead_frac"] = df["lead_laps"] / df["total_laps"]
    df["crashed"] = df["status"].fillna("").str.contains("Accident").astype(float)
    df["run_rank"] = df.groupby("race_id")["avg_ps"].rank(method="first")
    race_codes, race_idx = np.unique(df["race_id"].values, return_inverse=True)
    top10 = (df["run_rank"] <= 10).astype(float).values
    return df, race_idx, len(race_codes), top10


def simulate(df: pd.DataFrame, n_draws: int = N_DRAWS, seed: int = RNG_SEED):
    """Returns (df with per-car value quantiles, draws table, value matrix [draws x rows])."""
    rng = np.random.default_rng(seed)
    df, race_idx, n_races, top10 = prepare(df)
    P = draw_params(n_draws, rng)
    alphas = np.empty(n_draws)
    values = np.empty((n_draws, len(df)), dtype=np.float32)
    seconds = np.empty((n_draws, len(df)), dtype=np.float32)
    shares = np.empty((n_draws, len(df)), dtype=np.float32)
    viewers = df["viewers_m"].values
    is_d500 = (df["race_id"] == DAYTONA_500).values
    for i, p in enumerate(P.itertuples()):
        a = solve_alpha(df, race_idx, n_races, top10, p.phi, p.crash_bonus, p.top10_target)
        alphas[i] = a
        s = _shares(df.avg_ps.values, df.lead_frac.values, df.crashed.values,
                    race_idx, n_races, a, p.phi, p.crash_bonus)
        pool = p.coverage_min * 60 * (1 - p.ad_load) * p.car_shot_share * p.cars_per_shot * p.clear_share
        sec = s * pool
        cpm = np.where(is_d500, p.cpm_daytona500, p.cpm)
        cost30 = cpm * viewers * 1000.0            # viewers in millions -> CPM * thousands
        shares[i], seconds[i] = s, sec
        values[i] = sec / 30.0 * cost30 * p.primary_share
    P["alpha"] = alphas
    q = lambda m, x: np.quantile(m, x, axis=0)
    df["share_p50"] = q(shares, 0.5)
    df["clear_sec_p10"], df["clear_sec_p50"], df["clear_sec_p90"] = q(seconds, 0.1), q(seconds, 0.5), q(seconds, 0.9)
    df["value_p10"], df["value_p50"], df["value_p90"] = q(values, 0.1), q(values, 0.5), q(values, 0.9)
    df["value_mean"] = values.mean(axis=0)
    return df, P, values


def qualification(con=None) -> pd.DataFrame:
    """Open-car qualification odds per race from 2025 entries."""
    con = con or duckdb.connect(str(DB), read_only=True)
    q = con.execute(f"""
        WITH charter AS (SELECT car_number FROM entries GROUP BY 1 HAVING count(*) = 36)
        SELECT e.race_id, r.race_name, r.track_name,
               count(*) FILTER (WHERE c.car_number IS NULL) AS open_entries,
               count(*) FILTER (WHERE c.car_number IS NULL AND e.started) AS open_starters,
               count(*) FILTER (WHERE c.car_number IS NULL AND NOT e.started) AS open_non_starters
        FROM entries e JOIN races r USING (race_id)
        LEFT JOIN charter c USING (car_number)
        GROUP BY 1, 2, 3 ORDER BY 1
    """).df()
    q["oversubscribed"] = q["open_entries"] > OPEN_SPOTS
    return q


def p_qualify_daytona500(rng, n):
    """Beta posterior: 2025 had 4 of 8 contested open spots filled (the 5th open
    starter came in on the Open Exemption Provisional), with a uniform prior."""
    return rng.beta(1 + 4, 1 + 4, n)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_starters()
    res, draws, values = simulate(df)
    res.to_csv(OUT / "car_race_value.csv", index=False)
    draws.to_csv(OUT / "mc_draws.csv", index=False)
    np.save(OUT / "mc_values.npy", values)
    qualification().to_csv(OUT / "qualification.csv", index=False)
    print(f"rows={len(res)}  draws={len(draws)}  alpha median={draws.alpha.median():.3f}")
    return res, draws, values


if __name__ == "__main__":
    run()
