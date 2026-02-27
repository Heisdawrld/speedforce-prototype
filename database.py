“””
database.py — ProPredictor persistence layer v2
Full tracker support: seeded demo data, performance stats, reliability scores.
“””
import sqlite3, os, json
from datetime import datetime, timezone, timedelta

DB_PATH = os.environ.get(“DB_PATH”, “propredictor.db”)

def get_conn():
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
return conn

def init_db():
with get_conn() as conn:
# Create tables if they don’t exist (safe on fresh DB)
conn.executescript(”””
CREATE TABLE IF NOT EXISTS predictions (
id                  INTEGER PRIMARY KEY AUTOINCREMENT,
match_id            INTEGER NOT NULL,
league_id           INTEGER,
league_name         TEXT,
home_team           TEXT,
away_team           TEXT,
match_date          TEXT,
market              TEXT,
probability         REAL,
fair_odds           REAL,
bookie_odds         REAL,
edge                REAL,
confidence          REAL,
xg_home             REAL,
xg_away             REAL,
likely_score        TEXT,
logged_at           TEXT,
actual_home_score   INTEGER DEFAULT NULL,
actual_away_score   INTEGER DEFAULT NULL,
result              TEXT DEFAULT NULL,
settled_at          TEXT DEFAULT NULL,
UNIQUE(match_id, market)
);
CREATE TABLE IF NOT EXISTS h2h_cache (
cache_key   TEXT PRIMARY KEY,
data        TEXT,
cached_at   TEXT
);
CREATE TABLE IF NOT EXISTS injury_cache (
cache_key   TEXT PRIMARY KEY,
data        TEXT,
cached_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_pred_league ON predictions(league_id);
CREATE INDEX IF NOT EXISTS idx_pred_market ON predictions(market);
CREATE INDEX IF NOT EXISTS idx_pred_result ON predictions(result);
CREATE INDEX IF NOT EXISTS idx_pred_date   ON predictions(match_date);
“””)
# ── Safe migration: add new columns if they don’t exist ──
# This handles both fresh DBs and existing deployed DBs on Render
existing_cols = {r[1] for r in conn.execute(“PRAGMA table_info(predictions)”).fetchall()}
migrations = [
(“tag”,               “TEXT”),
(“reliability_score”, “REAL DEFAULT NULL”),
]
for col, col_type in migrations:
if col not in existing_cols:
try:
conn.execute(f”ALTER TABLE predictions ADD COLUMN {col} {col_type}”)
print(f”[DB] migrated: added column ‘{col}’”)
except Exception as e:
print(f”[DB] migration warning for ‘{col}’: {e}”)

def log_prediction(match_id, league_id, league_name, home_team, away_team,
match_date, market, probability, fair_odds, bookie_odds,
edge, confidence, xg_home, xg_away, likely_score,
tag=None, reliability_score=None):
try:
with get_conn() as conn:
conn.execute(”””
INSERT OR IGNORE INTO predictions
(match_id, league_id, league_name, home_team, away_team,
match_date, market, probability, fair_odds, bookie_odds,
edge, confidence, xg_home, xg_away, likely_score,
tag, reliability_score, logged_at)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
“””, (match_id, league_id, league_name, home_team, away_team,
match_date, market, probability, fair_odds, bookie_odds,
edge, confidence, xg_home, xg_away, likely_score,
tag, reliability_score,
datetime.now(timezone.utc).isoformat()))
except Exception as e:
print(f”[DB] log_prediction: {e}”)

def settle_prediction(match_id, market, home_score, away_score):
result = _evaluate_result(market, home_score, away_score)
try:
with get_conn() as conn:
conn.execute(”””
UPDATE predictions
SET actual_home_score=?, actual_away_score=?,
result=?, settled_at=?
WHERE match_id=? AND market=? AND result IS NULL
“””, (home_score, away_score, result,
datetime.now(timezone.utc).isoformat(),
match_id, market))
except Exception as e:
print(f”[DB] settle: {e}”)

def _evaluate_result(market, h, a):
try:
total = h + a
m = market.upper()
if “HOME WIN” in m:  return “WIN” if h > a else “LOSS”
if “AWAY WIN” in m:  return “WIN” if a > h else “LOSS”
if m == “DRAW”:      return “WIN” if h == a else “LOSS”
if “OVER 1.5” in m:  return “WIN” if total > 1 else “LOSS”
if “OVER 2.5” in m:  return “WIN” if total > 2 else “LOSS”
if “OVER 3.5” in m:  return “WIN” if total > 3 else “LOSS”
if “UNDER 2.5” in m: return “WIN” if total <= 2 else “LOSS”
if “UNDER 1.5” in m: return “WIN” if total <= 1 else “LOSS”
if m in (“GG”,“BTTS”,“BTTS YES”):
return “WIN” if h > 0 and a > 0 else “LOSS”
if m in (“NG”,“BTTS NO”):
return “WIN” if (h == 0 or a == 0) else “LOSS”
return “VOID”
except:
return “VOID”

def get_tracker_stats():
with get_conn() as conn:
total = conn.execute(
“SELECT COUNT(*) as n FROM predictions WHERE result IN (‘WIN’,‘LOSS’)”
).fetchone()[“n”]
wins  = conn.execute(
“SELECT COUNT(*) as n FROM predictions WHERE result=‘WIN’”
).fetchone()[“n”]
# Rolling 7-day
week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
week_total = conn.execute(
“SELECT COUNT(*) as n FROM predictions WHERE result IN (‘WIN’,‘LOSS’) AND settled_at >= ?”,
(week_ago,)
).fetchone()[“n”]
week_wins = conn.execute(
“SELECT COUNT(*) as n FROM predictions WHERE result=‘WIN’ AND settled_at >= ?”,
(week_ago,)
).fetchone()[“n”]
# By market
by_market = conn.execute(”””
SELECT market,
COUNT(*) as total,
SUM(CASE WHEN result=‘WIN’ THEN 1 ELSE 0 END) as wins,
AVG(probability) as avg_prob,
AVG(edge) as avg_edge
FROM predictions WHERE result IN (‘WIN’,‘LOSS’)
GROUP BY market ORDER BY total DESC
“””).fetchall()
# By league
by_league = conn.execute(”””
SELECT league_name,
COUNT(*) as total,
SUM(CASE WHEN result=‘WIN’ THEN 1 ELSE 0 END) as wins
FROM predictions WHERE result IN (‘WIN’,‘LOSS’)
GROUP BY league_name ORDER BY total DESC LIMIT 8
“””).fetchall()
# Recent 15
recent = conn.execute(”””
SELECT home_team, away_team, market, probability,
fair_odds, edge, result, match_date, league_name,
actual_home_score, actual_away_score, tag
FROM predictions WHERE result IN (‘WIN’,‘LOSS’)
ORDER BY settled_at DESC LIMIT 15
“””).fetchall()
# Pending
pending_rows = conn.execute(”””
SELECT home_team, away_team, market, probability,
fair_odds, match_date, league_name, tag
FROM predictions WHERE result IS NULL
ORDER BY logged_at DESC LIMIT 10
“””).fetchall()
pending_count = conn.execute(
“SELECT COUNT(*) as n FROM predictions WHERE result IS NULL”
).fetchone()[“n”]
# Streak
last10 = conn.execute(”””
SELECT result FROM predictions WHERE result IN (‘WIN’,‘LOSS’)
ORDER BY settled_at DESC LIMIT 10
“””).fetchall()
streak = _calc_streak([r[“result”] for r in last10])
# ROI (assuming 1 unit per bet at fair odds)
roi_data = conn.execute(”””
SELECT result, fair_odds FROM predictions
WHERE result IN (‘WIN’,‘LOSS’) AND fair_odds IS NOT NULL
“””).fetchall()
roi = _calc_roi(roi_data)

```
    hit_rate      = round(wins / total * 100, 1) if total > 0 else 0
    week_hit_rate = round(week_wins / week_total * 100, 1) if week_total > 0 else 0

    return {
        "total": total, "wins": wins, "losses": total-wins,
        "hit_rate": hit_rate, "pending": pending_count,
        "week_total": week_total, "week_wins": week_wins,
        "week_hit_rate": week_hit_rate,
        "by_market": [dict(r) for r in by_market],
        "by_league": [dict(r) for r in by_league],
        "recent":    [dict(r) for r in recent],
        "pending_rows": [dict(r) for r in pending_rows],
        "streak": streak,
        "roi":    roi,
    }
```

def _calc_streak(results):
if not results: return {“type”:”—”,“count”:0}
cur = results[0]; count = 1
for r in results[1:]:
if r == cur: count += 1
else: break
return {“type”: cur, “count”: count}

def _calc_roi(rows):
if not rows: return 0.0
profit = 0.0
for r in rows:
if r[“result”] == “WIN”:
profit += (r[“fair_odds”] - 1)
else:
profit -= 1.0
roi = (profit / len(rows)) * 100
return round(roi, 1)

def get_recent_pending(limit=50):
with get_conn() as conn:
rows = conn.execute(”””
SELECT match_id, market, home_team, away_team, match_date
FROM predictions WHERE result IS NULL
ORDER BY logged_at ASC LIMIT ?
“””, (limit,)).fetchall()
return [dict(r) for r in rows]

def cache_set(table, key, json_str):
with get_conn() as conn:
conn.execute(f”””
INSERT OR REPLACE INTO {table} (cache_key, data, cached_at)
VALUES (?, ?, ?)
“””, (key, json_str, datetime.now(timezone.utc).isoformat()))

def cache_get(table, key, max_age_hours=24):
with get_conn() as conn:
row = conn.execute(
f”SELECT data, cached_at FROM {table} WHERE cache_key=?”, (key,)
).fetchone()
if not row: return None
cached_at = datetime.fromisoformat(row[“cached_at”])
if datetime.now(timezone.utc).replace(tzinfo=None) - cached_at.replace(tzinfo=None) > timedelta(hours=max_age_hours):
return None
return row[“data”]
