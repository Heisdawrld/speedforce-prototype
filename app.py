from flask import Flask, render_template_string, request, jsonify
import requests, os, math, json
from datetime import datetime, timedelta, timezone
import match_predictor, database, external_data

app = Flask(__name__)
database.init_db()

BSD_TOKEN  = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL   = "https://sports.bzzoiro.com/api"
WAT_OFFSET = 1

# -----------------------------------------------------------------------------
# LEAGUE REGISTRY
# Maps Bzzoiro league IDs -> display metadata.
# The KEY issue: we can't hardcode IDs without knowing what Bzzoiro returns.
# Solution: auto-discover leagues from live data, merge with known metadata.
# -----------------------------------------------------------------------------

# Known metadata by league name (lowercase) -- name-based matching is reliable
# even when IDs differ across API providers
KNOWN_LEAGUES_BY_NAME = {
    "premier league":        {"country":"England",     "icon":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","tier":1},
    "la liga":               {"country":"Spain",       "icon":"🇪🇸","tier":1},
    "serie a":               {"country":"Italy",       "icon":"🇮🇹","tier":1},
    "bundesliga":            {"country":"Germany",     "icon":"🇩🇪","tier":1},
    "ligue 1":               {"country":"France",      "icon":"🇫🇷","tier":1},
    "champions league":      {"country":"Europe",      "icon":"🏆","tier":1},
    "uefa champions league": {"country":"Europe",      "icon":"🏆","tier":1},
    "europa league":         {"country":"Europe",      "icon":"🏆","tier":1},
    "conference league":     {"country":"Europe",      "icon":"🏆","tier":2},
    "liga portugal":         {"country":"Portugal",    "icon":"🇵🇹","tier":2},
    "primeira liga":         {"country":"Portugal",    "icon":"🇵🇹","tier":2},
    "eredivisie":            {"country":"Netherlands", "icon":"🇳🇱","tier":2},
    "premier liga":          {"country":"Russia",      "icon":"🇷🇺","tier":2},
    "russian premier league":{"country":"Russia",      "icon":"🇷🇺","tier":2},
    "süper lig":             {"country":"Turkey",      "icon":"🇹🇷","tier":2},
    "super lig":             {"country":"Turkey",      "icon":"🇹🇷","tier":2},
    "championship":          {"country":"England",     "icon":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","tier":2},
    "scottish premiership":  {"country":"Scotland",    "icon":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","tier":2},
    "scottish prem":         {"country":"Scotland",    "icon":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","tier":2},
    "belgian pro league":    {"country":"Belgium",     "icon":"🇧🇪","tier":2},
    "jupiler pro league":    {"country":"Belgium",     "icon":"🇧🇪","tier":2},
    "swiss super league":    {"country":"Switzerland", "icon":"🇨🇭","tier":2},
    "austrian bundesliga":   {"country":"Austria",     "icon":"🇦🇹","tier":2},
    "greek super league":    {"country":"Greece",      "icon":"🇬🇷","tier":2},
    "super league greece":   {"country":"Greece",      "icon":"🇬🇷","tier":2},
    "mls":                   {"country":"USA",         "icon":"🇺🇸","tier":2},
    "brasileirão série a":   {"country":"Brazil",      "icon":"🇧🇷","tier":2},
    "brasileirao":           {"country":"Brazil",      "icon":"🇧🇷","tier":2},
    "serie a (brazil)":      {"country":"Brazil",      "icon":"🇧🇷","tier":2},
    "liga mx":               {"country":"Mexico",      "icon":"🇲🇽","tier":2},
    "liga profesional":      {"country":"Argentina",   "icon":"🇦🇷","tier":2},
    "liga argentina":        {"country":"Argentina",   "icon":"🇦🇷","tier":2},
    "saudi professional league":{"country":"Saudi Arabia","icon":"🇸🇦","tier":2},
    "saudi pro league":      {"country":"Saudi Arabia","icon":"🇸🇦","tier":3},
    "uae pro league":        {"country":"UAE",         "icon":"🇦🇪","tier":3},
    "israeli premier league":{"country":"Israel",      "icon":"🇮🇱","tier":3},
    "croatian hnl":          {"country":"Croatia",     "icon":"🇭🇷","tier":3},
    "serbian superliga":     {"country":"Serbia",      "icon":"🇷🇸","tier":3},
    "bulgarian first league":{"country":"Bulgaria",    "icon":"🇧🇬","tier":3},
    "romanian superliga":    {"country":"Romania",     "icon":"🇷🇴","tier":3},
    "czech liga":            {"country":"Czech Rep",   "icon":"🇨🇿","tier":3},
    "polish ekstraklasa":    {"country":"Poland",      "icon":"🇵🇱","tier":3},
    "ekstraklasa":           {"country":"Poland",      "icon":"🇵🇱","tier":3},
    "ukrainian premier league":{"country":"Ukraine",   "icon":"🇺🇦","tier":3},
    "danish superliga":      {"country":"Denmark",     "icon":"🇩🇰","tier":3},
    "eliteserien":           {"country":"Norway",      "icon":"🇳🇴","tier":3},
    "allsvenskan":           {"country":"Sweden",      "icon":"🇸🇪","tier":3},
    "chinese super league":  {"country":"China",       "icon":"🇨🇳","tier":3},
    "j1 league":             {"country":"Japan",       "icon":"🇯🇵","tier":3},
    "j-league":              {"country":"Japan",       "icon":"🇯🇵","tier":3},
    "ligue 2":               {"country":"France",      "icon":"🇫🇷","tier":3},
    "2. bundesliga":         {"country":"Germany",     "icon":"🇩🇪","tier":3},
    "serie b":               {"country":"Italy",       "icon":"🇮🇹","tier":3},
    "segunda división":      {"country":"Spain",       "icon":"🇪🇸","tier":3},
    "league one":            {"country":"England",     "icon":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","tier":3},
    "league two":            {"country":"England",     "icon":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","tier":3},
    "copa libertadores":     {"country":"S. America",  "icon":"🏆","tier":2},
    "africa cup of nations": {"country":"Africa",      "icon":"🌍","tier":2},
    "afcon":                 {"country":"Africa",      "icon":"🌍","tier":2},
}

# In-memory league registry built from live data
# structure: { league_id: {"name":..,"country":..,"icon":..,"tier":..} }
_LEAGUE_REGISTRY = {}

def _lookup_league_meta(name: str) -> dict:
    """Find metadata for a league by fuzzy name matching."""
    n = name.lower().strip()
    # Exact match
    if n in KNOWN_LEAGUES_BY_NAME:
        return KNOWN_LEAGUES_BY_NAME[n]
    # Partial match
    for key, meta in KNOWN_LEAGUES_BY_NAME.items():
        if key in n or n in key:
            return meta
    # Fallback: guess from country flag in name
    return {"country": "World", "icon": "🌐", "tier": 3}

def _build_league_registry(all_matches: list) -> dict:
    """
    Build/update the league registry from real API data.
    This is the fix for the mismatch -- we trust the API's own league IDs
    and enrich them with our metadata by name.
    """
    global _LEAGUE_REGISTRY
    seen = {}
    for m in all_matches:
        event  = m.get("event", {})
        league = event.get("league", {})
        l_id   = league.get("id")
        l_name = league.get("name", "Unknown")
        if l_id is None:
            continue
        if l_id not in seen:
            meta = _lookup_league_meta(l_name)
            seen[l_id] = {
                "id":      l_id,
                "name":    l_name,
                "country": meta["country"],
                "icon":    meta["icon"],
                "tier":    meta["tier"],
            }
    _LEAGUE_REGISTRY = seen
    return seen

# -- API HELPERS ---------------------------------------------------------------

def api_get(path, params=None):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] {path} -> {e}")
        return {}

def fetch_all_predictions():
    """
    Fetch ALL predictions across all pages. Caches 30 min.
    After fetch, rebuilds the live league registry.
    """
    cache_key = "all_predictions_v4"
    cached = database.cache_get("h2h_cache", cache_key, max_age_hours=0.5)
    if cached:
        try:
            data = json.loads(cached)
            _build_league_registry(data)
            return data
        except:
            pass

    all_matches = []
    page_url    = f"{BASE_URL}/predictions/"
    headers     = {"Authorization": f"Token {BSD_TOKEN}"}
    page = 1; max_pages = 25

    while page_url and page <= max_pages:
        try:
            r = requests.get(page_url, headers=headers, timeout=15)
            r.raise_for_status()
            data     = r.json()
            results  = data.get("results", [])
            all_matches.extend(results)
            page_url = data.get("next")
            page += 1
            print(f"[fetch] page {page-1}: +{len(results)} (total {len(all_matches)})")
        except Exception as e:
            print(f"[fetch] stopped at page {page}: {e}")
            break

    database.cache_set("h2h_cache", cache_key, json.dumps(all_matches))
    _build_league_registry(all_matches)
    return all_matches

def fetch_league_matches(l_id: int) -> list:
    """
    STRICT league filtering -- only matches where event.league.id == l_id.
    The registry ensures we're always using the API's own league IDs.
    """
    all_matches = fetch_all_predictions()
    return [
        m for m in all_matches
        if m.get("event", {}).get("league", {}).get("id") == l_id
    ]

# -- LIVE ODDS (API Football) --------------------------------------------------

# API Football league IDs for odds endpoint
_AFL_ODDS_LEAGUE_MAP = {
    "Premier League": 39, "La Liga": 140, "Serie A": 135, "Bundesliga": 78,
    "Ligue 1": 61, "Champions League": 2, "Europa League": 3,
    "Liga Portugal": 94, "Eredivisie": 88, "Süper Lig": 203,
    "Championship": 40, "Scottish Premiership": 179,
}

def get_live_odds(home_team: str, away_team: str, league_name: str) -> dict:
    """
    Fetch live bookmaker odds from API Football.
    Returns dict of market -> bookmaker_odds for Bet365 / best available.
    Falls back gracefully -- never crashes.
    """
    api_key = external_data.APIFOOTBALL_KEY
    if not api_key:
        return {}

    cache_key = f"odds_{home_team[:8]}_{away_team[:8]}".replace(" ","_")
    cached = database.cache_get("h2h_cache", cache_key, max_age_hours=2)
    if cached:
        try: return json.loads(cached)
        except: pass

    afl_lg = _AFL_ODDS_LEAGUE_MAP.get(league_name)
    if not afl_lg:
        return {}

    try:
        r = requests.get(
            "https://v3.football.api-sports.io/odds",
            headers={
                "x-rapidapi-key":  api_key,
                "x-rapidapi-host": "v3.football.api-sports.io"
            },
            params={"league": afl_lg, "season": 2025, "bookmaker": 6},  # 6 = Bet365
            timeout=10
        )
        data = r.json().get("response", [])
        if not data:
            return {}

        odds_out = {}
        for fixture in data:
            teams = fixture.get("fixture", {})
            # match by team name (fuzzy)
            h_api = fixture.get("teams", {}).get("home", {}).get("name", "")
            a_api = fixture.get("teams", {}).get("away", {}).get("name", "")
            if home_team.lower()[:5] not in h_api.lower() and \
               away_team.lower()[:5] not in a_api.lower():
                continue
            for bookie in fixture.get("bookmakers", []):
                for bet in bookie.get("bets", []):
                    name = bet.get("name","")
                    if name == "Match Winner":
                        for v in bet.get("values",[]):
                            if v["value"]=="Home":   odds_out["home"] = float(v["odd"])
                            elif v["value"]=="Draw": odds_out["draw"] = float(v["odd"])
                            elif v["value"]=="Away": odds_out["away"] = float(v["odd"])
                    elif name == "Goals Over/Under":
                        for v in bet.get("values",[]):
                            if v["value"]=="Over 1.5":  odds_out["over_15"] = float(v["odd"])
                            elif v["value"]=="Over 2.5": odds_out["over_25"] = float(v["odd"])
                            elif v["value"]=="Under 2.5":odds_out["under_25"]= float(v["odd"])
                    elif name == "Both Teams Score":
                        for v in bet.get("values",[]):
                            if v["value"]=="Yes": odds_out["btts_yes"] = float(v["odd"])
                            elif v["value"]=="No": odds_out["btts_no"]  = float(v["odd"])
            if odds_out:
                break

        database.cache_set("h2h_cache", cache_key, json.dumps(odds_out))
        return odds_out
    except Exception as e:
        print(f"[odds] {e}")
        return {}

# -- RELIABILITY ENGINE --------------------------------------------------------

def compute_reliability(api_data: dict, enriched: dict, res: dict) -> dict:
    """
    Reliability Engine -- evaluates match conditions beyond probability.

    Returns:
        score     : 0-100 reliability score
        tag       : ✅ RELIABLE / ⚠️ AVOID / 🔄 VERSATILE / SOLID TIP / MONITOR
        reason    : 1-line explanation
        suppress  : bool -- if True, mark tip as questionable even if prob is high
    """
    event    = api_data.get("event", {})
    h_name   = event.get("home_team", "")
    a_name   = event.get("away_team", "")
    lg_name  = event.get("league", {}).get("name", "")
    h_form   = enriched.get("home_form", []) or res.get("form", {}).get("home", [])
    a_form   = enriched.get("away_form", []) or res.get("form", {}).get("away", [])
    h_inj    = enriched.get("home_injuries", [])
    a_inj    = enriched.get("away_injuries", [])
    rec      = res.get("recommended", {})
    h_win    = float(api_data.get("prob_home_win", 33))
    a_win    = float(api_data.get("prob_away_win", 33))
    draw     = float(api_data.get("prob_draw", 33))
    fav      = max(h_win, a_win)
    signals  = rec.get("agree", 0)
    conv     = rec.get("conv", 0)

    score  = 60  # baseline
    notes  = []
    flags  = []

    # -- Positive signals (raise score) --
    if fav >= 65:
        score += 10; notes.append("Clear favourite")
    if signals >= 3:
        score += 15; notes.append("All 3 signals aligned")
    elif signals >= 2:
        score += 8
    if conv >= 65:
        score += 10
    # Form stability
    h_pts = sum(3 if r=="W" else 1 if r=="D" else 0 for r in h_form[-5:]) if h_form else 0
    a_pts = sum(3 if r=="W" else 1 if r=="D" else 0 for r in a_form[-5:]) if a_form else 0
    h_stable = h_pts >= 9  # 3+ good results
    a_stable = a_pts >= 9
    if h_stable and (rec.get("tip") in ("HOME WIN","GG","OVER 2.5")):
        score += 8; notes.append("Home side in solid form")
    if a_stable and rec.get("tip") == "AWAY WIN":
        score += 8; notes.append("Away side in solid form")

    # -- Negative signals (reduce score) --
    # Slump detection
    h_slump = list(h_form[-3:]).count("L") >= 3 if len(h_form) >= 3 else False
    a_slump = list(a_form[-3:]).count("L") >= 3 if len(a_form) >= 3 else False
    if h_slump:
        score -= 20; flags.append("Home team on a 3-game losing run")
    if a_slump:
        score -= 15; flags.append("Away team on a 3-game losing run")

    # Key injuries
    key_out = len(h_inj) + len(a_inj)
    if key_out >= 3:
        score -= 20; flags.append(f"{key_out} key players sidelined")
    elif key_out >= 1:
        score -= 10; flags.append(f"{key_out} injury concern(s)")

    # Volatility -- close 3-way market
    spread = max(h_win, draw, a_win) - min(h_win, draw, a_win)
    if spread < 10:
        score -= 20; flags.append("3-way market very tight -- high volatility")
    elif spread < 15:
        score -= 10; flags.append("Closely contested match")

    # Cup / derby / friendly detection
    lg_lower = lg_name.lower()
    is_cup = any(w in lg_lower for w in ["cup","copa","coupe","pokal","fa cup","league cup","carabao"])
    is_friendly = "friendly" in lg_lower or "international" in lg_lower
    # Derby -- same city / rivalry names
    h_l = h_name.lower(); a_l = a_name.lower()
    is_derby = (
        any(w in h_l and w in a_l for w in ["city","united","fc","milan","madrid","london"]) or
        (h_l[:4] == a_l[:4])  # same name prefix = potential city rivals
    )

    if is_friendly:
        score -= 35; flags.append("International friendly -- low predictability")
    if is_cup:
        score -= 10; flags.append("Cup match -- upsets more common")
    if is_derby and not is_cup:
        score -= 12; flags.append("Derby fixture -- form often irrelevant")

    # Clamp
    score = max(0, min(100, score))

    # -- Determine tag --
    suppress = False
    if is_friendly or (is_derby and score < 50):
        tag = "🔄 VERSATILE"
        reason = flags[0] if flags else "Unpredictable fixture type"
    elif score <= 42 or (h_slump and key_out >= 2):
        tag = "⚠️ AVOID"
        reason = flags[0] if flags else "Multiple reliability concerns"
        suppress = True
    elif score >= 78 and signals >= 2 and not flags:
        tag = "✅ RELIABLE"
        reason = notes[0] if notes else "Strong model confidence across all signals"
    elif score >= 65:
        tag = "✅ RELIABLE"
        reason = notes[0] if notes else "Good signal agreement"
    elif conv >= 55:
        tag = "SOLID TIP"
        reason = "Moderate conviction -- worth considering"
    else:
        tag = "MONITOR"
        reason = "Insufficient signal strength -- watch closer to kickoff"

    return {
        "score":    score,
        "tag":      tag,
        "reason":   reason,
        "suppress": suppress,
        "flags":    flags,
        "notes":    notes,
    }

# -- DATE / TIME ---------------------------------------------------------------

def parse_dt(raw):
    if not raw:
        return datetime.now(tz=timezone.utc) + timedelta(hours=WAT_OFFSET)
    try:
        ts = int(float(str(raw)))
        if ts > 1_000_000_000:
            return datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=WAT_OFFSET)
    except (ValueError, TypeError):
        pass
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc) + timedelta(hours=WAT_OFFSET)
    except:
        return datetime.now(tz=timezone.utc) + timedelta(hours=WAT_OFFSET)

def now_wat():
    return datetime.now(tz=timezone.utc) + timedelta(hours=WAT_OFFSET)

def group_by_date(matches):
    today = now_wat().date()
    tomorrow = today + timedelta(days=1)
    groups = {}
    for m in matches:
        e   = m.get("event", {})
        raw = e.get("event_timestamp") or e.get("event_date", "")
        dt  = parse_dt(raw)
        d   = dt.date()
        if d == today:       key = "TODAY"
        elif d == tomorrow:  key = "TOMORROW"
        elif d < today:      key = "EARLIER"
        else:
            diff = (d - today).days
            key  = dt.strftime("%A").upper()[:3] if diff <= 6 else dt.strftime("%-d %b").upper()
        groups.setdefault(key, []).append((dt, m))
    for k in groups:
        groups[k].sort(key=lambda x: x[0])
    order   = ["EARLIER","TODAY","TOMORROW","MON","TUE","WED","THU","FRI","SAT","SUN"]
    ordered = {k: groups[k] for k in order if k in groups}
    for k in groups:
        if k not in ordered:
            ordered[k] = groups[k]
    return ordered

# -- UI HELPERS ----------------------------------------------------------------

def _quick_sure(m):
    try:
        return max(float(m.get("prob_home_win",0)), float(m.get("prob_away_win",0))) >= 82
    except: return False

def form_dot(r):
    cls = {"W":"dot-w","D":"dot-d","L":"dot-l"}.get(r.upper(),"dot-d")
    return f'<span class="dot {cls}">{r.upper()}</span>'

def form_dots(fl):
    if not fl: return '<span style="font-size:.6rem;color:var(--t)">--</span>'
    return '<div class="dots">'+''.join(form_dot(r) for r in list(fl)[-5:])+'</div>'

def prob_bar(label, pct, color="green"):
    c = {"green":"var(--g)","blue":"var(--b)","orange":"var(--w)","red":"var(--r)"}.get(color,"var(--g)")
    pct = round(float(pct), 1)
    return f'''<div class="prow">
      <div class="plabel"><span>{label}</span><span class="pval">{pct}%</span></div>
      <div class="ptrack"><div class="pfill" style="width:{min(pct,100)}%;background:{c}"></div></div>
    </div>'''

def result_badge(r):
    if r=="WIN":  return '<span class="badge badge-green">WIN</span>'
    if r=="LOSS": return '<span class="badge badge-red">LOSS</span>'
    return '<span class="badge badge-muted">PENDING</span>'

def tag_badge(tag):
    cls = {
        "✅ RELIABLE":   "badge-reliable",
        "⚠️ AVOID":      "badge-avoid",
        "🔄 VERSATILE":  "badge-versatile",
        "✅ SURE MATCH": "badge-sure",
        "ELITE PICK":    "badge-green",
        "STRONG PICK":   "badge-green",
        "SOLID TIP":     "badge-blue",
        "MONITOR":       "badge-muted",
    }.get(tag, "badge-muted")
    return f'<span class="badge {cls}">{tag}</span>'

def reliability_bar(score):
    c = "var(--g)" if score>=70 else "var(--w)" if score>=50 else "var(--r)"
    return f'''<div style="margin-top:10px">
      <div style="display:flex;justify-content:space-between;font-size:.6rem;margin-bottom:3px">
        <span style="letter-spacing:1px;text-transform:uppercase">Reliability Score</span>
        <span style="color:{c};font-weight:700">{score}/100</span>
      </div>
      <div class="ptrack"><div class="pfill" style="width:{score}%;background:{c}"></div></div>
    </div>'''

def tip_color(tip):
    if "WIN" in tip: return "var(--g)"
    if tip in ("GG","OVER 2.5","OVER 1.5","OVER 3.5"): return "var(--b)"
    if "UNDER" in tip or tip == "NG": return "var(--cy)"
    if "DRAW" in tip: return "var(--w)"
    return "var(--t2)"

# -- CSS -----------------------------------------------------------------------

CSS = """
:root{
  --bg:#04070c;--s:#0a0e16;--s2:#101520;--s3:#171e2a;
  --g:#00e676;--b:#4f8ef7;--w:#ff9500;--r:#f44336;
  --pu:#a855f7;--cy:#00bcd4;--gold:#ffc107;
  --t:#6e7d8e;--t2:#94a3b8;--wh:#e2e8f0;
  --bdr:rgba(255,255,255,.055);--bdr2:rgba(255,255,255,.1);
  --gs:linear-gradient(135deg,rgba(0,230,118,.07),rgba(79,142,247,.04));
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--t);font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;font-size:13px;min-height:100vh;padding-bottom:100px;overflow-x:hidden}
a{text-decoration:none;color:inherit}
::selection{background:rgba(0,230,118,.18)}
::-webkit-scrollbar{width:3px;height:3px}
::-webkit-scrollbar-thumb{background:var(--bdr2);border-radius:3px}

/* NAV */
nav{position:sticky;top:0;z-index:200;background:rgba(4,7,12,.92);backdrop-filter:blur(28px);border-bottom:1px solid var(--bdr)}
.nav-i{max-width:500px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;padding:11px 14px}
.logo{font-size:.95rem;font-weight:900;letter-spacing:-.5px;color:var(--wh)}
.logo span{color:var(--g)}
.logo sub{font-size:.45rem;color:var(--t);letter-spacing:1px;text-transform:uppercase;font-weight:400;vertical-align:middle;margin-left:2px}
.nav-pills{display:flex;gap:4px}
.npill{font-size:.58rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:5px 12px;border-radius:50px;border:1px solid var(--bdr);color:var(--t);transition:all .2s}
.npill.on,.npill:hover{border-color:var(--g);color:var(--g);background:rgba(0,230,118,.07)}

/* SHELL */
.shell{max-width:500px;margin:0 auto;padding:0 12px}

/* CARDS */
.card{background:var(--s);border:1px solid var(--bdr);border-radius:16px;padding:16px;margin-bottom:8px;transition:border-color .2s}

/* BADGES */
.badge{display:inline-flex;align-items:center;gap:3px;font-size:.56rem;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;padding:3px 9px;border-radius:50px}
.badge-green   {background:rgba(0,230,118,.1);color:var(--g);border:1px solid rgba(0,230,118,.2)}
.badge-blue    {background:rgba(79,142,247,.1);color:var(--b);border:1px solid rgba(79,142,247,.2)}
.badge-orange  {background:rgba(255,149,0,.1);color:var(--w);border:1px solid rgba(255,149,0,.2)}
.badge-muted   {background:rgba(110,125,142,.07);color:var(--t);border:1px solid var(--bdr)}
.badge-red     {background:rgba(244,67,54,.1);color:var(--r);border:1px solid rgba(244,67,54,.2)}
.badge-reliable{background:rgba(0,230,118,.12);color:var(--g);border:1px solid rgba(0,230,118,.3);font-size:.6rem}
.badge-avoid   {background:rgba(244,67,54,.1);color:var(--r);border:1px solid rgba(244,67,54,.28);font-size:.6rem}
.badge-versatile{background:rgba(255,193,7,.1);color:var(--gold);border:1px solid rgba(255,193,7,.25);font-size:.6rem}
.badge-sure    {background:rgba(0,230,118,.14);color:var(--g);border:1px solid rgba(0,230,118,.35);font-size:.62rem}
.badge-pu      {background:rgba(168,85,247,.1);color:var(--pu);border:1px solid rgba(168,85,247,.2)}

/* TYPOGRAPHY */
.eyebrow{font-size:.55rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--t);margin-bottom:4px}
.title  {font-size:2.4rem;font-weight:900;color:var(--wh);line-height:1;letter-spacing:-.8px}
.sep    {font-size:.55rem;letter-spacing:2px;text-transform:uppercase;color:var(--t);padding:14px 0 10px;border-bottom:1px solid var(--bdr);margin-bottom:12px}

/* PROB BARS */
.prow{margin-bottom:9px}
.plabel{display:flex;justify-content:space-between;margin-bottom:3px;font-size:.68rem}
.pval{color:var(--wh);font-weight:700}
.ptrack{height:4px;background:rgba(255,255,255,.05);border-radius:50px;overflow:hidden}
.pfill{height:100%;border-radius:50px;transition:width .7s cubic-bezier(.4,0,.2,1)}

/* FORM DOTS */
.dots{display:flex;gap:3px}
.dot{width:22px;height:22px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:.56rem;font-weight:700}
.dot-w{background:rgba(0,230,118,.14);color:var(--g)}
.dot-d{background:rgba(79,142,247,.14);color:var(--b)}
.dot-l{background:rgba(244,67,54,.14);color:var(--r)}

/* TABS */
.tabs{display:flex;gap:5px;overflow-x:auto;padding:2px 0 8px;margin-bottom:10px;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{flex-shrink:0;font-size:.6rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;padding:6px 13px;border-radius:50px;border:1px solid var(--bdr);color:var(--t);white-space:nowrap;transition:all .2s;cursor:pointer}
.tab.on,.tab:hover{border-color:var(--g);color:var(--g);background:rgba(0,230,118,.07)}

/* SEARCH */
.search-wrap{position:relative;margin-bottom:12px}
.search-input{width:100%;background:var(--s2);border:1px solid var(--bdr);border-radius:12px;padding:10px 14px 10px 38px;color:var(--wh);font-size:.8rem;outline:none;transition:border-color .2s}
.search-input:focus{border-color:var(--g)}
.search-input::placeholder{color:var(--t)}
.s-icon{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--t);pointer-events:none}
.s-clear{position:absolute;right:12px;top:50%;transform:translateY(-50%);color:var(--t);cursor:pointer;display:none;font-size:.75rem;padding:4px}
.s-clear.show{display:block}

/* LEAGUE GRID */
.league-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:8px}
.league-tile{background:var(--s);border:1px solid var(--bdr);border-radius:14px;padding:14px 12px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;display:block}
.league-tile:hover,.league-tile:active{border-color:rgba(0,230,118,.22);background:var(--s2);transform:scale(.983)}
.tile-icon{font-size:1.4rem;margin-bottom:6px;display:block}
.tile-name{font-size:.72rem;font-weight:800;color:var(--wh);line-height:1.2;margin-bottom:2px}
.tile-country{font-size:.57rem;letter-spacing:1px;text-transform:uppercase;color:var(--t)}
.tile-count{position:absolute;top:9px;right:9px;font-size:.55rem;font-weight:700;color:var(--g);background:rgba(0,230,118,.1);border:1px solid rgba(0,230,118,.15);border-radius:50px;padding:2px 7px}
.tile-sure{position:absolute;bottom:9px;right:9px;font-size:.55rem;color:var(--g)}
.league-tile.no-matches{opacity:.38;pointer-events:none}
.tier-header{font-size:.56rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t);padding:16px 0 8px;display:flex;align-items:center;gap:8px}
.tier-header::after{content:'';flex:1;height:1px;background:var(--bdr)}

/* FIXTURE ROWS */
.fix-wrap{background:var(--s);border:1px solid var(--bdr);border-radius:16px;overflow:hidden;margin-bottom:8px}
.fix-row{display:flex;align-items:center;padding:12px 14px;border-bottom:1px solid var(--bdr);cursor:pointer;transition:background .15s;gap:10px;text-decoration:none}
.fix-row:last-child{border-bottom:none}
.fix-row:hover,.fix-row:active{background:rgba(255,255,255,.022)}
.fix-time{font-size:.64rem;color:var(--t);font-weight:600;min-width:36px;flex-shrink:0}
.fix-teams{flex:1;min-width:0}
.fix-home,.fix-away{font-size:.78rem;font-weight:700;color:var(--wh);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fix-vs{font-size:.52rem;color:var(--t);margin:1px 0;letter-spacing:1px}
.fix-right{text-align:right;flex-shrink:0}
.fix-tip{font-size:.58rem;font-weight:700;letter-spacing:.5px}
.fix-prob{font-size:.6rem;color:var(--t);margin-top:1px}
.fix-tag{font-size:.5rem;color:var(--t);margin-top:2px}
.fix-live{display:inline-block;width:5px;height:5px;border-radius:50%;background:var(--r);animation:pulse 1.5s infinite;margin-right:3px;vertical-align:middle}

/* MATCH PAGE */
.team-row{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin:10px 0 4px}
.team-name{font-size:1.45rem;font-weight:900;color:var(--wh);line-height:1.1;letter-spacing:-.3px}
.team-name.away{text-align:right}
.vs-pill{flex-shrink:0;background:var(--s2);border:1px solid var(--bdr);border-radius:50px;padding:4px 10px;font-size:.58rem;font-weight:700;color:var(--t);letter-spacing:1px;align-self:center}

/* TIP BOXES */
.rec-box{background:var(--gs);border:1px solid rgba(0,230,118,.16);border-radius:18px;padding:18px;margin-bottom:8px}
.rec-box.suppressed{border-color:rgba(244,67,54,.25);background:rgba(244,67,54,.04)}
.rec-tip-name{font-size:1.55rem;font-weight:900;color:var(--wh);letter-spacing:-.3px;margin:7px 0 5px;line-height:1}
.rec-pct{font-size:2.7rem;font-weight:900;color:var(--g);line-height:1;letter-spacing:-1px}
.rec-pct.suppressed{color:var(--r)}
.rec-reason{font-size:.68rem;color:var(--t2);line-height:1.6;margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,.06)}
.edge-pos{background:rgba(0,230,118,.1);color:var(--g);border:1px solid rgba(0,230,118,.2);display:inline-flex;padding:3px 9px;border-radius:50px;font-size:.58rem;font-weight:700}
.edge-neg{background:rgba(244,67,54,.07);color:var(--r);border:1px solid rgba(244,67,54,.15);display:inline-flex;padding:3px 9px;border-radius:50px;font-size:.58rem;font-weight:700}
.tier-box{border-radius:15px;padding:14px}
.tier-box.safe{background:rgba(79,142,247,.05);border:1px solid rgba(79,142,247,.18)}
.tier-box.risky{background:rgba(255,149,0,.05);border:1px solid rgba(255,149,0,.18)}
.tier-label{font-size:.54rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px}
.tier-tip{font-size:.9rem;font-weight:800;color:var(--wh);line-height:1.2;margin-bottom:6px;min-height:34px}
.tier-pct{font-size:1.65rem;font-weight:900;line-height:1}

/* SIGNALS */
.sig-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:3px}
.sig-on{background:var(--g);box-shadow:0 0 5px rgba(0,230,118,.4)}
.sig-off{background:var(--bdr2)}

/* GRID */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin-bottom:8px}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:8px}
.sbox{background:var(--s2);border:1px solid var(--bdr);border-radius:12px;padding:12px;text-align:center;transition:all .2s}
.sval{font-size:1.55rem;font-weight:800;color:var(--wh);line-height:1}
.sval.g{color:var(--g)}.sval.b{color:var(--b)}.sval.w{color:var(--w)}.sval.r{color:var(--r)}.sval.gold{color:var(--gold)}
.slbl{font-size:.52rem;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);margin-top:4px}

/* MOMENTUM */
.mom-bar{height:6px;background:rgba(255,255,255,.05);border-radius:50px;overflow:hidden;margin:8px 0;position:relative}
.mom-h{position:absolute;left:0;top:0;height:100%;background:linear-gradient(90deg,var(--g),rgba(0,230,118,.4));border-radius:50px}
.mom-a{position:absolute;right:0;top:0;height:100%;background:linear-gradient(270deg,var(--b),rgba(79,142,247,.4));border-radius:50px}

/* CONFIDENCE RING */
.cring{position:relative;width:64px;height:64px;flex-shrink:0}
.cring-num{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:800;color:var(--wh)}

/* H2H */
.h2h-bar{display:flex;height:5px;border-radius:50px;overflow:hidden;margin:10px 0}
.h2h-row{display:flex;align-items:center;padding:7px 0;border-bottom:1px solid var(--bdr);gap:8px}
.h2h-row:last-child{border-bottom:none}
.h2h-date{color:var(--t);min-width:46px;font-size:.58rem;flex-shrink:0}
.h2h-teams{flex:1;color:var(--wh);font-weight:600;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.h2h-score{font-weight:800;color:var(--wh);font-size:.78rem;min-width:28px;text-align:right;flex-shrink:0}

/* LAST MATCHES */
.lm-row{display:flex;align-items:center;padding:7px 0;border-bottom:1px solid var(--bdr);gap:8px}
.lm-row:last-child{border-bottom:none}
.lm-res{width:20px;height:20px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:.55rem;font-weight:700;flex-shrink:0}

/* INJURIES */
.inj-row{display:flex;align-items:center;gap:7px;padding:7px 0;border-bottom:1px solid var(--bdr);font-size:.7rem}
.inj-row:last-child{border-bottom:none}
.inj-dot{width:6px;height:6px;border-radius:50%;background:var(--r);flex-shrink:0}
.inj-dot.susp{background:var(--w)}

/* ANALYST */
.analyst-item{padding:9px 0;border-bottom:1px solid var(--bdr);font-size:.7rem;line-height:1.6;color:var(--t2)}
.analyst-item:last-child{border-bottom:none}
.analyst-item strong{color:var(--wh);font-size:.68rem}

/* RELIABILITY BOX */
.rel-box{border-radius:14px;padding:13px 14px;margin-bottom:8px}
.rel-box.reliable{background:rgba(0,230,118,.05);border:1px solid rgba(0,230,118,.18)}
.rel-box.avoid   {background:rgba(244,67,54,.05);border:1px solid rgba(244,67,54,.22)}
.rel-box.versatile{background:rgba(255,193,7,.05);border:1px solid rgba(255,193,7,.2)}
.rel-box.neutral {background:var(--s2);border:1px solid var(--bdr)}

/* TRACKER PAGE */
.tracker-hero{background:var(--gs);border:1px solid rgba(0,230,118,.14);border-radius:18px;padding:20px;margin-bottom:10px}
.big-stat{font-size:3.2rem;font-weight:900;line-height:1;letter-spacing:-1px}
.streak-box{background:var(--s2);border:1px solid var(--bdr);border-radius:12px;padding:12px;text-align:center}
.perf-row{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--bdr)}
.perf-row:last-child{border-bottom:none}
.result-row{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--bdr);gap:10px}
.result-row:last-child{border-bottom:none}
.result-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.win-chart{display:flex;gap:3px;align-items:flex-end;height:32px;margin-top:8px}
.win-bar{flex:1;border-radius:3px 3px 0 0;min-height:4px;transition:height .4s ease}
.market-pill{display:inline-flex;align-items:center;padding:2px 8px;border-radius:50px;font-size:.6rem;font-weight:700;background:var(--s3);color:var(--t2);border:1px solid var(--bdr)}
.pending-row{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid var(--bdr);font-size:.7rem}
.pending-row:last-child{border-bottom:none}

/* BACK */
.back{display:inline-flex;align-items:center;gap:4px;font-size:.6rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);padding:14px 0 16px;transition:color .2s}
.back:hover{color:var(--wh)}

/* ACCA */
.acca-row{display:flex;justify-content:space-between;align-items:center;padding:13px 14px;border-bottom:1px solid var(--bdr);transition:background .15s;gap:10px}
.acca-row:hover{background:rgba(255,255,255,.02)}
.acca-row:last-child{border-bottom:none}

/* MISC */
.empty{text-align:center;padding:50px 20px;color:var(--t);font-size:.75rem;line-height:1.9}
.info-box{background:var(--s2);border:1px solid var(--bdr);border-radius:12px;padding:12px 14px;font-size:.68rem;line-height:1.7;color:var(--t);margin-bottom:8px}
.count-bubble{display:inline-flex;align-items:center;justify-content:center;min-width:18px;height:18px;border-radius:50px;background:rgba(0,230,118,.12);color:var(--g);font-size:.58rem;font-weight:700;padding:0 5px;border:1px solid rgba(0,230,118,.18)}
.live-badge{display:inline-flex;align-items:center;gap:4px;font-size:.55rem;font-weight:700;letter-spacing:1.2px;padding:3px 8px;border-radius:50px;background:rgba(244,67,54,.12);color:var(--r);border:1px solid rgba(244,67,54,.25);text-transform:uppercase}

/* EXPAND */
.expand-toggle{display:flex;justify-content:space-between;align-items:center;cursor:pointer;padding:12px 0;font-size:.72rem;font-weight:700;color:var(--t2);user-select:none}
.expand-toggle:hover{color:var(--wh)}
.expand-arrow{transition:transform .3s;color:var(--t)}
.expand-arrow.open{transform:rotate(180deg)}
.expand-body{overflow:hidden;max-height:0;transition:max-height .4s ease}
.expand-body.open{max-height:2000px}

@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.75)}}
@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.up{animation:up .3s ease both}
.d1{animation-delay:.04s}.d2{animation-delay:.08s}.d3{animation-delay:.13s}.d4{animation-delay:.18s}
"""

# -- LAYOUT --------------------------------------------------------------------

LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>ProPred NG</title>
<style>""" + CSS + """</style>
</head>
<body>
<nav>
  <div class="nav-i">
    <div class="logo">PRO<span>PRED</span><sub>NG</sub></div>
    <div class="nav-pills">
      <a href="/" class="npill {{ 'on' if page=='home' else '' }}">Leagues</a>
      <a href="/acca" class="npill {{ 'on' if page=='acca' else '' }}">ACCA</a>
      <a href="/tracker" class="npill {{ 'on' if page=='tracker' else '' }}">Track</a>
      <span id="quota-badge" style="font-size:.5rem;color:var(--t);padding:4px 8px;background:var(--s2);border:1px solid var(--bdr);border-radius:50px;display:none"></span>
    </div>
  </div>
</nav>
<div class="shell">{{ content|safe }}</div>
<script>
// Expandable
document.querySelectorAll('.expand-toggle').forEach(el=>{
  el.addEventListener('click',()=>{
    const b=el.nextElementSibling, ar=el.querySelector('.expand-arrow');
    b.classList.toggle('open'); if(ar) ar.classList.toggle('open');
  });
});
// Prob bars animate on scroll
const obs=new IntersectionObserver(entries=>{
  entries.forEach(e=>{if(e.isIntersecting){e.target.style.width=e.target.dataset.w+'%'}});
},{threshold:0.1});
document.querySelectorAll('.pfill').forEach(el=>{
  el.dataset.w=parseFloat(el.style.width)||0;el.style.width='0%';obs.observe(el);
});
// Quota monitor -- shows remaining API calls in nav
fetch('/api/quota').then(r=>r.json()).then(d=>{
  const b=document.getElementById('quota-badge');
  if(b&&d.remaining!==undefined){
    b.textContent=d.remaining+' calls left';
    b.style.display='';
    if(d.remaining<20) b.style.color='var(--r)';
    else if(d.remaining<50) b.style.color='var(--w)';
    else b.style.color='var(--g)';
    b.title='API Football: '+d.used+' used of 100 today. Resets at midnight UTC.';
  }
}).catch(()=>{});
// Search
const si=document.getElementById('ls');
if(si){
  const sc=document.querySelector('.s-clear');
  si.addEventListener('input',function(){
    const q=this.value.toLowerCase();
    sc.classList.toggle('show',q.length>0);
    document.querySelectorAll('.league-tile').forEach(t=>{
      t.style.display=(t.dataset.n||'').includes(q)?'':'none';
    });
    document.querySelectorAll('.tier-header').forEach(h=>{
      const g=h.nextElementSibling;
      if(g&&g.classList.contains('league-grid')){
        const v=[...g.querySelectorAll('.league-tile')].some(t=>t.style.display!=='none');
        h.style.display=v?'':'none'; g.style.display=v?'':'none';
      }
    });
  });
  if(sc) sc.addEventListener('click',()=>{
    si.value=''; sc.classList.remove('show');
    document.querySelectorAll('.league-tile,.tier-header').forEach(e=>e.style.display='');
  });
}
</script>
</body>
</html>"""

# -- HOME ---------------------------------------------------------------------


def _fast_reliability(api_data: dict, res: dict) -> dict:
    """
    Fast reliability check for list views (no enriched data, no API calls).
    Uses only data already in the prediction result and raw API data.
    """
    event   = api_data.get("event", {})
    lg_name = event.get("league", {}).get("name", "")
    h_form  = res.get("form", {}).get("home", [])
    a_form  = res.get("form", {}).get("away", [])
    h_win   = float(api_data.get("prob_home_win", 33))
    a_win   = float(api_data.get("prob_away_win", 33))
    draw    = float(api_data.get("prob_draw", 33))
    rec     = res.get("recommended", {})
    signals = rec.get("agree", 0)
    conv    = rec.get("conv", 0)
    fav     = max(h_win, a_win)

    lg_lower = lg_name.lower()
    is_friendly = "friendly" in lg_lower or "international" in lg_lower
    is_cup      = any(w in lg_lower for w in ["cup","copa","coupe","pokal","carabao"])
    h_slump     = list(h_form[-3:]).count("L") >= 3 if len(h_form) >= 3 else False
    a_slump     = list(a_form[-3:]).count("L") >= 3 if len(a_form) >= 3 else False
    tight       = (max(h_win, draw, a_win) - min(h_win, draw, a_win)) < 8

    if is_friendly:
        return {"tag": "🔄 VERSATILE", "score": 30}
    if h_slump or a_slump:
        return {"tag": "⚠️ AVOID", "score": 35}
    if tight and conv < 45:
        return {"tag": "⚠️ AVOID", "score": 38}
    if is_cup:
        return {"tag": "🔄 VERSATILE", "score": 48}
    if fav >= 65 and signals >= 2 and conv >= 60:
        return {"tag": "✅ RELIABLE", "score": 82}
    if conv >= 55 and signals >= 1:
        return {"tag": "✅ RELIABLE", "score": 70}
    if conv >= 42:
        return {"tag": "SOLID TIP", "score": 58}
    return {"tag": "MONITOR", "score": 42}

@app.route("/")
def index():
    all_matches  = fetch_all_predictions()
    registry     = _LEAGUE_REGISTRY

    # Count matches and sure picks per league
    counts = {}; sure_counts = {}
    for m in all_matches:
        lid = m.get("event",{}).get("league",{}).get("id")
        if lid is not None:
            counts[lid]      = counts.get(lid, 0) + 1
            if _quick_sure(m):
                sure_counts[lid] = sure_counts.get(lid, 0) + 1

    total_fix = len(all_matches)
    total_lg  = len([lid for lid in counts if counts[lid] > 0])

    c  = f'''<div class="up" style="padding:22px 0 14px">
      <p class="eyebrow">Football Intelligence</p>
      <h1 class="title" style="margin-top:5px">LEAGUES</h1>
      <div style="display:flex;gap:12px;margin-top:8px">
        <div><span class="count-bubble">{total_fix}</span>
          <span style="font-size:.62rem;color:var(--t);margin-left:4px">fixtures</span></div>
        <div><span class="count-bubble">{total_lg}</span>
          <span style="font-size:.62rem;color:var(--t);margin-left:4px">leagues</span></div>
      </div>
    </div>'''

    c += '''<div class="search-wrap up d1">
      <span class="s-icon">🔍</span>
      <input id="ls" class="search-input" type="text" placeholder="Search league or country...">
      <span class="s-clear">✕</span>
    </div>'''

    # Build tier lists -- with-matches leagues first, then empty ones
    # Deduplicated with set tracking to avoid any lid appearing twice
    all_ids = sorted(registry.keys(),
        key=lambda lid: (registry[lid].get("tier",3), -counts.get(lid,0)))

    tiers = {1:[], 2:[], 3:[]}
    seen_lids = set()
    # Pass 1: leagues with matches
    for lid in all_ids:
        if counts.get(lid, 0) > 0 and lid not in seen_lids:
            t = registry[lid].get("tier", 3)
            tiers[t].append(lid)
            seen_lids.add(lid)
    # Pass 2: empty leagues (only show if total matches > 20 -- registry is rich)
    if len(seen_lids) > 0:
        for lid in all_ids:
            if lid not in seen_lids:
                t = registry[lid].get("tier", 3)
                tiers[t].append(lid)
                seen_lids.add(lid)

    tier_labels = {1:"⭐ Top Leagues", 2:"🌍 Major Leagues", 3:"🔭 More Leagues"}
    for tier, lids in sorted(tiers.items()):
        if not lids: continue
        c += f'<div class="tier-header up">{tier_labels[tier]}</div>'
        c += '<div class="league-grid">'
        for lid in lids:
            meta  = registry[lid]
            cnt   = counts.get(lid, 0)
            sure  = sure_counts.get(lid, 0)
            no_cls = " no-matches" if cnt == 0 else ""
            cb    = f'<span class="tile-count">{cnt}</span>' if cnt > 0 else ""
            sb    = f'<span class="tile-sure">✅ {sure}</span>' if sure > 0 else ""
            c += f'''<a href="/league/{lid}" class="league-tile{no_cls}"
              data-n="{meta["name"].lower()} {meta["country"].lower()}">
              {cb}{sb}
              <span class="tile-icon">{meta["icon"]}</span>
              <div class="tile-name">{meta["name"]}</div>
              <div class="tile-country">{meta["country"]}</div>
            </a>'''
        c += '</div>'

    return render_template_string(LAYOUT, content=c, page="home")

# -- LEAGUE PAGE ---------------------------------------------------------------

@app.route("/league/<int:l_id>")
def league_page(l_id):
    # Registry-first: get league meta from live data
    _ = fetch_all_predictions()  # ensure registry built
    meta   = _LEAGUE_REGISTRY.get(l_id, {"name":"League","icon":"🌐","country":"","tier":2})
    matches= fetch_league_matches(l_id)
    back   = '<a href="/" class="back"><- Leagues</a>'

    if not matches:
        return render_template_string(LAYOUT,
            content=f'{back}<div class="empty">{meta["icon"]} {meta["name"]}<br><br>No fixtures right now.<br><span style="font-size:.62rem">Check back closer to matchday.</span></div>',
            page="league")

    groups    = group_by_date(matches)
    date_keys = list(groups.keys())
    active    = request.args.get("tab", date_keys[0] if date_keys else "TODAY")

    tabs = '<div class="tabs">'
    for k in date_keys:
        n = len(groups[k])
        tabs += f'<a href="/league/{l_id}?tab={k}" class="tab {"on" if k==active else ""}">{k}<span class="count-bubble" style="margin-left:4px">{n}</span></a>'
    tabs += '</div>'

    rows = '<div class="fix-wrap">'
    for dt, m in groups.get(active, []):
        e    = m.get("event", {})
        h    = e.get("home_team", "?")
        a    = e.get("away_team", "?")
        mid  = m.get("id", 0)
        raw  = e.get("event_timestamp") or e.get("event_date","")
        dt   = parse_dt(raw)
        res  = match_predictor.analyze_match(m, l_id)
        tip  = res["recommended"]["tip"] if res else "--"
        prob = res["recommended"]["prob"] if res else 0
        tc   = tip_color(tip)
        status  = e.get("status","")
        live_dot= '<span class="fix-live"></span>' if status in ("live","inplay","1H","2H","HT") else ""
        # Quick reliability tag for fixture list
        qtag = ""
        if res:
            rtag = res.get("tag","")
            if "AVOID" in rtag:  qtag = '<div class="fix-tag" style="color:var(--r)">⚠️ AVOID</div>'
            elif "RELIABLE" in rtag: qtag = '<div class="fix-tag" style="color:var(--g)">✅ RELIABLE</div>'
            elif "VERSATILE" in rtag: qtag = '<div class="fix-tag" style="color:var(--gold)">🔄 VERSATILE</div>'

        rows += f'''<a href="/match/{mid}" class="fix-row">
          <span class="fix-time">{live_dot}{dt.strftime("%H:%M")}</span>
          <div class="fix-teams">
            <div class="fix-home">{h}</div>
            <div class="fix-vs">VS</div>
            <div class="fix-away">{a}</div>
          </div>
          <div class="fix-right">
            <div class="fix-tip" style="color:{tc}">{tip}</div>
            <div class="fix-prob">{prob}%</div>
            {qtag}
          </div>
        </a>'''
    rows += '</div>'

    c  = back
    c += f'''<div class="up" style="margin-bottom:18px">
      <p class="eyebrow">{meta["icon"]} {meta["country"]}</p>
      <h2 class="title" style="font-size:1.75rem;margin-top:4px">{meta["name"]}</h2>
      <p style="font-size:.6rem;color:var(--t);margin-top:5px">{len(matches)} fixtures * {len(date_keys)} matchday(s)</p>
    </div>'''
    c += tabs + rows
    return render_template_string(LAYOUT, content=c, page="league")

# -- MATCH PAGE ----------------------------------------------------------------

@app.route("/match/<int:match_id>")
def match_display(match_id):
    data = api_get(f"/predictions/{match_id}/")
    if not data:
        return render_template_string(LAYOUT,
            content='<a href="/" class="back"><- Home</a><div class="empty">Match unavailable</div>',
            page="match")

    event   = data.get("event", {})
    league  = event.get("league", {})
    l_id    = league.get("id", 0)
    l_name  = league.get("name", "")
    _ = fetch_all_predictions()
    meta    = _LEAGUE_REGISTRY.get(l_id, {"name":l_name,"icon":"🌐","country":""})
    h       = event.get("home_team","Home")
    a       = event.get("away_team","Away")
    raw_ts  = event.get("event_timestamp") or event.get("event_date","")
    dt      = parse_dt(raw_ts)

    enriched  = external_data.enrich_match(data)
    narrative = external_data.build_analyst_narrative(enriched, h, a)
    res       = match_predictor.analyze_match(data, l_id, enriched)

    if not res:
        return render_template_string(LAYOUT,
            content=f'<a href="/league/{l_id}" class="back"><- {meta["name"]}</a><div class="empty">Analysis unavailable</div>',
            page="match")

    # Reliability engine
    reliability = compute_reliability(data, enriched, res)
    # Override the tag from match_predictor with reliability engine result
    res["tag"] = reliability["tag"]

    # Fetch live odds
    live_odds = get_live_odds(h, a, meta["name"])

    # Log prediction
    try:
        database.log_prediction(
            match_id=match_id, league_id=l_id, league_name=meta["name"],
            home_team=h, away_team=a, match_date=dt.strftime("%Y-%m-%d %H:%M"),
            market=res["recommended"]["tip"],
            probability=res["recommended"]["prob"],
            fair_odds=res["recommended"]["odds"],
            bookie_odds=live_odds.get("home") or live_odds.get("over_25"),
            edge=res["recommended"].get("edge"),
            confidence=res["confidence"],
            xg_home=res["xg_h"], xg_away=res["xg_a"],
            likely_score="",
            tag=reliability["tag"],
            reliability_score=reliability["score"])
    except: pass
    _try_settle(data, match_id)

    rec        = res["recommended"]
    safe       = res["safest"]
    risky_list = res["risky"]
    risky_main = risky_list[0] if risky_list else {"tip":"--","prob":0,"odds":0}
    ox         = res["1x2"]; mkts = res["markets"]
    mom        = res["momentum"]
    h_form_d   = enriched.get("home_form") or res["form"]["home"]
    a_form_d   = enriched.get("away_form") or res["form"]["away"]
    h_inj      = enriched.get("home_injuries",[])
    a_inj      = enriched.get("away_injuries",[])
    h2h_sum    = enriched.get("h2h_summary")
    h_last     = enriched.get("home_last",[])
    a_last     = enriched.get("away_last",[])
    h_stats    = enriched.get("home_stats")
    a_stats    = enriched.get("away_stats")

    conf    = res["confidence"]
    rc      = "#00e676" if conf>=60 else "#4f8ef7" if conf>=45 else "#ff9500"
    r_svg   = 26; cx=cy=33
    circ    = 2*math.pi*r_svg; dash = circ*(conf/100)

    edge     = rec.get("edge")
    edge_html= (f'<span class="edge-pos">+{edge}% edge</span>' if edge and edge>0
                else f'<span class="edge-neg">{edge}% edge</span>' if edge else "")
    total_mom= max(mom["home"]+mom["away"],1)
    mh_w     = round(mom["home"]/total_mom*100)
    ma_w     = round(mom["away"]/total_mom*100)
    agree_html=''.join([f'<span class="sig-dot {"sig-on" if i<rec["agree"] else "sig-off"}"></span>' for i in range(3)])
    suppressed = reliability.get("suppress", False)

    c = f'<a href="/league/{l_id}" class="back"><- {meta["name"]}</a>'

    # -- HEADER --
    c += f'''<div class="up" style="margin-bottom:14px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div style="flex:1;min-width:0">
          {tag_badge(reliability["tag"])}
          <div class="team-row">
            <div class="team-name">{h}</div>
            <div class="vs-pill">VS</div>
            <div class="team-name away">{a}</div>
          </div>
          <p style="font-size:.58rem;color:var(--t);letter-spacing:1px;margin-top:4px">
            {meta["icon"]} {meta["name"]} * {dt.strftime("%-d %b %Y")} * {dt.strftime("%H:%M")} WAT
          </p>
        </div>
        <div class="cring" style="margin-left:10px;margin-top:6px">
          <svg width="64" height="64" viewBox="0 0 66 66">
            <circle cx="{cx}" cy="{cy}" r="{r_svg}" stroke="rgba(255,255,255,.05)" stroke-width="5" fill="none"/>
            <circle cx="{cx}" cy="{cy}" r="{r_svg}" stroke="{rc}" stroke-width="5" fill="none"
              stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-linecap="round"
              transform="rotate(-90 {cx} {cy})"/>
          </svg>
          <div class="cring-num">{conf:.0f}%</div>
        </div>
      </div>
    </div>'''

    # -- RELIABILITY BOX --
    rel_cls = ("reliable" if "RELIABLE" in reliability["tag"] or "SURE" in reliability["tag"]
               else "avoid" if "AVOID" in reliability["tag"]
               else "versatile" if "VERSATILE" in reliability["tag"]
               else "neutral")
    rel_icon = {"reliable":"✅","avoid":"⚠️","versatile":"🔄","neutral":"📊"}[rel_cls]
    c += f'<div class="rel-box {rel_cls} up d1">'
    c += f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
    c += f'<span style="font-size:.62rem;font-weight:700;color:var(--t2)">{rel_icon} {reliability["tag"]}</span>'
    c += f'<span style="font-size:.7rem;font-weight:800;color:var(--wh)">{reliability["score"]}/100</span>'
    c += '</div>'
    c += f'<p style="font-size:.68rem;color:var(--t2);line-height:1.5">{reliability["reason"]}</p>'
    if reliability["flags"]:
        c += f'<p style="font-size:.62rem;color:var(--r);margin-top:5px">⚠ {" * ".join(reliability["flags"][:2])}</p>'
    c += f'''<div style="margin-top:8px">
      <div class="ptrack"><div class="pfill" style="width:{reliability["score"]}%;background:{"var(--g)" if reliability["score"]>=65 else "var(--w)" if reliability["score"]>=45 else "var(--r)"}"></div></div>
    </div></div>'''

    # -- INJURIES --
    if h_inj or a_inj:
        c += '<div class="card up d1" style="border-color:rgba(244,67,54,.2)">'
        c += '<p class="sep" style="padding-top:0;margin-top:0;color:var(--r)">⚠ Injuries & Suspensions</p>'
        for tn, inj_list in [(h, h_inj), (a, a_inj)]:
            if not inj_list: continue
            c += f'<p class="eyebrow" style="margin-bottom:6px">{tn}</p>'
            for inj in inj_list[:4]:
                dc = "inj-dot susp" if "suspend" in inj.get("type","").lower() else "inj-dot"
                c += f'<div class="inj-row"><div class="{dc}"></div><span style="color:var(--wh);font-weight:600">{inj["name"]}</span><span style="margin-left:auto;font-size:.58rem;color:var(--t)">{inj["type"]}</span></div>'
        c += '</div>'

    # -- RECOMMENDED TIP --
    sup_cls = " suppressed" if suppressed else ""
    pct_cls = " suppressed" if suppressed else ""
    if suppressed:
        supp_warning = '<p style="font-size:.66rem;color:var(--r);margin-top:6px;padding:7px 10px;background:rgba(244,67,54,.07);border-radius:8px;border:1px solid rgba(244,67,54,.15)">⚠️ Reliability engine flags this tip -- bet with caution</p>'
    else:
        supp_warning = ""

    # Live odds display
    lo_html = ""
    if live_odds:
        tip_key = {"HOME WIN":"home","AWAY WIN":"away","OVER 2.5":"over_25","GG":"btts_yes"}.get(rec["tip"])
        lo = live_odds.get(tip_key)
        if lo:
            lo_html = f'<span style="font-size:.62rem;color:var(--gold);margin-left:8px">Bet365: {lo}</span>'

    c += f'''<div class="rec-box{sup_cls} up d2">
      <p class="eyebrow">⚡ Recommended Tip</p>
      <p class="rec-tip-name">{rec["tip"]}</p>
      <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:8px">
        <p class="rec-pct{pct_cls}">{rec["prob"]}%</p>
        <div>
          <p style="font-size:.54rem;letter-spacing:1.5px;color:var(--t)">FAIR ODDS</p>
          <p style="font-size:1.3rem;font-weight:800;color:var(--wh)">{rec["odds"]}{lo_html}</p>
        </div>
        {edge_html}
      </div>
      <div style="display:flex;align-items:center;gap:5px;margin-bottom:4px">
        {agree_html}
        <span style="font-size:.58rem;color:var(--t)">{rec["agree"]}/3 signals agree</span>
      </div>
      <p class="rec-reason">{rec["reason"]}</p>
      {supp_warning}
    </div>'''

    # -- SAFE + RISKY --
    safe_odds_str = f'<p style="font-size:.6rem;color:var(--t);margin-top:4px">Fair {safe["odds"]}</p>' if safe.get("odds") else ""
    c += f'''<div class="g2 up d2">
      <div class="tier-box safe">
        <p class="tier-label" style="color:var(--b)">🛡 Safest Bet</p>
        <p class="tier-tip">{safe["tip"]}</p>
        <p class="tier-pct" style="color:var(--b)">{round(safe["prob"],1)}%</p>
        {safe_odds_str}
      </div>
      <div class="tier-box risky">
        <p class="tier-label" style="color:var(--w)">🎯 Risky Market</p>
        <p class="tier-tip">{risky_main["tip"]}</p>
        <p class="tier-pct" style="color:var(--w)">{risky_main["prob"]}%</p>
        <p style="font-size:.6rem;color:var(--t);margin-top:4px">~{risky_main["odds"]} odds</p>
      </div>
    </div>'''

    if len(risky_list) > 1:
        c += '<div class="card up d2" style="padding:0 16px">'
        c += '<div class="expand-toggle"><span>More Combo Markets</span><span class="expand-arrow">▾</span></div>'
        c += '<div class="expand-body">'
        for rk in risky_list[1:]:
            c += f'<div style="display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-top:1px solid var(--bdr)"><span style="font-weight:700;color:var(--wh);font-size:.72rem">{rk["tip"]}</span><span style="color:var(--w);font-weight:700;font-size:.72rem">{rk["prob"]}% * ~{rk["odds"]}</span></div>'
        c += '<div style="height:4px"></div></div></div>'

    # -- xG + Squad Intel --
    si = res.get("squad_intel", {})
    h_sq_score = si.get("home_score", 0)
    a_sq_score = si.get("away_score", 0)
    h_penalty  = si.get("home_penalty", 1.0)
    a_penalty  = si.get("away_penalty", 1.0)
    h_missing  = si.get("home_missing", 0)
    a_missing  = si.get("away_missing", 0)
    # Only show Squad Intelligence card when real player API data was fetched
    # squad_intel defaults to 0/0 so this is False unless batch job ran
    has_squad  = h_sq_score > 0 and a_sq_score > 0 and (
        (enriched.get("home_squad") if enriched else None) is not None or
        (enriched.get("away_squad") if enriched else None) is not None
    )

    c += f'''<div class="g2 up d2">
      <div class="sbox"><p class="sval g">{res["xg_h"]}</p><p class="slbl">xG {h.split()[0]}</p></div>
      <div class="sbox"><p class="sval b">{res["xg_a"]}</p><p class="slbl">xG {a.split()[0]}</p></div>
    </div>'''

    # Squad Strength -- only shown when player data available
    if has_squad:
        h_sq_c = "var(--g)" if h_sq_score>=65 else "var(--w)" if h_sq_score>=45 else "var(--r)"
        a_sq_c = "var(--g)" if a_sq_score>=65 else "var(--w)" if a_sq_score>=45 else "var(--r)"
        h_pen_html = f'<span style="font-size:.55rem;color:var(--r)"> -{round((1-h_penalty)*100)}% xG</span>' if h_penalty < 0.95 else ""
        a_pen_html = f'<span style="font-size:.55rem;color:var(--r)"> -{round((1-a_penalty)*100)}% xG</span>' if a_penalty < 0.95 else ""
        h_miss_html = f'<span style="font-size:.58rem;color:var(--r)">⚠ {h_missing} key out</span>' if h_missing > 0 else ""
        a_miss_html = f'<span style="font-size:.58rem;color:var(--r)">⚠ {a_missing} key out</span>' if a_missing > 0 else ""

        # Top players from squad -- safe None handling
        h_sq_data = enriched.get("home_squad") if enriched else None
        a_sq_data = enriched.get("away_squad") if enriched else None
        h_top = (h_sq_data.get("top_players", []) if isinstance(h_sq_data, dict) else [])
        a_top = (a_sq_data.get("top_players", []) if isinstance(a_sq_data, dict) else [])
        h_tp  = h_top[0] if h_top else None
        a_tp  = a_top[0] if a_top else None

        c += f'''<div class="card up d2">
          <p class="sep" style="padding-top:0;margin-top:0">⚡ Squad Intelligence</p>
          <div class="g2" style="margin-bottom:10px">
            <div>
              <p style="font-size:.64rem;font-weight:700;color:var(--wh);margin-bottom:3px">{h.split()[0]}{h_pen_html}</p>
              <div class="ptrack" style="margin-bottom:4px"><div class="pfill" style="width:{h_sq_score}%;background:{h_sq_c}"></div></div>
              <p style="font-size:.6rem;color:{h_sq_c};font-weight:700">{h_sq_score:.0f}/100 {h_miss_html}</p>
              {f'<p style="font-size:.6rem;color:var(--t);margin-top:3px">★ {h_tp["name"]} {h_tp["rating"]:.1f} * {h_tp["goals"]}G</p>' if h_tp else ""}
            </div>
            <div>
              <p style="font-size:.64rem;font-weight:700;color:var(--wh);margin-bottom:3px;text-align:right">{a.split()[0]}{a_pen_html}</p>
              <div class="ptrack" style="margin-bottom:4px"><div class="pfill" style="width:{a_sq_score}%;background:{a_sq_c}"></div></div>
              <p style="font-size:.6rem;color:{a_sq_c};font-weight:700;text-align:right">{a_sq_score:.0f}/100 {a_miss_html}</p>
              {f'<p style="font-size:.6rem;color:var(--t);margin-top:3px;text-align:right">★ {a_tp["name"]} {a_tp["rating"]:.1f} * {a_tp["goals"]}G</p>' if a_tp else ""}
            </div>
          </div>
        </div>'''  

    # -- ANALYST VIEW --
    has_narr = any(narrative.get(k) for k in ["form","h2h","goals","injuries","morale","squad","top_player"])
    if has_narr:
        c += '<div class="card up d3"><p class="sep" style="padding-top:0;margin-top:0">📋 Analyst View</p>'
        for key, label in [
            ("form","Form"),("morale","Momentum"),("h2h","H2H Pattern"),
            ("goals","Goal Trend"),("squad","Squad Edge"),
            ("top_player","Home Key Man"),("top_player_away","Away Key Man"),
            ("injuries","Absences")
        ]:
            val = narrative.get(key)
            if val:
                c += f'<div class="analyst-item"><strong>{label} * </strong>{val}</div>'
        c += '</div>'

    # -- 1X2 + Goal markets (expandable) --
    c += f'''<div class="card up d3">
      <div class="expand-toggle"><span>1 x 2 Probabilities</span><span class="expand-arrow open">▾</span></div>
      <div class="expand-body open">
        {prob_bar("Home Win", ox["home"])}
        {prob_bar("Draw", ox["draw"], "blue")}
        {prob_bar("Away Win", ox["away"], "orange")}
      </div>
    </div>
    <div class="card up d3">
      <div class="expand-toggle"><span>Goal Markets</span><span class="expand-arrow open">▾</span></div>
      <div class="expand-body open">
        {prob_bar("GG -- Both Score", mkts["gg"])}
        {prob_bar("NG -- Clean Sheet", mkts["ng"], "orange")}
        {prob_bar("Over 1.5", mkts["over_15"])}
        {prob_bar("Over 2.5", mkts["over_25"])}
        {prob_bar("Over 3.5", mkts["over_35"])}
        {prob_bar("Under 2.5", mkts["under_25"], "blue")}
      </div>
    </div>'''

    # -- H2H --
    if h2h_sum and h2h_sum["total"] >= 2:
        n=h2h_sum["total"]; hw=h2h_sum["home_wins"]; dr=h2h_sum["draws"]; aw=h2h_sum["away_wins"]
        hw_w=round(hw/n*100); dr_w=round(dr/n*100); aw_w=round(aw/n*100)
        c += f'<div class="card up d3">'
        c += f'<div class="expand-toggle"><span>Head to Head * Last {n}</span><span class="expand-arrow open">▾</span></div>'
        c += '<div class="expand-body open">'
        c += f'''<div class="g3" style="margin-bottom:10px">
          <div class="sbox"><p class="sval g" style="font-size:1.3rem">{hw}</p><p class="slbl">{h.split()[0]}</p></div>
          <div class="sbox"><p class="sval" style="font-size:1.3rem">{dr}</p><p class="slbl">Draw</p></div>
          <div class="sbox"><p class="sval b" style="font-size:1.3rem">{aw}</p><p class="slbl">{a.split()[0]}</p></div>
        </div>
        <div class="h2h-bar">
          <div style="flex:{hw_w};background:var(--g)"></div>
          <div style="flex:{dr_w};background:var(--t)"></div>
          <div style="flex:{aw_w};background:var(--b)"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:.6rem;margin-bottom:12px;margin-top:4px">
          <span>Avg goals <strong style="color:var(--wh)">{h2h_sum["avg_goals"]}</strong></span>
          <span>O2.5 <strong style="color:var(--wh)">{h2h_sum["over_25_pct"]}%</strong></span>
          <span>GG <strong style="color:var(--wh)">{h2h_sum["btts_pct"]}%</strong></span>
        </div>'''
        for mh in h2h_sum.get("matches",[])[:6]:
            hg=mh.get("home_goals","?"); ag=mh.get("away_goals","?")
            c += f'<div class="h2h-row"><span class="h2h-date">{mh.get("date","")[:7]}</span><span class="h2h-teams">{mh.get("home","?")} vs {mh.get("away","?")}</span><span class="h2h-score">{hg}-{ag}</span></div>'
        c += '</div></div>'

    # -- Last 5 matches per team --
    def last_blk(title, matches, team_name):
        if not matches: return ""
        b = f'<div class="card up d3"><div class="expand-toggle"><span>{title}</span><span class="expand-arrow">▾</span></div><div class="expand-body">'
        for m in matches[:5]:
            hg=m.get("home_goals") or 0; ag=m.get("away_goals") or 0
            is_h = m["home"]==team_name
            r = ("W" if (hg>ag if is_h else ag>hg) else "D" if hg==ag else "L")
            rc2 = {"W":"dot-w","D":"dot-d","L":"dot-l"}[r]
            opp = m["away"] if is_h else m["home"]
            b += f'''<div class="lm-row">
              <div class="lm-res {rc2}">{r}</div>
              <div style="flex:1">
                <div style="font-size:.72rem;font-weight:700;color:var(--wh)">{"vs" if is_h else "@"} {opp}</div>
                <div style="font-size:.58rem;color:var(--t)">{m.get("league","")} * {m.get("date","")}</div>
              </div>
              <span style="font-size:.78rem;font-weight:800;color:var(--wh)">{hg}-{ag}</span>
            </div>'''
        b += '</div></div>'
        return b

    c += last_blk(f"{h} -- Last 5", h_last, h)
    c += last_blk(f"{a} -- Last 5", a_last, a)

    # -- Season stats --
    if h_stats or a_stats:
        c += '<div class="card up d4"><div class="expand-toggle"><span>Season Stats</span><span class="expand-arrow">▾</span></div><div class="expand-body">'
        for tn, st in [(h, h_stats),(a, a_stats)]:
            if not st: continue
            c += f'<p class="eyebrow" style="margin:10px 0 7px">{tn}</p>'
            for lbl, val in [
                ("W / D / L", f'{st.get("wins",0)} / {st.get("draws",0)} / {st.get("losses",0)}'),
                ("Goals scored", f'{st.get("goals_scored",0)} ({st.get("avg_scored",0):.1f}/g)'),
                ("Goals conceded", f'{st.get("goals_conceded",0)} ({st.get("avg_conceded",0):.1f}/g)'),
                ("Clean sheets", st.get("clean_sheets",0)),
            ]:
                c += f'<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--bdr);font-size:.7rem"><span>{lbl}</span><span style="color:var(--wh);font-weight:700">{val}</span></div>'
        c += '</div></div>'

    # -- Form + Momentum --
    c += f'''<div class="card up d4">
      <p class="sep" style="padding-top:0;margin-top:0">Form & Momentum</p>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <span style="font-size:.74rem;font-weight:700;color:var(--wh);flex:1">{h}</span>
        {form_dots(h_form_d)}
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <span style="font-size:.74rem;font-weight:700;color:var(--wh);flex:1">{a}</span>
        {form_dots(a_form_d)}
      </div>
      <div style="display:flex;justify-content:space-between;font-size:.64rem;margin-bottom:5px">
        <span style="color:var(--g)">{h.split()[0]} {mom["home"]}%</span>
        <span style="color:var(--b)">{a.split()[0]} {mom["away"]}%</span>
      </div>
      <div class="mom-bar">
        <div class="mom-h" style="width:{mh_w}%"></div>
        <div class="mom-a" style="width:{ma_w}%"></div>
      </div>
      <p style="font-size:.66rem;color:var(--t2);margin-top:8px;line-height:1.5">{mom["narrative"]}</p>
      <p style="font-size:.63rem;color:var(--t);margin-top:5px;line-height:1.5">{res["style"]}</p>
    </div>'''

    return render_template_string(LAYOUT, content=c, page="match")

# -- ACCA ----------------------------------------------------------------------

@app.route("/acca")
def acca():
    all_matches = fetch_all_predictions()
    # ACCA only uses TODAY + TOMORROW fixtures -- never future dates or stale matches
    today_wat    = now_wat().date()
    tomorrow_wat = today_wat + timedelta(days=1)
    acca_matches = []
    for m in all_matches:
        e   = m.get("event", {})
        raw = e.get("event_timestamp") or e.get("event_date", "")
        dt  = parse_dt(raw)
        d   = dt.date()
        if d == today_wat or d == tomorrow_wat:
            acca_matches.append(m)
    picks, combined = match_predictor.pick_acca(acca_matches, n=5, min_conv=42.0)

    c = '<div style="padding:22px 0 14px" class="up"><p class="eyebrow">Daily Best Picks</p><h1 class="title" style="margin-top:5px">ACCA</h1></div>'
    if not picks:
        c += '<div class="empty">No qualifying ACCA picks today.<br><span style="font-size:.62rem">All tips must meet minimum odds (1.25) and reliability standards.</span></div>'
        return render_template_string(LAYOUT, content=c, page="acca")

    c += '<div class="fix-wrap up d1">'
    for p in picks:
        e    = p["match"].get("event",{})
        h, a = e.get("home_team","?"), e.get("away_team","?")
        res  = p["result"]; mid = p["match"].get("id",0)
        meta = _LEAGUE_REGISTRY.get(p["league_id"], {"icon":"🌐","name":"--"})
        rec  = res["recommended"]
        edge = rec.get("edge")
        tc   = tip_color(rec["tip"])
        rtag = res.get("tag","")
        tag_html = ""
        if "RELIABLE" in rtag: tag_html = '<span style="font-size:.52rem;color:var(--g)">✅ RELIABLE</span>'
        elif "AVOID" in rtag:  tag_html = '<span style="font-size:.52rem;color:var(--r)">⚠️ AVOID</span>'
        c += f'''<a href="/match/{mid}" class="acca-row">
          <div style="flex:1;min-width:0">
            <p style="font-size:.56rem;color:var(--t);letter-spacing:1px;text-transform:uppercase;margin-bottom:2px">{meta["icon"]} {meta["name"]}</p>
            <p style="font-size:.8rem;font-weight:700;color:var(--wh)">{h} vs {a}</p>
            <p style="font-size:.62rem;margin-top:2px">
              <span style="color:{tc};font-weight:700">{rec["tip"]}</span>
              <span style="color:var(--t)"> * {rec["prob"]}%{"  +"+str(edge)+"% edge" if edge and edge>0 else ""}</span>
              {tag_html}
            </p>
            <p style="font-size:.6rem;color:var(--t);margin-top:2px;line-height:1.4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{rec["reason"][:68]}{"..." if len(rec["reason"])>68 else ""}</p>
          </div>
          <div style="text-align:right;flex-shrink:0;margin-left:10px">
            <p style="font-size:1.35rem;font-weight:900;color:var(--g)">{rec["odds"]}</p>
            <p style="font-size:.55rem;color:var(--t)">fair odds</p>
          </div>
        </a>'''
    c += '</div>'

    c += f'''<div class="tracker-hero up d2" style="text-align:center;margin-top:10px">
      <p class="eyebrow">Combined Fair Odds</p>
      <p class="big-stat" style="color:var(--g);margin:8px 0">{combined}</p>
      <p style="font-size:.58rem;color:var(--t);letter-spacing:1px">{len(picks)}-FOLD ACCUMULATOR * Min odds 1.25 per leg</p>
    </div>
    <p style="font-size:.56rem;color:var(--t);text-align:center;padding:14px;letter-spacing:.8px">Fair model odds shown. Verify with your bookmaker. Bet responsibly.</p>'''
    return render_template_string(LAYOUT, content=c, page="acca")

# -- TRACKER -------------------------------------------------------------------

@app.route("/tracker")
def tracker():
    stats  = database.get_tracker_stats()
    total  = stats["total"]; wins = stats["wins"]; losses = stats["losses"]
    hr     = stats["hit_rate"]; pending = stats["pending"]
    streak = stats["streak"]; roi = stats["roi"]
    whr    = stats["week_hit_rate"]; wtotal = stats["week_total"]
    hr_c   = "var(--g)" if hr>=60 else "var(--w)" if hr>=50 else "var(--r)"
    whr_c  = "var(--g)" if whr>=60 else "var(--w)" if whr>=50 else "var(--r)"
    roi_c  = "var(--g)" if roi>=0 else "var(--r)"

    c = '<div style="padding:22px 0 14px" class="up"><p class="eyebrow">Model Performance</p><h1 class="title" style="margin-top:5px">TRACKER</h1></div>'

    # -- Empty state -- shown when no real predictions logged yet --
    if total == 0:
        c += '''<div style="background:var(--s);border:1px solid var(--bdr);border-radius:18px;padding:28px 20px;text-align:center;margin-top:8px">
          <div style="font-size:2rem;margin-bottom:12px">📊</div>
          <p style="font-size:.85rem;font-weight:800;color:var(--wh);margin-bottom:8px">No Results Yet</p>
          <p style="font-size:.7rem;color:var(--t);line-height:1.8;max-width:280px;margin:0 auto">
            The Tracker only shows predictions this model has actually made.<br><br>
            Browse any match page and the prediction gets logged automatically.
            Once that match finishes, the result settles here with a WIN or LOSS.
          </p>
          <div style="margin-top:18px;padding-top:16px;border-top:1px solid var(--bdr)">
            <a href="/" style="display:inline-flex;align-items:center;gap:6px;font-size:.65rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--g);padding:10px 20px;border:1px solid rgba(0,230,118,.25);border-radius:50px">Browse Leagues -></a>
          </div>
        </div>'''
        return render_template_string(LAYOUT, content=c, page="tracker")

    # -- Hero stats --
    c += f'''<div class="tracker-hero up d1">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <div>
          <p class="eyebrow" style="margin-bottom:4px">Overall Hit Rate</p>
          <p class="big-stat" style="color:{hr_c}">{hr}%</p>
          <p style="font-size:.6rem;color:var(--t);margin-top:3px">{total} settled tips</p>
        </div>
        <div style="text-align:right">
          <p class="eyebrow" style="margin-bottom:4px">This Week</p>
          <p style="font-size:1.8rem;font-weight:900;color:{whr_c};line-height:1">{whr}%</p>
          <p style="font-size:.6rem;color:var(--t);margin-top:3px">{wtotal} tips</p>
        </div>
      </div>
      <div class="ptrack" style="margin-bottom:14px">
        <div class="pfill" style="width:{hr}%;background:{hr_c}"></div>
      </div>
      <div class="g4">
        <div class="sbox" style="padding:10px 6px">
          <p class="sval g" style="font-size:1.3rem">{wins}</p><p class="slbl">Wins</p>
        </div>
        <div class="sbox" style="padding:10px 6px">
          <p class="sval r" style="font-size:1.3rem">{losses}</p><p class="slbl">Losses</p>
        </div>
        <div class="sbox" style="padding:10px 6px">
          <p class="sval" style="font-size:1.3rem;color:{roi_c}">{roi:+.1f}%</p><p class="slbl">ROI</p>
        </div>
        <div class="sbox" style="padding:10px 6px">
          <p class="sval w" style="font-size:1.3rem">{pending}</p><p class="slbl">Open</p>
        </div>
      </div>
    </div>'''

    # -- Streak --
    if streak["count"] > 0:
        sc   = "var(--g)" if streak["type"]=="WIN" else "var(--r)"
        sico = "🔥" if streak["type"]=="WIN" else "❄️"
        c += f'''<div class="streak-box up d1" style="margin-bottom:8px">
          <p style="font-size:.56rem;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);margin-bottom:5px">{sico} Current Streak</p>
          <p style="font-size:1.6rem;font-weight:900;color:{sc};line-height:1">{streak["count"]} {streak["type"]}{"S" if streak["count"]>1 else ""} in a row</p>
        </div>'''

    # -- Last 10 visual bar chart --
    last10 = stats["recent"][:10]
    if last10:
        c += '<div class="card up d2"><p class="sep" style="padding-top:0;margin-top:0">Last 10 Results</p>'
        c += '<div style="display:flex;gap:4px;margin-bottom:12px">'
        for r in reversed(last10):
            col = "var(--g)" if r["result"]=="WIN" else "var(--r)"
            icon = "✓" if r["result"]=="WIN" else "✗"
            c += f'<div style="flex:1;background:{col};border-radius:5px;padding:7px 2px;text-align:center;font-size:.58rem;font-weight:700;color:#000">{icon}</div>'
        c += '</div>'
        w10 = sum(1 for r in last10 if r["result"]=="WIN")
        c += f'<p style="font-size:.65rem;color:var(--t2);text-align:center">{w10}/10 in last 10 * <span style="color:{"var(--g)" if w10>=6 else "var(--w)" if w10>=5 else "var(--r)"}">{"Strong form 🔥" if w10>=7 else "Good form" if w10>=6 else "Average form" if w10>=5 else "Struggling ❄️"}</span></p>'
        c += '</div>'

    # -- By market --
    if stats["by_market"]:
        c += '<div class="card up d2"><p class="sep" style="padding-top:0;margin-top:0">Performance by Market</p>'
        for row in stats["by_market"]:
            mhr  = round(row["wins"]/row["total"]*100,1) if row["total"] else 0
            mhrc = "var(--g)" if mhr>=60 else "var(--w)" if mhr>=50 else "var(--r)"
            bar_w= round(mhr)
            c += f'''<div class="perf-row">
              <div style="flex:1">
                <p style="font-weight:700;color:var(--wh);font-size:.72rem">{row["market"]}</p>
                <div style="display:flex;align-items:center;gap:6px;margin-top:4px">
                  <div class="ptrack" style="flex:1;height:3px">
                    <div class="pfill" style="width:{bar_w}%;background:{mhrc}"></div>
                  </div>
                  <span style="font-size:.6rem;color:var(--t)">{row["total"]} tips</span>
                </div>
              </div>
              <p style="font-size:1.3rem;font-weight:900;color:{mhrc};margin-left:12px">{mhr}%</p>
            </div>'''
        c += '</div>'

    # -- By league --
    if stats["by_league"]:
        c += '<div class="card up d3"><p class="sep" style="padding-top:0;margin-top:0">Performance by League</p>'
        for row in stats["by_league"]:
            lhr  = round(row["wins"]/row["total"]*100,1) if row["total"] else 0
            lhrc = "var(--g)" if lhr>=60 else "var(--w)" if lhr>=50 else "var(--r)"
            lg_meta = _lookup_league_meta(row["league_name"])
            c += f'<div class="perf-row"><div><p style="font-weight:700;color:var(--wh);font-size:.72rem">{lg_meta["icon"]} {row["league_name"]}</p><p style="font-size:.6rem;color:var(--t)">{row["total"]} tips settled</p></div><p style="font-size:1.1rem;font-weight:900;color:{lhrc}">{lhr}%</p></div>'
        c += '</div>'

    # -- Recent results full list --
    if stats["recent"]:
        c += '<div class="card up d3"><p class="sep" style="padding-top:0;margin-top:0">Recent Results</p>'
        for row in stats["recent"]:
            hs  = row.get("actual_home_score"); as_ = row.get("actual_away_score")
            sc  = f"{hs}-{as_}" if hs is not None else "--"
            res_col = "var(--g)" if row["result"]=="WIN" else "var(--r)"
            dot_col = "var(--g)" if row["result"]=="WIN" else "var(--r)"
            c += f'''<div class="result-row">
              <div class="result-dot" style="background:{dot_col}"></div>
              <div style="flex:1;min-width:0">
                <p style="font-weight:700;color:var(--wh);font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{row["home_team"]} vs {row["away_team"]}</p>
                <p style="font-size:.6rem;color:var(--t);margin-top:1px">{row["market"]} * {round(row["probability"],1)}% * {row["league_name"]}</p>
              </div>
              <div style="text-align:right;flex-shrink:0;margin-left:8px">
                <p style="font-size:.7rem;font-weight:800;color:{res_col}">{row["result"]}</p>
                <p style="font-size:.6rem;color:var(--t)">{sc}</p>
              </div>
            </div>'''
        c += '</div>'

    # -- Pending tips --
    if stats["pending_rows"]:
        c += '<div class="card up d4"><p class="sep" style="padding-top:0;margin-top:0">⏳ Awaiting Results</p>'
        for row in stats["pending_rows"]:
            c += f'''<div class="pending-row">
              <div style="flex:1;min-width:0">
                <p style="font-weight:700;color:var(--wh);font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{row["home_team"]} vs {row["away_team"]}</p>
                <p style="font-size:.6rem;color:var(--t)">{row["market"]} * {round(row["probability"],1)}% * {row["league_name"]}</p>
              </div>
              <div style="text-align:right;flex-shrink:0">
                <p style="font-size:.62rem;font-weight:700;color:var(--gold)">{round(row["fair_odds"],2)} odds</p>
                <p style="font-size:.58rem;color:var(--t)">{row["match_date"][:10]}</p>
              </div>
            </div>'''
        c += '</div>'

    return render_template_string(LAYOUT, content=c, page="tracker")

# -- API -----------------------------------------------------------------------

@app.route("/api/counts")
def api_counts():
    all_matches = fetch_all_predictions()
    counts = {}
    for m in all_matches:
        lid = m.get("event",{}).get("league",{}).get("id")
        if lid is not None:
            counts[str(lid)] = counts.get(str(lid), 0) + 1
    return jsonify(counts)

@app.route("/api/leagues")
def api_leagues():
    fetch_all_predictions()
    return jsonify(_LEAGUE_REGISTRY)


# -- BATCH JOB + QUOTA MONITOR -------------------------------------------------

@app.route("/api/batch")
def api_batch():
    """
    Pre-fetch squad stats for all teams playing today.
    Call this once per day (e.g. via cron or Render scheduled job at 6am WAT).
    Safe to call multiple times -- skips teams already in 24h cache.
    """
    import external_data as ed
    all_matches = fetch_all_predictions()
    today_wat    = now_wat().date()
    tomorrow_wat = today_wat + timedelta(days=1)
    today_matches = [
        m for m in all_matches
        if parse_dt(m.get("event",{}).get("event_timestamp") or
                    m.get("event",{}).get("event_date","")).date() in (today_wat, tomorrow_wat)
    ]
    result = ed.run_daily_batch(today_matches)
    quota  = ed.get_quota_status()
    return jsonify({
        "status":       "ok",
        "today_matches": len(today_matches),
        "calls_made":   result["calls_made"],
        "calls_skipped":result["calls_skipped"],
        "quota":        quota,
    })

@app.route("/api/quota")
def api_quota():
    import external_data as ed
    return jsonify(ed.get_quota_status())

# -- UTILITIES -----------------------------------------------------------------

def _try_settle(api_data, match_id):
    try:
        event  = api_data.get("event", {})
        status = str(event.get("status","")).lower()
        hs = event.get("home_score"); as_ = event.get("away_score")
        if status in ("finished","ft","fulltime") and hs is not None and as_ is not None:
            for p in database.get_recent_pending():
                if p["match_id"] == match_id:
                    database.settle_prediction(match_id, p["market"], int(hs), int(as_))
    except Exception as e:
        print(f"[settle] {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
