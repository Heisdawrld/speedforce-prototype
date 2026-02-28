"""
data.py -- Unified Data Layer v2
API-Football  : fixtures (1 call/day cached), form, H2H, lineups, events, stats
football-data : standings (free, unlimited)
The Odds API  : sharp bookmaker odds (2hr cache)
Sportmonks    : AI predictions, xG, value bets (6hr cache)

Quota rules:
  API-Football 100/day -> 1 call per date (gets ALL leagues at once)
  Everything else cached aggressively to SQLite
"""

import os, json, math, requests
from datetime import datetime, timezone, timedelta
import database

# ── KEYS ──────────────────────────────────────────────────────────────────────
AFL_KEY  = os.environ.get("APIFOOTBALL_KEY",  "d1d7aaea599eb42ce6a723c2935ee70e")
FD_KEY   = os.environ.get("FDORG_KEY",        "9f4755094ff9435695b794f91f4c1474")
ODDS_KEY = os.environ.get("ODDS_API_KEY",     "f40efeabae93fc096daa59c7e2ab6fc2")
SM_TOK   = os.environ.get("SPORTMONKS_TOKEN", "EbRqkfYJgeCOtHzoC1AXpk1OO4semN0DtJ1P84zrYVNRCT1x4dHVsP9FGJAV")

AFL_URL  = "https://v3.football.api-sports.io"
FD_URL   = "https://api.football-data.org/v4"
ODDS_URL = "https://api.the-odds-api.com/v4"
SM_URL   = "https://api.sportmonks.com/v3/football"

WAT = 1  # UTC+1 Nigeria

def _current_season():
    n = datetime.now(timezone.utc)
    return n.year - 1 if n.month < 7 else n.year

# ── MEMORY CACHE ──────────────────────────────────────────────────────────────
_mem = {}
def _mg(k, h):
    e = _mem.get(k)
    if not e: return None
    return e[1] if (datetime.now(timezone.utc)-e[0]).total_seconds() < h*3600 else None
def _ms(k, v): _mem[k] = (datetime.now(timezone.utc), v)

# ── HTTP CALLERS ───────────────────────────────────────────────────────────────
def _afl(path, params=None, ch=1):
    p  = params or {}
    ck = ("A"+path+json.dumps(sorted(p.items())))[:190]
    v  = _mg(ck, ch)
    if v is not None: return v
    c  = database.cache_get("h2h_cache", ck, max_age_hours=ch)
    if c:
        try: v=json.loads(c); _ms(ck,v); return v
        except: pass
    try:
        r = requests.get(AFL_URL+path,
            headers={"x-rapidapi-key":AFL_KEY,"x-rapidapi-host":"v3.football.api-sports.io"},
            params=p, timeout=13)
        if r.status_code == 429: print("[AFL] RATE LIMITED"); return None
        if r.status_code != 200: print(f"[AFL]{path} {r.status_code}"); return None
        v = r.json().get("response", [])
        _ms(ck,v); database.cache_set("h2h_cache", ck, json.dumps(v))
        return v
    except Exception as e: print(f"[AFL]{path} {e}"); return None

def _fd(path, params=None, ch=6):
    p  = params or {}
    ck = ("F"+path+json.dumps(sorted(p.items())))[:190]
    v  = _mg(ck, ch)
    if v is not None: return v
    c  = database.cache_get("h2h_cache", ck, max_age_hours=ch)
    if c:
        try: v=json.loads(c); _ms(ck,v); return v
        except: pass
    try:
        r = requests.get(FD_URL+path, headers={"X-Auth-Token":FD_KEY},
                         params=p, timeout=13)
        if r.status_code != 200: print(f"[FD]{path} {r.status_code}"); return None
        v = r.json()
        _ms(ck,v); database.cache_set("h2h_cache", ck, json.dumps(v))
        return v
    except Exception as e: print(f"[FD]{path} {e}"); return None

def _sm(path, params=None, ch=6):
    p  = params or {}
    ck = ("S"+path+json.dumps(sorted(p.items())))[:190]
    v  = _mg(ck, ch)
    if v is not None: return v
    c  = database.cache_get("h2h_cache", ck, max_age_hours=ch)
    if c:
        try: v=json.loads(c); _ms(ck,v); return v
        except: pass
    try:
        r = requests.get(SM_URL+path, headers={"Authorization":SM_TOK},
                         params=p, timeout=13)
        if r.status_code != 200: print(f"[SM]{path} {r.status_code} {r.text[:60]}"); return None
        v = r.json().get("data")
        if v is not None:
            _ms(ck,v); database.cache_set("h2h_cache", ck, json.dumps(v))
        return v
    except Exception as e: print(f"[SM]{path} {e}"); return None

def _odds(ch=2):
    ck = "ODDS_ALL"
    v  = _mg(ck, ch)
    if v is not None: return v
    c  = database.cache_get("h2h_cache", ck, max_age_hours=ch)
    if c:
        try: v=json.loads(c); _ms(ck,v); return v
        except: pass
    if not ODDS_KEY: return []
    try:
        r = requests.get(f"{ODDS_URL}/sports/soccer/odds/",
            params={"apiKey":ODDS_KEY,"regions":"uk,eu",
                    "markets":"h2h,totals","oddsFormat":"decimal"},
            timeout=13)
        if r.status_code != 200: print(f"[ODDS]{r.status_code}"); return []
        v = r.json() if isinstance(r.json(), list) else []
        _ms(ck,v); database.cache_set("h2h_cache", ck, json.dumps(v))
        return v
    except Exception as e: print(f"[ODDS]{e}"); return []

# ── LEAGUE LIST (API-Football IDs) ────────────────────────────────────────────
LEAGUES = {
    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    78,   # Bundesliga
    61,   # Ligue 1
    2,    # Champions League
    3,    # Europa League
    848,  # Conference League
    88,   # Eredivisie
    94,   # Primeira Liga
    203,  # Super Lig
    179,  # Scottish Prem
    144,  # Belgian Pro League
    40,   # Championship
    41,   # League One
    197,  # Greek Super League
    106,  # Ekstraklasa
    113,  # Allsvenskan
    103,  # Eliteserien
    271,  # Danish Superliga
    207,  # Romanian Liga 1
    218,  # Austrian Bundesliga
    283,  # Czech Liga
    253,  # MLS
    262,  # Liga MX
    71,   # Brasileirao
    128,  # Argentine Primera
    307,  # Saudi Pro League
    98,   # J1 League
    233,  # Egyptian Premier League
    235,  # Russian Premier League
    332,  # Ukrainian Premier League
    323,  # South African PSL
}

# football-data.org competition codes
FD_CODES = {
    39:"PL", 140:"PD", 135:"SA", 78:"BL1", 61:"FL1",
    2:"CL", 3:"EL", 40:"ELC", 88:"DED", 94:"PPL",
}

# ── PARSE HELPER ──────────────────────────────────────────────────────────────
def _dt(raw):
    if not raw: return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z","+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except: return datetime.now(timezone.utc)

def _parse(raw):
    fx  = raw.get("fixture",{})
    lg  = raw.get("league",{})
    ht  = raw.get("teams",{}).get("home",{})
    at  = raw.get("teams",{}).get("away",{})
    gs  = raw.get("goals",{})
    st  = fx.get("status",{})
    ss  = st.get("short","NS")
    el  = st.get("elapsed")
    live = ss in ("1H","HT","2H","ET","BT","P","INT")
    ft   = ss in ("FT","AET","PEN")
    sh   = gs.get("home") if (live or ft) else None
    sa   = gs.get("away") if (live or ft) else None
    ko   = fx.get("date","")
    kod  = _dt(ko)
    tod  = (datetime.now(timezone.utc)+timedelta(hours=WAT)).date()
    tmr  = tod+timedelta(days=1)
    if kod.date()==tod:  dl="TODAY"
    elif kod.date()==tmr: dl="TOMORROW"
    else:                dl=kod.strftime("%a %d %b").lstrip("0").upper()
    return {
        "id":       fx.get("id"),
        "home_id":  ht.get("id"),   "home":   ht.get("name","Home"),
        "away_id":  at.get("id"),   "away":   at.get("name","Away"),
        "league_id":lg.get("id",0), "league": lg.get("name",""),
        "country":  lg.get("country",""),
        "season":   lg.get("season") or (datetime.now(timezone.utc).year - 1 if datetime.now(timezone.utc).month < 7 else datetime.now(timezone.utc).year),
        "kickoff":  ko,
        "date_label":dl,
        "state":    f"{el}'" if live and el else ("FT" if ft else "NS"),
        "is_live":  live, "is_ft": ft, "is_ns": not live and not ft,
        "score_h":  sh,   "score_a": sa,
        "venue":    fx.get("venue",{}).get("name",""),
        "referee":  fx.get("referee"),
        "_raw":     raw,
    }

# ── FIXTURES ──────────────────────────────────────────────────────────────────
def fixtures_for_date(date_str):
    """ONE API-Football call per date. Falls back to football-data.org if needed."""
    ck = f"date_{date_str}"
    v  = _mg(ck, 0.5)
    if v is not None: return v
    c  = database.cache_get("h2h_cache", ck, max_age_hours=0.5)
    if c:
        try: v=json.loads(c); _ms(ck,v); return v
        except: pass
    # Try API-Football first
    raw = _afl("/fixtures", {"date":date_str,"timezone":"Africa/Lagos"}, ch=0.5)
    if raw is not None:
        result = [_parse(r) for r in raw if r.get("league",{}).get("id") in LEAGUES]
        print(f"[data] AFL {date_str}: {len(raw)} raw -> {len(result)} matched")
        if result:
            _ms(ck, result); database.cache_set("h2h_cache", ck, json.dumps(result))
            return result
        if raw:
            ids = list(set(r.get("league",{}).get("id") for r in raw[:20]))
            print(f"[data] AFL returned fixtures but none matched our LEAGUES set. Sample IDs: {ids}")
    else:
        print(f"[data] API-Football returned None for {date_str} (rate limit or key issue)")
    # Fallback to football-data.org
    print(f"[data] Falling back to football-data.org for {date_str}")
    result = _fd_fixtures_for_date(date_str)
    if result:
        _ms(ck, result); database.cache_set("h2h_cache", ck, json.dumps(result))
    return result


def _fd_fixtures_for_date(date_str):
    """Fallback using football-data.org (free tier, no daily call limit)."""
    CURRENT_SEASON = datetime.now(timezone.utc).year - 1 if datetime.now(timezone.utc).month < 7 else datetime.now(timezone.utc).year
    result = []; seen = set()
    for lg_id, code in FD_CODES.items():
        try:
            data = _fd(f"/competitions/{code}/matches", {"dateFrom":date_str,"dateTo":date_str}, ch=1)
            if not data: continue
            matches = data.get("matches", [])
            lg_name = data.get("competition",{}).get("name","")
            country = data.get("competition",{}).get("area",{}).get("name","")
            s_raw = data.get("season",{}).get("startDate","")
            try: season_yr = int(s_raw[:4])
            except: season_yr = CURRENT_SEASON
            for m in matches:
                fid = m.get("id")
                if not fid or fid in seen: continue
                seen.add(fid)
                ss = m.get("status","SCHEDULED")
                live = ss in ("IN_PLAY","PAUSED","HALF_TIME")
                ft   = ss in ("FINISHED","AWARDED")
                score = m.get("score",{})
                sh = (score.get("fullTime",{}) or {}).get("home")
                sa = (score.get("fullTime",{}) or {}).get("away")
                h_team = m.get("homeTeam",{}); a_team = m.get("awayTeam",{})
                ko = m.get("utcDate","")
                kod = _dt(ko)
                tod = (datetime.now(timezone.utc)+timedelta(hours=WAT)).date()
                tmr = tod+timedelta(days=1)
                if kod.date()==tod:  dl="TODAY"
                elif kod.date()==tmr: dl="TOMORROW"
                else: dl=kod.strftime("%a %d %b").lstrip("0").upper()
                result.append({
                    "id": fid, "home_id": h_team.get("id"), "home": h_team.get("name","Home"),
                    "away_id": a_team.get("id"), "away": a_team.get("name","Away"),
                    "league_id": lg_id, "league": lg_name, "country": country,
                    "season": season_yr, "kickoff": ko, "date_label": dl,
                    "state": "LIVE" if live else ("FT" if ft else "NS"),
                    "is_live": live, "is_ft": ft, "is_ns": not live and not ft,
                    "score_h": sh, "score_a": sa, "venue": "", "referee": None, "_raw": m,
                })
        except Exception as e:
            print(f"[FD_fallback] {code}: {e}")
    print(f"[data] FD fallback: {len(result)} fixtures for {date_str}")
    return result

def get_fixtures_window(days=3):
    """Fixtures for today + next N days (WAT timezone)."""
    wat_now = datetime.now(timezone.utc) + timedelta(hours=WAT)
    ck = f"win_{days}_{wat_now.strftime('%Y-%m-%d')}"
    v  = _mg(ck, 0.4)
    if v is not None: return v
    all_fx = []; seen = set()
    for i in range(days):
        d = (wat_now + timedelta(days=i)).strftime("%Y-%m-%d")
        for fx in fixtures_for_date(d):
            if fx["id"] and fx["id"] not in seen:
                seen.add(fx["id"]); all_fx.append(fx)
    all_fx.sort(key=lambda f: f["kickoff"] or "")
    _ms(ck, all_fx)
    return all_fx

def get_live_fixtures():
    raw = _afl("/fixtures", {"live":"all"}, ch=0.08) or []
    return [_parse(r) for r in raw if r.get("league",{}).get("id") in LEAGUES]

def get_fixture_by_id(fid):
    raw = _afl("/fixtures", {"id":fid}, ch=0.25)
    return raw[0] if raw else None

# ── FORM ──────────────────────────────────────────────────────────────────────
def get_form(team_id, league_id, season=None, last=6):
    if season is None: season = _current_season()
    raw = _afl("/fixtures",
        {"team":team_id,"league":league_id,"season":season,"last":last,"status":"FT"},
        ch=3)
    if not raw: return []
    form = []
    for fx in raw:
        ht = fx.get("teams",{}).get("home",{}); at = fx.get("teams",{}).get("away",{})
        gs = fx.get("goals",{})
        hg = gs.get("home",0) or 0; ag = gs.get("away",0) or 0
        if ht.get("id") == team_id:
            form.append("W" if hg>ag else "D" if hg==ag else "L")
        else:
            form.append("W" if ag>hg else "D" if ag==hg else "L")
    return form

# ── H2H ───────────────────────────────────────────────────────────────────────
def get_h2h(h_id, a_id, last=10):
    raw = _afl("/fixtures/headtohead",
        {"h2h":f"{h_id}-{a_id}","last":last,"status":"FT"}, ch=24)
    if not raw: return {}
    n = len(raw); hw=dr=aw=tg=o25=bt=0
    for fx in raw:
        gs=fx.get("goals",{}); hg=gs.get("home",0)or 0; ag=gs.get("away",0)or 0
        tg+=hg+ag
        if hg+ag>2: o25+=1
        if hg>0 and ag>0: bt+=1
        hid=fx.get("teams",{}).get("home",{}).get("id")
        if hg>ag: (hw:=hw+1) if hid==h_id else (aw:=aw+1)
        elif hg==ag: dr+=1
        else: (aw:=aw+1) if hid==h_id else (hw:=hw+1)
    return {"total":n,"home_wins":hw,"draws":dr,"away_wins":aw,
            "avg_goals":round(tg/n,2),"over_25_pct":round(o25/n*100),
            "btts_pct":round(bt/n*100)}

# ── STANDINGS ─────────────────────────────────────────────────────────────────
def get_standings(league_id, season=None):
    if season is None: season = _current_season()
    comp = FD_CODES.get(league_id)
    if not comp: return {}
    data = _fd(f"/competitions/{comp}/standings", {"season":season}, ch=6)
    if not data: return {}
    out = {}
    try:
        for tbl in data.get("standings",[]):
            if tbl.get("type")=="TOTAL":
                for row in tbl.get("table",[]):
                    tid=row.get("team",{}).get("id")
                    nm =row.get("team",{}).get("name","")
                    pos=row.get("position")
                    if tid: out[tid]=pos
                    if nm:  out[nm]=pos
    except: pass
    return out

# ── LINEUPS ───────────────────────────────────────────────────────────────────
def get_lineups(fid):
    raw = _afl("/fixtures/lineups", {"fixture":fid}, ch=1)
    if not raw: return [], []
    def parse(team_data):
        return [{"name":p.get("player",{}).get("name",""),
                 "number":p.get("player",{}).get("number"),
                 "pos":p.get("player",{}).get("pos","")}
                for p in team_data.get("startXI",[])]
    return parse(raw[0]) if raw else [], parse(raw[1]) if len(raw)>1 else []

# ── EVENTS ────────────────────────────────────────────────────────────────────
def get_events(fid):
    raw = _afl("/fixtures/events", {"fixture":fid}, ch=0.25)
    if not raw: return {"goals":[],"cards":[]}
    goals=[]; cards=[]
    for ev in raw:
        t=ev.get("type","").lower(); det=ev.get("detail","").lower()
        mn=ev.get("time",{}).get("elapsed",0)
        tm=ev.get("team",{}).get("name",""); pl=ev.get("player",{}).get("name","")
        if t=="goal" and "own" not in det:
            goals.append({"minute":mn,"player":pl,"team":tm})
        elif t=="card":
            cards.append({"minute":mn,"player":pl,"team":tm,
                          "color":"yellow" if "yellow" in det else "red"})
    return {"goals":goals,"cards":cards}

# ── STATS ─────────────────────────────────────────────────────────────────────
def get_stats(fid):
    raw = _afl("/fixtures/statistics", {"fixture":fid}, ch=0.25)
    if not raw: return {}, {}
    def ps(d):
        o={}
        for s in d.get("statistics",[]):
            k=s.get("type","").lower().replace(" ","_"); o[k]=s.get("value")
        return o
    return ps(raw[0]) if raw else {}, ps(raw[1]) if len(raw)>1 else {}

# ── INJURIES ──────────────────────────────────────────────────────────────────
def get_injuries(team_id, league_id, season=None):
    if season is None: season = _current_season()
    raw = _afl("/injuries", {"team":team_id,"league":league_id,"season":season}, ch=6)
    if not raw: return []
    return [{"player":p.get("player",{}).get("name",""),
             "reason":p.get("player",{}).get("reason","")} for p in raw]

# ── ODDS ──────────────────────────────────────────────────────────────────────
def get_odds(home, away):
    all_games = _odds(ch=2)
    hn=home.lower()[:7]; an=away.lower()[:7]
    for g in all_games:
        gh=g.get("home_team","").lower(); ga=g.get("away_team","").lower()
        if (hn in gh or gh[:7] in hn) and (an in ga or ga[:7] in an):
            return _parse_odds(g)
    return {}

def _parse_odds(g):
    bh=bd=ba=bo25=bu25=bo15=0
    for bk in g.get("bookmakers",[]):
        for mkt in bk.get("markets",[]):
            key=mkt.get("key","")
            for oc in mkt.get("outcomes",[]):
                nm=oc.get("name",""); pr=float(oc.get("price",0))
                pt=float(oc.get("point",0)) if "point" in oc else 0
                if key=="h2h":
                    if nm==g.get("home_team"): bh=max(bh,pr)
                    elif nm==g.get("away_team"): ba=max(ba,pr)
                    elif nm=="Draw": bd=max(bd,pr)
                elif key=="totals":
                    if nm=="Over"  and pt==2.5: bo25=max(bo25,pr)
                    if nm=="Under" and pt==2.5: bu25=max(bu25,pr)
                    if nm=="Over"  and pt==1.5: bo15=max(bo15,pr)
    out={}
    if bh:   out["home"]=round(bh,2)
    if bd:   out["draw"]=round(bd,2)
    if ba:   out["away"]=round(ba,2)
    if bo25: out["over_25"]=round(bo25,2)
    if bu25: out["under_25"]=round(bu25,2)
    if bo15: out["over_15"]=round(bo15,2)
    return out

# ── SPORTMONKS PREDICTIONS ────────────────────────────────────────────────────
def get_sm_predictions(fid):
    data = _sm(f"/predictions/probabilities/fixtures/{fid}", ch=6)
    if not data: return {}
    if isinstance(data,list) and data: data=data[0]
    if not isinstance(data,dict): return {}
    p = data.get("predictions") or data
    def g(k, *alts):
        for key in (k,)+alts:
            v = p.get(key)
            if v is not None:
                try: return float(v)
                except: pass
        return 0.0
    return {
        "home_win": g("home_win","home","home_win_percentage"),
        "draw":     g("draw","draw_percentage"),
        "away_win": g("away_win","away","away_win_percentage"),
        "over_25":  g("over_2_5","over_25","goals_over_2_5"),
        "btts":     g("btts","both_teams_score"),
    }

def get_sm_xg(fid):
    data = _sm(f"/fixtures/{fid}", {"include":"statistics"}, ch=0.5)
    if not data: return None, None
    if isinstance(data,list) and data: data=data[0]
    stats = data.get("statistics",[]) if isinstance(data,dict) else []
    xh=xa=None
    for s in (stats or []):
        if not isinstance(s,dict): continue
        tp = s.get("type",{})
        nm = tp.get("developer_name","") if isinstance(tp,dict) else str(tp)
        if "xg" in nm.lower() or "expected_goals" in nm.lower():
            loc = s.get("location","")
            val = s.get("data",{}).get("value") if isinstance(s.get("data"),dict) else s.get("value")
            try:
                if "home" in loc: xh=float(val)
                elif "away" in loc: xa=float(val)
            except: pass
    return xh, xa

# ── POISSON ENGINE ────────────────────────────────────────────────────────────
def poisson_probs(xg_h, xg_a):
    def pmf(k,l): return (l**k)*math.exp(-l)/math.factorial(k) if l>0 else (1.0 if k==0 else 0.0)
    hw=dw=aw=o15=o25=bt=0.0
    for hg in range(10):
        ph=pmf(hg,xg_h)
        for ag in range(10):
            pa=pmf(ag,xg_a); j=ph*pa
            if hg>ag: hw+=j
            elif hg==ag: dw+=j
            else: aw+=j
            if hg+ag>1: o15+=j
            if hg+ag>2: o25+=j
            if hg>0 and ag>0: bt+=j
    return (round(hw*100,1),round(dw*100,1),round(aw*100,1),
            round(o25*100,1),round(o15*100,1),round(bt*100,1))

def estimate_xg(form, standing, is_home=True):
    try:
        import match_predictor as mp
        fs = mp.form_score(form) if form else 0.5
    except: fs=0.5
    base = 1.35 if is_home else 1.05
    base *= (0.6+fs*0.8)
    if standing:
        if standing<=6:   base*=1.15
        elif standing>=15: base*=0.88
    return round(max(base,0.3),2)

# ── FULL ENRICHMENT ───────────────────────────────────────────────────────────
def enrich(fid, card=None):
    """Full enrichment for one fixture. All 4 APIs. Returns analyst-ready dict."""
    c = card or {}
    h_id  = c.get("home_id");  a_id  = c.get("away_id")
    lg_id = c.get("league_id",0); season = c.get("season") or _current_season()
    h_nm  = c.get("home","Home"); a_nm  = c.get("away","Away")
    state = c.get("state","NS"); kickoff = c.get("kickoff","")
    score_h = c.get("score_h"); score_a = c.get("score_a")
    referee = None

    # Refresh from API if live or no card
    raw = get_fixture_by_id(fid)
    if raw:
        p = _parse(raw)
        h_id    = h_id   or p["home_id"];   a_id    = a_id   or p["away_id"]
        h_nm    = h_nm   or p["home"];      a_nm    = a_nm   or p["away"]
        lg_id   = lg_id  or p["league_id"]; season  = season or p["season"]
        state   = p["state"]; kickoff = p["kickoff"] or kickoff
        score_h = p["score_h"]; score_a = p["score_a"]
        referee = p["referee"]

    # Form
    h_form = get_form(h_id, lg_id, season) if h_id else []
    a_form = get_form(a_id, lg_id, season) if a_id else []

    # H2H
    h2h = get_h2h(h_id, a_id) if h_id and a_id else {}

    # Standings
    stds  = get_standings(lg_id, season)
    h_std = stds.get(h_id) or stds.get(h_nm)
    a_std = stds.get(a_id) or stds.get(a_nm)

    # Events, stats, lineups
    evts             = get_events(fid)
    hs, as_          = get_stats(fid)
    h_lu, a_lu       = get_lineups(fid)

    # Odds
    odds = get_odds(h_nm, a_nm)

    # Sportmonks
    sm   = get_sm_predictions(fid)
    xg_h, xg_a = get_sm_xg(fid)

    # xG fallback from API-Football stats
    if xg_h is None:
        try: xg_h = float(hs.get("expected_goals") or 0) or None
        except: pass
    if xg_a is None:
        try: xg_a = float(as_.get("expected_goals") or 0) or None
        except: pass

    # Probabilities -- Sportmonks first, Poisson fallback
    hw   = sm.get("home_win", 0)
    dw   = sm.get("draw",     0)
    aw   = sm.get("away_win", 0)
    o25  = sm.get("over_25",  0)
    btts = sm.get("btts",     0)

    xg_hc = xg_h or estimate_xg(h_form, h_std, True)
    xg_ac = xg_a or estimate_xg(a_form, a_std, False)

    if hw == 0 and dw == 0 and aw == 0:
        hw, dw, aw, po25, po15, pbt = poisson_probs(xg_hc, xg_ac)
        if o25  == 0: o25  = po25
        if btts == 0: btts = pbt
        o15 = po15
    else:
        _, _, _, po25, po15, pbt = poisson_probs(xg_hc, xg_ac)
        o15 = po15
        if o25  == 0: o25  = po25
        if btts == 0: btts = pbt

    tot = hw+dw+aw
    if tot > 0 and abs(tot-100) > 1:
        hw=round(hw/tot*100,1); dw=round(dw/tot*100,1); aw=round(aw/tot*100,1)

    o35 = round(max(o25-22, 4.0), 1)

    # Injuries
    h_inj = get_injuries(h_id, lg_id, season) if h_id else []
    a_inj = get_injuries(a_id, lg_id, season) if a_id else []

    return {
        "fixture_id":  fid,
        "home_id":     h_id,    "away_id":    a_id,
        "home_name":   h_nm,    "away_name":  a_nm,
        "league_id":   lg_id,   "league_name":c.get("league",""),
        "country":     c.get("country",""),
        "season":      season,
        "kickoff":     kickoff, "state": state, "referee": referee,
        "score_home":  score_h, "score_away": score_a,
        "home_win":    hw,    "draw":    dw,    "away_win": aw,
        "over_25":     o25,   "over_15": o15,   "btts":    btts,
        "over_35":     o35,
        "xg_home":     xg_hc, "xg_away": xg_ac,
        "home_form":   h_form, "away_form":  a_form,
        "h2h":         h2h,
        "home_standing":h_std, "away_standing":a_std,
        "home_lineup": h_lu,   "away_lineup":  a_lu,
        "goals":       evts.get("goals",[]),
        "cards":       evts.get("cards",[]),
        "home_stats":  hs,     "away_stats":   as_,
        "odds_home":   odds.get("home"),
        "odds_draw":   odds.get("draw"),
        "odds_away":   odds.get("away"),
        "odds_o25":    odds.get("over_25"),
        "odds_o15":    odds.get("over_15"),
        "odds_btts":   None,
        "home_injuries":h_inj, "away_injuries":a_inj,
    }
