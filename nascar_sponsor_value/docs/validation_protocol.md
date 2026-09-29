# Validation protocol: hand-coding broadcast segments

The coverage model is calibrated to published benchmarks, not measured. This protocol measures it directly on real broadcast footage and scores the model against it. It is the step that turns "calibrated estimate" into "validated estimate."

## Sample (about 2–3 hours of work)

- **One race** you can watch legally as a full replay (a streaming service you subscribe to, or the network's own app).
- **Three 10-minute segments of green-flag racing**: early (after the first pit cycle), middle, and the final stage. Skip commercials, cautions and pre-race.
- If time allows, a second race on a different network, so network style can be compared.

## Coding rules

1. Pause every **5 seconds** of green-flag coverage (120 checkpoints per 10-minute segment).
2. At each checkpoint, list every car whose **car number and primary sponsor logo are both readable** in that frame. If none, write `none`.
3. Record the shot type: `wide`, `tight` (1–3 cars), `in-car`, `pit`, `graphic`, `booth` or `other`.
4. Code one segment twice, a day apart, without looking at the first pass. This gives your agreement rate (Cohen's kappa).

Use `data/validation/coding_template.csv`: one row per checkpoint, with car numbers separated by `;`.

## Scoring

Run `python src/score_validation.py data/validation/<your_file>.csv <race_id>`. It reports:
- **Top-10 share:** share of car appearances going to the top 10 by average running position. The model assumes 45–55%.
- **Rank correlation (Spearman)** between each car's coded appearances and the model's predicted coverage share.
- **Backmarker seconds:** coded appearance time for the bottom quarter vs. the model's prediction.
- **Car shots and cars per shot:** measured values for two of the model's assumptions.

Report the result either way. If the model misses, the fix is to recalibrate the ranges in `src/model.py` and say so in the README.
