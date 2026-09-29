"""Data-quality tests for the 2025 warehouse. Run: pytest -q"""
from pathlib import Path
import duckdb
import pytest

DB = Path(__file__).resolve().parents[1] / "data" / "nascar_2025.duckdb"


@pytest.fixture(scope="module")
def con():
    return duckdb.connect(str(DB), read_only=True)


def q(con, sql):
    return con.execute(sql).fetchall()


def test_36_points_races(con):
    assert q(con, "SELECT count(*) FROM races")[0][0] == 36


def test_every_race_has_loop_data(con):
    assert q(con, "SELECT count(DISTINCT race_id) FROM loop")[0][0] == 36


def test_laps_led_sum_to_race_distance(con):
    bad = q(con, """SELECT r.race_id, r.total_laps, sum(l.lead_laps)
                    FROM races r JOIN loop l USING (race_id)
                    GROUP BY 1, 2 HAVING sum(l.lead_laps) <> r.total_laps""")
    assert bad == []


def test_field_size_matches_starters(con):
    bad = q(con, """SELECT r.race_id, r.cars_in_field, count(*) FROM races r
                    JOIN loop l USING (race_id) GROUP BY 1, 2
                    HAVING count(*) <> r.cars_in_field""")
    assert bad == []


def test_track_finish_positions_unique_and_contiguous(con):
    bad = q(con, """SELECT race_id FROM loop GROUP BY race_id
                    HAVING count(DISTINCT ps) <> count(*) OR min(ps) <> 1 OR max(ps) <> count(*)""")
    assert bad == []


def test_official_finish_positions_unique_among_starters(con):
    bad = q(con, """SELECT race_id FROM entries WHERE started GROUP BY race_id
                    HAVING count(DISTINCT finish) <> count(*)""")
    assert bad == []


def test_every_starter_joins_to_an_entry(con):
    assert q(con, "SELECT count(*) FROM loop")[0][0] == q(con, "SELECT count(*) FROM starters")[0][0]


def test_avg_running_position_in_range(con):
    assert q(con, "SELECT count(*) FROM loop WHERE avg_ps < 1 OR avg_ps > 45")[0][0] == 0


def test_top15_laps_not_more_than_laps(con):
    assert q(con, "SELECT count(*) FROM loop WHERE top15_laps > laps OR lead_laps > laps")[0][0] == 0


def test_ny_racing_2025_entries(con):
    # 15 entries: 14 starts + the Daytona 500 DNQ (Yeley / Green River Whiskey)
    n, starts = q(con, "SELECT count(*), sum(started::int) FROM entries WHERE is_ny_racing")[0]
    assert (n, starts) == (15, 14)


def test_daytona_500_had_four_dnqs(con):
    assert q(con, "SELECT count(*) FROM entries WHERE race_id = 5546 AND NOT started")[0][0] == 4


def test_every_race_has_a_known_broadcaster(con):
    assert q(con, "SELECT count(*) FROM races WHERE network_group IS NULL")[0][0] == 0
