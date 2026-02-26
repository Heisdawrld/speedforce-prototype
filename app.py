from flask import Flask, render_template_string, request, jsonify
import requests
from datetime import datetime, timedelta, timezone
import match_predictor
import os

app = Flask(__name__)

BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL  = "https://sports.bzzoiro.com/api"

LEAGUES = [
    {"id": 1,  "name": "Premier League",  "geo": "England",  "icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"id": 12, "name": "Championship",    "geo": "England",  "icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"id": 4,  "name": "Serie A",         "geo": "Italy",    "icon": "🇮🇹"},
    {"id": 5,  "name": "Bundesliga",      "geo": "Germany",  "icon": "🇩🇪"},
    {"id": 14, "name": "Pro League",      "geo": "Belgium",  "icon": "🇧🇪"},
    {"id": 18, "name": "MLS",             "geo": "USA",      "icon": "🇺🇸"},
]

# ─────────────────────────────────────────────────────────────────────────────
# SHARED LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>ProPredictor</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,400;0,700;0,900;1,900&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg:      #06080c;
      --surface: #0d1117;
      --border:  rgba(255,255,255,0.06);
      --accent:  #00e676;
      --accent2: #00b0ff;
      --warn:    #ff6d00;
      --muted:   #3d4451;
      --text:    #c9d1d9;
      --white:   #f0f6fc;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    html { scroll-behavior: smooth; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'DM Mono', monospace;
      font-size: 13px;
      min-height: 100vh;
      padding-bottom: 80px;
    }
    a { text-decoration: none; color: inherit; }

    /* ── Shell ── */
    .shell { max-width: 480px; margin: 0 auto; padding: 0 16px; }

    /* ── Nav ── */
    nav {
      position: sticky; top: 0; z-index: 100;
      background: rgba(6,8,12,0.85);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--border);
    }
    .nav-inner {
      max-width: 480px; margin: 0 auto;
      display: flex; justify-content: space-between; align-items: center;
      padding: 14px 16px;
    }
    .logo {
      font-family: 'Barlow Condensed', sans-serif;
      font-style: italic;
      font-weight: 900;
      font-size: 1.3rem;
      letter-spacing: -0.5px;
      color: var(--white);
    }
    .logo em { color: var(--accent); font-style: normal; }
    .nav-links { display: flex; gap: 6px; }
    .nav-pill {
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 700;
      font-size: 0.7rem;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      padding: 6px 12px;
      border-radius: 100px;
      border: 1px solid var(--border);
      color: var(--muted);
      transition: all 0.2s;
    }
    .nav-pill:hover, .nav-pill.active {
      border-color: var(--accent);
      color: var(--accent);
      background: rgba(0,230,118,0.08);
    }

    /* ── Cards ── */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px;
      margin-bottom: 12px;
      transition: border-color 0.2s;
    }
    .card:hover { border-color: rgba(255,255,255,0.12); }
    .card-link { display: block; }
    .card-link:active { transform: scale(0.98); }

    /* ── Labels ── */
    .eyebrow {
      font-size: 0.58rem;
      font-weight: 500;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 4px;
    }
    .pill {
      display: inline-block;
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 700;
      font-size: 0.65rem;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      padding: 4px 10px;
      border-radius: 100px;
    }
    .pill-green  { background: rgba(0,230,118,0.12);  color: var(--accent); border: 1px solid rgba(0,230,118,0.25); }
    .pill-blue   { background: rgba(0,176,255,0.12);  color: var(--accent2); border: 1px solid rgba(0,176,255,0.25); }
    .pill-orange { background: rgba(255,109,0,0.12);  color: var(--warn); border: 1px solid rgba(255,109,0,0.25); }
    .pill-muted  { background: rgba(61,68,81,0.3);    color: var(--muted); border: 1px solid var(--border); }

    /* ── Headings ── */
    .display {
      font-family: 'Barlow Condensed', sans-serif;
      font-style: italic;
      font-weight: 900;
      line-height: 0.95;
      color: var(--white);
    }

    /* ── Probability bars ── */
    .prob-row { margin-bottom: 14px; }
    .prob-label { display: flex; justify-content: space-between; margin-bottom: 5px; }
    .prob-name  { font-size: 0.68rem; letter-spacing: 1px; text-transform: uppercase; color: var(--muted); }
    .prob-pct   { font-size: 0.7rem; font-weight: 500; color: var(--white); }
    .prob-track {
      height: 5px;
      background: rgba(255,255,255,0.05);
      border-radius: 100px;
      overflow: hidden;
    }
    .prob-fill {
      height: 100%;
      border-radius: 100px;
      background: linear-gradient(90deg, var(--accent2), var(--accent));
      transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .prob-fill.warm { background: linear-gradient(90deg, var(--warn), #ffd600); }

    /* ── Form dots ── */
    .form-dots { display: flex; gap: 4px; }
    .dot {
      width: 22px; height: 22px;
      border-radius: 6px;
      display: flex; align-items: center; justify-content: center;
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 900;
      font-size: 0.65rem;
    }
    .dot-W { background: rgba(0,230,118,0.18); color: var(--accent); }
    .dot-D { background: rgba(0,176,255,0.15); color: var(--accent2); }
    .dot-L { background: rgba(255,109,0,0.15); color: var(--warn); }

    /* ── Section header ── */
    .section-head {
      font-size: 0.58rem;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: var(--muted);
      margin: 28px 0 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border);
    }

    /* ── Stats grid ── */
    .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .stat-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      text-align: center;
    }
    .stat-val {
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 900;
      font-size: 2rem;
      color: var(--white);
      line-height: 1;
    }
    .stat-val.accent { color: var(--accent); }
    .stat-val.blue   { color: var(--accent2); }
    .stat-label { font-size: 0.58rem; letter-spacing: 1.5px; color: var(--muted); text-transform: uppercase; margin-top: 4px; }

    /* ── Hero rec box ── */
    .rec-box {
      background: linear-gradient(135deg, rgba(0,230,118,0.08), rgba(0,176,255,0.06));
      border: 1px solid rgba(0,230,118,0.2);
      border-radius: 20px;
      padding: 24px;
      margin-bottom: 12px;
    }
    .rec-market {
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 900;
      font-style: italic;
      font-size: 2.2rem;
      color: var(--white);
      letter-spacing: -0.5px;
      line-height: 1;
      margin: 8px 0;
    }
    .rec-pct {
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 900;
      font-size: 3.5rem;
      color: var(--accent);
      letter-spacing: -2px;
      line-height: 1;
    }

    /* ── Back link ── */
    .back {
      display: inline-flex; align-items: center; gap: 6px;
      font-size: 0.65rem;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: var(--muted);
      padding: 12px 0 24px;
      transition: color 0.2s;
    }
    .back:hover { color: var(--white); }

    /* ── Date tab ── */
    .date-tabs { display: flex; gap: 8px; margin-bottom: 16px; overflow-x: auto; padding-bottom: 4px; }
    .date-tabs::-webkit-scrollbar { display: none; }
    .date-tab {
      flex-shrink: 0;
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 700;
      font-size: 0.7rem;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      padding: 7px 14px;
      border-radius: 100px;
      border: 1px solid var(--border);
      color: var(--muted);
      cursor: pointer;
      transition: all 0.2s;
    }
    .date-tab.active, .date-tab:hover {
      border-color: var(--accent);
      color: var(--accent);
      background: rgba(0,230,118,0.08);
    }

    /* ── Fixture row ── */
    .fixture-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 18px;
      border-bottom: 1px solid var(--border);
      transition: background 0.15s;
      cursor: pointer;
    }
    .fixture-row:last-child { border-bottom: none; }
    .fixture-row:hover { background: rgba(255,255,255,0.02); }
    .fixture-row:active { background: rgba(0,230,118,0.04); }
    .fix-time { font-size: 0.65rem; color: var(--muted); min-width: 40px; }
    .fix-teams {
      flex: 1;
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 700;
      font-size: 1rem;
      color: var(--white);
      text-align: center;
      letter-spacing: 0.3px;
    }
    .fix-vs { color: var(--muted); font-size: 0.75rem; margin: 0 4px; }
    .fix-arrow { color: var(--accent); font-size: 0.7rem; min-width: 20px; text-align: right; }

    /* ── ACCA slip ── */
    .acca-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
    }
    .acca-row:last-child { border-bottom: none; }
    .acca-match {
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 700;
      font-size: 0.9rem;
      color: var(--white);
      letter-spacing: 0.3px;
    }
    .acca-market {
      font-size: 0.6rem;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: var(--muted);
      margin-top: 2px;
    }
    .acca-odds {
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 900;
      font-size: 1.3rem;
      color: var(--accent);
    }

    /* ── Empty state ── */
    .empty { text-align: center; padding: 60px 20px; color: var(--muted); font-size: 0.75rem; letter-spacing: 1px; }

    /* ── Animations ── */
    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(16px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .fade-up { animation: fadeUp 0.4s ease both; }
    .delay-1 { animation-delay: 0.05s; }
    .delay-2 { animation-delay: 0.10s; }
    .delay-3 { animation-delay: 0.15s; }
    .delay-4 { animation-delay: 0.20s; }

    /* ── Confidence arc ── */
    .conf-ring { position: relative; width: 80px; height: 80px; flex-shrink: 0; }
    .conf-ring svg { transform: rotate(-90deg); }
    .conf-num {
      position: absolute; inset: 0;
      display: flex; align-items: center; justify-content: center;
      font-family: 'Barlow Condensed', sans-serif;
      font-weight: 900;
      font-size: 1.1rem;
      color: var(--white);
    }
  </style>
</head>
<body>

<nav>
  <div class="nav-inner">
    <a href="/" class="logo">PRO<em>PRED</em></a>
    <div class="nav-links">
      <a href="/" class="nav-pill {{ 'active' if page == 'home' else '' }}">Leagues</a>
      <a href="/acca" class="nav-pill {{ 'active' if page == 'acca' else '' }}">ACCA</a>
    </div>
  </div>
</nav>

<div class="shell">
  {{ content | safe }}
</div>

<script>
// Animate probability bars on load
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.prob-fill[data-w]').forEach(el => {
    el.style.width = '0%';
    setTimeout(() => { el.style.width = el.dataset.w + '%'; }, 100);
  });
});
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def api_get(path, params=None):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API Error] {path} → {e}")
        return {}

def fmt_dt(raw, offset_h=1):
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        dt = dt + timedelta(hours=offset_h)
        return dt
    except:
        return datetime.now(tz=timezone.utc)

def group_by_date(matches):
    now   = datetime.now(tz=timezone.utc)
    today = now.date()
    tom   = today + timedelta(days=1)
    groups = {}
    for m in matches:
        event = m.get("event", {})
        dt    = fmt_dt(event.get("start_time", ""))
        d     = dt.date()
        if d == today:
            key = "TODAY"
        elif d == tom:
            key = "TOMORROW"
        else:
            key = dt.strftime("%-d %b").upper()
        groups.setdefault(key, []).append((dt, m))
    for k in groups:
        groups[k].sort(key=lambda x: x[0])
    return groups

def form_dots_html(form_list):
    html = '<div class="form-dots">'
    for r in list(form_list)[-5:]:
        html += f'<div class="dot dot-{r}">{r}</div>'
    html += '</div>'
    return html

def prob_bar(label, pct, warm=False):
    fill_class = "prob-fill warm" if warm else "prob-fill"
    return f"""
    <div class="prob-row">
      <div class="prob-label">
        <span class="prob-name">{label}</span>
        <span class="prob-pct">{pct}%</span>
      </div>
      <div class="prob-track">
        <div class="{fill_class}" data-w="{pct}" style="width:{pct}%"></div>
      </div>
    </div>"""

def conf_ring_html(value):
    r = 34; cx = 40; cy = 40
    circ = 2 * 3.14159 * r
    dash = circ * (value / 100)
    color = "#00e676" if value >= 60 else "#00b0ff" if value >= 45 else "#ff6d00"
    return f"""
    <div class="conf-ring">
      <svg width="80" height="80" viewBox="0 0 80 80">
        <circle cx="{cx}" cy="{cy}" r="{r}" stroke="rgba(255,255,255,0.05)" stroke-width="5" fill="none"/>
        <circle cx="{cx}" cy="{cy}" r="{r}" stroke="{color}" stroke-width="5" fill="none"
          stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-linecap="round"/>
      </svg>
      <div class="conf-num">{value}%</div>
    </div>"""

def tag_pill(tag):
    cls = "pill-green" if tag in ("ELITE VALUE","STRONG PICK") else \
          "pill-blue"  if tag == "QUANT EDGE" else "pill-muted"
    return f'<span class="pill {cls}">{tag}</span>'

# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    content = """
    <div style="padding: 32px 0 20px">
      <p class="eyebrow" style="margin-bottom:8px">Football Intelligence</p>
      <h1 class="display" style="font-size:3rem">SELECT<br>YOUR<br>LEAGUE</h1>
    </div>
    """
    for i, l in enumerate(LEAGUES):
        delay = f"delay-{min(i+1,4)}"
        content += f"""
        <a href="/league/{l['id']}" class="card card-link fade-up {delay}">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
              <p class="eyebrow">{l['icon']} {l['geo']}</p>
              <p class="display" style="font-size:1.6rem;margin-top:4px">{l['name']}</p>
            </div>
            <span style="color:var(--muted);font-size:1rem">›</span>
          </div>
        </a>"""
    return render_template_string(LAYOUT, content=content, page="home")


@app.route("/league/<int:l_id>")
def league_page(l_id):
    league = next((l for l in LEAGUES if l["id"] == l_id), {"name": "League", "icon": ""})
    data   = api_get(f"/predictions/", {"league": l_id})
    matches = data.get("results", [])

    if not matches:
        content = f"""
        <a href="/" class="back">← Leagues</a>
        <h2 class="display" style="font-size:2.2rem;margin-bottom:24px">{league['name']}</h2>
        <div class="empty">No fixtures available right now</div>"""
        return render_template_string(LAYOUT, content=content, page="league")

    groups = group_by_date(matches)
    date_keys = list(groups.keys())
    active_tab = request.args.get("tab", date_keys[0] if date_keys else "TODAY")

    # Date tabs
    tabs_html = '<div class="date-tabs">'
    for k in date_keys:
        act = "active" if k == active_tab else ""
        count = len(groups[k])
        tabs_html += f'<a href="/league/{l_id}?tab={k}" class="date-tab {act}">{k} <span style="opacity:0.5">({count})</span></a>'
    tabs_html += '</div>'

    # Fixtures for active tab
    fixtures_html = '<div class="card" style="padding:0;overflow:hidden">'
    shown = groups.get(active_tab, [])
    if not shown:
        fixtures_html += '<div class="empty">No matches</div>'
    for dt, m in shown:
        event = m.get("event", {})
        h     = event.get("home_team", "?")
        a     = event.get("away_team", "?")
        mid   = m.get("id", 0)
        fixtures_html += f"""
        <a href="/match/{mid}" class="fixture-row">
          <span class="fix-time">{dt.strftime('%H:%M')}</span>
          <span class="fix-teams">{h}<span class="fix-vs">vs</span>{a}</span>
          <span class="fix-arrow">›</span>
        </a>"""
    fixtures_html += '</div>'

    content = f"""
    <a href="/" class="back">← Leagues</a>
    <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:24px">
      <h2 class="display" style="font-size:2.2rem">{league['icon']}<br>{league['name']}</h2>
      <span style="color:var(--muted);font-size:0.65rem;letter-spacing:1px">{len(matches)} FIXTURES</span>
    </div>
    {tabs_html}
    {fixtures_html}"""
    return render_template_string(LAYOUT, content=content, page="league")


@app.route("/match/<int:match_id>")
def match_display(match_id):
    data   = api_get(f"/predictions/{match_id}/")
    if not data:
        return render_template_string(LAYOUT,
            content='<a href="/" class="back">← Home</a><div class="empty">Match data unavailable</div>',
            page="match")

    event  = data.get("event", {})
    h      = event.get("home_team", "Home")
    a      = event.get("away_team", "Away")
    l_id   = data.get("league_id", 1)
    l_name = data.get("league_name", "")
    dt     = fmt_dt(event.get("start_time", ""))

    res = match_predictor.analyze_match(data, l_id)

    back_url = f"/league/{l_id}"
    one_x_two = res["1x2"]
    mkts      = res["markets"]
    form      = res["form"]
    standings = res["standings"]

    content = f"""
    <a href="{back_url}" class="back">← {l_name}</a>

    <div class="fade-up" style="margin-bottom:24px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          {tag_pill(res['tag'])}
          <h2 class="display" style="font-size:2rem;margin-top:10px;line-height:1.1">
            {h}<br>
            <span style="color:var(--muted);font-size:1.1rem;font-style:normal">vs</span><br>
            {a}
          </h2>
          <p style="color:var(--muted);font-size:0.65rem;letter-spacing:1.5px;margin-top:8px;text-transform:uppercase">
            {dt.strftime('%-d %b %Y · %H:%M')} UTC+1
          </p>
        </div>
        {conf_ring_html(res['confidence'])}
      </div>
    </div>

    <!-- Recommended -->
    <div class="rec-box fade-up delay-1">
      <p class="eyebrow">⚡ Best Market</p>
      <p class="rec-market">{res['rec']['t']}</p>
      <div style="display:flex;align-items:baseline;gap:12px">
        <p class="rec-pct">{res['rec']['p']}%</p>
        <div>
          <p style="font-family:'Barlow Condensed',sans-serif;font-size:0.7rem;color:var(--muted);letter-spacing:1px">FAIR ODDS</p>
          <p style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:1.4rem;color:var(--white)">{res['rec']['odds']}</p>
        </div>
      </div>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <span style="font-size:0.62rem;color:var(--muted);letter-spacing:1px">Also consider:</span>
        <span class="pill pill-blue">{res['second']['t']} {res['second']['p']}%</span>
      </div>
    </div>

    <!-- xG -->
    <div class="stat-grid fade-up delay-2" style="margin-bottom:12px">
      <div class="stat-box">
        <p class="stat-val accent">{res['xg_h']}</p>
        <p class="stat-label">xG {h.split()[0]}</p>
      </div>
      <div class="stat-box">
        <p class="stat-val blue">{res['xg_a']}</p>
        <p class="stat-label">xG {a.split()[0]}</p>
      </div>
    </div>

    <!-- 1X2 -->
    <div class="card fade-up delay-2">
      <p class="section-head" style="margin-top:0;border:none;padding:0 0 12px">1 × 2</p>
      {prob_bar('Home Win', one_x_two['home'])}
      {prob_bar('Draw', one_x_two['draw'], warm=True)}
      {prob_bar('Away Win', one_x_two['away'])}
    </div>

    <!-- Markets -->
    <div class="card fade-up delay-3">
      <p class="section-head" style="margin-top:0;border:none;padding:0 0 12px">Markets</p>
      {prob_bar('Over 2.5', mkts['over_25'])}
      {prob_bar('Under 2.5', mkts['under_25'], warm=True)}
      {prob_bar('Over 1.5', mkts['over_15'])}
      {prob_bar('BTTS', mkts['btts'])}
    </div>

    <!-- Form & Standings -->
    <div class="card fade-up delay-4">
      <p class="section-head" style="margin-top:0;border:none;padding:0 0 14px">Form · Last 5</p>
      <div style="display:flex;flex-direction:column;gap:12px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.85rem;color:var(--white)">{h}</span>
          {form_dots_html(form['home'])}
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.85rem;color:var(--white)">{a}</span>
          {form_dots_html(form['away'])}
        </div>
      </div>
      <div style="display:flex;gap:16px;margin-top:16px;padding-top:14px;border-top:1px solid var(--border)">
        <div>
          <p class="eyebrow">Standing</p>
          <p style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:1.3rem;color:var(--white)">
            #{standings['home']}
          </p>
          <p style="font-size:0.6rem;color:var(--muted)">{h.split()[0]}</p>
        </div>
        <div>
          <p class="eyebrow">Standing</p>
          <p style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:1.3rem;color:var(--white)">
            #{standings['away']}
          </p>
          <p style="font-size:0.6rem;color:var(--muted)">{a.split()[0]}</p>
        </div>
        <div>
          <p class="eyebrow">Confidence Gap</p>
          <p style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:1.3rem;color:var(--accent)">
            {res['confidence_gap']}pts
          </p>
        </div>
      </div>
    </div>"""

    return render_template_string(LAYOUT, content=content, page="match")


@app.route("/acca")
def acca():
    data    = api_get("/predictions/")
    matches = data.get("results", [])

    picks, combined_odds = match_predictor.pick_acca(matches, n=5, min_prob=0.52)

    if not picks:
        content = """
        <div style="padding:32px 0 20px">
          <p class="eyebrow">Daily Accumulator</p>
          <h1 class="display" style="font-size:2.8rem">ACCA<br>BUILDER</h1>
        </div>
        <div class="empty">No qualifying picks today — check back later</div>"""
        return render_template_string(LAYOUT, content=content, page="acca")

    rows_html = '<div class="card" style="padding:0;overflow:hidden">'
    for i, p in enumerate(picks):
        event   = p["match"].get("event", {})
        h       = event.get("home_team", "?")
        a       = event.get("away_team", "?")
        res     = p["result"]
        mid     = p["match"].get("id", 0)
        rows_html += f"""
        <a href="/match/{mid}" class="acca-row">
          <div>
            <p class="acca-match">{h} vs {a}</p>
            <p class="acca-market">{res['rec']['t']} · {res['rec']['p']}%</p>
          </div>
          <p class="acca-odds">{res['rec']['odds']}</p>
        </a>"""
    rows_html += '</div>'

    content = f"""
    <div style="padding:32px 0 20px" class="fade-up">
      <p class="eyebrow">Daily Accumulator</p>
      <h1 class="display" style="font-size:2.8rem">ACCA<br>BUILDER</h1>
    </div>

    {rows_html}

    <div class="rec-box fade-up delay-2" style="margin-top:16px;text-align:center">
      <p class="eyebrow">Combined Odds</p>
      <p class="rec-pct" style="font-size:4.5rem">{combined_odds}</p>
      <p style="font-size:0.65rem;color:var(--muted);letter-spacing:1px;margin-top:4px">{len(picks)}-FOLD ACCA</p>
    </div>

    <p style="font-size:0.6rem;color:var(--muted);text-align:center;padding:16px;letter-spacing:1px">
      Fair odds shown. Always gamble responsibly.
    </p>"""

    return render_template_string(LAYOUT, content=content, page="acca")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
