from flask import Flask, render_template_string, request
import requests
from datetime import datetime, timedelta, timezone
import match_predictor
import os

app = Flask(__name__)

BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL  = "https://sports.bzzoiro.com/api"

# All leagues we support — keyed by their API league id
LEAGUES = [
    {"id": 1,  "name": "Premier League",   "country": "England",  "icon": "ENG"},
    {"id": 12, "name": "Championship",     "country": "England",  "icon": "ENG"},
    {"id": 3,  "name": "La Liga",          "country": "Spain",    "icon": "ESP"},
    {"id": 4,  "name": "Serie A",          "country": "Italy",    "icon": "ITA"},
    {"id": 5,  "name": "Bundesliga",       "country": "Germany",  "icon": "GER"},
    {"id": 14, "name": "Pro League",       "country": "Belgium",  "icon": "BEL"},
    {"id": 18, "name": "MLS",              "country": "USA",      "icon": "USA"},
    {"id": 2,  "name": "Liga Portugal",    "country": "Portugal", "icon": "POR"},
    {"id": 11, "name": "Süper Lig",        "country": "Turkey",   "icon": "TUR"},
    {"id": 13, "name": "Scottish Prem",    "country": "Scotland", "icon": "SCO"},
    {"id": 20, "name": "Liga MX",          "country": "Mexico",   "icon": "MEX"},
]
LEAGUE_MAP = {l["id"]: l for l in LEAGUES}

WAT_OFFSET = 1  # Nigeria = UTC+1

# ─── API helper ───────────────────────────────────────────────────────────────
def api_get(path, params=None):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=headers,
                         params=params, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API Error] {path} → {e}")
        return {}

def parse_dt(raw):
    """Parse any ISO datetime to UTC-aware datetime, then convert to WAT (UTC+1)."""
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc + timedelta(hours=WAT_OFFSET)
    except:
        return datetime.now(tz=timezone.utc)

def now_wat():
    return datetime.now(tz=timezone.utc) + timedelta(hours=WAT_OFFSET)

def group_matches_by_date(matches):
    """Group into TODAY / TOMORROW / future dates in WAT."""
    today    = now_wat().date()
    tomorrow = today + timedelta(days=1)
    groups   = {}
    for m in matches:
        event = m.get("event", {})
        dt    = parse_dt(event.get("event_date", ""))
        d     = dt.date()
        if d == today:
            key = "TODAY"
        elif d == tomorrow:
            key = "TOMORROW"
        else:
            key = dt.strftime("%-d %b").upper()
        groups.setdefault(key, []).append((dt, m))
    for k in groups:
        groups[k].sort(key=lambda x: x[0])
    return groups

# ─── HTML helpers ─────────────────────────────────────────────────────────────
def form_dots(form_list):
    if not form_list:
        return '<span style="color:#3d4451;font-size:0.65rem">No form data</span>'
    html = '<div class="dots">'
    for r in list(form_list)[-5:]:
        r = r.upper()
        html += f'<span class="dot dot-{r}">{r}</span>'
    html += '</div>'
    return html

def prob_bar(label, pct, color="green"):
    colors = {"green": "var(--g)", "blue": "var(--b)", "warn": "var(--w)"}
    c = colors.get(color, "var(--g)")
    return f"""
    <div class="prow">
      <div class="plabel"><span>{label}</span><span class="pval">{pct}%</span></div>
      <div class="ptrack"><div class="pfill" style="width:{pct}%;background:{c}"></div></div>
    </div>"""

def tag_badge(tag):
    cls = {"ELITE VALUE": "badge-green", "STRONG PICK": "badge-green",
           "QUANT EDGE": "badge-blue", "MONITOR": "badge-muted"}.get(tag, "badge-muted")
    return f'<span class="badge {cls}">{tag}</span>'

def trend_icon(trend):
    return {"RISING": "↑", "FALLING": "↓", "STABLE": "→"}.get(trend, "→")

# ─── Shared layout ────────────────────────────────────────────────────────────
LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>ProPredictor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#07090e; --s:#0e1219; --s2:#141820;
  --g:#00e676; --b:#2979ff; --w:#ff6d00; --r:#f44336;
  --t:#8892a4; --wh:#e8edf5;
  --bdr:rgba(255,255,255,0.07);
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--t);font-family:'Inter',sans-serif;font-size:13px;min-height:100vh;padding-bottom:90px}
a{text-decoration:none;color:inherit}

/* Nav */
nav{position:sticky;top:0;z-index:99;background:rgba(7,9,14,0.9);backdrop-filter:blur(16px);border-bottom:1px solid var(--bdr)}
.nav-i{max-width:480px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;padding:13px 16px}
.logo{font-family:'Bebas Neue',sans-serif;font-size:1.35rem;letter-spacing:1px;color:var(--wh)}
.logo em{color:var(--g);font-style:normal}
.nav-links{display:flex;gap:6px}
.npill{font-size:0.65rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:5px 12px;border-radius:50px;border:1px solid var(--bdr);color:var(--t);transition:all .2s}
.npill:hover,.npill.on{border-color:var(--g);color:var(--g);background:rgba(0,230,118,.08)}

/* Shell */
.shell{max-width:480px;margin:0 auto;padding:0 14px}

/* Cards */
.card{background:var(--s);border:1px solid var(--bdr);border-radius:16px;padding:18px;margin-bottom:10px}
.card-link{display:block;transition:transform .15s}
.card-link:active{transform:scale(.98)}

/* Badges */
.badge{display:inline-block;font-size:0.58rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:3px 9px;border-radius:50px}
.badge-green{background:rgba(0,230,118,.12);color:var(--g);border:1px solid rgba(0,230,118,.25)}
.badge-blue{background:rgba(41,121,255,.12);color:var(--b);border:1px solid rgba(41,121,255,.25)}
.badge-orange{background:rgba(255,109,0,.12);color:var(--w);border:1px solid rgba(255,109,0,.25)}
.badge-muted{background:rgba(136,146,164,.08);color:var(--t);border:1px solid var(--bdr)}

/* Typography */
.display{font-family:'Bebas Neue',sans-serif;color:var(--wh);line-height:1}
.eyebrow{font-size:0.58rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--t);margin-bottom:4px}
.section-sep{font-size:0.58rem;letter-spacing:2.5px;text-transform:uppercase;color:var(--t);padding:20px 0 10px;border-bottom:1px solid var(--bdr);margin-bottom:12px}

/* Prob bars */
.prow{margin-bottom:11px}
.plabel{display:flex;justify-content:space-between;margin-bottom:4px;font-size:0.68rem}
.pval{color:var(--wh);font-weight:600}
.ptrack{height:4px;background:rgba(255,255,255,.05);border-radius:50px;overflow:hidden}
.pfill{height:100%;border-radius:50px;transition:width .7s cubic-bezier(.4,0,.2,1)}

/* Form dots */
.dots{display:flex;gap:4px}
.dot{width:22px;height:22px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:0.6rem;font-weight:700}
.dot-W{background:rgba(0,230,118,.15);color:var(--g)}
.dot-D{background:rgba(41,121,255,.15);color:var(--b)}
.dot-L{background:rgba(244,67,54,.15);color:var(--r)}

/* Date tabs */
.tabs{display:flex;gap:7px;overflow-x:auto;padding-bottom:4px;margin-bottom:14px;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{flex-shrink:0;font-size:0.65rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:6px 13px;border-radius:50px;border:1px solid var(--bdr);color:var(--t);cursor:pointer;transition:all .2s;white-space:nowrap}
.tab:hover,.tab.on{border-color:var(--g);color:var(--g);background:rgba(0,230,118,.08)}

/* Fixture rows */
.fix-wrap{background:var(--s);border:1px solid var(--bdr);border-radius:16px;overflow:hidden;margin-bottom:10px}
.fix-row{display:flex;align-items:center;padding:13px 16px;border-bottom:1px solid var(--bdr);transition:background .15s;cursor:pointer}
.fix-row:last-child{border-bottom:none}
.fix-row:hover{background:rgba(255,255,255,.02)}
.fix-row:active{background:rgba(0,230,118,.04)}
.fix-time{font-size:0.7rem;color:var(--t);min-width:38px;font-weight:600}
.fix-teams{flex:1;text-align:center;font-size:0.85rem;font-weight:700;color:var(--wh);padding:0 8px}
.fix-vs{color:var(--t);font-size:0.65rem;margin:0 4px;font-weight:400}
.fix-arr{color:var(--g);font-size:0.7rem;min-width:14px;text-align:right}

/* Back */
.back{display:inline-flex;align-items:center;gap:5px;font-size:0.65rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);padding:14px 0 20px;transition:color .2s}
.back:hover{color:var(--wh)}

/* Rec box */
.rec-box{background:linear-gradient(135deg,rgba(0,230,118,.07),rgba(41,121,255,.05));border:1px solid rgba(0,230,118,.18);border-radius:18px;padding:20px;margin-bottom:10px}
.rec-market{font-family:'Bebas Neue',sans-serif;font-size:2rem;color:var(--wh);letter-spacing:.5px;margin:6px 0 2px}
.rec-pct{font-family:'Bebas Neue',sans-serif;font-size:3.2rem;color:var(--g);letter-spacing:-1px;line-height:1}

/* Stat grid */
.sgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}
.sbox{background:var(--s2);border:1px solid var(--bdr);border-radius:13px;padding:14px;text-align:center}
.sval{font-family:'Bebas Neue',sans-serif;font-size:1.8rem;color:var(--wh);line-height:1}
.sval.g{color:var(--g)} .sval.b{color:var(--b)} .sval.w{color:var(--w)}
.slbl{font-size:0.58rem;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);margin-top:3px}

/* Momentum bar */
.mbar-wrap{position:relative;height:8px;background:rgba(255,255,255,.06);border-radius:50px;overflow:hidden;margin:10px 0}
.mbar-h{position:absolute;left:0;top:0;height:100%;background:var(--g);border-radius:50px;transition:width .8s}
.mbar-a{position:absolute;right:0;top:0;height:100%;background:var(--b);border-radius:50px;transition:width .8s}

/* Upset ring */
.upset-row{display:flex;align-items:center;gap:12px;padding:12px;background:var(--s2);border-radius:12px;border:1px solid var(--bdr)}

/* ACCA row */
.acca-row{display:flex;justify-content:space-between;align-items:center;padding:13px 16px;border-bottom:1px solid var(--bdr)}
.acca-row:last-child{border-bottom:none}
.acca-match{font-size:0.82rem;font-weight:700;color:var(--wh)}
.acca-mkt{font-size:0.6rem;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);margin-top:2px}
.acca-odds{font-family:'Bebas Neue',sans-serif;font-size:1.3rem;color:var(--g)}

/* Conf ring */
.cring{position:relative;width:72px;height:72px;flex-shrink:0}
.cring svg{transform:rotate(-90deg)}
.cring-num{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:'Bebas Neue',sans-serif;font-size:1rem;color:var(--wh)}

/* Edge pill */
.edge{font-size:0.6rem;font-weight:700;padding:2px 8px;border-radius:50px}
.edge-pos{background:rgba(0,230,118,.12);color:var(--g)}
.edge-neg{background:rgba(244,67,54,.12);color:var(--r)}

/* League card */
.league-card{background:var(--s);border:1px solid var(--bdr);border-radius:16px;padding:18px 20px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;transition:border-color .2s}
.league-card:hover{border-color:rgba(255,255,255,.15)}
.league-card:active{transform:scale(.98)}

/* Animations */
@keyframes fu{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.fu{animation:fu .35s ease both}
.d1{animation-delay:.05s}.d2{animation-delay:.1s}.d3{animation-delay:.15s}.d4{animation-delay:.2s}

/* Empty */
.empty{text-align:center;padding:50px 20px;color:var(--t);font-size:0.75rem;letter-spacing:1px}
</style>
</head>
<body>
<nav>
  <div class="nav-i">
    <a href="/" class="logo">PRO<em>PRED</em></a>
    <div class="nav-links">
      <a href="/" class="npill {{ 'on' if page=='home' else '' }}">Leagues</a>
      <a href="/acca" class="npill {{ 'on' if page=='acca' else '' }}">ACCA</a>
    </div>
  </div>
</nav>
<div class="shell">{{ content|safe }}</div>
</body>
</html>"""

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    c = '<div style="padding:28px 0 16px" class="fu">'
    c += '<p class="eyebrow">Football Intelligence</p>'
    c += '<h1 class="display" style="font-size:2.8rem;margin-top:4px">SELECT<br>YOUR LEAGUE</h1>'
    c += '</div>'
    for i, l in enumerate(LEAGUES):
        d = f"d{min(i+1,4)}"
        c += f"""
        <a href="/league/{l['id']}" class="league-card fu {d}">
          <div>
            <p class="eyebrow">{l['icon']} · {l['country']}</p>
            <p class="display" style="font-size:1.5rem;margin-top:3px">{l['name']}</p>
          </div>
          <span style="color:var(--t);font-size:1.1rem">›</span>
        </a>"""
    return render_template_string(LAYOUT, content=c, page="home")


@app.route("/league/<int:l_id>")
def league_page(l_id):
    league = LEAGUE_MAP.get(l_id, {"name": "League", "icon": "—", "country": ""})

    # Fetch ALL predictions — API ignores ?league filter
    data    = api_get("/predictions/")
    all_matches = data.get("results", [])

    # ── CLIENT-SIDE FILTER by league id ──
    matches = [m for m in all_matches
               if m.get("event", {}).get("league", {}).get("id") == l_id]

    back = '<a href="/" class="back">← Leagues</a>'

    if not matches:
        c = f'{back}<h2 class="display" style="font-size:2rem;margin-bottom:20px">{league["name"]}</h2>'
        c += '<div class="empty">No fixtures available right now</div>'
        return render_template_string(LAYOUT, content=c, page="league")

    groups    = group_matches_by_date(matches)
    date_keys = list(groups.keys())
    active    = request.args.get("tab", date_keys[0] if date_keys else "TODAY")

    # Date tabs
    tabs = '<div class="tabs">'
    for k in date_keys:
        on = "on" if k == active else ""
        tabs += f'<a href="/league/{l_id}?tab={k}" class="tab {on}">{k} ({len(groups[k])})</a>'
    tabs += '</div>'

    # Fixture list
    rows = '<div class="fix-wrap">'
    shown = groups.get(active, [])
    if not shown:
        rows += '<div class="empty" style="padding:30px">No matches this day</div>'
    for dt, m in shown:
        event = m.get("event", {})
        h     = event.get("home_team", "?")
        a     = event.get("away_team", "?")
        mid   = m.get("id", 0)
        rows += f"""
        <a href="/match/{mid}" class="fix-row">
          <span class="fix-time">{dt.strftime('%H:%M')}</span>
          <span class="fix-teams">{h}<span class="fix-vs">vs</span>{a}</span>
          <span class="fix-arr">›</span>
        </a>"""
    rows += '</div>'

    c  = back
    c += f'<div class="fu" style="margin-bottom:20px">'
    c += f'<p class="eyebrow">{league["icon"]} · {league["country"]}</p>'
    c += f'<h2 class="display" style="font-size:2rem;margin-top:4px">{league["name"]}</h2>'
    c += f'<p style="font-size:0.65rem;color:var(--t);margin-top:5px;letter-spacing:1px">{len(matches)} FIXTURES FOUND</p>'
    c += f'</div>{tabs}{rows}'
    return render_template_string(LAYOUT, content=c, page="league")


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
    h      = event.get("home_team", "Home")
    a      = event.get("away_team", "Away")
    dt     = parse_dt(event.get("event_date", ""))

    res = match_predictor.analyze_match(data, l_id)
    if not res:
        return render_template_string(LAYOUT,
            content=f'<a href="/league/{l_id}" class="back">← {l_info["name"]}</a><div class="empty">Analysis unavailable</div>',
            page="match")

    ox  = res["1x2"]
    mkts = res["markets"]
    mom  = res["momentum"]
    ups  = res["upset"]
    frm  = res["form"]
    std  = res["standings"]

    # Confidence ring color
    conf = res["confidence"]
    ring_color = "#00e676" if conf >= 60 else "#2979ff" if conf >= 45 else "#ff6d00"
    r, cx, cy   = 30, 36, 36
    import math
    circ = 2 * math.pi * r
    dash = circ * (conf / 100)

    # Edge pill
    edge = res["rec"].get("edge")
    if edge is not None:
        edge_html = f'<span class="edge {"edge-pos" if edge > 0 else "edge-neg"}">{"+" if edge > 0 else ""}{edge}% edge</span>'
    else:
        edge_html = ''

    # Momentum bar widths — normalize so they sum ~100
    total_mom = max(mom["home"] + mom["away"], 1)
    mh_w = round(mom["home"] / total_mom * 100)
    ma_w = round(mom["away"] / total_mom * 100)

    # Upset color map
    ups_color = {"warn": "var(--w)", "blue": "var(--b)", "muted": "var(--t)"}.get(ups["color"], "var(--t)")

    c  = f'<a href="/league/{l_id}" class="back">← {l_info["name"]}</a>'

    # Header
    c += f"""
    <div class="fu" style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:18px">
      <div>
        {tag_badge(res['tag'])}
        <h2 class="display" style="font-size:1.9rem;margin-top:8px;line-height:1.05">
          {h}<br><span style="color:var(--t);font-size:1rem;font-family:'Inter',sans-serif;font-weight:400">vs</span><br>{a}
        </h2>
        <p style="font-size:0.62rem;color:var(--t);margin-top:7px;letter-spacing:1.2px">
          {dt.strftime('%-d %b %Y')} · {dt.strftime('%H:%M')} WAT
        </p>
      </div>
      <div class="cring fu d1">
        <svg width="72" height="72" viewBox="0 0 72 72">
          <circle cx="{cx}" cy="{cy}" r="{r}" stroke="rgba(255,255,255,.06)" stroke-width="5" fill="none"/>
          <circle cx="{cx}" cy="{cy}" r="{r}" stroke="{ring_color}" stroke-width="5" fill="none"
            stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>
        </svg>
        <div class="cring-num">{conf:.0f}%</div>
      </div>
    </div>"""

    # Rec box
    c += f"""
    <div class="rec-box fu d1">
      <p class="eyebrow">⚡ Best Market</p>
      <p class="rec-market">{res['rec']['t']}</p>
      <div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap">
        <p class="rec-pct">{res['rec']['p']}%</p>
        <div>
          <p style="font-size:0.58rem;letter-spacing:1.5px;color:var(--t)">FAIR ODDS</p>
          <p class="display" style="font-size:1.5rem">{res['rec']['odds']}</p>
        </div>
        {f'<div>{edge_html}</div>' if edge_html else ''}
      </div>
      <p style="font-size:0.65rem;color:var(--t);margin-top:8px">
        Also consider: <strong style="color:var(--wh)">{res['second']['t']}</strong> ({res['second']['p']}%)
      </p>
    </div>"""

    # xG + likely score
    c += f"""
    <div class="sgrid fu d2">
      <div class="sbox">
        <p class="sval g">{res['xg_h']}</p>
        <p class="slbl">xG {h.split()[0]}</p>
      </div>
      <div class="sbox">
        <p class="sval b">{res['xg_a']}</p>
        <p class="slbl">xG {a.split()[0]}</p>
      </div>
    </div>
    <div class="card fu d2" style="text-align:center;padding:14px 18px">
      <p class="eyebrow">Most Likely Score</p>
      <p class="display" style="font-size:2.2rem;color:var(--wh);margin-top:2px">{res['likely_score']}</p>
    </div>"""

    # 1X2
    c += f"""
    <div class="card fu d2">
      <p class="section-sep" style="padding-top:0;margin-top:0">1 × 2</p>
      {prob_bar('Home Win', ox['home'])}
      {prob_bar('Draw', ox['draw'], 'blue')}
      {prob_bar('Away Win', ox['away'], 'warn')}
    </div>"""

    # Markets
    c += f"""
    <div class="card fu d3">
      <p class="section-sep" style="padding-top:0;margin-top:0">Goal Markets</p>
      {prob_bar('Over 1.5', mkts['over_15'])}
      {prob_bar('Over 2.5', mkts['over_25'])}
      {prob_bar('Over 3.5', mkts['over_35'])}
      {prob_bar('Under 2.5', mkts['under_25'], 'warn')}
      {prob_bar('BTTS', mkts['btts'], 'blue')}
    </div>"""

    # Momentum
    c += f"""
    <div class="card fu d3">
      <p class="section-sep" style="padding-top:0;margin-top:0">Momentum</p>
      <div style="display:flex;justify-content:space-between;font-size:0.68rem;margin-bottom:6px">
        <span style="color:var(--g)">{trend_icon(mom['h_trend'])} {h.split()[0]} ({mom['home']}%)</span>
        <span style="color:var(--b)">{a.split()[0]} ({mom['away']}%) {trend_icon(mom['a_trend'])}</span>
      </div>
      <div class="mbar-wrap">
        <div class="mbar-h" style="width:{mh_w}%"></div>
        <div class="mbar-a" style="width:{ma_w}%"></div>
      </div>
      <p style="font-size:0.65rem;color:var(--t);margin-top:8px">{mom['narrative']}</p>
    </div>"""

    # Upset index
    c += f"""
    <div class="card fu d3">
      <p class="section-sep" style="padding-top:0;margin-top:0">Upset Analysis</p>
      <div class="upset-row">
        <div style="flex:1">
          <p style="font-size:0.65rem;font-weight:700;color:{ups_color};letter-spacing:1px">{ups['label']}</p>
          <p style="font-size:0.62rem;color:var(--t);margin-top:3px">Underdog index: {ups['index']}%</p>
        </div>
        <div class="sbox" style="min-width:60px;padding:10px">
          <p class="sval" style="font-size:1.5rem;color:{ups_color}">{ups['index']}</p>
        </div>
      </div>
    </div>"""

    # Play style
    c += f"""
    <div class="card fu d4">
      <p class="section-sep" style="padding-top:0;margin-top:0">Style Profile</p>
      <p style="font-size:0.72rem;line-height:1.6;color:var(--t)">{res['style']}</p>
    </div>"""

    # Form & standings
    c += f"""
    <div class="card fu d4">
      <p class="section-sep" style="padding-top:0;margin-top:0">Form · Last 5</p>
      <div style="display:flex;flex-direction:column;gap:12px;margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:0.78rem;font-weight:700;color:var(--wh)">{h}</span>
          {form_dots(frm['home'])}
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:0.78rem;font-weight:700;color:var(--wh)">{a}</span>
          {form_dots(frm['away'])}
        </div>
      </div>
      <div style="display:flex;gap:20px;padding-top:14px;border-top:1px solid var(--bdr)">
        <div><p class="eyebrow">Standing</p>
          <p class="display" style="font-size:1.4rem">{'#'+str(std['home']) if std['home'] else '—'}</p>
          <p style="font-size:0.6rem;color:var(--t)">{h.split()[0]}</p></div>
        <div><p class="eyebrow">Standing</p>
          <p class="display" style="font-size:1.4rem">{'#'+str(std['away']) if std['away'] else '—'}</p>
          <p style="font-size:0.6rem;color:var(--t)">{a.split()[0]}</p></div>
      </div>
    </div>"""

    return render_template_string(LAYOUT, content=c, page="match")


@app.route("/acca")
def acca():
    data    = api_get("/predictions/")
    matches = data.get("results", [])
    picks, combined = match_predictor.pick_acca(matches, n=5, min_prob=52.0)

    c  = '<div style="padding:28px 0 16px" class="fu">'
    c += '<p class="eyebrow">Daily Best Picks</p>'
    c += '<h1 class="display" style="font-size:2.8rem;margin-top:4px">ACCA<br>BUILDER</h1>'
    c += '</div>'

    if not picks:
        c += '<div class="empty">No qualifying picks today — lower the threshold or check back later</div>'
        return render_template_string(LAYOUT, content=c, page="acca")

    c += '<div class="fix-wrap fu d1">'
    for p in picks:
        event = p["match"].get("event", {})
        h     = event.get("home_team", "?")
        a     = event.get("away_team", "?")
        res   = p["result"]
        mid   = p["match"].get("id", 0)
        l_id  = p["league_id"]
        l_info = LEAGUE_MAP.get(l_id, {"icon": "—"})
        edge  = res["rec"].get("edge")
        edge_str = f' +{edge}% edge' if edge and edge > 0 else ''
        c += f"""
        <a href="/match/{mid}" class="acca-row">
          <div>
            <p style="font-size:0.58rem;color:var(--t);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:3px">{l_info.get('icon','—')} {l_info.get('name','')}</p>
            <p class="acca-match">{h} vs {a}</p>
            <p class="acca-mkt">{res['rec']['t']} · {res['rec']['p']}%{edge_str}</p>
          </div>
          <p class="acca-odds">{res['rec']['odds']}</p>
        </a>"""
    c += '</div>'

    c += f"""
    <div class="rec-box fu d2" style="text-align:center;margin-top:12px">
      <p class="eyebrow">Combined Odds</p>
      <p class="rec-pct" style="font-size:4rem">{combined}</p>
      <p style="font-size:0.62rem;color:var(--t);margin-top:4px;letter-spacing:1px">{len(picks)}-FOLD ACCUMULATOR</p>
    </div>
    <p style="font-size:0.6rem;color:var(--t);text-align:center;padding:14px;letter-spacing:1px">
      Fair odds shown · Gamble responsibly
    </p>"""

    return render_template_string(LAYOUT, content=c, page="acca")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
