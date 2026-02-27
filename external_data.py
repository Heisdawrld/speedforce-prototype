"""
external_data.py -- API Football Integration v2
Three new intelligence layers over v1:

  LAYER 1 -- Squad Strength Index
    /players endpoint, 1 call per team, cached 24h
    Weighted rating by position -> 0-100 strength score
    Injury penalty: -8% xG per key player missing

  LAYER 2 -- Rolling xG (last 5 matches)
    Zero extra API calls -- computed from existing fixture data
    Dynamic goals-scored/conceded proxy replaces static season averages

  LAYER 3 -- Home/Away Splits
    Zero extra API calls -- deeper parse of /teams/statistics response
    Venue-specific win rates feed directly into conviction engine

Free-tier quota architecture (100 calls/day):
  ~30 calls  -- morning batch (1 per unique team today, 24h cached)
  ~40 calls  -- on-demand H2H + last5 + injuries during the day
  ~30 buffer -- reserved / cache misses
"""

import os, json, requests, time
from datetime import datetime, timezone, timedelta
import database

APIFOOTBALL_KEY  = os.environ.get("APIFOOTBALL_KEY", "d1d7aaea599eb42ce6a723c2935ee70e")
APIFOOTBALL_BASE = "https://v3.football.api-sports.io"
CURRENT_SEASON   = 2025

# -- football-data.org -- FREE unlimited for top 10 leagues ------------------
# Used for: standings, H2H, recent results -- saves API Football quota
# for player stats (the expensive layer)
FDORG_KEY  = os.environ.get("FDORG_KEY", "9f4755094ff9435695b794f91f4c1474")
FDORG_BASE = "https://api.football-data.org/v4"

# Bzzoiro league ID -> football-data.org competition code
FDORG_LEAGUE_MAP = {
    1:  "PL",   # Premier League
    3:  "PD",   # La Liga
    4:  "SA",   # Serie A
    5:  "BL1",  # Bundesliga
    6:  "FL1",  # Ligue 1
    7:  "CL",   # Champions League
    8:  "EL",   # Europa League
    9:  "DED",  # Eredivisie
    12: "ELC",  # Championship
    13: "PPL",  # Primeira Liga
    2:  "PPL",  # Liga Portugal
}

def _fdorg_get(endpoint, params=None):
    """football-data.org API caller -- free, no quota tracking needed."""
    if not FDORG_KEY:
        return None
    try:
        r = requests.get(
            f"{FDORG_BASE}{endpoint}",
            headers={"X-Auth-Token": FDORG_KEY},
            params=params or {}, timeout=10
        )
        if r.status_code == 429:
            print("[FDOrg] rate limited -- backing off")
            return None
        if r.status_code != 200:
            print(f"[FDOrg] {endpoint}: HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as e:
        print(f"[FDOrg] {endpoint} failed: {e}")
        return None

def get_standings_fdorg(our_league_id):
    """
    Get live standings via football-data.org (free, unlimited).
    Returns same format as get_standings() for drop-in use.
    """
    code = FDORG_LEAGUE_MAP.get(our_league_id)
    if not code:
        return None
    ck = f"fdorg_standings_{our_league_id}"
    cached = database.cache_get("h2h_cache", ck, max_age_hours=6)
    if cached:
        try: return json.loads(cached)
        except: pass

    data = _fdorg_get(f"/competitions/{code}/standings")
    if not data:
        return None
    table = {}
    try:
        for grp in data.get("standings", []):
            if grp.get("type") != "TOTAL":
                continue
            for t in grp.get("table", []):
                tid = str(t["team"]["id"])
                table[tid] = {
                    "rank":    t.get("position", 0),
                    "name":    t["team"]["name"],
                    "points":  t.get("points", 0),
                    "played":  t.get("playedGames", 0),
                    "gd":      t.get("goalDifference", 0),
                    "form":    t.get("form", "") or "",
                    "wins":    t.get("won", 0),
                    "draws":   t.get("draw", 0),
                    "losses":  t.get("lost", 0),
                    "gf":      t.get("goalsFor", 0),
                    "ga":      t.get("goalsAgainst", 0),
                }
    except Exception as e:
        print(f"[FDOrg standings] {e}")
        return None
    if table:
        database.cache_set("h2h_cache", ck, json.dumps(table))
    _mem_set(ck, json.dumps(table))
    return table if table else None

def get_team_last_matches_fdorg(team_fdorg_id, our_league_id, last=5):
    """
    Get last N results for a team via football-data.org (free, unlimited).
    Returns same format as get_last_matches() for drop-in use.
    """
    code = FDORG_LEAGUE_MAP.get(our_league_id)
    if not code or not team_fdorg_id:
        return []
    ck = f"fdorg_last_{team_fdorg_id}_{last}"
    cached = database.cache_get("h2h_cache", ck, max_age_hours=6)
    if cached:
        try: return json.loads(cached)
        except: pass

    data = _fdorg_get(f"/teams/{team_fdorg_id}/matches",
                      {"status": "FINISHED", "limit": last})
    if not data:
        return []
    matches = []
    for m in data.get("matches", [])[-last:]:
        home = m.get("homeTeam", {}).get("name", "?")
        away = m.get("awayTeam", {}).get("name", "?")
        sc   = m.get("score", {}).get("fullTime", {})
        hg   = sc.get("home")
        ag   = sc.get("away")
        matches.append({
            "date":       (m.get("utcDate","")[:10]),
            "home":       home,
            "away":       away,
            "home_goals": hg,
            "away_goals": ag,
            "league":     code,
        })
    matches.sort(key=lambda x: x["date"], reverse=True)
    if matches:
        database.cache_set("h2h_cache", ck, json.dumps(matches))
    _mem_set(ck, json.dumps(matches))
    return matches


LEAGUE_ID_MAP = {
    1: 39, 2: 94, 3: 140, 4: 135, 5: 78, 6: 61,
    7: 2, 8: 3, 9: 88, 10: 235, 11: 203, 12: 40,
    13: 179, 14: 144, 15: 207, 16: 218, 17: 197,
    18: 253, 19: 71, 20: 262, 21: 128,
    32: 307, 33: 188, 34: 382, 44: 848,
}

POSITION_WEIGHTS = {
    "Attacker":   0.40,
    "Midfielder": 0.35,
    "Defender":   0.20,
    "Goalkeeper": 0.05,
}

# In-memory quota tracker
_quota = {"date": "", "count": 0}

# In-memory cache -- survives within a single server session
# Key: cache_key string -> (data, timestamp)
# This means repeat page loads within the same Render session = 0 API calls
_mem_cache = {}

def _mem_get(key, max_age_hours=24):
    """Check in-memory cache first before hitting SQLite."""
    if key not in _mem_cache:
        return None
    data, ts = _mem_cache[key]
    from datetime import datetime, timezone, timedelta
    age = datetime.now(timezone.utc) - ts
    if age > timedelta(hours=max_age_hours):
        del _mem_cache[key]
        return None
    return data

def _mem_set(key, data):
    """Store in memory cache."""
    from datetime import datetime, timezone
    _mem_cache[key] = (data, datetime.now(timezone.utc))

# -- Core API caller -----------------------------------------------------------

def _get(endpoint, params):
    if not APIFOOTBALL_KEY:
        return None
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _quota["date"] != today:
        _quota["date"] = today
        _quota["count"] = 0
    _quota["count"] += 1
    print(f"[APIFootball] #{_quota['count']}/100 {endpoint} {list(params.items())[:2]}")

    try:
        r = requests.get(
            f"{APIFOOTBALL_BASE}{endpoint}",
            headers={"x-rapidapi-key": APIFOOTBALL_KEY,
                     "x-rapidapi-host": "v3.football.api-sports.io"},
            params=params, timeout=12
        )
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            print(f"[APIFootball] error: {data['errors']}")
            return None
        return data.get("response", [])
    except Exception as e:
        print(f"[APIFootball] {endpoint} failed: {e}")
        return None

def get_quota_status():
    return {"used": _quota["count"], "remaining": max(0, 100 - _quota["count"])}

# ===============================================================
# LAYER 1 -- SQUAD STRENGTH INDEX
# ===============================================================

def get_squad_stats(team_api_id, league_api_id):
    """
    Fetch player statistics for a team. 1 API call, cached 24 hours.
    Returns list of player dicts with rating, position, goals, assists, minutes.
    """
    if not team_api_id or not league_api_id:
        return []
    ck = f"squad_{team_api_id}_{league_api_id}_{CURRENT_SEASON}"
    cached = database.cache_get("h2h_cache", ck, max_age_hours=24)
    if cached:
        try: return json.loads(cached)
        except: pass

    data = _get("/players", {
        "team": team_api_id, "league": league_api_id, "season": CURRENT_SEASON
    })
    if not data:
        return []

    players = []
    for entry in data:
        p     = entry.get("player", {})
        stats = entry.get("statistics", [{}])[0]
        games = stats.get("games", {})
        goals = stats.get("goals", {})
        shots = stats.get("shots", {})
        passes= stats.get("passes", {})
        mins  = games.get("minutes") or 0
        try:
            rating = round(float(games.get("rating") or 0), 3)
        except:
            rating = 0.0
        if not rating or rating < 1.0 or mins < 90:
            continue
        players.append({
            "id":         p.get("id"),
            "name":       p.get("name", "?"),
            "position":   games.get("position", "Midfielder"),
            "rating":     rating,
            "minutes":    mins,
            "goals":      goals.get("total") or 0,
            "assists":    goals.get("assists") or 0,
            "shots_on":   shots.get("on") or 0,
            "key_passes": passes.get("key") or 0,
            "injured":    p.get("injured", False),
        })

    players.sort(key=lambda x: x["minutes"], reverse=True)
    database.cache_set("h2h_cache", ck, json.dumps(players))
    return players

def compute_squad_strength(players, injury_list=None):
    """
    Squad Strength Index (0-100).

    Steps:
      1. Group by position
      2. Top-N weighted average rating per position
      3. Position-weighted composite (Attacker 40%, Mid 35%, Def 20%, GK 5%)
      4. Scale: 6.0 rating = 30 strength, 7.0 = 70, 8.0 = 100+
      5. Injury penalty: -8% xG multiplier per missing key player

    Returns score, attack, defense, penalty multiplier, top players list.
    """
    if not players:
        return _default_squad()

    inj_names = set()
    if injury_list:
        inj_names = {i.get("name","").lower() for i in injury_list}

    by_pos = {"Attacker":[], "Midfielder":[], "Defender":[], "Goalkeeper":[]}
    for p in players:
        pos = p.get("position", "Midfielder")
        if pos in by_pos:
            by_pos[pos].append(p)

    top_n   = {"Attacker":2, "Midfielder":3, "Defender":4, "Goalkeeper":1}
    pos_avg = {}
    for pos, limit in top_n.items():
        pool = sorted(by_pos[pos], key=lambda x: x["rating"], reverse=True)[:limit]
        pos_avg[pos] = (sum(p["rating"] for p in pool) / len(pool)) if pool else 6.5

    raw    = sum(pos_avg[pos] * w for pos, w in POSITION_WEIGHTS.items())
    score  = max(0, min(100, (raw - 6.0) * 40))
    atk    = max(0, min(100, (pos_avg["Attacker"]*0.55 + pos_avg["Midfielder"]*0.45 - 6.0) * 40))
    def_s  = max(0, min(100, (pos_avg["Defender"]*0.65 + pos_avg["Goalkeeper"]*0.35 - 6.0) * 40))

    # Key player injury check: top-3 attackers + goalkeeper
    key_pool = (sorted(by_pos["Attacker"],   key=lambda x: x["rating"], reverse=True)[:3] +
                sorted(by_pos["Goalkeeper"],  key=lambda x: x["rating"], reverse=True)[:1])
    key_missing = sum(
        1 for kp in key_pool
        if kp.get("injured") or any(inj in kp["name"].lower() for inj in inj_names)
    )
    penalty = round(max(0.70, 1.0 - key_missing * 0.08), 3)

    return {
        "score":        round(score, 1),
        "attack":       round(atk,  1),
        "defense":      round(def_s, 1),
        "key_missing":  key_missing,
        "penalty":      penalty,
        "top_players":  sorted(players, key=lambda x: x["rating"], reverse=True)[:3],
        "player_count": len(players),
    }

def _default_squad():
    return {"score":50.0, "attack":50.0, "defense":50.0,
            "key_missing":0, "penalty":1.0, "top_players":[], "player_count":0}

# ===============================================================
# LAYER 2 -- ROLLING xG (zero extra API calls)
# ===============================================================

def compute_rolling_xg(last_matches, team_name):
    """
    Compute rolling xG proxy from last 5 match goals.
    Zero additional API calls -- uses already-fetched fixture data.

    Returns rolling_for, rolling_against, trend, momentum_factor.
    momentum_factor: 0.88 (falling) -> 1.0 (stable) -> 1.12 (rising)
    """
    if not last_matches:
        return {"rolling_for":1.2, "rolling_against":1.0,
                "trend":"STABLE", "momentum_factor":1.0}

    scored = []; conceded = []
    for m in last_matches[:5]:
        hg = m.get("home_goals") or 0
        ag = m.get("away_goals") or 0
        if m.get("home","") == team_name:
            scored.append(hg); conceded.append(ag)
        else:
            scored.append(ag); conceded.append(hg)

    n = len(scored)
    if n == 0:
        return {"rolling_for":1.2, "rolling_against":1.0,
                "trend":"STABLE", "momentum_factor":1.0}

    avg_for     = round(sum(scored) / n, 3)
    avg_against = round(sum(conceded) / n, 3)
    trend = "STABLE"; mf = 1.0

    if n >= 4:
        recent  = sum(scored[:2]) / 2
        earlier = sum(scored[2:]) / max(n-2, 1)
        diff    = recent - earlier
        if   diff >=  0.5: trend = "RISING";  mf = 1.12
        elif diff <= -0.5: trend = "FALLING"; mf = 0.88
        else:              mf = round(1.0 + diff * 0.1, 3)

    return {"rolling_for": avg_for, "rolling_against": avg_against,
            "trend": trend, "momentum_factor": round(mf, 3)}

# ===============================================================
# LAYER 3 -- HOME/AWAY SPLITS (zero extra API calls)
# ===============================================================

def parse_home_away_splits(raw_stats):
    """
    Extract venue-split stats from /teams/statistics raw response.
    Called inside get_team_stats -- no extra API call.
    """
    if not raw_stats:
        return None
    s   = raw_stats[0] if isinstance(raw_stats, list) else raw_stats
    fix = s.get("fixtures", {})
    gf  = s.get("goals", {}).get("for", {})
    ga  = s.get("goals", {}).get("against", {})

    def si(d, *ks):
        try:
            v = d
            for k in ks: v = v[k]
            return int(v or 0)
        except: return 0

    def sf(d, *ks):
        try:
            v = d
            for k in ks: v = v[k]
            return float(v or 0)
        except: return 0.0

    hp = si(fix,"played","home") or 1
    ap = si(fix,"played","away") or 1
    return {
        "home_played":   hp,
        "away_played":   ap,
        "home_wins":     si(fix,"wins","home"),
        "away_wins":     si(fix,"wins","away"),
        "home_draws":    si(fix,"draws","home"),
        "away_draws":    si(fix,"draws","away"),
        "home_losses":   si(fix,"loses","home"),
        "away_losses":   si(fix,"loses","away"),
        "home_win_rate": round(si(fix,"wins","home") / hp, 3),
        "away_win_rate": round(si(fix,"wins","away") / ap, 3),
        "home_gf_avg":   sf(gf,"average","home"),
        "home_ga_avg":   sf(ga,"average","home"),
        "away_gf_avg":   sf(gf,"average","away"),
        "away_ga_avg":   sf(ga,"average","away"),
    }

# ===============================================================
# BATCH JOB -- 6am WAT daily pre-fetch
# ===============================================================

def run_daily_batch(today_matches):
    """
    Pre-fetch squad stats for all teams playing today.
    Skips teams already in 24h cache. Rate-limited at 5 req/sec.
    Returns call count for monitoring.
    """
    made = 0; skipped = 0; seen = set()

    for m in today_matches:
        event    = m.get("event", {})
        our_l_id = event.get("league", {}).get("id", 0)
        ext_l_id = LEAGUE_ID_MAP.get(our_l_id)
        if not ext_l_id:
            continue
        for side in ("home_team_obj", "away_team_obj"):
            t_id = (event.get(side) or {}).get("api_id")
            if not t_id or t_id in seen:
                continue
            seen.add(t_id)
            ck = f"squad_{t_id}_{ext_l_id}_{CURRENT_SEASON}"
            if database.cache_get("h2h_cache", ck, max_age_hours=22):
                skipped += 1
                continue
            get_squad_stats(t_id, ext_l_id)
            made += 1
            time.sleep(0.25)

    print(f"[batch] done -- {made} fetched, {skipped} cached | quota: {get_quota_status()}")
    return {"calls_made": made, "calls_skipped": skipped}

# ===============================================================
# EXISTING FUNCTIONS -- H2H, last matches, injuries, stats, standings
# Injury cache extended: 4h -> 12h to protect quota
# ===============================================================

def get_h2h(home_api_id, away_api_id, last=8):
    if not home_api_id or not away_api_id: return []
    ck = f"h2h_{min(home_api_id,away_api_id)}_{max(home_api_id,away_api_id)}"
    mem = _mem_get(ck, 24)
    if mem: return json.loads(mem)
    cached = database.cache_get("h2h_cache", ck, max_age_hours=24)
    if cached:
        _mem_set(ck, cached)
        try: return json.loads(cached)
        except: pass
    data = _get("/fixtures/headtohead",
                {"h2h": f"{home_api_id}-{away_api_id}", "last": last, "status": "FT"})
    if not data: return []
    results = []
    for f in data:
        fix   = f.get("fixture",{}); teams = f.get("teams",{})
        goals = f.get("goals",{});   score = f.get("score",{})
        ht    = score.get("halftime",{})
        results.append({
            "date":       fix.get("date","")[:10],
            "home":       teams.get("home",{}).get("name","?"),
            "away":       teams.get("away",{}).get("name","?"),
            "home_goals": goals.get("home"),
            "away_goals": goals.get("away"),
            "ht_home":    ht.get("home"),
            "ht_away":    ht.get("away"),
            "status":     fix.get("status",{}).get("short",""),
        })
    database.cache_set("h2h_cache", ck, json.dumps(results))
    _mem_set(ck, json.dumps(results))
    return results

def summarise_h2h(h2h_list, home_name, away_name):
    if not h2h_list: return None
    fin = [m for m in h2h_list
           if m.get("status")=="FT" and m.get("home_goals") is not None]
    if not fin: return None
    hw=dr=aw=tg=o15=o25=btts_c=0
    for m in fin:
        hg=m["home_goals"] or 0; ag=m["away_goals"] or 0
        tg += hg+ag
        if hg+ag>1: o15+=1
        if hg+ag>2: o25+=1
        if hg>0 and ag>0: btts_c+=1
        if m["home"]==home_name:
            if hg>ag: hw+=1
            elif hg==ag: dr+=1
            else: aw+=1
        else:
            if ag>hg: hw+=1
            elif hg==ag: dr+=1
            else: aw+=1
    n=len(fin)
    return {"total":n,"home_wins":hw,"draws":dr,"away_wins":aw,
            "avg_goals":round(tg/n,2),"over_15_pct":round(o15/n*100,1),
            "over_25_pct":round(o25/n*100,1),"btts_pct":round(btts_c/n*100,1),
            "matches":fin}

def get_last_matches(team_api_id, last=5):
    if not team_api_id: return []
    ck = f"last_{team_api_id}_{last}"
    mem = _mem_get(ck, 6)
    if mem: return json.loads(mem)
    cached = database.cache_get("h2h_cache", ck, max_age_hours=6)
    if cached:
        _mem_set(ck, cached)
        try: return json.loads(cached)
        except: pass
    data = _get("/fixtures", {"team": team_api_id, "last": last, "status": "FT"})
    if not data: return []
    matches = []
    for f in data:
        fix=f.get("fixture",{}); teams=f.get("teams",{})
        goals=f.get("goals",{}); lg=f.get("league",{})
        matches.append({
            "date":       fix.get("date","")[:10],
            "home":       teams.get("home",{}).get("name","?"),
            "away":       teams.get("away",{}).get("name","?"),
            "home_goals": goals.get("home"),
            "away_goals": goals.get("away"),
            "league":     lg.get("name",""),
        })
    matches.sort(key=lambda x: x["date"], reverse=True)
    database.cache_set("h2h_cache", ck, json.dumps(matches))
    _mem_set(ck, json.dumps(matches))
    return matches

def get_team_form_from_matches(matches, team_name):
    form = []
    for m in matches:
        hg=m.get("home_goals") or 0; ag=m.get("away_goals") or 0
        if m.get("home","")==team_name:
            form.append("W" if hg>ag else "D" if hg==ag else "L")
        else:
            form.append("W" if ag>hg else "D" if hg==ag else "L")
    return form

def get_injuries(team_api_id, league_api_id):
    if not team_api_id or not league_api_id: return []
    ck = f"inj_{team_api_id}_{league_api_id}"
    mem = _mem_get(ck, 12)
    if mem: return json.loads(mem)
    # Extended to 12h (was 4h) -- injuries don't change hourly, saves quota
    cached = database.cache_get("injury_cache", ck, max_age_hours=12)
    if cached:
        _mem_set(ck, cached)
        try: return json.loads(cached)
        except: pass
    data = _get("/injuries",
                {"team": team_api_id, "league": league_api_id, "season": CURRENT_SEASON})
    if not data: return []
    injuries = [{"name":   i.get("player",{}).get("name","?"),
                 "type":   i.get("injury",{}).get("type","Injured"),
                 "reason": i.get("injury",{}).get("reason","")} for i in data[:8]]
    database.cache_set("injury_cache", ck, json.dumps(injuries))
    _mem_set(ck, json.dumps(injuries))
    return injuries

def get_team_stats(team_api_id, league_api_id):
    if not team_api_id or not league_api_id: return None
    ck = f"stats_{team_api_id}_{league_api_id}"
    mem = _mem_get(ck, 12)
    if mem: return json.loads(mem)
    cached = database.cache_get("h2h_cache", ck, max_age_hours=12)
    if cached:
        _mem_set(ck, cached)
        try: return json.loads(cached)
        except: pass
    data = _get("/teams/statistics",
                {"team": team_api_id, "league": league_api_id, "season": CURRENT_SEASON})
    if not data: return None
    s   = data[0] if isinstance(data,list) else data
    gf  = s.get("goals",{}).get("for",{})
    ga  = s.get("goals",{}).get("against",{})
    fix = s.get("fixtures",{})
    stats = {
        "played":           max(fix.get("played",{}).get("total",1) or 1, 1),
        "wins":             fix.get("wins",{}).get("total",0),
        "draws":            fix.get("draws",{}).get("total",0),
        "losses":           fix.get("loses",{}).get("total",0),
        "goals_scored":     gf.get("total",{}).get("total",0),
        "goals_conceded":   ga.get("total",{}).get("total",0),
        "avg_scored":       float(gf.get("average",{}).get("total",0) or 0),
        "avg_conceded":     float(ga.get("average",{}).get("total",0) or 0),
        "clean_sheets":     s.get("clean_sheet",{}).get("total",0),
        "failed_to_score":  s.get("failed_to_score",{}).get("total",0),
        "form":             s.get("form",""),
        "home_wins":        fix.get("wins",{}).get("home",0),
        "away_wins":        fix.get("wins",{}).get("away",0),
        # Layer 3: venue splits
        "splits":           parse_home_away_splits(s),
    }
    database.cache_set("h2h_cache", ck, json.dumps(stats))
    _mem_set(ck, json.dumps(stats))
    return stats

def get_standings(league_api_id):
    ck = f"standings_{league_api_id}"
    mem = _mem_get(ck, 6)
    if mem: return json.loads(mem)
    cached = database.cache_get("h2h_cache", ck, max_age_hours=6)
    if cached:
        _mem_set(ck, cached)
        try: return json.loads(cached)
        except: pass
    data = _get("/standings", {"league": league_api_id, "season": CURRENT_SEASON})
    if not data: return {}
    table = {}
    try:
        for team in data[0]["league"]["standings"][0]:
            tid = str(team["team"]["id"])
            table[tid] = {
                "rank": team.get("rank",0),
                "name": team["team"]["name"],
                "points": team.get("points",0),
                "played": team.get("all",{}).get("played",0),
                "gd": team.get("goalsDiff",0),
                "form": team.get("form",""),
            }
    except Exception as e:
        print(f"[standings] {e}")
    database.cache_set("h2h_cache", ck, json.dumps(table))
    _mem_set(ck, json.dumps(table))
    return table

# ===============================================================
# ENRICH MATCH
# ===============================================================

def enrich_match(api_data):
    enriched = {
        "h2h":[], "h2h_summary":None,
        "home_last":[], "away_last":[],
        "home_injuries":[], "away_injuries":[],
        "home_stats":None, "away_stats":None,
        "standings":{}, "has_data":False,
        "home_form":[], "away_form":[],
        # new
        "home_squad":None, "away_squad":None,
        "home_rolling_xg":None, "away_rolling_xg":None,
    }
    if not APIFOOTBALL_KEY:
        return enriched
    try:
        event       = api_data.get("event", {})
        our_l_id    = event.get("league",{}).get("id",0)
        ext_l_id    = LEAGUE_ID_MAP.get(our_l_id)
        home_obj    = event.get("home_team_obj",{}) or {}
        away_obj    = event.get("away_team_obj",{}) or {}
        h_ext       = home_obj.get("api_id")
        a_ext       = away_obj.get("api_id")
        h_name      = event.get("home_team","")
        a_name      = event.get("away_team","")

        if h_ext and a_ext:
            enriched["h2h"]          = get_h2h(h_ext, a_ext)
            enriched["h2h_summary"]  = summarise_h2h(enriched["h2h"], h_name, a_name)
            enriched["home_last"]    = get_last_matches(h_ext)
            enriched["away_last"]    = get_last_matches(a_ext)
            enriched["home_form"]    = get_team_form_from_matches(enriched["home_last"], h_name)
            enriched["away_form"]    = get_team_form_from_matches(enriched["away_last"], a_name)
            # Layer 2: rolling xG -- zero extra calls
            enriched["home_rolling_xg"] = compute_rolling_xg(enriched["home_last"], h_name)
            enriched["away_rolling_xg"] = compute_rolling_xg(enriched["away_last"], a_name)

        if ext_l_id:
            enriched["home_injuries"] = get_injuries(h_ext, ext_l_id)
            enriched["away_injuries"] = get_injuries(a_ext, ext_l_id)
            enriched["home_stats"]    = get_team_stats(h_ext, ext_l_id)
            enriched["away_stats"]    = get_team_stats(a_ext, ext_l_id)
            # Try football-data.org standings first (free, unlimited)
            # Fall back to API Football only if FDOrg doesn't cover this league
            fdorg_standings = get_standings_fdorg(our_l_id)
            enriched["standings"] = fdorg_standings if fdorg_standings else get_standings(ext_l_id)
            # Layer 1: squad strength -- batch pre-fetched, cache hit here
            if h_ext:
                enriched["home_squad"] = compute_squad_strength(
                    get_squad_stats(h_ext, ext_l_id), enriched["home_injuries"])
            if a_ext:
                enriched["away_squad"] = compute_squad_strength(
                    get_squad_stats(a_ext, ext_l_id), enriched["away_injuries"])

        enriched["has_data"] = bool(
            enriched["h2h"] or enriched["home_last"] or enriched["home_stats"])
    except Exception as e:
        import traceback
        print(f"[enrich_match] {e}\n{traceback.format_exc()}")
    return enriched

# ===============================================================
# ANALYST NARRATIVE
# ===============================================================

def build_analyst_narrative(enriched, h_name, a_name):
    h = h_name.split()[0]; a = a_name.split()[0]
    h_form  = enriched.get("home_form",[])
    a_form  = enriched.get("away_form",[])
    h2h     = enriched.get("h2h_summary")
    h_st    = enriched.get("home_stats")
    a_st    = enriched.get("away_stats")
    h_inj   = enriched.get("home_injuries",[])
    a_inj   = enriched.get("away_injuries",[])
    h_sq    = enriched.get("home_squad")
    a_sq    = enriched.get("away_squad")
    h_rxg   = enriched.get("home_rolling_xg")
    a_rxg   = enriched.get("away_rolling_xg")
    out     = {}

    # Form
    if h_form or a_form:
        h_pts = sum(3 if r=="W" else 1 if r=="D" else 0 for r in h_form)
        a_pts = sum(3 if r=="W" else 1 if r=="D" else 0 for r in a_form)
        hp = round(h_pts/max(len(h_form)*3,1)*100)
        ap = round(a_pts/max(len(a_form)*3,1)*100)
        hs = " ".join(h_form) or "--"; as_ = " ".join(a_form) or "--"
        if hp > ap+20:   out["form"] = f"{h} in strong form ({hs}) * {a} struggling ({as_})"
        elif ap > hp+20: out["form"] = f"{a} in-form ({as_}) * {h} poor run ({hs})"
        else:            out["form"] = f"Evenly matched recent form * {h}: {hs} * {a}: {as_}"
        if hp>=80:   out["morale"] = f"{h} full of confidence -- {h_form.count('W')} wins in last {len(h_form)}"
        elif ap>=80: out["morale"] = f"{a} on a hot streak -- {a_form.count('W')} wins in last {len(a_form)}"
        else:        out["morale"] = None

    # H2H
    if h2h and h2h["total"]>=3:
        hw=h2h["home_wins"]; dr=h2h["draws"]; aw=h2h["away_wins"]; n=h2h["total"]
        if hw/n>=0.6:   dom=f"{h} dominant in this fixture ({hw}W-{dr}D-{aw}L)"
        elif aw/n>=0.6: dom=f"{a} historically strong here ({aw}W-{dr}D-{hw}L)"
        elif dr/n>=0.5: dom=f"This fixture draws frequently -- {dr} of {n} meetings ended level"
        else:           dom=f"Tight H2H -- {hw}W {dr}D {aw}L over {n} meetings"
        out["h2h"] = f"{dom} * Avg {h2h['avg_goals']} goals"

    # Goals -- rolling xG preferred over season averages
    if h_rxg and a_rxg:
        hf=h_rxg["rolling_for"]; hag=h_rxg["rolling_against"]
        af=a_rxg["rolling_for"]; aag=a_rxg["rolling_against"]
        exp = round((hf+aag+af+hag)/2,1)
        note=""
        if h_rxg["trend"]=="RISING": note=f" * {h} scoring more in recent games"
        elif a_rxg["trend"]=="RISING": note=f" * {a} on an attacking upswing"
        if exp>=3.0:   out["goals"]=f"High-scoring game likely -- {h} {hf:.1f}/g, {a} {af:.1f}/g (last 5){note}"
        elif exp>=2.2: out["goals"]=f"Goals expected -- {h} scores {hf:.1f}/g, {a} scores {af:.1f}/g (last 5){note}"
        else:          out["goals"]=f"Tight match -- {h} concedes {hag:.1f}/g, {a} concedes {aag:.1f}/g (last 5)"
    elif h_st and a_st:
        hs_a=h_st.get("avg_scored",0); hc_a=h_st.get("avg_conceded",0)
        as_a=a_st.get("avg_scored",0); ac_a=a_st.get("avg_conceded",0)
        exp=round((hs_a+ac_a+as_a+hc_a)/2,1)
        if exp>=3.0:   out["goals"]=f"Both sides open defensively -- {h} {hs_a}/g, {a} {as_a}/g"
        elif exp>=2.2: out["goals"]=f"Goals expected -- {h} scores {hs_a}, concedes {hc_a} * {a} scores {as_a}, concedes {ac_a}"
        else:          out["goals"]=f"Tight match likely -- {h} concedes {hc_a}/g, {a} concedes {ac_a}/g"

    # Squad intelligence
    if h_sq and a_sq and h_sq["player_count"]>0:
        hs=h_sq["score"]; as_s=a_sq["score"]
        if abs(hs-as_s)>=12:
            s=h if hs>as_s else a; ws=a if hs>as_s else h
            out["squad"] = (f"{s} hold a clear squad quality edge "
                           f"({max(hs,as_s):.0f}/100 vs {min(hs,as_s):.0f}/100)")
        else:
            out["squad"] = f"Evenly matched squads -- {h} {hs:.0f}/100 vs {a} {as_s:.0f}/100"
        if h_sq["key_missing"]>0: out["squad"]+=f" * {h} missing {h_sq['key_missing']} key player(s)"
        if a_sq["key_missing"]>0: out["squad"]+=f" * {a} missing {a_sq['key_missing']} key player(s)"
        if h_sq["top_players"]:
            tp=h_sq["top_players"][0]
            out["top_player"]=f"{h} key man: {tp['name']} ({tp['rating']:.1f} rating, {tp['goals']}G {tp['assists']}A)"
        if a_sq["top_players"]:
            tp=a_sq["top_players"][0]
            out["top_player_away"]=f"{a} key man: {tp['name']} ({tp['rating']:.1f} rating, {tp['goals']}G {tp['assists']}A)"

    # Injuries
    miss=[]
    if h_inj: miss.append(f"{h}: {', '.join(i['name'] for i in h_inj[:2])}")
    if a_inj: miss.append(f"{a}: {', '.join(i['name'] for i in a_inj[:2])}")
    if miss: out["injuries"]=" * ".join(miss)+" sidelined"

    return out
