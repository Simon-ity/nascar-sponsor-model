"""Build the DuckDB warehouse from raw per-race CSVs pulled from NASCAR's public feeds.

Tables
------
races    one row per 2025 Cup points race (36)
entries  one row per car entered, including non-starters (DNQ / withdrawn)
loop     one row per starter: NASCAR loop data (avg running position, laps led, ...)

Known source quirks, each handled below:
* Official results can differ from loop `ps` after post-race penalties
  (spring Martinsville 5553, spring Talladega 5555). `entries.finish` keeps the
  official result; `loop.ps` keeps the on-track finish.
* Non-starters appear in results with finishing_position 0 (Daytona 500 DNQs,
  withdrawals). They are kept with `started = false`.
* Fall Talladega (5580) has an empty results feed; entries are rebuilt from loop
  data plus a driver lookup built from the other 35 races. Sponsor is unknown.
"""
from pathlib import Path
import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "nascar_2025.duckdb"

TALLADEGA_FALL_META = {
    # Source: Wikipedia "2025 YellaWood 500" (NBC, 188 scheduled laps, 193 run in overtime)
    "race_id": 5580, "race_name": "YellaWood 500", "track_name": "Talladega Superspeedway",
    "race_date": "2025-10-19", "broadcaster": "NBC", "cars_in_field": 40, "total_laps": 193,
    "lead_changes": 77, "leaders": 27, "cautions": 6, "caution_laps": 28,
}

TRACK_TYPE = {
    "Daytona International Speedway": "superspeedway", "Talladega Superspeedway": "superspeedway",
    "Atlanta Motor Speedway": "superspeedway",
    "Circuit of The Americas": "road", "Sonoma Raceway": "road", "Watkins Glen International": "road",
    "Chicago Street Race": "road", "Charlotte Motor Speedway Road Course": "road",
    "Autódromo Hermanos Rodríguez": "road",
    "Martinsville Speedway": "short", "Bristol Motor Speedway": "short", "Richmond Raceway": "short",
    "Phoenix Raceway": "short", "New Hampshire Motor Speedway": "short", "Iowa Speedway": "short",
    "World Wide Technology Raceway": "short",
}  # everything else = intermediate (1.25-2 mile ovals)

NETWORK_GROUP = {"FOX": "FOX", "FS1": "FOX", "PRIME VIDEO": "Prime Video", "TNT": "TNT",
                 "NBC": "NBC", "USA": "NBC"}


def load_races() -> pd.DataFrame:
    metas = [pd.read_csv(p) for p in sorted(RAW.glob("*_meta.csv"))]
    races = pd.concat(metas + [pd.DataFrame([TALLADEGA_FALL_META])], ignore_index=True)
    races["race_date"] = pd.to_datetime(races["race_date"]).dt.date
    races["broadcaster"] = races["broadcaster"].str.strip().str.upper()
    races["network_group"] = races["broadcaster"].map(NETWORK_GROUP)
    races["over_the_air"] = races["broadcaster"].isin(["FOX", "NBC"])
    races["track_type"] = races["track_name"].map(TRACK_TYPE).fillna("intermediate")
    return races.sort_values("race_date").reset_index(drop=True)


def load_loop() -> pd.DataFrame:
    frames = []
    for p in sorted(RAW.glob("*_loop.csv")):
        df = pd.read_csv(p)
        df.insert(0, "race_id", int(p.name.split("_")[0]))
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_entries(loop: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for p in sorted(RAW.glob("*_results.csv")):
        df = pd.read_csv(p, dtype={"car_number": str, "sponsor": str})
        df.insert(0, "race_id", int(p.name.split("_")[0]))
        frames.append(df)
    entries = pd.concat(frames, ignore_index=True)
    entries = entries.rename(columns={"finishing_position": "finish",
                                      "starting_position": "start",
                                      "finishing_status": "status",
                                      "laps_completed": "laps",
                                      "driver_fullname": "driver"})
    entries["sponsor"] = entries["sponsor"].fillna("").str.strip().str.replace("\\\\", "\\", regex=False)
    entries["driver"] = entries["driver"].str.strip()

    # Rebuild fall Talladega from loop + driver lookup (latest team/car for each driver).
    lookup = (entries[entries["finish"] > 0].sort_values("race_id")
              .groupby("driver_id")[["car_number", "driver", "team_name"]].last())
    tal = loop[loop["race_id"] == 5580][["race_id", "driver_id", "ps", "start_ps", "laps"]]
    tal = tal.join(lookup, on="driver_id").rename(columns={"ps": "finish", "start_ps": "start"})
    tal["sponsor"] = ""
    tal["status"] = "Unknown (feed empty)"
    entries = pd.concat([entries, tal[entries.columns.intersection(tal.columns)]], ignore_index=True)

    # A car started if it has loop data for that race.
    started = loop[["race_id", "driver_id"]].assign(started=True)
    entries = entries.merge(started, on=["race_id", "driver_id"], how="left")
    entries["started"] = entries["started"].fillna(False).astype(bool)
    entries["is_ny_racing"] = entries["team_name"].fillna("").str.contains("NY Racing")
    return entries


def build() -> None:
    races = load_races()
    loop = load_loop()
    entries = load_entries(loop)
    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    for name, df in {"races": races, "loop": loop, "entries": entries}.items():
        con.register(f"_{name}", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM _{name}")
    con.execute("""
        CREATE VIEW starters AS
        SELECT r.*, e.car_number, e.driver, e.team_name, e.sponsor, e.finish, e.status,
               e.is_ny_racing, l.start_ps, l.ps AS track_finish, l.mid_ps, l.avg_ps,
               l.laps AS loop_laps, l.lead_laps, l.passes_gf, l.top15_laps, l.rating
        FROM loop l
        JOIN entries e USING (race_id, driver_id)
        JOIN races r USING (race_id)
    """)
    con.close()
    print(f"built {DB.name}: {len(races)} races, {len(entries)} entries, {len(loop)} starters")


if __name__ == "__main__":
    build()
