"""Findings, charts and the calculator's data file. Run after model.py."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

from model import (DB, PARAMS, DAYTONA_500, load_starters, prepare, _shares, solve_alpha,
                   draw_params, p_qualify_daytona500, simulate)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"
FIG = ROOT / "images"
FIG.mkdir(parents=True, exist_ok=True)

from viz import use_style, headline, source, short_track, FIELD as ACCENT, NY, INK, INK_2 as MUTED, CONTEXT
use_style()
NET_ORDER = ["FOX", "FS1", "PRIME VIDEO", "TNT", "USA", "NBC"]


def fmt_k(x):
    return f"${x/1e6:.2f}M" if x >= 1e6 else f"${x/1e3:,.0f}K"


def backmarker_run(df):
    """Value of a typical No. 44-style run in each race: cars in the bottom quarter of
    the field by average running position, no laps led, not crashed out.
    Median across those cars, per race."""
    pct = df.groupby("race_id").avg_ps.rank(pct=True)
    m = (pct >= 0.75) & (df.lead_laps == 0) & ~df.status.fillna("").str.contains("Accident")
    g = df[m].groupby(["race_id", "race_date", "track_name", "broadcaster", "viewers_m"])
    return g.agg(value_p10=("value_p10", "median"), value_p50=("value_p50", "median"),
                 value_p90=("value_p90", "median"), clear_sec=("clear_sec_p50", "median"),
                 n=("value_p50", "size")).reset_index().sort_values("race_date")


def fig_concentration(df, V):
    """Share of season sponsor value by car, ranked."""
    car_idx = df.groupby("car_number").indices
    carval = np.array([V[:, i].sum(1) for i in car_idx.values()]).T
    shares = carval / carval.sum(1, keepdims=True)
    order = np.argsort(-np.median(shares, 0))
    med = np.median(shares, 0)[order]
    cum = np.cumsum(med)
    names = np.array([str(k) for k in car_idx.keys()])[order]
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = [NY if n == "44" else (ACCENT if i < 10 else CONTEXT) for i, n in enumerate(names)]
    ax.bar(range(1, len(med) + 1), med * 100, color=colors, width=0.78)
    ax.set_xlabel("Cars ranked by 2025 broadcast exposure value")
    ax.set_ylabel("Share of all sponsor value (%)")
    k44 = list(names).index("44") + 1
    ax.annotate("No. 44 (14 starts)", (k44, med[k44 - 1] * 100 + 0.1), xytext=(k44 - 9, 2.6),
                arrowprops=dict(arrowstyle="-", color=INK, lw=1), color=INK, fontsize=10, fontweight="bold")
    ax.text(5.5, med[0] * 100 * 0.93, f"Top 10: {cum[9]:.0%} of all value", color=INK, fontsize=11, fontweight="bold")
    headline(fig, "The top 10 cars take 40% of sponsor TV value",
             "Median share of 2025 primary-sponsor broadcast value by car, 2,000 simulations")
    source(fig)
    fig.savefig(FIG / "concentration.png"); plt.close(fig)
    return {"top10_share": float(cum[9]), "bottom20_share": float(med[-20:].sum()), "n_cars": len(med)}


def fig_curve(df):
    """Clear seconds on screen vs average running position (all 2025 starts)."""
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ok = ~df.status.fillna("").str.contains("Accident")
    led = df.lead_laps > 0
    ax.scatter(df.avg_ps[ok & ~led], df.clear_sec_p50[ok & ~led], s=14, color=CONTEXT, alpha=.55, label="Starts, no laps led")
    ax.scatter(df.avg_ps[ok & led], df.clear_sec_p50[ok & led], s=18, color=ACCENT, alpha=.75, label="Starts that led laps")
    ny = df[df.is_ny_racing]
    ax.scatter(ny.avg_ps, ny.clear_sec_p50, s=60, color=NY, edgecolor="white", linewidth=1.2, label="No. 44", zorder=3)
    ax.set_yscale("log")
    ax.set_yticks([10, 20, 50, 100, 200, 500, 1000])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}s"))
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_ylim(df.clear_sec_p50.min() * 0.8, df.clear_sec_p50.max() * 1.3)
    ax.set_xlabel("Average running position"); ax.set_ylabel("Clear logo time per race (log scale)")
    ax.legend(loc="upper right")
    headline(fig, "Camera time falls off fast behind the leaders",
             "Median clear primary-logo seconds per start, all 1,369 starts of 2025 (crashes excluded)")
    source(fig)
    fig.savefig(FIG / "exposure_curve.png"); plt.close(fig)


def fig_ny(ny):
    """One column per No. 44 start, in date order along the x axis. Color marks FOX's
    window (FOX + FS1), each column carries its median as a number, and a dashed line
    marks the median start."""
    n = len(ny)
    x = np.arange(n)
    fox = ny.broadcaster.isin(["FOX", "FS1"]).values
    col = np.where(fox, ACCENT, CONTEXT)
    p10, p50, p90 = ny.value_p10.values / 1e3, ny.value_p50.values / 1e3, ny.value_p90.values / 1e3
    typical = np.median(p50)
    ymax = p90.max() * 1.12

    fig, ax = plt.subplots(figsize=(13, 6.6))
    ax.vlines(x, p10, p90, color=col, alpha=.35, lw=12)
    ax.scatter(x, p50, color=col, s=90, edgecolor="white", linewidth=1.4, zorder=3)
    for xi, v, hi in zip(x, p50, p90):
        ax.text(xi, hi + ymax * 0.015, f"${v:,.0f}K", ha="center", va="bottom", fontsize=10, fontweight="bold", color=INK)

    # Column labels: the date in ink, then track and network underneath.
    lab = ax.get_xaxis_transform()
    for xi, d, t, b in zip(x, pd.to_datetime(ny.race_date), ny.track_name, ny.broadcaster):
        ax.text(xi, -0.03, f"{d:%b %-d}", transform=lab, ha="center", va="top", fontsize=10.5, color=INK, fontweight="bold")
        ax.text(xi, -0.085, f"{short_track(t)}\n{b.title() if b == 'PRIME VIDEO' else b}", transform=lab,
                ha="center", va="top", fontsize=9, color=MUTED, linespacing=1.3)
    ax.set_xticks(x, [""] * n)
    ax.tick_params(axis="x", length=0)

    # FOX's window comes first because the season is in date order.
    k = int(fox.sum())
    ax.axvline(k - 0.5, color=MUTED, lw=1)
    ax.text(k - 0.62, ymax * 0.97, "FOX'S WINDOW\n(FOX, FS1)", ha="right", va="top", fontsize=9, color=INK, fontweight="bold")
    ax.text(k - 0.38, ymax * 0.97, "REST OF SEASON", ha="left", va="top", fontsize=9, color=INK, fontweight="bold")
    ax.hlines(typical, -0.6, n - 0.4, color=MUTED, lw=1.2, ls="--", zorder=1)
    ax.text(n - 0.3, typical, f"Median start\n${typical:,.0f}K", ha="left", va="center", fontsize=9, color=MUTED)

    i_top = int(np.argmax(p50))
    if ny.status.fillna("").iloc[i_top].startswith("Accident"):
        ax.text(x[i_top] + 0.3, p50[i_top], "Crashed out:\nreplays add camera\ntime in the model",
                fontsize=8.5, color=MUTED, style="italic", va="center")

    ax.set_xlim(-0.6, n + 0.35)  # right margin holds the median label
    ax.set_ylim(0, ymax)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}K"))
    ax.set_ylabel("Primary-sponsor value per start")
    ax.grid(axis="x", visible=False)
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.15)
    headline(fig, "The No. 44's best TV value came in FOX's window",
             "Each 2025 start in date order: median value (dot and number) and 80% range (bar). Plum = FOX's window, rose = rest of season")
    source(fig)
    fig.savefig(FIG / "ny44_races.png"); plt.close(fig)


def fig_network(bm):
    g = bm.groupby("broadcaster").agg(v=("value_p50", "median"), aud=("viewers_m", "median"), n=("race_id", "size"))
    g = g.reindex([n for n in NET_ORDER if n in g.index])
    fig, ax = plt.subplots(figsize=(10, 5))
    cols = [ACCENT if n in ("FOX", "FS1") else CONTEXT for n in g.index]
    ax.bar(g.index, g.v / 1e3, color=cols, width=0.65)
    for i, (v, a, n) in enumerate(zip(g.v, g.aud, g.n)):
        ax.text(i, v / 1e3 + 4, fmt_k(v), ha="center", fontsize=13, fontweight="bold", color=INK)
        ax.text(i, 5, f"{a:.1f}M viewers\n{n} races", ha="center", fontsize=9, color="white" if n and cols[i] == ACCENT else INK)
    ax.set_ylabel("Value of one backmarker start ($K)")
    ax.set_ylim(0, g.v.max() / 1e3 * 1.18)
    ax.grid(axis="x", visible=False)
    headline(fig, "A back-of-field start is worth 3x more on FOX than on USA",
             "Median primary-sponsor value of a bottom-quarter run, no laps led, by 2025 network. FOX's window in plum")
    source(fig, "Source: NASCAR loop data 2025 · Audiences: Nielsen via The Daily Downforce tracker")
    fig.savefig(FIG / "network_window.png"); plt.close(fig)
    return g


def _ols_hc3(y, X):
    """OLS with HC3 robust standard errors. Returns coefficients, SEs, R², residual df."""
    XtXi = np.linalg.inv(X.T @ X)
    b = XtXi @ X.T @ y
    e = y - X @ b
    h = np.einsum("ij,jk,ik->i", X, XtXi, X)
    meat = X.T @ (X * (e ** 2 / (1 - h) ** 2)[:, None])
    se = np.sqrt(np.diag(XtXi @ meat @ XtXi))
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return b, se, r2, len(y) - X.shape[1]


def audience_tests():
    """Network effect on real audiences, no model assumptions: Kruskal-Wallis across
    networks, and OLS on log(viewers) with network + track type dummies (USA and
    intermediate ovals as the baseline). Networks air in fixed parts of the season,
    so the network term also carries some time-of-year effect."""
    con = duckdb.connect(str(DB), read_only=True)
    r = con.execute("SELECT race_id, race_name, race_date, broadcaster, track_type FROM races").df()
    con.close()
    r = r.merge(pd.read_csv(ROOT / "data" / "raw" / "viewership_2025.csv")[["race_id", "viewers_m"]], on="race_id")
    kw = stats.kruskal(*[g.viewers_m for _, g in r.groupby("broadcaster")])

    def fit(d):
        X = pd.get_dummies(d[["broadcaster", "track_type"]]).astype(float)
        X = X.drop(columns=["broadcaster_USA", "track_type_intermediate"])
        X.insert(0, "const", 1.0)
        b, se, r2, dof = _ols_hc3(np.log(d.viewers_m.values), X.values)
        t = stats.t.ppf(0.975, dof)
        coef = pd.DataFrame({"x": np.exp(b), "lo": np.exp(b - t * se), "hi": np.exp(b + t * se)}, index=X.columns)
        return coef, r2

    coef, r2 = fit(r)
    coef_no500, _ = fit(r[r.race_id != DAYTONA_500])
    nets = coef.loc[coef.index.str.startswith("broadcaster_")].rename(index=lambda k: k.replace("broadcaster_", ""))
    res = {"kruskal_H": float(kw.statistic), "kruskal_p": float(kw.pvalue), "r2": float(r2), "n_races": len(r),
           "vs_usa": {k: {c: float(v) for c, v in row.items()} for k, row in nets.iterrows()},
           "fox_vs_usa_without_daytona500": float(coef_no500.loc["broadcaster_FOX", "x"])}
    return r, nets, res


def fig_audience_regression(nets, res):
    """Audience multiplier vs. USA per network, 95% CI, controlling for track type."""
    order = [n for n in NET_ORDER if n in nets.index or n == "USA"]
    rows = nets.reindex(order)
    rows.loc["USA"] = [1.0, 1.0, 1.0]
    y = np.arange(len(order))[::-1]
    col = [ACCENT if n in ("FOX", "FS1") else CONTEXT for n in order]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.axvline(1, color=MUTED, lw=1.2, ls="--", zorder=1)
    ax.hlines(y, rows.lo, rows.hi, color=col, lw=9, alpha=.4)
    ax.scatter(rows.x, y, color=col, s=90, edgecolor="white", linewidth=1.4, zorder=3)
    for yi, n, (x, lo, hi) in zip(y, order, rows[["x", "lo", "hi"]].values):
        lab = "baseline" if n == "USA" else f"{x:.1f}×"
        ax.text(max(hi, 1) + 0.08, yi, lab, va="center", fontsize=10.5, fontweight="bold" if n != "USA" else "normal",
                color=INK if n != "USA" else MUTED)
    ax.set_yticks(y, [n.title() if n == "PRIME VIDEO" else n for n in order])
    ax.set_xlim(0, rows.hi.max() + 0.6)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}×"))
    ax.set_xlabel("Audience relative to a USA race (95% confidence interval)")
    ax.grid(axis="y", visible=False)
    headline(fig, f"A FOX race draws about {res['vs_usa']['FOX']['x']:.1f}× the audience of a USA race",
             f"Regression on log(viewers), {res['n_races']} races of 2025, controlling for track type, robust (HC3) errors. "
             f"R² = {res['r2']:.2f}. FOX's window in plum")
    source(fig, "Source: Nielsen via The Daily Downforce tracker · NASCAR schedule 2025")
    fig.savefig(FIG / "audience_regression.png"); plt.close(fig)


def fig_audience_by_network(r, res):
    """Every 2025 race's audience, grouped by network, with the network median."""
    rng = np.random.default_rng(3)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for i, n in enumerate(NET_ORDER):
        v = r.loc[r.broadcaster == n, "viewers_m"].values
        c = ACCENT if n in ("FOX", "FS1") else CONTEXT
        ax.scatter(i + rng.uniform(-0.16, 0.16, len(v)), v, s=60, color=c, edgecolor="white", linewidth=1.2, zorder=3)
        m = np.median(v)
        ax.hlines(m, i - 0.3, i + 0.3, color=INK, lw=2, zorder=4)
        ax.text(i + 0.34, m, f"{m:.1f}M", va="center", fontsize=9.5, color=INK)
    d5 = r.loc[r.race_id == DAYTONA_500].iloc[0]
    ax.annotate("Daytona 500", (0.12, d5.viewers_m), xytext=(0.45, d5.viewers_m - 0.3), fontsize=9, color=MUTED,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=1))
    ax.set_xticks(range(len(NET_ORDER)), [n.title() if n == "PRIME VIDEO" else n for n in NET_ORDER])
    ax.set_xlim(-0.5, len(NET_ORDER) - 0.2)
    ax.set_ylim(0, r.viewers_m.max() * 1.1)
    ax.set_ylabel("Viewers (millions)")
    ax.grid(axis="x", visible=False)
    headline(fig, "Audiences differ by network, and FOX's window draws the most",
             f"Each dot is one 2025 race; bar = network median. Kruskal–Wallis H = {res['kruskal_H']:.1f}, "
             f"p = {res['kruskal_p']:.5f}. FOX's window in plum")
    source(fig, "Source: Nielsen via The Daily Downforce tracker · NASCAR schedule 2025")
    fig.savefig(FIG / "audience_by_network.png"); plt.close(fig)


def sensitivity(df, base_values_total):
    """One-at-a-time swing: fix each parameter at its low / high end, others at midpoint."""
    d, race_idx, n_races, top10 = prepare(df)
    ny = d.is_ny_racing.values
    mid = {k: (lo + hi) / 2 for k, (lo, hi, _) in PARAMS.items()}

    def ny_value(p):
        a = solve_alpha(d, race_idx, n_races, top10, p["phi"], p["crash_bonus"], p["top10_target"])
        s = _shares(d.avg_ps.values, d.lead_frac.values, d.crashed.values, race_idx, n_races, a, p["phi"], p["crash_bonus"])
        pool = p["coverage_min"] * 60 * (1 - p["ad_load"]) * p["car_shot_share"] * p["cars_per_shot"] * p["clear_share"]
        cpm = np.where(d.race_id.values == DAYTONA_500, p["cpm_daytona500"], p["cpm"])
        v = s * pool / 30 * cpm * d.viewers_m.values * 1000 * p["primary_share"]
        return v[ny].sum() / ny.sum()

    base = ny_value(mid)
    rows = []
    for k, (lo, hi, basis) in PARAMS.items():
        vlo, vhi = ny_value({**mid, k: lo}), ny_value({**mid, k: hi})
        rows.append({"param": k, "low": lo, "high": hi, "value_at_low": vlo, "value_at_high": vhi,
                     "swing": abs(vhi - vlo), "basis": basis})
    s = pd.DataFrame(rows).sort_values("swing")
    fig, ax = plt.subplots(figsize=(10, 5.6))
    y = np.arange(len(s))
    ax.barh(y, s.value_at_high - base, left=base, color=ACCENT, height=0.62, label="Assumption at high end")
    ax.barh(y, s.value_at_low - base, left=base, color=CONTEXT, height=0.62, label="Assumption at low end")
    ax.axvline(base, color=INK, lw=1.5)
    ax.set_yticks(y, s.param, fontsize=10)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: fmt_k(x)))
    ax.set_xlabel("No. 44 average value per start")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    headline(fig, "Ad pricing and logo clarity move the answer most",
             f"No. 44 value per start when each assumption moves to the end of its range (others at midpoint; base {fmt_k(base)})")
    source(fig)
    fig.savefig(FIG / "sensitivity.png"); plt.close(fig)
    return s, base


def calculator_data(df, draws, n=400):
    """Export what the browser calculator needs: a reference field and a thinned
    sample of Monte Carlo draws. The page recomputes shares in JS, so uncertainty
    and the crash/laps-led toggles stay live."""
    ref = df[df.race_id == 5568].avg_ps.sort_values().round(2).tolist()  # Nashville field as reference
    cols = ["alpha", "phi", "crash_bonus", "coverage_min", "ad_load", "car_shot_share",
            "cars_per_shot", "clear_share", "cpm", "cpm_daytona500", "primary_share"]
    sample = draws[cols].sample(n, random_state=1).round(5)
    races = (df.groupby(["race_id", "race_name", "track_name", "race_date", "broadcaster", "viewers_m"])
               .size().reset_index()[["race_id", "race_name", "track_name", "race_date", "broadcaster", "viewers_m"]])
    races["race_date"] = races["race_date"].astype(str)
    return {"reference_field": ref, "draws": sample.to_dict(orient="list"),
            "races": races.to_dict(orient="records"), "daytona500_id": DAYTONA_500}


def main():
    df = pd.read_csv(OUT / "car_race_value.csv", dtype={"car_number": str})
    V = np.load(OUT / "mc_values.npy")
    draws = pd.read_csv(OUT / "mc_draws.csv")
    q = pd.read_csv(OUT / "qualification.csv")

    conc = fig_concentration(df, V)
    fig_curve(df)
    ny = df[df.is_ny_racing].sort_values("race_date")
    fig_ny(ny)
    bm = backmarker_run(df)
    bm.to_csv(OUT / "backmarker_run_by_race.csv", index=False)
    net = fig_network(bm)
    races_aud, nets, aud = audience_tests()
    fig_audience_regression(nets, aud)
    fig_audience_by_network(races_aud, aud)
    sens, sens_base = sensitivity(load_starters(), None)
    sens.to_csv(OUT / "sensitivity.csv", index=False)

    ny_tot = V[:, df.is_ny_racing.values].sum(1)
    rng = np.random.default_rng(7)
    d500 = bm[bm.race_id == DAYTONA_500].iloc[0]
    pq = p_qualify_daytona500(rng, 100_000)
    fox_window = bm.broadcaster.isin(["FOX", "FS1"])
    summary = {
        "season_total_value": {k: float(np.quantile(V.sum(1), p)) for k, p in [("p10", .1), ("p50", .5), ("p90", .9)]},
        "concentration": conc,
        "ny44": {
            "entries": 15, "starts": int(len(ny)),
            "season_value": {k: float(np.quantile(ny_tot, p)) for k, p in [("p10", .1), ("p50", .5), ("p90", .9)]},
            "per_start_median": float(np.median(ny_tot) / len(ny)),
            "median_clear_sec_per_start": float(ny.clear_sec_p50.median()),
            "median_avg_running_position": float(ny.avg_ps.median()),
            "top15_laps_total": int(ny.top15_laps.sum()),
            "best_value_race": ny.loc[ny.value_p50.idxmax(), ["track_name", "race_date", "value_p50", "status"]].to_dict(),
        },
        "median_car_value_per_race": float(df.groupby("race_id").value_p50.median().mean()),
        "leader_vs_backmarker_seconds": {
            "most_laps_led_median_sec": float(df.loc[df.groupby("race_id").lead_laps.idxmax()].clear_sec_p50.median()),
            "backmarker_median_sec": float(bm.clear_sec.median()),
        },
        "backmarker_run_by_network": {k: {"value_p50": float(v), "median_viewers_m": float(a), "races": int(n)}
                                       for k, (v, a, n) in net[["v", "aud", "n"]].iterrows()},
        "fox_window_share_of_backmarker_value": float(bm[fox_window].value_p50.sum() / bm.value_p50.sum()),
        "fox_window_races": int(fox_window.sum()),
        "daytona500": {
            "backmarker_value_if_in": float(d500.value_p50),
            "p_qualify_mean": float(pq.mean()), "p_qualify_p10": float(np.quantile(pq, .1)),
            "p_qualify_p90": float(np.quantile(pq, .9)),
            "expected_value": float(d500.value_p50 * pq.mean()),
            "open_entries": int(q.loc[q.race_id == DAYTONA_500, "open_entries"].iloc[0]),
        },
        "oversubscribed_races": q[q.oversubscribed][["race_name", "open_entries", "open_non_starters"]].to_dict(orient="records"),
        "audience_tests": aud,
        "sensitivity_base_per_start": float(sens_base),
        "sensitivity_top3": sens.sort_values("swing", ascending=False).head(3)[["param", "value_at_low", "value_at_high"]].to_dict(orient="records"),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (ROOT / "app" / "model_data.json").write_text(json.dumps(calculator_data(df, draws)))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
