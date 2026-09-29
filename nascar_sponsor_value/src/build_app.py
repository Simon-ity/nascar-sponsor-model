"""Inject model data into the calculator template -> app/index.html (one self-contained file)."""
import json
from pathlib import Path
from model import PARAMS

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    "coverage_min": ("Race coverage", "{:.0f}–{:.0f} min"), "ad_load": ("Commercial load", "{:.0%}–{:.0%}"),
    "car_shot_share": ("Coverage showing cars", "{:.0%}–{:.0%}"), "cars_per_shot": ("Cars per shot", "{:.1f}–{:.1f}"),
    "clear_share": ("Logos clear and in focus", "{:.0%}–{:.0%}"), "phi": ("Coverage following the leader", "{:.0%}–{:.0%}"),
    "top10_target": ("Top-10 share of coverage", "{:.0%}–{:.0%}"), "crash_bonus": ("Extra coverage for a crash", "{:.1%}–{:.1%}"),
    "cpm": ("CPM, regular race", "${:.0f}–${:.0f}"), "cpm_daytona500": ("CPM, Daytona 500", "${:.0f}–${:.0f}"),
    "primary_share": ("Primary sponsor's share of car", "{:.0%}–{:.0%}"),
}


def main():
    data = (ROOT / "app" / "model_data.json").read_text()
    assumptions = [{"label": LABELS[k][0], "range": LABELS[k][1].format(lo, hi),
                    "basis": basis.replace("Assumption: ", "Assumption. ")}
                   for k, (lo, hi, basis) in PARAMS.items()]
    html = (ROOT / "app" / "template.html").read_text()
    html = html.replace("__DATA__", data).replace("__ASSUMPTIONS__", json.dumps(assumptions))
    (ROOT / "app" / "index.html").write_text(html)
    print(f"app/index.html {len(html)/1024:.0f} KB")


if __name__ == "__main__":
    main()
