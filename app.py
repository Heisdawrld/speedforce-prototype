from flask import Flask, render_template_string, request, jsonify
import requests, os, math, json
from datetime import datetime, timedelta, timezone
import match_predictor, database, external_data

app = Flask(__name__)
database.init_db()

BSD_TOKEN  = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL   = "https://sports.bzzoiro.com/api"
WAT_OFFSET = 1

# ── 30+ Leagues ───────────────────────────────────────────────────────────────
LEAGUES = [
    # Tier 1 — Big 5 + Europe
    {"id": 1,  "name": "Premier League",    "country": "England",     "icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "tier": 1},
    {"id": 3,  "name": "La Liga",           "country": "Spain",       "icon": "🇪🇸", "tier": 1},
    {"id": 4,  "name": "Serie A",           "country": "Italy",       "icon": "🇮🇹", "tier": 1},
    {"id": 5,  "name": "Bundesliga",        "country": "Germany",     "icon": "🇩🇪", "tier": 1},
    {"id": 6,  "name": "Ligue 1",           "country": "France",      "icon": "🇫🇷", "tier": 1},
    {"id": 7,  "name": "Champions League",  "country": "Europe",      "icon": "🏆", "tier": 1},
    {"id": 8,  "name": "Europa League",     "country": "Europe",      "icon": "🏆", "tier": 1},
    # Tier 2 — Strong leagues
    {"id": 2,  "name": "Liga Portugal",     "country": "Portugal",    "icon": "🇵🇹", "tier": 2},
    {"id": 9,  "name": "Eredivisie",        "country": "Netherlands", "icon": "🇳🇱", "tier": 2},
    {"id": 10, "name": "Premier Liga",      "country": "Russia",      "icon": "🇷🇺", "tier": 2},
    {"id": 11, "name": "Süper Lig",         "country": "Turkey",      "icon": "🇹🇷", "tier": 2},
    {"id": 12, "name": "Championship",      "country": "England",     "icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "tier": 2},
    {"id": 13, "name": "Scottish Prem",     "country": "Scotland",    "icon": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "tier": 2},
    {"id": 14, "name": "Belgian Pro Lg",    "country": "Belgium",     "icon": "🇧🇪", "tier": 2},
    {"id": 15, "name": "Swiss Super Lg",    "country": "Switzerland", "icon": "🇨🇭", "tier": 2},
    {"id": 16, "name": "Austrian Bundesliga","country": "Austria",    "icon": "🇦🇹", "tier": 2},
    {"id": 17, "name": "Greek Super Lg",    "country": "Greece",      "icon": "🇬🇷", "tier": 2},
    # Americas
    {"id": 18, "name": "MLS",               "country": "USA",         "icon": "🇺🇸", "tier": 2},
    {"id": 19, "name": "Brasileirão",       "country": "Brazil",      "icon": "🇧🇷", "tier": 2},
    {"id": 20, "name": "Liga MX",           "country": "Mexico",      "icon": "🇲🇽", "tier": 2},
    {"id": 21, "name": "Argentine Liga",    "country": "Argentina",   "icon": "🇦🇷", "tier": 2},
    # Eastern Europe & Others
    {"id": 22, "name": "Bulgarian A PFG",   "country": "Bulgaria",    "icon": "🇧🇬", "tier": 3},
    {"id": 23, "name": "Romanian Superliga","country": "Romania",     "icon": "🇷🇴", "tier": 3},
    {"id": 24, "name": "Czech Liga",        "country": "Czech Rep",   "icon": "🇨🇿", "tier": 3},
    {"id": 25, "name": "Polish Ekstraklasa","country": "Poland",      "icon": "🇵🇱", "tier": 3},
    {"id": 26, "name": "Ukrainian PL",      "country": "Ukraine",     "icon": "🇺🇦", "tier": 3},
    {"id": 27, "name": "Danish Superliga",  "country": "Denmark",     "icon": "🇩🇰", "tier": 3},
    {"id": 28, "name": "Norwegian Eliteser","country": "Norway",      "icon": "🇳🇴", "tier": 3},
    {"id": 29, "name": "Swedish Allsvenskan","country": "Sweden",     "icon": "🇸🇪", "tier": 3},
    {"id": 30, "name": "Chinese Super Lg",  "country": "China",       "icon": "🇨🇳", "tier": 3},
    {"id": 31, "name": "J-League",          "country": "Japan",       "icon": "🇯🇵", "tier": 3},
    {"id": 32, "name": "Saudi Pro League",  "country": "Saudi Arabia","icon": "🇸🇦", "tier": 3},
    {"id": 33, "name": "UAE Pro League",    "country": "UAE",         "icon": "🇦🇪", "tier": 3},
    {"id": 34, "name": "Israeli PL",        "country": "Israel",      "icon": "🇮🇱", "tier": 3},
    {"id": 35, "name": "Croatian HNL",      "country": "Croatia",     "icon": "🇭🇷", "tier": 3},
    {"id": 36, "name": "Serbian SuperLiga", "country": "Serbia",      "icon": "🇷🇸", "tier": 3},
    {"id": 37, "name": "Slovenian PrvaLiga","country": "Slovenia",    "icon": "🇸🇮", "tier": 3},
    {"id": 38, "name": "Ligue 2",           "country": "France",      "icon": "🇫🇷", "tier": 3},
    {"id": 39, "name": "2. Bundesliga",     "country": "Germany",     "icon": "🇩🇪", "tier": 3},
    {"id": 40, "name": "Serie B",           "country": "Italy",       "icon": "🇮🇹", "tier": 3},
    {"id": 41, "name": "Segunda División",  "country": "Spain",       "icon": "🇪🇸", "tier": 3},
    {"id": 42, "name": "League One",        "country": "England",     "icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "tier": 3},
    {"id": 43, "name": "League Two",        "country": "England",     "icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "tier": 3},
    {"id": 44, "name": "Conf. League",      "country": "Europe",      "icon": "🏆", "tier": 2},
    {"id": 45, "name": "African Nations",   "country": "Africa",      "icon": "🌍", "tier": 2},
    {"id": 46, "name": "Copa Libertadores", "country": "S. America",  "icon": "🏆", "tier": 2},
]
LEAGUE_MAP = {l["id"]: l for l in LEAGUES}

# ── API helpers ───────────────────────────────────────────────────────────────

def api_get(path, params=None):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=headers,
                         params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] {path} -> {e}")
        return {}

def fetch_all_predictions():
    """
    Fetch ALL available predictions across all pages.
    Bzzoiro paginates — we walk every page until next=null.
    Caches in SQLite for 30 min to avoid hammering the API.
    """
    cache_key = "all_predictions"
    cached = database.cache_get("h2h_cache", cache_key, max_age_hours=0.5)
    if cached:
        try:
            return json.loads(cached)
        except:
            pass

    all_matches = []
    page_url    = f"{BASE_URL}/predictions/"
    headers     = {"Authorization": f"Token {BSD_TOKEN}"}
    page        = 1
    max_pages   = 20  # safety cap

    while page_url and page <= max_pages:
        try:
            r = requests.get(page_url, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            all_matches.extend(results)
            page_url = data.get("next")
            page += 1
            print(f"[fetch] page {page-1}: +{len(results)} matches (total {len(all_matches)})")
        except Exception as e:
            print(f"[fetch] stopped at page {page}: {e}")
            break

    database.cache_set("h2h_cache", cache_key, json.dumps(all_matches))
    return all_matches

def fetch_league_matches(l_id):
    """Fetch predictions filtered by league ID."""
    all_matches = fetch_all_predictions()
    return [m for m in all_matches
            if m.get("event",{}).get("league",{}).get("id") == l_id]

# ── Date / time ───────────────────────────────────────────────────────────────

def parse_dt(raw):
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc) + timedelta(hours=WAT_OFFSET)
    except:
        return datetime.now(tz=timezone.utc)

def now_wat():
    return datetime.now(tz=timezone.utc) + timedelta(hours=WAT_OFFSET)

def group_by_date(matches):
    today    = now_wat().date()
    tomorrow = today + timedelta(days=1)
    groups   = {}
    for m in matches:
        dt  = parse_dt(m.get("event",{}).get("event_date",""))
        d   = dt.date()
        if d == today:           key = "TODAY"
        elif d == tomorrow:      key = "TOMORROW"
        elif d < today:          key = "EARLIER"
        else:
            # Sat, Sun, Mon etc.
            diff = (d - today).days
            if diff <= 6:        key = dt.strftime("%A").upper()[:3]
            else:                key = dt.strftime("%-d %b").upper()
        groups.setdefault(key, []).append((dt, m))
    for k in groups:
        groups[k].sort(key=lambda x: x[0])
    # Order keys sensibly
    order = ["EARLIER","TODAY","TOMORROW","MON","TUE","WED","THU","FRI","SAT","SUN"]
    ordered = {k: groups[k] for k in order if k in groups}
    for k in groups:
        if k not in ordered:
            ordered[k] = groups[k]
    return ordered

# ── UI helpers ────────────────────────────────────────────────────────────────

def form_dot(r):
    r   = r.upper()
    cls = {"W":"dot-w","D":"dot-d","L":"dot-l"}.get(r,"dot-d")
    return f'<span class="dot {cls}">{r}</span>'

def form_dots(form_list):
    if not form_list:
        return '<span style="font-size:0.6rem;color:var(--t)">No data</span>'
    return '<div class="dots">' + ''.join(form_dot(r) for r in list(form_list)[-5:]) + '</div>'

def prob_bar(label, pct, color="green"):
    c = {"green":"var(--g)","blue":"var(--b)","orange":"var(--w)","red":"var(--r)"}.get(color,"var(--g)")
    return f'''<div class="prow">
      <div class="plabel"><span>{label}</span><span class="pval">{pct}%</span></div>
      <div class="ptrack"><div class="pfill" style="width:{min(pct,100)}%;background:{c}"></div></div>
    </div>'''

def result_badge(r):
    if r=="WIN":  return '<span class="badge badge-green">WIN</span>'
    if r=="LOSS": return '<span class="badge badge-red">LOSS</span>'
    return '<span class="badge badge-muted">PENDING</span>'

def tag_badge(tag):
    cls = {"ELITE PICK":"badge-green","STRONG PICK":"badge-green",
           "SOLID TIP":"badge-blue","MONITOR":"badge-muted"}.get(tag,"badge-muted")
    return f'<span class="badge {cls}">{tag}</span>'

def tip_color(tip):
    if "WIN" in tip or tip in ("HOME WIN","AWAY WIN"): return "var(--g)"
    if "GG" in tip or "OVER" in tip: return "var(--b)"
    if "DRAW" in tip: return "var(--w)"
    return "var(--t)"

# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
:root{
  --bg:#05080d;--s:#0b0f17;--s2:#111820;--s3:#18202e;
  --g:#00e676;--b:#4f8ef7;--w:#ff9500;--r:#f44336;--pu:#a855f7;--cy:#00bcd4;
  --t:#7a8799;--t2:#9aa5b4;--wh:#e8edf5;--bdr:rgba(255,255,255,.06);
  --bdr2:rgba(255,255,255,.1);
  --gs: linear-gradient(135deg,rgba(0,230,118,.08),rgba(79,142,247,.05));
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--t);font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;font-size:13px;min-height:100vh;padding-bottom:100px;overflow-x:hidden}
a{text-decoration:none;color:inherit}
::selection{background:rgba(0,230,118,.2)}

/* Scrollbar */
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bdr2);border-radius:4px}

/* NAV */
nav{position:sticky;top:0;z-index:200;background:rgba(5,8,13,.9);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border-bottom:1px solid var(--bdr)}
.nav-i{max-width:500px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;padding:10px 14px}
.logo{font-size:.95rem;font-weight:900;letter-spacing:-.5px;color:var(--wh)}
.logo span{color:var(--g)}
.nav-pills{display:flex;gap:4px}
.npill{font-size:.58rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:5px 11px;border-radius:50px;border:1px solid var(--bdr);color:var(--t);transition:all .2s}
.npill.on,.npill:hover{border-color:var(--g);color:var(--g);background:rgba(0,230,118,.07)}

/* SHELL */
.shell{max-width:500px;margin:0 auto;padding:0 12px}

/* CARDS */
.card{background:var(--s);border:1px solid var(--bdr);border-radius:16px;padding:16px;margin-bottom:8px;transition:border-color .2s}
.card:hover{border-color:var(--bdr2)}
.card-flat{background:var(--s2);border:1px solid var(--bdr);border-radius:12px;padding:12px;margin-bottom:6px}

/* BADGES */
.badge{display:inline-flex;align-items:center;font-size:.56rem;font-weight:700;letter-spacing:1.6px;text-transform:uppercase;padding:3px 9px;border-radius:50px;gap:4px}
.badge-green{background:rgba(0,230,118,.1);color:var(--g);border:1px solid rgba(0,230,118,.2)}
.badge-blue{background:rgba(79,142,247,.1);color:var(--b);border:1px solid rgba(79,142,247,.2)}
.badge-orange{background:rgba(255,149,0,.1);color:var(--w);border:1px solid rgba(255,149,0,.2)}
.badge-muted{background:rgba(122,135,153,.07);color:var(--t);border:1px solid var(--bdr)}
.badge-red{background:rgba(244,67,54,.1);color:var(--r);border:1px solid rgba(244,67,54,.2)}
.badge-pu{background:rgba(168,85,247,.1);color:var(--pu);border:1px solid rgba(168,85,247,.2)}

/* TYPOGRAPHY */
.eyebrow{font-size:.56rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--t);margin-bottom:4px}
.title{font-size:2.4rem;font-weight:900;color:var(--wh);line-height:1;letter-spacing:-.8px}
.sep{font-size:.56rem;letter-spacing:2px;text-transform:uppercase;color:var(--t);padding:14px 0 10px;border-bottom:1px solid var(--bdr);margin-bottom:12px}

/* PROB BARS */
.prow{margin-bottom:9px}
.plabel{display:flex;justify-content:space-between;margin-bottom:3px;font-size:.68rem}
.pval{color:var(--wh);font-weight:700}
.ptrack{height:4px;background:rgba(255,255,255,.05);border-radius:50px;overflow:hidden}
.pfill{height:100%;border-radius:50px;transition:width .6s ease}

/* FORM DOTS */
.dots{display:flex;gap:3px}
.dot{width:22px;height:22px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:.58rem;font-weight:700;letter-spacing:0}
.dot-w{background:rgba(0,230,118,.15);color:var(--g)}
.dot-d{background:rgba(79,142,247,.15);color:var(--b)}
.dot-l{background:rgba(244,67,54,.15);color:var(--r)}

/* TABS */
.tabs{display:flex;gap:5px;overflow-x:auto;padding:2px 0 8px;margin-bottom:10px;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{flex-shrink:0;font-size:.6rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;padding:6px 13px;border-radius:50px;border:1px solid var(--bdr);color:var(--t);white-space:nowrap;cursor:pointer;transition:all .2s}
.tab.on,.tab:active,.tab:hover{border-color:var(--g);color:var(--g);background:rgba(0,230,118,.07)}

/* SEARCH BAR */
.search-wrap{position:relative;margin-bottom:12px}
.search-input{width:100%;background:var(--s2);border:1px solid var(--bdr);border-radius:12px;padding:10px 14px 10px 38px;color:var(--wh);font-size:.8rem;outline:none;transition:border-color .2s}
.search-input:focus{border-color:var(--g)}
.search-input::placeholder{color:var(--t)}
.search-icon{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--t);font-size:.9rem;pointer-events:none}
.search-clear{position:absolute;right:12px;top:50%;transform:translateY(-50%);color:var(--t);font-size:.8rem;cursor:pointer;display:none;padding:4px}
.search-clear.show{display:block}

/* LEAGUE GRID */
.league-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:8px}
.league-tile{background:var(--s);border:1px solid var(--bdr);border-radius:14px;padding:14px 12px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden}
.league-tile:hover,.league-tile:active{border-color:rgba(0,230,118,.25);background:var(--s2);transform:scale(.985)}
.league-tile .tile-icon{font-size:1.4rem;margin-bottom:6px;display:block}
.league-tile .tile-name{font-size:.72rem;font-weight:800;color:var(--wh);line-height:1.2;margin-bottom:2px}
.league-tile .tile-country{font-size:.58rem;letter-spacing:1px;text-transform:uppercase;color:var(--t)}
.league-tile .tile-count{position:absolute;top:10px;right:10px;font-size:.56rem;font-weight:700;color:var(--g);background:rgba(0,230,118,.1);border:1px solid rgba(0,230,118,.15);border-radius:50px;padding:2px 7px}
.league-tile.no-matches{opacity:.45}

/* TIER HEADERS */
.tier-header{font-size:.57rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t);padding:16px 0 8px;display:flex;align-items:center;gap:8px}
.tier-header::after{content:'';flex:1;height:1px;background:var(--bdr)}

/* FIXTURE ROWS */
.fix-wrap{background:var(--s);border:1px solid var(--bdr);border-radius:16px;overflow:hidden;margin-bottom:8px}
.fix-row{display:flex;align-items:center;padding:13px 14px;border-bottom:1px solid var(--bdr);cursor:pointer;transition:background .15s;gap:10px;text-decoration:none}
.fix-row:last-child{border-bottom:none}
.fix-row:hover,.fix-row:active{background:rgba(255,255,255,.025)}
.fix-time{font-size:.66rem;color:var(--t);font-weight:600;min-width:36px}
.fix-teams{flex:1}
.fix-home,.fix-away{font-size:.78rem;font-weight:700;color:var(--wh);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:150px}
.fix-vs{font-size:.56rem;color:var(--t);margin:2px 0;letter-spacing:1px}
.fix-right{text-align:right;flex-shrink:0}
.fix-tip{font-size:.58rem;font-weight:700;letter-spacing:.8px;text-transform:uppercase}
.fix-prob{font-size:.62rem;color:var(--t);margin-top:1px}
.fix-live{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--r);animation:pulse 1.5s infinite;margin-right:4px;vertical-align:middle}

/* MATCH PAGE */
.match-header{margin-bottom:16px}
.team-row{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:4px}
.team-name{font-size:1.5rem;font-weight:900;color:var(--wh);line-height:1.1;letter-spacing:-.3px}
.team-name.away{text-align:right}
.vs-pill{flex-shrink:0;background:var(--s2);border:1px solid var(--bdr);border-radius:50px;padding:5px 12px;font-size:.62rem;font-weight:700;color:var(--t);letter-spacing:1px;align-self:center}
.match-meta{font-size:.6rem;color:var(--t);letter-spacing:1px;margin-top:8px}

/* TIP BOXES */
.rec-box{background:var(--gs);border:1px solid rgba(0,230,118,.18);border-radius:18px;padding:18px;margin-bottom:8px}
.rec-tip-name{font-size:1.6rem;font-weight:900;color:var(--wh);letter-spacing:-.3px;margin:7px 0 5px;line-height:1}
.rec-pct{font-size:2.8rem;font-weight:900;color:var(--g);line-height:1;letter-spacing:-1px}
.rec-reason{font-size:.68rem;color:var(--t2);line-height:1.6;margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,.06)}
.edge-badge{display:inline-flex;align-items:center;padding:3px 9px;border-radius:50px;font-size:.58rem;font-weight:700}
.edge-pos{background:rgba(0,230,118,.1);color:var(--g);border:1px solid rgba(0,230,118,.2)}
.edge-neg{background:rgba(244,67,54,.07);color:var(--r);border:1px solid rgba(244,67,54,.15)}

.tier-box{border-radius:15px;padding:14px;cursor:default}
.tier-box.safe{background:rgba(79,142,247,.06);border:1px solid rgba(79,142,247,.2)}
.tier-box.risky{background:rgba(255,149,0,.06);border:1px solid rgba(255,149,0,.2)}
.tier-label{font-size:.55rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px}
.tier-tip{font-size:.92rem;font-weight:800;color:var(--wh);line-height:1.2;margin-bottom:6px;min-height:36px}
.tier-pct{font-size:1.7rem;font-weight:900;line-height:1}

/* SIGNALS */
.sig-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:3px;transition:background .3s}
.sig-on{background:var(--g);box-shadow:0 0 6px rgba(0,230,118,.4)}
.sig-off{background:var(--bdr2)}

/* GRID */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin-bottom:8px}
.sbox{background:var(--s2);border:1px solid var(--bdr);border-radius:12px;padding:13px;text-align:center;transition:all .2s}
.sbox:hover{border-color:var(--bdr2)}
.sval{font-size:1.55rem;font-weight:800;color:var(--wh);line-height:1}
.sval.g{color:var(--g)}.sval.b{color:var(--b)}.sval.w{color:var(--w)}.sval.r{color:var(--r)}
.slbl{font-size:.54rem;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);margin-top:4px}

/* MOMENTUM */
.mom-bar{height:6px;background:rgba(255,255,255,.05);border-radius:50px;overflow:hidden;margin:8px 0;position:relative}
.mom-h{position:absolute;left:0;top:0;height:100%;background:linear-gradient(90deg,var(--g),rgba(0,230,118,.5));border-radius:50px;transition:width .6s ease}
.mom-a{position:absolute;right:0;top:0;height:100%;background:linear-gradient(270deg,var(--b),rgba(79,142,247,.5));border-radius:50px;transition:width .6s ease}

/* CRING */
.cring{position:relative;width:66px;height:66px;flex-shrink:0}
.cring-num{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.82rem;font-weight:800;color:var(--wh)}

/* H2H */
.h2h-bar{display:flex;height:6px;border-radius:50px;overflow:hidden;margin:10px 0}
.h2h-row{display:flex;align-items:center;padding:7px 0;border-bottom:1px solid var(--bdr);font-size:.68rem;gap:8px}
.h2h-row:last-child{border-bottom:none}
.h2h-date{color:var(--t);min-width:48px;font-size:.6rem;flex-shrink:0}
.h2h-teams{flex:1;color:var(--wh);font-weight:600;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.h2h-score{font-weight:800;color:var(--wh);font-size:.78rem;min-width:30px;text-align:right;flex-shrink:0}

/* LAST MATCHES */
.lm-row{display:flex;align-items:center;padding:7px 0;border-bottom:1px solid var(--bdr);gap:8px}
.lm-row:last-child{border-bottom:none}
.lm-res{width:20px;height:20px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:.55rem;font-weight:700;flex-shrink:0}

/* INJURY */
.inj-row{display:flex;align-items:center;gap:7px;padding:7px 0;border-bottom:1px solid var(--bdr);font-size:.7rem}
.inj-row:last-child{border-bottom:none}
.inj-dot{width:6px;height:6px;border-radius:50%;background:var(--r);flex-shrink:0}
.inj-dot.susp{background:var(--w)}

/* ANALYST */
.analyst-item{padding:9px 0;border-bottom:1px solid var(--bdr);font-size:.7rem;line-height:1.6;color:var(--t2)}
.analyst-item:last-child{border-bottom:none}
.analyst-item strong{color:var(--wh);font-size:.68rem}

/* BACK */
.back{display:inline-flex;align-items:center;gap:4px;font-size:.6rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);padding:14px 0 16px;transition:color .2s}
.back:hover{color:var(--wh)}

/* TRACKER */
.track-row{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid var(--bdr);font-size:.7rem}
.track-row:last-child{border-bottom:none}

/* ACCA */
.acca-row{display:flex;justify-content:space-between;align-items:center;padding:13px 14px;border-bottom:1px solid var(--bdr);transition:background .15s}
.acca-row:hover{background:rgba(255,255,255,.02)}
.acca-row:last-child{border-bottom:none}

/* MISC */
.empty{text-align:center;padding:50px 20px;color:var(--t);font-size:.75rem;line-height:1.8}
.info-box{background:var(--s2);border:1px solid var(--bdr);border-radius:11px;padding:11px 13px;font-size:.68rem;line-height:1.7;color:var(--t);margin-bottom:8px}
.info-box strong{color:var(--wh)}
.divider{height:1px;background:var(--bdr);margin:16px 0}

/* EXPANDABLE */
.expand-toggle{display:flex;justify-content:space-between;align-items:center;cursor:pointer;padding:12px 0;font-size:.72rem;font-weight:700;color:var(--t2);transition:color .2s}
.expand-toggle:hover{color:var(--wh)}
.expand-arrow{transition:transform .3s;font-size:.8rem}
.expand-arrow.open{transform:rotate(180deg)}
.expand-body{overflow:hidden;max-height:0;transition:max-height .4s ease}
.expand-body.open{max-height:2000px}

/* PULSE */
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.8)}}
@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideIn{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:translateX(0)}}
.up{animation:up .3s ease both}
.d1{animation-delay:.04s}.d2{animation-delay:.08s}.d3{animation-delay:.13s}.d4{animation-delay:.18s}

/* BOTTOM SHEET */
.sheet-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:300;opacity:0;pointer-events:none;transition:opacity .3s;backdrop-filter:blur(4px)}
.sheet-overlay.open{opacity:1;pointer-events:all}
.bottom-sheet{position:fixed;bottom:0;left:0;right:0;max-width:500px;margin:0 auto;background:var(--s);border-radius:20px 20px 0 0;border-top:1px solid var(--bdr2);z-index:301;transform:translateY(100%);transition:transform .35s cubic-bezier(.4,0,.2,1);padding:20px 16px 40px;max-height:75vh;overflow-y:auto}
.bottom-sheet.open{transform:translateY(0)}
.sheet-handle{width:36px;height:4px;background:var(--bdr2);border-radius:50px;margin:0 auto 20px}

/* FLOATING ACTION */
.fab{position:fixed;bottom:24px;right:18px;width:52px;height:52px;border-radius:50%;background:var(--g);color:#000;font-size:1.4rem;display:flex;align-items:center;justify-content:center;border:none;cursor:pointer;box-shadow:0 4px 20px rgba(0,230,118,.4);z-index:150;transition:transform .2s}
.fab:hover{transform:scale(1.08)}

/* COUNT BADGE */
.count-bubble{display:inline-flex;align-items:center;justify-content:center;min-width:18px;height:18px;border-radius:50px;background:rgba(0,230,118,.15);color:var(--g);font-size:.58rem;font-weight:700;padding:0 5px;border:1px solid rgba(0,230,118,.2)}
"""

# ── Layout template ───────────────────────────────────────────────────────────

LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>ProPredictor NG</title>
<style>""" + CSS + """</style>
</head>
<body>
<nav>
  <div class="nav-i">
    <div class="logo">PRO<span>PRED</span></div>
    <div class="nav-pills">
      <a href="/" class="npill {{ 'on' if page=='home' else '' }}">Leagues</a>
      <a href="/acca" class="npill {{ 'on' if page=='acca' else '' }}">ACCA</a>
      <a href="/tracker" class="npill {{ 'on' if page=='tracker' else '' }}">Track</a>
    </div>
  </div>
</nav>
<div class="shell">{{ content|safe }}</div>

<script>
// Expandable sections
document.querySelectorAll('.expand-toggle').forEach(el => {
  el.addEventListener('click', () => {
    const body  = el.nextElementSibling;
    const arrow = el.querySelector('.expand-arrow');
    body.classList.toggle('open');
    if (arrow) arrow.classList.toggle('open');
  });
});

// Bottom sheet
function openSheet(id) {
  document.getElementById('overlay-'+id).classList.add('open');
  document.getElementById('sheet-'+id).classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeSheet(id) {
  document.getElementById('overlay-'+id).classList.remove('open');
  document.getElementById('sheet-'+id).classList.remove('open');
  document.body.style.overflow = '';
}
document.querySelectorAll('.sheet-overlay').forEach(el => {
  el.addEventListener('click', () => {
    const id = el.id.replace('overlay-','');
    closeSheet(id);
  });
});

// Search
const searchInput = document.getElementById('league-search');
if (searchInput) {
  const clearBtn = document.querySelector('.search-clear');
  searchInput.addEventListener('input', function() {
    const q = this.value.toLowerCase();
    clearBtn.classList.toggle('show', q.length > 0);
    document.querySelectorAll('.league-tile').forEach(tile => {
      const name = tile.dataset.name || '';
      tile.style.display = name.includes(q) ? '' : 'none';
    });
    document.querySelectorAll('.tier-header').forEach(hdr => {
      // hide tier if all tiles hidden
      let next = hdr.nextElementSibling;
      let grid = null;
      while (next && next.classList.contains('tier-header')) next = next.nextElementSibling;
      if (next && next.classList.contains('league-grid')) grid = next;
      if (grid) {
        const visible = [...grid.querySelectorAll('.league-tile')].some(t => t.style.display !== 'none');
        hdr.style.display = visible ? '' : 'none';
        grid.style.display = visible ? '' : 'none';
      }
    });
  });
  if (clearBtn) clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    clearBtn.classList.remove('show');
    document.querySelectorAll('.league-tile,.tier-header').forEach(el => el.style.display = '');
  });
}

// Tab active highlight
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', function() {
    // handled by href, just visual
  });
});

// Animate prob bars on scroll
const observer = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) e.target.style.width = e.target.dataset.width + '%';
  });
}, { threshold: 0.1 });
document.querySelectorAll('.pfill').forEach(el => {
  const w = el.style.width;
  el.dataset.width = parseFloat(w);
  el.style.width = '0%';
  observer.observe(el);
});
</script>
</body>
</html>"""


# ── HOME PAGE ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    all_matches = fetch_all_predictions()

    # Count matches per league
    league_counts = {}
    for m in all_matches:
        l_id = m.get("event",{}).get("league",{}).get("id")
        if l_id:
            league_counts[l_id] = league_counts.get(l_id, 0) + 1

    total_fixtures = len(all_matches)
    total_leagues  = len([l for l in LEAGUES if league_counts.get(l["id"], 0) > 0])

    c  = f'''<div class="up" style="padding:22px 0 14px">
      <p class="eyebrow">Football Intelligence</p>
      <h1 class="title" style="margin-top:5px">LEAGUES</h1>
      <div style="display:flex;gap:12px;margin-top:8px">
        <div><span class="count-bubble">{total_fixtures}</span> <span style="font-size:.65rem;color:var(--t)">fixtures</span></div>
        <div><span class="count-bubble">{total_leagues}</span> <span style="font-size:.65rem;color:var(--t)">leagues</span></div>
      </div>
    </div>'''

    # Search
    c += '''<div class="search-wrap up d1">
      <span class="search-icon">🔍</span>
      <input type="text" id="league-search" class="search-input" placeholder="Search leagues or countries…">
      <span class="search-clear">✕</span>
    </div>'''

    # Group by tier
    tier_names = {1: "⭐ Top Leagues", 2: "🌍 Major Leagues", 3: "🔭 More Leagues"}
    for tier, tier_label in tier_names.items():
        tier_leagues = [l for l in LEAGUES if l.get("tier") == tier]
        # Only show tier if at least one league has matches OR it's tier 1
        has_any = any(league_counts.get(l["id"], 0) > 0 for l in tier_leagues)
        if not has_any and tier == 3:
            # Still show tier 3 but collapsed
            c += f'<div class="tier-header">{tier_label}</div>'
        else:
            c += f'<div class="tier-header up d{tier}">{tier_label}</div>'

        c += '<div class="league-grid">'
        for l in tier_leagues:
            count = league_counts.get(l["id"], 0)
            no_cls = " no-matches" if count == 0 else ""
            count_badge = f'<span class="tile-count">{count}</span>' if count > 0 else ""
            c += f'''<a href="/league/{l["id"]}" class="league-tile{no_cls}" data-name="{l["name"].lower()} {l["country"].lower()}">
              {count_badge}
              <span class="tile-icon">{l["icon"]}</span>
              <div class="tile-name">{l["name"]}</div>
              <div class="tile-country">{l["country"]}</div>
            </a>'''
        c += '</div>'

    return render_template_string(LAYOUT, content=c, page="home")


# ── LEAGUE PAGE ───────────────────────────────────────────────────────────────

@app.route("/league/<int:l_id>")
def league_page(l_id):
    league  = LEAGUE_MAP.get(l_id, {"name":"League","icon":"","country":"","tier":1})
    matches = fetch_league_matches(l_id)
    back    = '<a href="/" class="back">← Leagues</a>'

    if not matches:
        return render_template_string(LAYOUT,
            content=f'{back}<div class="empty">No fixtures available for {league["name"]} right now.<br><span style="font-size:.65rem">Check back closer to matchday</span></div>',
            page="league")

    groups    = group_by_date(matches)
    date_keys = list(groups.keys())
    active    = request.args.get("tab", date_keys[0] if date_keys else "TODAY")

    # Tab bar
    tabs = '<div class="tabs">'
    for k in date_keys:
        n    = len(groups[k])
        tabs += f'<a href="/league/{l_id}?tab={k}" class="tab {"on" if k==active else ""}">{k} <span class="count-bubble" style="margin-left:3px">{n}</span></a>'
    tabs += '</div>'

    # Fixture rows
    rows = '<div class="fix-wrap">'
    for dt, m in groups.get(active, []):
        e   = m.get("event", {})
        h   = e.get("home_team","?")
        a   = e.get("away_team","?")
        mid = m.get("id", 0)
        res = match_predictor.analyze_match(m, l_id)
        tip = res["recommended"]["tip"] if res else "—"
        tip_c = tip_color(tip)
        prob  = res["recommended"]["prob"] if res else 0
        status = e.get("status","")
        live_dot = '<span class="fix-live"></span>' if status in ("live","inplay","1H","2H","HT") else ""

        rows += f'''<a href="/match/{mid}" class="fix-row">
          <span class="fix-time">{live_dot}{dt.strftime("%H:%M")}</span>
          <div class="fix-teams">
            <div class="fix-home">{h}</div>
            <div class="fix-vs">VS</div>
            <div class="fix-away">{a}</div>
          </div>
          <div class="fix-right">
            <div class="fix-tip" style="color:{tip_c}">{tip}</div>
            <div class="fix-prob">{prob}%</div>
          </div>
        </a>'''
    rows += '</div>'

    c  = back
    c += f'''<div class="up" style="margin-bottom:18px">
      <p class="eyebrow">{league["icon"]} {league["country"]}</p>
      <h2 class="title" style="font-size:1.8rem;margin-top:4px">{league["name"]}</h2>
      <p style="font-size:.62rem;color:var(--t);margin-top:5px">{len(matches)} fixtures across {len(date_keys)} matchday(s)</p>
    </div>'''
    c += tabs + rows
    return render_template_string(LAYOUT, content=c, page="league")


# ── MATCH PAGE ────────────────────────────────────────────────────────────────

@app.route("/match/<int:match_id>")
def match_display(match_id):
    data = api_get(f"/predictions/{match_id}/")
    if not data:
        return render_template_string(LAYOUT,
            content='<a href="/" class="back">← Home</a><div class="empty">Match data unavailable</div>',
            page="match")

    event  = data.get("event", {})
    league = event.get("league", {})
    l_id   = league.get("id", 1)
    l_info = LEAGUE_MAP.get(l_id, {"name": league.get("name",""), "icon":"", "country":""})
    h      = event.get("home_team","Home")
    a      = event.get("away_team","Away")
    dt     = parse_dt(event.get("event_date",""))

    enriched  = external_data.enrich_match(data)
    narrative = external_data.build_analyst_narrative(enriched, h, a)
    res       = match_predictor.analyze_match(data, l_id, enriched)

    if not res:
        return render_template_string(LAYOUT,
            content=f'<a href="/league/{l_id}" class="back">← {l_info["name"]}</a><div class="empty">Analysis unavailable</div>',
            page="match")

    try:
        database.log_prediction(
            match_id=match_id, league_id=l_id, league_name=l_info.get("name",""),
            home_team=h, away_team=a, match_date=dt.strftime("%Y-%m-%d %H:%M"),
            market=res["recommended"]["tip"], probability=res["recommended"]["prob"],
            fair_odds=res["recommended"]["odds"], bookie_odds=None,
            edge=res["recommended"].get("edge"), confidence=res["confidence"],
            xg_home=res["xg_h"], xg_away=res["xg_a"], likely_score="")
    except: pass
    _try_settle(data, match_id)

    rec  = res["recommended"]
    safe = res["safest"]
    risky_list = res["risky"]
    risky_main = risky_list[0] if risky_list else {"tip":"—","prob":0,"odds":0}
    ox   = res["1x2"];  mkts = res["markets"]
    mom  = res["momentum"]
    h_form_display = enriched.get("home_form") or res["form"]["home"]
    a_form_display = enriched.get("away_form") or res["form"]["away"]
    h_inj = enriched.get("home_injuries", [])
    a_inj = enriched.get("away_injuries", [])
    h2h_sum = enriched.get("h2h_summary")
    h_last  = enriched.get("home_last", [])
    a_last  = enriched.get("away_last", [])
    h_stats = enriched.get("home_stats")
    a_stats = enriched.get("away_stats")

    conf  = res["confidence"]
    rc    = "#00e676" if conf>=60 else "#4f8ef7" if conf>=45 else "#ff9500"
    r_svg = 27; cx = cy = 33
    circ  = 2 * math.pi * r_svg
    dash  = circ * (conf / 100)

    edge      = rec.get("edge")
    edge_html = f'<span class="edge-badge {"edge-pos" if edge and edge>0 else "edge-neg"}">{"+" if edge and edge>0 else ""}{edge}% edge</span>' if edge is not None else ""
    total_mom = max(mom["home"] + mom["away"], 1)
    mh_w = round(mom["home"] / total_mom * 100)
    ma_w = round(mom["away"] / total_mom * 100)
    agree_html = ''.join([f'<span class="sig-dot {"sig-on" if i < rec["agree"] else "sig-off"}"></span>' for i in range(3)])

    c = f'<a href="/league/{l_id}" class="back">← {l_info["name"]}</a>'

    # ── HEADER ──
    c += f'''<div class="match-header up">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div style="flex:1">
          {tag_badge(res["tag"])}
          <div class="team-row" style="margin-top:10px">
            <div class="team-name">{h}</div>
            <div class="vs-pill">VS</div>
            <div class="team-name away">{a}</div>
          </div>
          <p class="match-meta">{l_info["icon"]} {l_info["name"]} · {dt.strftime("%-d %b %Y")} · {dt.strftime("%H:%M")} WAT</p>
        </div>
        <div class="cring" style="margin-left:10px;margin-top:4px">
          <svg width="66" height="66" viewBox="0 0 66 66">
            <circle cx="{cx}" cy="{cy}" r="{r_svg}" stroke="rgba(255,255,255,.06)" stroke-width="5" fill="none"/>
            <circle cx="{cx}" cy="{cy}" r="{r_svg}" stroke="{rc}" stroke-width="5" fill="none"
              stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>
          </svg>
          <div class="cring-num">{conf:.0f}%</div>
        </div>
      </div>
    </div>'''

    # ── INJURIES ──
    if h_inj or a_inj:
        c += '<div class="card up d1" style="border-color:rgba(244,67,54,.2)">'
        c += '<p class="sep" style="padding-top:0;margin-top:0;color:var(--r)">⚠ Injuries & Suspensions</p>'
        for tn, inj_list in [(h, h_inj), (a, a_inj)]:
            if not inj_list: continue
            c += f'<p class="eyebrow" style="margin-bottom:6px">{tn}</p>'
            for inj in inj_list[:4]:
                dc = "inj-dot susp" if "suspend" in inj.get("type","").lower() else "inj-dot"
                c += f'<div class="inj-row"><div class="{dc}"></div><span style="color:var(--wh);font-weight:600">{inj["name"]}</span><span style="margin-left:auto;font-size:.6rem;color:var(--t)">{inj["type"]}</span></div>'
        c += '</div>'

    # ── RECOMMENDED TIP ──
    c += f'''<div class="rec-box up d1">
      <p class="eyebrow">⚡ Recommended Tip</p>
      <p class="rec-tip-name">{rec["tip"]}</p>
      <div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:8px">
        <p class="rec-pct">{rec["prob"]}%</p>
        <div>
          <p style="font-size:.56rem;letter-spacing:1.5px;color:var(--t)">FAIR ODDS</p>
          <p style="font-size:1.35rem;font-weight:800;color:var(--wh)">{rec["odds"]}</p>
        </div>
        {edge_html}
      </div>
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
        {agree_html}
        <span style="font-size:.6rem;color:var(--t)">{rec["agree"]}/3 signals agree</span>
      </div>
      <p class="rec-reason">{rec["reason"]}</p>
    </div>'''

    # ── SAFE + RISKY ──
    safe_odds_str = f'<p style="font-size:.6rem;color:var(--t);margin-top:5px">Fair odds {safe["odds"]}</p>' if safe.get("odds") else ""
    c += f'''<div class="g2 up d2">
      <div class="tier-box safe">
        <p class="tier-label" style="color:var(--b)">🛡 Safest Bet</p>
        <p class="tier-tip">{safe["tip"]}</p>
        <p class="tier-pct" style="color:var(--b)">{safe["prob"]}%</p>
        {safe_odds_str}
      </div>
      <div class="tier-box risky">
        <p class="tier-label" style="color:var(--w)">🎯 Risky Market</p>
        <p class="tier-tip">{risky_main["tip"]}</p>
        <p class="tier-pct" style="color:var(--w)">{risky_main["prob"]}%</p>
        <p style="font-size:.6rem;color:var(--t);margin-top:5px">~{risky_main["odds"]} odds</p>
      </div>
    </div>'''

    # More risky combos in expandable
    if len(risky_list) > 1:
        c += '<div class="card up d2" style="padding:0 16px">'
        c += '<div class="expand-toggle"><span>More Combo Markets</span><span class="expand-arrow">▾</span></div>'
        c += '<div class="expand-body">'
        for rk in risky_list[1:]:
            c += f'<div style="display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-top:1px solid var(--bdr)"><span style="font-weight:700;color:var(--wh);font-size:.74rem">{rk["tip"]}</span><span style="color:var(--w);font-weight:700;font-size:.74rem">{rk["prob"]}% · ~{rk["odds"]}</span></div>'
        c += '<div style="height:4px"></div></div></div>'

    # ── xG ──
    c += f'''<div class="g2 up d2">
      <div class="sbox"><p class="sval g">{res["xg_h"]}</p><p class="slbl">xG {h.split()[0]}</p></div>
      <div class="sbox"><p class="sval b">{res["xg_a"]}</p><p class="slbl">xG {a.split()[0]}</p></div>
    </div>'''

    # ── ANALYST VIEW ──
    has_narrative = any(narrative.get(k) for k in ["form","h2h","goals","injuries","morale"])
    if has_narrative:
        c += '<div class="card up d2">'
        c += '<p class="sep" style="padding-top:0;margin-top:0">📋 Analyst View</p>'
        labels = {"form":"Form","morale":"Momentum","h2h":"H2H Pattern","goals":"Goal Trend","injuries":"Absences"}
        for key, label in labels.items():
            val = narrative.get(key)
            if val:
                c += f'<div class="analyst-item"><strong>{label} · </strong>{val}</div>'
        c += '</div>'

    # ── 1X2 + GOAL MARKETS (tappable/expandable) ──
    c += f'''<div class="card up d3">
      <div class="expand-toggle"><span style="font-size:.72rem;font-weight:700;color:var(--t2)">1 × 2 Probabilities</span><span class="expand-arrow open">▾</span></div>
      <div class="expand-body open">
        {prob_bar("Home Win", ox["home"])}
        {prob_bar("Draw", ox["draw"], "blue")}
        {prob_bar("Away Win", ox["away"], "orange")}
      </div>
    </div>'''

    c += f'''<div class="card up d3">
      <div class="expand-toggle"><span style="font-size:.72rem;font-weight:700;color:var(--t2)">Goal Markets</span><span class="expand-arrow open">▾</span></div>
      <div class="expand-body open">
        {prob_bar("GG (Both Score)", mkts["gg"])}
        {prob_bar("NG (Clean Sheet)", mkts["ng"], "orange")}
        {prob_bar("Over 1.5", mkts["over_15"])}
        {prob_bar("Over 2.5", mkts["over_25"])}
        {prob_bar("Over 3.5", mkts["over_35"])}
        {prob_bar("Under 2.5", mkts["under_25"], "blue")}
      </div>
    </div>'''

    # ── H2H ──
    if h2h_sum and h2h_sum["total"] >= 2:
        n = h2h_sum["total"]
        hw = h2h_sum["home_wins"]; dr = h2h_sum["draws"]; aw = h2h_sum["away_wins"]
        hw_w = round(hw/n*100); dr_w = round(dr/n*100); aw_w = round(aw/n*100)
        c += f'<div class="card up d3">'
        c += f'<div class="expand-toggle"><span style="font-size:.72rem;font-weight:700;color:var(--t2)">Head to Head · Last {n}</span><span class="expand-arrow open">▾</span></div>'
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
        for m_h2h in h2h_sum.get("matches",[])[:6]:
            hg = m_h2h.get("home_goals","?"); ag = m_h2h.get("away_goals","?")
            d_str = m_h2h.get("date","")[:7]
            c += f'''<div class="h2h-row">
              <span class="h2h-date">{d_str}</span>
              <span class="h2h-teams">{m_h2h.get("home","?")} vs {m_h2h.get("away","?")}</span>
              <span class="h2h-score">{hg}–{ag}</span>
            </div>'''
        c += '</div></div>'

    # ── LAST MATCHES ──
    def last_block(title, matches, team_name):
        if not matches: return ""
        blk = f'<div class="card up d3"><div class="expand-toggle"><span style="font-size:.72rem;font-weight:700;color:var(--t2)">{title}</span><span class="expand-arrow">▾</span></div><div class="expand-body">'
        for m in matches[:5]:
            hg = m.get("home_goals") or 0; ag = m.get("away_goals") or 0
            is_h = m["home"] == team_name
            r = ("W" if (hg>ag if is_h else ag>hg) else "D" if hg==ag else "L")
            rc = {"W":"dot-w","D":"dot-d","L":"dot-l"}[r]
            opp = m["away"] if is_h else m["home"]
            lg  = m.get("league","")
            prefix = "vs" if is_h else "@"
            blk += f'''<div class="lm-row">
              <div class="lm-res {rc}">{r}</div>
              <div style="flex:1">
                <div style="font-size:.72rem;font-weight:700;color:var(--wh)">{prefix} {opp}</div>
                <div style="font-size:.58rem;color:var(--t)">{lg} · {m.get("date","")}</div>
              </div>
              <span style="font-size:.78rem;font-weight:800;color:var(--wh)">{hg}–{ag}</span>
            </div>'''
        blk += '</div></div>'
        return blk

    c += last_block(f"{h} — Last 5", h_last, h)
    c += last_block(f"{a} — Last 5", a_last, a)

    # ── SEASON STATS ──
    if h_stats or a_stats:
        c += '<div class="card up d4">'
        c += '<div class="expand-toggle"><span style="font-size:.72rem;font-weight:700;color:var(--t2)">Season Stats</span><span class="expand-arrow">▾</span></div>'
        c += '<div class="expand-body">'
        for tn, st in [(h, h_stats), (a, a_stats)]:
            if not st: continue
            c += f'<p class="eyebrow" style="margin:10px 0 7px">{tn}</p>'
            for lbl, val in [
                ("W / D / L", f'{st.get("wins",0)} / {st.get("draws",0)} / {st.get("losses",0)}'),
                ("Goals scored", f'{st.get("goals_scored",0)} ({st.get("avg_scored",0):.1f}/game)'),
                ("Goals conceded", f'{st.get("goals_conceded",0)} ({st.get("avg_conceded",0):.1f}/game)'),
                ("Clean sheets", st.get("clean_sheets",0)),
            ]:
                c += f'<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--bdr);font-size:.7rem"><span>{lbl}</span><span style="color:var(--wh);font-weight:700">{val}</span></div>'
        c += '</div></div>'

    # ── FORM & MOMENTUM ──
    c += f'''<div class="card up d4">
      <p class="sep" style="padding-top:0;margin-top:0">Form & Momentum</p>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <span style="font-size:.75rem;font-weight:700;color:var(--wh);flex:1">{h}</span>
        {form_dots(h_form_display)}
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <span style="font-size:.75rem;font-weight:700;color:var(--wh);flex:1">{a}</span>
        {form_dots(a_form_display)}
      </div>
      <div style="display:flex;justify-content:space-between;font-size:.66rem;margin-bottom:5px">
        <span style="color:var(--g)">{h.split()[0]} {mom["home"]}%</span>
        <span style="color:var(--b)">{a.split()[0]} {mom["away"]}%</span>
      </div>
      <div class="mom-bar">
        <div class="mom-h" style="width:{mh_w}%"></div>
        <div class="mom-a" style="width:{ma_w}%"></div>
      </div>
      <p style="font-size:.67rem;color:var(--t2);margin-top:8px;line-height:1.5">{mom["narrative"]}</p>
      <p style="font-size:.65rem;color:var(--t);margin-top:5px;line-height:1.5">{res["style"]}</p>
    </div>'''

    return render_template_string(LAYOUT, content=c, page="match")


# ── ACCA ──────────────────────────────────────────────────────────────────────

@app.route("/acca")
def acca():
    all_matches = fetch_all_predictions()
    picks, combined = match_predictor.pick_acca(all_matches, n=5, min_conv=42.0)

    c  = '<div style="padding:22px 0 14px" class="up"><p class="eyebrow">Daily Best Picks</p><h1 class="title" style="margin-top:5px">ACCA</h1></div>'
    if not picks:
        c += '<div class="empty">No qualifying picks right now.<br>Check back on matchday.</div>'
        return render_template_string(LAYOUT, content=c, page="acca")

    c += '<div class="fix-wrap up d1">'
    for p in picks:
        e    = p["match"].get("event",{})
        h, a = e.get("home_team","?"), e.get("away_team","?")
        res  = p["result"]; mid = p["match"].get("id",0)
        l_info = LEAGUE_MAP.get(p["league_id"], {"icon":"","name":""})
        rec  = res["recommended"]
        edge = rec.get("edge")
        tc   = tip_color(rec["tip"])
        c += f'''<a href="/match/{mid}" class="acca-row">
          <div style="flex:1">
            <p style="font-size:.57rem;color:var(--t);letter-spacing:1.2px;text-transform:uppercase;margin-bottom:3px">{l_info.get("icon","")} {l_info.get("name","")}</p>
            <p style="font-size:.8rem;font-weight:700;color:var(--wh)">{h} vs {a}</p>
            <p style="font-size:.62rem;margin-top:2px"><span style="color:{tc};font-weight:700">{rec["tip"]}</span> <span style="color:var(--t)">· {rec["prob"]}%{"  +" + str(edge) + "% edge" if edge and edge>0 else ""}</span></p>
            <p style="font-size:.6rem;color:var(--t);margin-top:2px;line-height:1.4">{rec["reason"][:65]}{"…" if len(rec["reason"])>65 else ""}</p>
          </div>
          <div style="text-align:right;margin-left:10px;flex-shrink:0">
            <p style="font-size:1.35rem;font-weight:900;color:var(--g)">{rec["odds"]}</p>
            <p style="font-size:.58rem;color:var(--t)">odds</p>
          </div>
        </a>'''
    c += '</div>'

    c += f'''<div style="background:var(--gs);border:1px solid rgba(0,230,118,.15);border-radius:18px;padding:20px;text-align:center;margin-top:10px" class="up d2">
      <p class="eyebrow">Combined Odds</p>
      <p style="font-size:4rem;font-weight:900;color:var(--g);letter-spacing:-2px;line-height:1;margin:6px 0">{combined}</p>
      <p style="font-size:.6rem;color:var(--t);letter-spacing:1px">{len(picks)}-FOLD ACCUMULATOR</p>
    </div>
    <p style="font-size:.58rem;color:var(--t);text-align:center;padding:14px;letter-spacing:1px">Fair odds shown · Bet responsibly</p>'''
    return render_template_string(LAYOUT, content=c, page="acca")


# ── TRACKER ───────────────────────────────────────────────────────────────────

@app.route("/tracker")
def tracker():
    stats   = database.get_tracker_stats()
    total   = stats["total"]; wins = stats["wins"]
    losses  = stats["losses"]; hr = stats["hit_rate"]; pending = stats["pending"]
    c = '<div style="padding:22px 0 14px" class="up"><p class="eyebrow">Model Performance</p><h1 class="title" style="margin-top:5px">TRACKER</h1></div>'

    if total == 0:
        c += '<div class="info-box">No settled results yet. Browse match pages — predictions auto-log and settle when results come in.</div>'
    else:
        hr_c = "var(--g)" if hr>=60 else "var(--w)" if hr>=50 else "var(--r)"
        c += f'''<div class="g2 up d1">
          <div class="sbox"><p class="sval" style="font-size:2.4rem;color:{hr_c}">{hr}%</p><p class="slbl">Hit Rate</p></div>
          <div class="sbox"><p class="sval g">{wins}</p><p class="slbl">Wins</p></div>
        </div>
        <div class="g2 up d1">
          <div class="sbox"><p class="sval r">{losses}</p><p class="slbl">Losses</p></div>
          <div class="sbox"><p class="sval">{pending}</p><p class="slbl">Pending</p></div>
        </div>'''

    if stats["by_market"]:
        c += '<div class="card up d2"><p class="sep" style="padding-top:0;margin-top:0">By Market</p>'
        for row in stats["by_market"]:
            mhr = round(row["wins"]/row["total"]*100,1) if row["total"] else 0
            hrc = "var(--g)" if mhr>=60 else "var(--w)" if mhr>=50 else "var(--r)"
            c += f'<div class="track-row"><div><p style="font-weight:700;color:var(--wh)">{row["market"]}</p><p style="font-size:.6rem;color:var(--t)">{row["total"]} tips · avg {round(row["avg_prob"] or 0,1)}%</p></div><p style="font-size:1.4rem;font-weight:900;color:{hrc}">{mhr}%</p></div>'
        c += '</div>'

    if stats["recent"]:
        c += '<div class="card up d3"><p class="sep" style="padding-top:0;margin-top:0">Recent Results</p>'
        for row in stats["recent"]:
            hs = row.get("actual_home_score"); as_ = row.get("actual_away_score")
            sc = f"{hs}–{as_}" if hs is not None else "—"
            c += f'<div class="track-row"><div style="flex:1"><p style="font-weight:700;color:var(--wh);font-size:.72rem">{row["home_team"]} vs {row["away_team"]}</p><p style="font-size:.6rem;color:var(--t)">{row["market"]} · {row["probability"]}% · {row["league_name"]}</p></div><div style="text-align:right"><p style="font-size:.62rem;color:var(--t);margin-bottom:3px">{sc}</p>{result_badge(row["result"])}</div></div>'
        c += '</div>'

    return render_template_string(LAYOUT, content=c, page="tracker")


# ── API endpoint for live fixture counts (used by JS) ─────────────────────────

@app.route("/api/counts")
def api_counts():
    all_matches = fetch_all_predictions()
    counts = {}
    for m in all_matches:
        l_id = m.get("event",{}).get("league",{}).get("id")
        if l_id:
            counts[l_id] = counts.get(l_id, 0) + 1
    return jsonify(counts)


# ── UTILITIES ─────────────────────────────────────────────────────────────────

def _try_settle(api_data, match_id):
    try:
        event  = api_data.get("event", {})
        status = event.get("status","")
        hs = event.get("home_score"); as_ = event.get("away_score")
        if status == "finished" and hs is not None and as_ is not None:
            for p in database.get_recent_pending():
                if p["match_id"] == match_id:
                    database.settle_prediction(match_id, p["market"], int(hs), int(as_))
    except Exception as e:
        print(f"[settle] {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
