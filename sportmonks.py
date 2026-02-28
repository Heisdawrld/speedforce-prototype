"""
sportmonks.py -- Complete Sportmonks API v3 Integration
Replaces Bzzoiro + API Football entirely.
Single source of truth for all football data.
"""

import os, json, requests, time
from datetime import datetime, timezone, timedelta
import database

TOKEN = os.environ.get("SPORTMONKS_TOKEN",
        "EbRqkfYJgeCOtHzoC1AXpk1OO4semN0DtJ1P84zrYVNRCT1x4dHVsP9FGJAV")
BASE  = "https://api.sportmonks.com/v3/football"
WAT   = 1  # UTC+1

# In-memory cache -- zero repeat API calls within same session
_mem = {}

def _mem_get(key, max_age_hours=6):
    if key not in _mem: return None
    data, ts = _mem[key]
    if datetime.now(timezone.utc) - ts > timedelta(hours=max_age_hours):
        del _mem[key]; return None
    return data

def _mem_set(key, data):
    _mem[key] = (data, datetime.now(timezone.utc))

def _get(endpoint, params=None, cache_hours=6, raw=False):
    """Core API caller with 2-layer cache (memory + SQLite)."""
    p    = params or {}
    ck   = f"sm_{endpoint}_{json.dumps(sorted(p.items()))}"[:200]

    mem = _mem_get(ck, cache_hours)
    if mem is not None: return mem

    db_cached = database.cache_get("h2h_cache", ck, max_age_hours=cache_hours)
    if db_cached:
        try:
            data = json.loads(db_cached)
            _mem_set(ck, data)
            return data
        except: pass

    try:
        r = requests.get(f"{BASE}{endpoint}",
                         headers={"Authorization": TOKEN},
                         params=p, timeout=15)
        if r.status_code == 429:
            print(f"[SM] rate limited: {endpoint}")
            return None
        if r.status_code != 200:
            print(f"[SM] {endpoint}: HTTP {r.status_code} {r.text[:100]}")
            return None
        resp = r.json()
        data = resp if raw else resp.get("data")
        if data is not None:
            _mem_set(ck, data)
            database.cache_set("h2h_cache", ck, json.dumps(data))
        return data
    except Exception as e:
        print(f"[SM] {endpoint}: {e}")
        return None

# ─────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────

def _get_paginated(endpoint, params=None, cache_hours=6, max_pages=10):
    """Fetch ALL pages. Sportmonks defaults 25/page -- this gets everything."""
    p = dict(params or {})
    p.setdefault("per_page", 100)
    ck = f"sm_paged_{endpoint}_{json.dumps(sorted(p.items()))}"[:200]

    mem = _mem_get(ck, cache_hours)
    if mem is not None: return mem

    db_cached = database.cache_get("h2h_cache", ck, max_age_hours=cache_hours)
    if db_cached:
        try:
            data = json.loads(db_cached)
            _mem_set(ck, data)
            return data
        except: pass

    all_items = []
    page = 1
    while page <= max_pages:
        try:
            r = requests.get(f"{BASE}{endpoint}",
                             headers={"Authorization": TOKEN},
                             params={**p, "page": page}, timeout=15)
            if r.status_code == 429:
                print(f"[SM] rate limited p{page}")
                break
            if r.status_code != 200:
                print(f"[SM] {endpoint} p{page}: HTTP {r.status_code}")
                break
            resp  = r.json()
            items = resp.get("data") or []
            meta  = resp.get("meta") or {}
            all_items.extend(items if isinstance(items, list) else [])
            pag   = meta.get("pagination") or {}
            total = int(pag.get("total_pages") or meta.get("last_page") or 1)
            if page >= total: break
            page += 1
        except Exception as e:
            print(f"[SM] paginated {endpoint} p{page}: {e}")
            break

    _mem_set(ck, all_items)
    if all_items:
        database.cache_set("h2h_cache", ck, json.dumps(all_items))
    return all_items

def get_fixtures_window(days=3):
    """Fetch fixtures for next N days -- handles pagination fully."""
    start = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    end   = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")
    return _get_paginated(
        f"/fixtures/between/{start}/{end}",
        {"include": "participants;league;league.country;scores;state"},
        cache_hours=0.5, max_pages=15
    )

def get_fixtures_today():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _get_paginated(
        f"/fixtures/date/{today}",
        {"include": "participants;league;league.country;scores;state"},
        cache_hours=0.5
    )

def get_fixtures_tomorrow():
    tmrw = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    return _get_paginated(
        f"/fixtures/date/{tmrw}",
        {"include": "participants;league;league.country;scores;state"},
        cache_hours=1
    )

def get_fixture_detail(fixture_id):
    """
    Full fixture data -- everything for match page.
    One call gets: scores, events, lineups, stats, odds, xG, referee
    """
    return _get(f"/fixtures/{fixture_id}",
                {"include": (
                    "participants;"
                    "league;"
                    "scores;"
                    "state;"
                    "events.participant;"
                    "lineups.player;"
                    "statistics.type;"
                    "referees;"
                    "metadata"
                )},
                cache_hours=0.25)

def get_livescores():
    return _get("/livescores",
                {"include": "participants;scores;state;events;league"},
                cache_hours=0.08) or []

def get_h2h(team1_id, team2_id):
    ck = f"h2h_{min(team1_id,team2_id)}_{max(team1_id,team2_id)}"
    mem = _mem_get(ck, 24)
    if mem: return mem
    data = _get(f"/fixtures/headtohead/{team1_id}/{team2_id}",
                {"include": "participants;scores;league",
                 "per_page": 10},
                cache_hours=24) or []
    _mem_set(ck, data)
    return data

def get_team_last_fixtures(team_id, last=5):
    data = _get(f"/teams/{team_id}",
                {"include": "latestFixtures.participants;latestFixtures.scores;latestFixtures.state"},
                cache_hours=6)
    if not data: return []
    raw = (data.get("latest_fixtures")
           or data.get("latestFixtures") or [])
    return raw[:last]

# ─────────────────────────────────────────────────────────────
# LEAGUES & STANDINGS
# ─────────────────────────────────────────────────────────────

def get_all_leagues():
    return _get("/leagues",
                {"include": "country", "per_page": 300},
                cache_hours=24) or []

def get_leagues_by_date(date=None):
    d = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _get(f"/leagues/date/{d}",
                {"include": "country"},
                cache_hours=2) or []

def get_standings(season_id):
    return _get(f"/standings/seasons/{season_id}",
                {"include": "participant"},
                cache_hours=6) or []

def get_live_standings(league_id):
    return _get(f"/standings/live/leagues/{league_id}",
                {"include": "participant"},
                cache_hours=0.5) or []

# ─────────────────────────────────────────────────────────────
# PREDICTIONS
# ─────────────────────────────────────────────────────────────

def get_predictions(fixture_id):
    # Sportmonks v3: use fixture-specific endpoint
    return _get(f"/predictions/probabilities/fixtures/{fixture_id}",
                cache_hours=6)

def get_value_bets(fixture_id):
    return _get(f"/predictions/value-bets/fixtures/{fixture_id}",
                cache_hours=6)

def parse_predictions(raw):
    """Extract clean probabilities from Sportmonks predictions."""
    if not raw: return None
    preds = raw if isinstance(raw, list) else [raw]
    out = {}
    for p in preds:
        name = (p.get("name") or p.get("type_id") or "").lower()
        val  = p.get("value") or p.get("probability") or p.get("percentage")
        if val is None: continue
        try:
            v = float(str(val).replace("%",""))
        except: continue
        if   "home"  in name or name == "1": out["home_win"]  = v
        elif "draw"  in name or name == "x": out["draw"]      = v
        elif "away"  in name or name == "2": out["away_win"]  = v
        elif "over 2.5" in name:             out["over_25"]   = v
        elif "over 1.5" in name:             out["over_15"]   = v
        elif "btts" in name or "gg" in name: out["btts"]      = v
    return out if out else None

# ─────────────────────────────────────────────────────────────
# ODDS
# ─────────────────────────────────────────────────────────────

def get_odds(fixture_id):
    return _get(f"/odds/pre-match/fixtures/{fixture_id}",
                {"include": "bookmaker;market",
                 "per_page": 100},
                cache_hours=3) or []

def parse_odds(raw_odds):
    """Extract key market odds -- best available across bookmakers."""
    out = {}
    if not raw_odds: return out
    odds_list = raw_odds if isinstance(raw_odds, list) else [raw_odds]
    for odd in odds_list:
        market_name = ""
        m = odd.get("market")
        if isinstance(m, dict):
            market_name = (m.get("name") or "").lower()
        elif isinstance(m, str):
            market_name = m.lower()

        label = (odd.get("label") or odd.get("name") or
                 odd.get("value") or "").lower()
        try:
            v = float(odd.get("value") or odd.get("odd") or
                      odd.get("price") or 0)
        except: continue
        if v <= 1.0: continue

        if "1x2" in market_name or "match winner" in market_name or "moneyline" in market_name:
            if "home" in label or label == "1":
                if "home" not in out or v < out["home"]: out["home"] = v
            elif "draw" in label or label == "x":
                if "draw" not in out or v < out["draw"]: out["draw"] = v
            elif "away" in label or label == "2":
                if "away" not in out or v < out["away"]: out["away"] = v
        elif "over/under" in market_name or "goals ou" in market_name:
            if "over" in label and "2.5" in label:
                if "over_25" not in out or v < out["over_25"]: out["over_25"] = v
            elif "under" in label and "2.5" in label:
                if "under_25" not in out or v < out["under_25"]: out["under_25"] = v
            elif "over" in label and "1.5" in label:
                if "over_15" not in out or v < out["over_15"]: out["over_15"] = v
        elif "both teams" in market_name or "btts" in market_name:
            if "yes" in label:
                if "btts_yes" not in out or v < out["btts_yes"]: out["btts_yes"] = v
    return out

# ─────────────────────────────────────────────────────────────
# STATISTICS & xG
# ─────────────────────────────────────────────────────────────

def parse_statistics(stats, home_id, away_id):
    """
    Parse fixture statistics into clean dict.
    Returns: shots, possession, xG, corners, cards per team.
    """
    if not stats: return {}, {}
    h = {}; a = {}

    stat_map = {
        "ball possession": "possession",
        "shots total":     "shots_total",
        "shots on target": "shots_on_target",
        "expected goals":  "xg",
        "corners":         "corners",
        "yellow cards":    "yellow_cards",
        "red cards":       "red_cards",
        "fouls":           "fouls",
        "attacks":         "attacks",
        "dangerous attacks":"dangerous_attacks",
        "passes":          "passes",
        "passes accurate": "passes_accurate",
    }

    stat_list = stats if isinstance(stats, list) else [stats]
    for s in stat_list:
        type_info = s.get("type") or {}
        type_name = (type_info.get("name") or
                     s.get("type_name") or "").lower()
        value     = s.get("data", {}).get("value") if isinstance(s.get("data"), dict) else s.get("value")
        part_id   = s.get("participant_id") or s.get("team_id")

        key = stat_map.get(type_name)
        if not key or value is None: continue

        try:
            v = float(str(value).replace("%",""))
        except: continue

        if part_id == home_id:   h[key] = v
        elif part_id == away_id: a[key] = v

    return h, a

def parse_lineups(lineups, home_id, away_id):
    """Extract confirmed starting XIs from lineups."""
    h_xi = []; a_xi = []
    if not lineups: return h_xi, a_xi
    for l in (lineups if isinstance(lineups, list) else [lineups]):
        player = l.get("player") or {}
        name   = player.get("display_name") or player.get("name","")
        pos    = l.get("position") or l.get("position_id","")
        is_start = l.get("type_id") in (11, 1) or l.get("formation_field") is not None
        if not is_start: continue
        entry = {"name": name, "position": str(pos)}
        if l.get("team_id") == home_id or l.get("participant_id") == home_id:
            h_xi.append(entry)
        elif l.get("team_id") == away_id or l.get("participant_id") == away_id:
            a_xi.append(entry)
    return h_xi, a_xi

def parse_events(events, home_id, away_id):
    """Parse match events into goals, cards, subs."""
    goals = []; cards = []; subs = []
    if not events: return goals, cards, subs
    for e in (events if isinstance(events, list) else [events]):
        type_id   = e.get("type_id") or 0
        minute    = e.get("minute") or e.get("result") or 0
        player    = (e.get("participant") or {})
        pname     = player.get("display_name") or player.get("name","")
        team_id   = e.get("participant_id") or e.get("team_id")
        side      = "home" if team_id == home_id else "away"

        # Goals: type_id 16
        if type_id == 16 or (isinstance(type_id, int) and type_id in (16, 19)):
            goals.append({"minute": minute, "player": pname, "side": side})
        # Yellow: 83, Red: 84
        elif type_id in (83, 84):
            color = "yellow" if type_id == 83 else "red"
            cards.append({"minute": minute, "player": pname,
                          "side": side, "color": color})
        # Sub: 18
        elif type_id == 18:
            subs.append({"minute": minute, "player": pname, "side": side})

    return goals, cards, subs

# ─────────────────────────────────────────────────────────────
# REFEREE
# ─────────────────────────────────────────────────────────────

def get_referee(referee_id):
    return _get(f"/referees/{referee_id}",
                {"include": "statistics"},
                cache_hours=24)

def parse_referee(ref_data):
    """Extract referee risk signals for prediction."""
    if not ref_data: return None
    try:
        stats = ref_data.get("statistics") or []
        total_g = total_yc = total_rc = total_pen = 0
        for s in (stats if isinstance(stats, list) else [stats]):
            total_g   += s.get("games", 0) or 0
            total_yc  += s.get("yellow_cards", 0) or 0
            total_rc  += s.get("red_cards", 0) or 0
            total_pen += s.get("penalties", 0) or 0
        if total_g == 0: return None
        avg_yc  = round(total_yc  / total_g, 2)
        avg_rc  = round(total_rc  / total_g, 2)
        pen_r   = round(total_pen / total_g, 3)
        return {
            "name":           ref_data.get("display_name") or ref_data.get("name",""),
            "games":          total_g,
            "avg_yellow":     avg_yc,
            "avg_red":        avg_rc,
            "penalty_rate":   pen_r,
            "high_card_game": avg_yc > 4.0,
            "pen_prone":      pen_r > 0.25,
        }
    except Exception as e:
        print(f"[SM] referee parse: {e}")
        return None

# ─────────────────────────────────────────────────────────────
# TEAM HELPERS
# ─────────────────────────────────────────────────────────────

def extract_teams(fixture):
    """
    Extract home/away team info from Sportmonks fixture.
    Sportmonks uses 'participants' with meta.location.
    Returns: (home_id, home_name, away_id, away_name)
    """
    parts = fixture.get("participants") or []
    home_id = home_name = away_id = away_name = None
    for p in parts:
        loc = (p.get("meta") or {}).get("location","")
        pid  = p.get("id")
        name = p.get("name") or p.get("short_name","")
        if loc == "home": home_id = pid; home_name = name
        elif loc == "away": away_id = pid; away_name = name
    return home_id, home_name, away_id, away_name

def extract_score(fixture):
    """Extract current/final score from fixture."""
    scores = fixture.get("scores") or []
    h = a = None
    for s in scores:
        desc = (s.get("description") or "").upper()
        score = s.get("score") or {}
        if "CURRENT" in desc or "FULLTIME" in desc or "2ND_HALF" in desc:
            h = score.get("participant") if score.get("participant") else None
            # Try structured format
            if h is None:
                goals = score.get("goals") or score.get("score")
                if isinstance(goals, dict):
                    h = goals.get("home") or goals.get("participant")
                    a = goals.get("away") or goals.get("visitor")
            break
    # Fallback: parse scores array
    if h is None:
        for s in scores:
            score = s.get("score") or {}
            participant = score.get("participant")
            if participant is not None:
                desc = (s.get("description") or "").upper()
                if "HOME" in desc: h = participant
                elif "AWAY" in desc: a = participant
    return h, a

def extract_state(fixture):
    """Get match state: NS, 1H, HT, 2H, FT, etc."""
    state = fixture.get("state") or {}
    if isinstance(state, dict):
        return (state.get("short_name") or
                state.get("name") or
                state.get("state") or "NS")
    return str(state) or "NS"

def extract_referee(fixture):
    """Get referee ID from fixture."""
    refs = fixture.get("referees") or []
    for r in (refs if isinstance(refs, list) else [refs]):
        if r.get("type_id") in (1, None):  # Main referee
            return r.get("id") or r.get("referee_id")
    return None

def build_form_string(last_fixtures, team_id):
    """Build W/D/L form string from last fixtures."""
    form = []
    for f in last_fixtures:
        parts  = f.get("participants") or []
        scores = f.get("scores") or []
        h_id = a_id = h_g = a_g = None
        for p in parts:
            loc = (p.get("meta") or {}).get("location","")
            if loc == "home":   h_id = p.get("id")
            elif loc == "away": a_id = p.get("id")
        for s in scores:
            desc = (s.get("description") or "").upper()
            if "CURRENT" in desc or "FULLTIME" in desc:
                sc = s.get("score") or {}
                h_g = sc.get("participant") if isinstance(sc.get("participant"), int) else None
                if h_g is None:
                    goals = sc.get("goals") or sc.get("score")
                    if isinstance(goals, dict):
                        h_g = goals.get("home"); a_g = goals.get("away")
        if h_g is None or a_g is None: continue
        try:
            h_g = int(h_g); a_g = int(a_g)
        except: continue
        if team_id == h_id:
            form.append("W" if h_g > a_g else "D" if h_g == a_g else "L")
        elif team_id == a_id:
            form.append("W" if a_g > h_g else "D" if h_g == a_g else "L")
    return form[-5:]

def parse_h2h_summary(h2h_fixtures, home_id, away_id):
    """Build H2H summary from Sportmonks fixtures."""
    if not h2h_fixtures: return None
    total = hw = dr = aw = goals = over25 = btts = 0
    matches = []
    for f in h2h_fixtures[:10]:
        parts  = f.get("participants") or []
        h_id_f = a_id_f = None
        h_name_f = a_name_f = ""
        for p in parts:
            loc = (p.get("meta") or {}).get("location","")
            if loc == "home":  h_id_f = p.get("id"); h_name_f = p.get("name","")
            elif loc == "away": a_id_f = p.get("id"); a_name_f = p.get("name","")
        h_g, a_g = extract_score(f)
        if h_g is None or a_g is None: continue
        try: h_g = int(h_g); a_g = int(a_g)
        except: continue
        total += 1
        if h_id_f == home_id:
            if h_g > a_g: hw += 1
            elif h_g == a_g: dr += 1
            else: aw += 1
        else:
            if a_g > h_g: hw += 1
            elif h_g == a_g: dr += 1
            else: aw += 1
        t = h_g + a_g
        goals += t
        if t > 2: over25 += 1
        if h_g > 0 and a_g > 0: btts += 1
        date = (f.get("starting_at") or f.get("date",""))[:10]
        matches.append({"date": date, "home": h_name_f, "away": a_name_f,
                        "home_goals": h_g, "away_goals": a_g})
    if total == 0: return None
    return {
        "total": total, "home_wins": hw, "draws": dr, "away_wins": aw,
        "avg_goals": round(goals/total, 1),
        "over_25_pct": round(over25/total*100),
        "btts_pct": round(btts/total*100),
        "matches": matches,
    }

# ─────────────────────────────────────────────────────────────
# MASTER ENRICH -- called for every match page
# ─────────────────────────────────────────────────────────────

def enrich_match(fixture_id):
    """
    Fetch everything needed for a match page prediction.
    Single entry point -- replaces external_data.enrich_match().
    """
    enriched = {
        "fixture_id":    fixture_id,
        "home_id":       None, "away_id":      None,
        "home_name":     "",   "away_name":    "",
        "state":         "NS",
        "score_home":    None, "score_away":   None,
        "league_id":     0,    "league_name":  "",
        "kickoff":       "",
        "predictions":   None,
        "odds":          {},
        "xg_home":       None, "xg_away":      None,
        "home_form":     [],   "away_form":    [],
        "home_injuries": [],   "away_injuries":[],
        "h2h_summary":   None,
        "referee":       None,
        "home_lineup":   [],   "away_lineup":  [],
        "home_stats":    {},   "away_stats":   {},
        "events":        {"goals":[], "cards":[], "subs":[]},
        "value_bets":    [],
    }

    # 1. Full fixture detail
    fx = get_fixture_detail(fixture_id)
    if not fx: return enriched

    # Extract teams
    h_id, h_name, a_id, a_name = extract_teams(fx)
    enriched["home_id"]   = h_id
    enriched["away_id"]   = a_id
    enriched["home_name"] = h_name or ""
    enriched["away_name"] = a_name or ""
    enriched["state"]     = extract_state(fx)
    enriched["score_home"], enriched["score_away"] = extract_score(fx)
    lg = fx.get("league") or {}
    if isinstance(lg, dict):
        enriched["league_id"]   = lg.get("id", 0)
        enriched["league_name"] = lg.get("name", "")
    enriched["kickoff"] = fx.get("starting_at") or fx.get("date","")

    # Parse stats, lineups, events from the single call
    if h_id and a_id:
        hs, as_ = parse_statistics(fx.get("statistics"), h_id, a_id)
        enriched["home_stats"] = hs
        enriched["away_stats"] = as_
        enriched["xg_home"] = hs.get("xg") or enriched["xg_home"]
        enriched["xg_away"] = as_.get("xg") or enriched["xg_away"]
        h_xi, a_xi = parse_lineups(fx.get("lineups"), h_id, a_id)
        enriched["home_lineup"] = h_xi
        enriched["away_lineup"] = a_xi
        goals, cards, subs = parse_events(fx.get("events"), h_id, a_id)
        enriched["events"] = {"goals": goals, "cards": cards, "subs": subs}

    # 2. Predictions
    preds = get_predictions(fixture_id)
    if preds:
        enriched["predictions"] = parse_predictions(
            preds if isinstance(preds, list) else [preds])

    # 3. Odds
    enriched["odds"] = parse_odds(get_odds(fixture_id))

    # 4. H2H
    if h_id and a_id:
        h2h = get_h2h(h_id, a_id)
        enriched["h2h_summary"] = parse_h2h_summary(h2h, h_id, a_id)

    # 5. Form
    if h_id:
        h_last = get_team_last_fixtures(h_id)
        enriched["home_form"] = build_form_string(h_last, h_id)
    if a_id:
        a_last = get_team_last_fixtures(a_id)
        enriched["away_form"] = build_form_string(a_last, a_id)

    # 6. Referee
    ref_id = extract_referee(fx)
    if ref_id:
        ref_data = get_referee(ref_id)
        enriched["referee"] = parse_referee(ref_data)

    # 7. Value bets
    vb = get_value_bets(fixture_id)
    enriched["value_bets"] = vb if isinstance(vb, list) else ([vb] if vb else [])

    return enriched
