"""
ProPredictor NG -- app.py v3
Clean rebuild using data.py (4 APIs) + match_predictor engine
"""
from flask import Flask, render_template_string, jsonify
import os, json
from datetime import datetime, timedelta, timezone
import match_predictor, database, data as D

app = Flask(__name__)
database.init_db()

WAT = 1

def now_wat():
    return datetime.now(timezone.utc) + timedelta(hours=WAT)

def kickoff_label(raw):
    if not raw: return ""
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z","+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        dt_wat = dt + timedelta(hours=WAT)
        if dt_wat.date() == now_wat().date():
            return dt_wat.strftime("%H:%M")
        return dt_wat.strftime("%H:%M %d %b")
    except: return ""

# ── LEAGUE META ────────────────────────────────────────────────────────────────
LEAGUE_META = {
    # id -> (display_name, flag, tier)
    39:  ("Premier League",       "EN", 1),
    140: ("La Liga",              "ES", 1),
    135: ("Serie A",              "IT", 1),
    78:  ("Bundesliga",           "DE", 1),
    61:  ("Ligue 1",              "FR", 1),
    2:   ("Champions League",     "CL", 1),
    3:   ("Europa League",        "EL", 1),
    848: ("Conference League",    "CL", 1),
    88:  ("Eredivisie",           "NL", 2),
    94:  ("Primeira Liga",        "PT", 2),
    203: ("Super Lig",            "TR", 2),
    179: ("Scottish Prem",        "SC", 2),
    144: ("Belgian Pro League",   "BE", 2),
    40:  ("Championship",         "EN", 2),
    41:  ("League One",           "EN", 2),
    197: ("Greek Super League",   "GR", 2),
    106: ("Ekstraklasa",          "PL", 2),
    113: ("Allsvenskan",          "SE", 2),
    103: ("Eliteserien",          "NO", 2),
    271: ("Danish Superliga",     "DK", 2),
    207: ("Romanian Liga 1",      "RO", 2),
    218: ("Austrian Bundesliga",  "AT", 2),
    283: ("Czech Liga",           "CZ", 2),
    253: ("MLS",                  "US", 2),
    262: ("Liga MX",              "MX", 2),
    71:  ("Brasileirao",          "BR", 2),
    128: ("Argentine Primera",    "AR", 2),
    307: ("Saudi Pro League",     "SA", 3),
    98:  ("J1 League",            "JP", 3),
    233: ("Egyptian Premier",     "EG", 3),
    235: ("Russian Premier",      "RU", 3),
    332: ("Ukrainian Premier",    "UA", 3),
    323: ("South African PSL",    "ZA", 3),
}

def lg_meta(lg_id, lg_name="", country=""):
    if lg_id in LEAGUE_META:
        nm, fl, tier = LEAGUE_META[lg_id]
        return {"name":nm, "flag":fl, "tier":tier, "country":country or nm}
    return {"name":lg_name or "Other", "flag":country[:2].upper() if country else "??",
            "tier":3, "country":country}

# ── CSS / LAYOUT ───────────────────────────────────────────────────────────────
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#03050a;--s:#080c14;--s2:#0d1220;--s3:#131929;
  --g:#00ff87;--g2:#00c864;--b:#4f8ef7;--r:#ff453a;
  --w:#ff9f0a;--pu:#bf5af2;--cy:#32d7f0;--gold:#ffd60a;
  --t:#2d3748;--t2:#4a5568;--t3:#718096;--wh:#f0f4f8;
  --bdr:rgba(255,255,255,.05);--bdr2:rgba(255,255,255,.10);
}
body{background:var(--bg);color:var(--wh);font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display',sans-serif;min-height:100vh;padding-bottom:40px}
a{color:inherit;text-decoration:none}

/* NAV */
.nav{position:sticky;top:0;z-index:100;background:rgba(3,5,10,.85);backdrop-filter:blur(20px);border-bottom:1px solid var(--bdr);padding:0 16px;display:flex;align-items:center;justify-content:space-between;height:52px}
.nav-logo{font-size:.95rem;font-weight:900;letter-spacing:-0.5px}
.nav-logo span{color:var(--g)}
.nav-links{display:flex;gap:6px}
.nav-btn{padding:6px 14px;border-radius:20px;font-size:.65rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;border:1px solid var(--bdr2);color:var(--t3);transition:all .2s}
.nav-btn:hover,.nav-btn.active{background:var(--g);color:#000;border-color:var(--g)}
.nav-live{color:var(--r);font-size:.6rem;font-weight:700}

/* WRAP */
.wrap{max-width:680px;margin:0 auto;padding:0 12px}

/* HERO */
.hero{padding:28px 16px 20px}
.hero-eye{font-size:.5rem;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:var(--t3);margin-bottom:8px}
.hero-title{font-size:2.8rem;font-weight:900;line-height:1;letter-spacing:-2px;margin-bottom:16px}
.hero-title span{color:var(--g)}
.hstats{display:flex;gap:20px;flex-wrap:wrap}
.hstat-n{font-size:1.6rem;font-weight:900;letter-spacing:-1px}
.hstat-l{font-size:.5rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t3);margin-top:1px}

/* SEARCH */
.search-wrap{padding:0 16px 16px}
.search{width:100%;background:var(--s);border:1px solid var(--bdr2);border-radius:12px;padding:12px 16px 12px 40px;color:var(--wh);font-size:.8rem;outline:none}
.search::placeholder{color:var(--t2)}
.search-icon{position:absolute;left:28px;top:50%;transform:translateY(-50%);color:var(--t2);font-size:.85rem}
.search-wrap{position:relative}

/* SECTION HEADER */
.sec-hdr{font-size:.5rem;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:var(--t3);padding:8px 16px 6px;display:flex;align-items:center;gap:6px}
.sec-dot{width:5px;height:5px;border-radius:50%;background:var(--g);display:inline-block}

/* LEAGUE GRID */
.lg-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:0 12px 4px}
.lg-tile{background:var(--s);border:1px solid var(--bdr);border-radius:14px;padding:14px;display:block;cursor:pointer;transition:all .2s;position:relative;overflow:hidden}
.lg-tile:hover{border-color:var(--g);background:var(--s2)}
.lt-badge{position:absolute;top:10px;right:10px;background:var(--g);color:#000;font-size:.48rem;font-weight:900;padding:2px 7px;border-radius:20px}
.lt-badge.live{background:var(--r);color:#fff}
.lt-badge.tmr{background:var(--b);color:#fff}
.lt-flag{font-size:.75rem;font-weight:800;color:var(--t2);margin-bottom:6px;font-family:monospace;letter-spacing:1px}
.lt-name{font-size:.82rem;font-weight:800;color:var(--wh);margin-bottom:2px}
.lt-country{font-size:.58rem;color:var(--t3);text-transform:uppercase;letter-spacing:1px}
.lt-live{font-size:.5rem;font-weight:700;color:var(--r);margin-top:4px}

/* FIXTURE LIST */
.fx-list{background:var(--s);border:1px solid var(--bdr);border-radius:14px;margin:0 12px 8px;overflow:hidden}
.fx-row{display:flex;align-items:center;padding:12px 14px;border-bottom:1px solid var(--bdr);cursor:pointer;transition:background .15s}
.fx-row:last-child{border-bottom:none}
.fx-row:hover{background:var(--s2)}
.fx-time{width:40px;font-size:.65rem;font-weight:700;color:var(--t2);flex-shrink:0}
.fx-teams{flex:1;min-width:0}
.fx-home{font-size:.78rem;font-weight:700;color:var(--wh)}
.fx-away{font-size:.7rem;color:var(--t3);margin-top:1px}
.fx-right{text-align:right;flex-shrink:0}
.fx-prob{font-size:.65rem;font-weight:800;color:var(--g)}
.fx-tag{font-size:.5rem;font-weight:700;letter-spacing:1px;text-transform:uppercase}
.fx-score{font-size:.85rem;font-weight:900;color:var(--wh);letter-spacing:1px}
.state-live{color:var(--r);font-weight:800;font-size:.65rem}
.state-ft{color:var(--t3);font-size:.65rem}

/* DATE HEADER IN LIST */
.date-hdr{font-size:.5rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t2);padding:8px 14px 4px;background:var(--s3)}

/* CARD */
.card{background:var(--s);border:1px solid var(--bdr);border-radius:14px;padding:16px;margin:0 12px 8px}
.card-title{font-size:.52rem;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--t3);margin-bottom:12px}

/* MATCH HERO */
.match-hero{background:linear-gradient(160deg,var(--s2),var(--s));border:1px solid var(--bdr2);border-radius:14px;padding:20px 16px;margin:12px 12px 8px;text-align:center}
.match-league{font-size:.52rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t3);margin-bottom:8px}
.match-teams{display:flex;align-items:center;justify-content:center;gap:12px;margin:12px 0 4px}
.team-name{font-size:.92rem;font-weight:800;color:var(--wh);max-width:110px;text-align:center;line-height:1.2}
.vs-sep{font-size:1rem;font-weight:900;color:var(--t2)}
.vs-score{font-size:2rem;font-weight:900;color:var(--wh);letter-spacing:2px}
.s-badge{display:inline-block;font-size:.58rem;font-weight:700;padding:3px 10px;border-radius:20px;letter-spacing:1px}
.s-live{background:rgba(255,69,58,.15);color:var(--r);border:1px solid rgba(255,69,58,.3)}
.s-ft{background:rgba(255,255,255,.06);color:var(--t3)}
.s-ns{background:rgba(0,255,135,.08);color:var(--g)}

/* PRED CARD */
.pred-card{border-radius:14px;padding:16px;margin:0 12px 8px;border:1px solid var(--bdr)}
.pred-card.reliable{border-color:rgba(0,255,135,.25);background:linear-gradient(145deg,rgba(0,255,135,.04),var(--s))}
.pred-card.sure{border-color:rgba(0,255,135,.4);background:linear-gradient(145deg,rgba(0,255,135,.08),var(--s))}
.pred-card.solid{border-color:rgba(79,142,247,.25);background:linear-gradient(145deg,rgba(79,142,247,.04),var(--s))}
.pred-card.volatile{border-color:rgba(255,159,10,.25);background:linear-gradient(145deg,rgba(255,159,10,.04),var(--s))}
.pred-card.avoid{border-color:rgba(255,69,58,.25);background:linear-gradient(145deg,rgba(255,69,58,.04),var(--s))}
.pred-card.monitor{border-color:var(--bdr2);background:var(--s)}
.tip-main{font-size:1.6rem;font-weight:900;letter-spacing:-0.5px;margin:4px 0}
.tip-prob{font-size:.65rem;color:var(--t3);margin-top:2px}
.tip-reason{font-size:.7rem;color:var(--t3);line-height:1.5;margin-top:10px;padding:10px;background:rgba(255,255,255,.03);border-radius:8px;border-left:2px solid var(--g)}
.badge{display:inline-block;font-size:.5rem;font-weight:800;padding:3px 8px;border-radius:20px;letter-spacing:1px;text-transform:uppercase}
.bg-green{background:rgba(0,255,135,.15);color:var(--g);border:1px solid rgba(0,255,135,.3)}
.bg-blue{background:rgba(79,142,247,.15);color:var(--b);border:1px solid rgba(79,142,247,.3)}
.bg-orange{background:rgba(255,159,10,.15);color:var(--w);border:1px solid rgba(255,159,10,.3)}
.bg-red{background:rgba(255,69,58,.15);color:var(--r);border:1px solid rgba(255,69,58,.3)}
.bg-muted{background:rgba(255,255,255,.06);color:var(--t3)}

/* PROB BAR */
.pbar-wrap{margin-bottom:10px}
.pbar-top{display:flex;justify-content:space-between;margin-bottom:4px}
.pbar-lbl{font-size:.62rem;color:var(--t3)}
.pbar-val{font-size:.62rem;font-weight:800}
.pbar-track{height:4px;background:rgba(255,255,255,.06);border-radius:4px}
.pbar-fill{height:100%;border-radius:4px;transition:width .6s ease}

/* FORM DOTS */
.form-dots{display:flex;gap:4px}
.fd{width:20px;height:20px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:.55rem;font-weight:900}
.fd-w{background:rgba(0,255,135,.15);color:var(--g)}
.fd-d{background:rgba(79,142,247,.15);color:var(--b)}
.fd-l{background:rgba(255,69,58,.15);color:var(--r)}

/* INFO ROW */
.info-row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--bdr)}
.info-row:last-child{border-bottom:none}
.info-lbl{font-size:.65rem;color:var(--t3)}
.info-val{font-size:.72rem;font-weight:700;color:var(--wh)}

/* H2H BAR */
.h2h-bar{display:flex;height:6px;border-radius:6px;overflow:hidden;margin-bottom:8px;gap:2px}
.h2h-h{background:var(--g);border-radius:3px}
.h2h-d{background:var(--t2);border-radius:3px}
.h2h-a{background:var(--b);border-radius:3px}
.h2h-labels{display:flex;justify-content:space-between;font-size:.58rem}

/* EVENTS */
.ev-row{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--bdr);font-size:.7rem}
.ev-row:last-child{border-bottom:none}
.ev-min{color:var(--g);font-weight:800;width:28px;flex-shrink:0}
.ev-icon{width:24px;text-align:center;font-size:.85rem}
.ev-name{flex:1;color:var(--wh);font-weight:600}
.ev-team{color:var(--t3);font-size:.6rem}

/* LINEUP GRID */
.lineup-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.lu-team{font-size:.6rem;font-weight:800;color:var(--t2);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.lu-player{font-size:.68rem;color:var(--wh);padding:3px 0;border-bottom:1px solid var(--bdr)}

/* TRACKER */
.tracker-hero{background:linear-gradient(145deg,var(--s2),var(--s));border:1px solid var(--bdr2);border-radius:14px;padding:20px 16px;margin:12px 12px 8px}
.big-num{font-size:3rem;font-weight:900;letter-spacing:-2px;line-height:1}
.big-lbl{font-size:.5rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t3);margin-top:2px}
.perf-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--bdr)}
.perf-row:last-child{border-bottom:none}
.result-row{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--bdr)}
.result-row:last-child{border-bottom:none}
.win-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}

/* ODDS STRIP */
.odds-strip{display:flex;gap:8px;margin-top:10px;padding-top:10px;border-top:1px solid var(--bdr)}
.odds-box{flex:1;text-align:center;background:var(--s3);border-radius:10px;padding:8px 4px}
.odds-lbl{font-size:.48rem;color:var(--t3);margin-bottom:2px;text-transform:uppercase;letter-spacing:1px}
.odds-val{font-size:.95rem;font-weight:900}

/* BACK */
.back{display:inline-flex;align-items:center;gap:6px;font-size:.65rem;color:var(--t3);padding:12px 16px;margin-bottom:4px}
.back:hover{color:var(--wh)}

/* EMPTY */
.empty{text-align:center;padding:60px 20px;color:var(--t2)}
.empty-icon{font-size:2.5rem;display:block;margin-bottom:12px}

/* ACCA */
.acca-pick{background:var(--s);border:1px solid var(--bdr);border-radius:12px;padding:14px;margin-bottom:8px}
.acca-tip{font-size:.92rem;font-weight:900;color:var(--g)}
.acca-match{font-size:.65rem;color:var(--t3);margin-top:2px}
.acca-odds{font-size:.8rem;font-weight:800;color:var(--gold);margin-top:4px}

/* ANIMATIONS */
.up{animation:fadeUp .4s ease both}
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.d1{animation-delay:.05s}.d2{animation-delay:.1s}.d3{animation-delay:.15s}.d4{animation-delay:.2s}

/* LIVE PULSE */
.live-dot::before{content:'';display:inline-block;width:6px;height:6px;background:var(--r);border-radius:50%;margin-right:4px;animation:pulse 1.4s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
"""

LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#03050a">
<title>ProPred NG</title>
<style>""" + CSS + """</style>
</head>
<body>
<nav class="nav">
  <a href="/" class="nav-logo">PRO<span>PRED</span> <small style="font-size:.5rem;color:var(--t2);font-weight:600">NG</small></a>
  <div class="nav-links">
    <a href="/" class="nav-btn {{ 'active' if page=='home' else '' }}">LEAGUES</a>
    <a href="/acca" class="nav-btn {{ 'active' if page=='acca' else '' }}">ACCA</a>
    <a href="/tracker" class="nav-btn {{ 'active' if page=='tracker' else '' }}">TRACKER</a>
  </div>
</nav>
<div class="wrap">
{{ content }}
</div>
<script>
// Search filter on home page
var si=document.getElementById('search');
if(si){si.addEventListener('input',function(){
  var q=this.value.toLowerCase();
  document.querySelectorAll('.lg-tile').forEach(function(t){
    t.style.display=t.dataset.n&&t.dataset.n.includes(q)?'':'none';
  });
});}
// Prob bar animations on scroll
var obs=new IntersectionObserver(function(entries){
  entries.forEach(function(e){
    if(e.isIntersecting){
      e.target.querySelectorAll('.pbar-fill').forEach(function(b){
        b.style.width=b.dataset.w+'%';
      });
    }
  });
},{threshold:0.1});
document.querySelectorAll('.card').forEach(function(c){obs.observe(c);});
// live count badge
fetch('/api/live-count').then(r=>r.json()).then(d=>{
  if(d.count>0){
    var links=document.querySelectorAll('.nav-links');
    if(links.length){
      var sp=document.createElement('span');
      sp.className='nav-live';sp.textContent='● '+d.count;
      links[0].appendChild(sp);
    }
  }
});
</script>
</body>
</html>
"""

def render(content, page="home"):
    from flask import render_template_string
    from markupsafe import Markup
    return render_template_string(LAYOUT, content=Markup(content), page=page)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def prob_bar(label, val, color="green"):
    clr = {"green":"var(--g)","blue":"var(--b)","orange":"var(--w)",
           "cyan":"var(--cy)","red":"var(--r)"}.get(color,"var(--g)")
    w   = min(max(float(val or 0), 0), 100)
    vc  = clr if w>=60 else ("var(--w)" if w>=40 else "var(--r)")
    return (
        '<div class="pbar-wrap">'
        '<div class="pbar-top">'
        f'<span class="pbar-lbl">{label}</span>'
        f'<span class="pbar-val" style="color:{vc}">{val:.0f}%</span>'
        '</div>'
        '<div class="pbar-track">'
        f'<div class="pbar-fill" style="width:0%;background:{clr}" data-w="{w}"></div>'
        '</div></div>'
    )

def form_dots(form_list):
    if not form_list: return '<span style="color:var(--t2);font-size:.6rem">No data</span>'
    html = '<div class="form-dots">'
    for r in list(form_list)[-6:]:
        r = r.upper()
        cls = "fd-w" if r=="W" else "fd-d" if r=="D" else "fd-l"
        html += f'<div class="fd {cls}">{r}</div>'
    return html + '</div>'

def tip_color(tip):
    if not tip: return "var(--wh)"
    t = tip.upper()
    if "HOME" in t: return "var(--g)"
    if "AWAY" in t: return "var(--b)"
    if "DRAW" in t: return "var(--w)"
    if "OVER" in t or "GG" in t or "BTTS" in t: return "var(--cy)"
    if "UNDER" in t or "NG" in t: return "var(--t3)"
    return "var(--wh)"

def get_quick_pred(fixture_card):
    """Quick prediction from form+xG for fixture list display. No extra API calls."""
    lg_id  = fixture_card.get("league_id",0)
    h_id   = fixture_card.get("home_id")
    a_id   = fixture_card.get("away_id")
    season = fixture_card.get("season",2025)
    h_form = D.get_form(h_id, lg_id, season, last=5) if h_id else []
    a_form = D.get_form(a_id, lg_id, season, last=5) if a_id else []
    stds   = D.get_standings(lg_id, season)
    h_std  = stds.get(h_id) or stds.get(fixture_card.get("home",""))
    a_std  = stds.get(a_id) or stds.get(fixture_card.get("away",""))
    xg_h   = D.estimate_xg(h_form, h_std, True)
    xg_a   = D.estimate_xg(a_form, a_std, False)
    hw, dw, aw, o25, o15, bt = D.poisson_probs(xg_h, xg_a)
    o35    = round(max(o25-22,4),1)
    odds_d = None
    tip, prob, conv, _, _ = match_predictor._pick_recommended(
        hw, dw, aw, o15, o25, o35, bt, bt, round(100-bt,1),
        xg_h, xg_a, h_form, a_form, h_std, a_std,
        None, None, None, None, None, None)
    tag = "RELIABLE" if conv>=55 else "SOLID" if conv>=40 else "MONITOR"
    return {"tip":tip,"prob":prob,"conv":conv,"tag":tag}

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    cards = D.get_fixtures_window(3)

    # Group by league
    leagues = {}
    name_count = {}
    for c in cards:
        lid = c["league_id"]
        lkey = f"{lid}_{c['country']}"
        if lkey not in leagues:
            meta = lg_meta(lid, c["league"], c["country"])
            leagues[lkey] = {
                "id":lid, "name":meta["name"], "flag":meta["flag"],
                "tier":meta["tier"], "country":c["country"],
                "fixtures":[], "live":0,
                "has_today":False, "has_tomorrow":False
            }
            name_count[meta["name"]] = name_count.get(meta["name"],0)+1
        leagues[lkey]["fixtures"].append(c)
        if c["is_live"]:                      leagues[lkey]["live"] += 1
        if c.get("date_label")=="TODAY":      leagues[lkey]["has_today"] = True
        if c.get("date_label")=="TOMORROW":   leagues[lkey]["has_tomorrow"] = True

    # Disambiguate same-named leagues
    for lkey, lg in leagues.items():
        if name_count.get(lg["name"],1) > 1:
            lg["display_name"] = f'{lg["name"]} ({lg["country"]})'
        else:
            lg["display_name"] = lg["name"]

    total_fx   = len(cards)
    total_live = sum(1 for c in cards if c["is_live"])
    today_fx   = sum(1 for c in cards if c.get("date_label")=="TODAY")
    tmrw_fx    = sum(1 for c in cards if c.get("date_label")=="TOMORROW")
    total_lg   = len(leagues)

    # Sort leagues
    sorted_lgs = sorted(leagues.items(),
        key=lambda x: (x[1]["tier"], -(x[1]["live"]),
                       -(1 if x[1]["has_today"] else 0),
                       -len(x[1]["fixtures"])))
    tiers = {}
    for lkey, lg in sorted_lgs:
        tiers.setdefault(lg["tier"], []).append((lkey, lg))

    tier_labels = {1:"Top Leagues", 2:"Major Leagues", 3:"More Leagues"}

    content = (
        '<div class="hero up">'
        '<div class="hero-eye">Football Intelligence &middot; 3-Day View</div>'
        '<div class="hero-title">LEAGUES<br><span>AHEAD</span></div>'
        '<div class="hstats">'
        f'<div><div class="hstat-n">{today_fx}</div><div class="hstat-l">Today</div></div>'
        f'<div><div class="hstat-n">{tmrw_fx}</div><div class="hstat-l">Tomorrow</div></div>'
        f'<div><div class="hstat-n" style="color:var(--r)">{total_live}</div><div class="hstat-l">Live</div></div>'
        f'<div><div class="hstat-n">{total_lg}</div><div class="hstat-l">Leagues</div></div>'
        '</div></div>'
    )

    content += (
        '<div class="search-wrap">'
        '<span class="search-icon">&#128269;</span>'
        '<input id="search" class="search" placeholder="Search league or country..." />'
        '</div>'
    )

    if not cards:
        content += '<div class="empty"><span class="empty-icon">&#9917;</span>No fixtures found.<br>API-Football may be rate limited or no matches scheduled.</div>'
        return render(content)

    for tier in sorted(tiers.keys()):
        label = tier_labels.get(tier, "More")
        content += f'<div class="sec-hdr"><span class="sec-dot"></span>{label}</div>'
        content += '<div class="lg-grid">'
        for lkey, lg in tiers[tier]:
            fxc  = len(lg["fixtures"])
            if lg["live"]:
                badge = f'<span class="lt-badge live">{lg["live"]} LIVE</span>'
            elif lg["has_today"]:
                badge = f'<span class="lt-badge">{fxc}</span>'
            elif lg["has_tomorrow"]:
                badge = f'<span class="lt-badge tmr">TMR {fxc}</span>'
            else:
                badge = f'<span class="lt-badge tmr">{fxc}</span>'
            content += (
                f'<a href="/league/{lg["id"]}" class="lg-tile" data-n="{lg["name"].lower()} {lg["country"].lower()}">'
                + badge
                + f'<div class="lt-flag">{lg["flag"]}</div>'
                + f'<div class="lt-name">{lg["display_name"]}</div>'
                + f'<div class="lt-country">{lg["country"]}</div>'
                + (''.join(['<div class="lt-live">&#9679; LIVE</div>'] if lg["live"] else []))
                + '</a>'
            )
        content += '</div>'

    return render(content)


@app.route("/league/<int:league_id>")
def league_page(league_id):
    all_cards = D.get_fixtures_window(3)
    lg_cards  = [c for c in all_cards if c["league_id"] == league_id]

    if not lg_cards:
        return render(
            '<a href="/" class="back">&#8592; Leagues</a>'
            '<div class="empty"><span class="empty-icon">&#9917;</span>No fixtures for this league.</div>'
        )

    lg_name  = lg_cards[0]["league"]
    country  = lg_cards[0]["country"]
    meta     = lg_meta(league_id, lg_name, country)

    # Group by date
    groups = {}
    for c in lg_cards:
        dl = c.get("date_label","TODAY")
        groups.setdefault(dl, []).append(c)
    for k in groups:
        groups[k].sort(key=lambda c: c["kickoff"] or "")

    content = (
        f'<a href="/" class="back">&#8592; Leagues</a>'
        f'<div style="padding:12px 16px 8px">'
        f'<div style="font-size:.52rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t3);margin-bottom:4px">{meta["flag"]} {country.upper()}</div>'
        f'<div style="font-size:1.8rem;font-weight:900;letter-spacing:-1px">{meta["name"]}</div>'
        f'<div style="font-size:.62rem;color:var(--t3);margin-top:4px">{len(lg_cards)} fixtures</div>'
        f'</div>'
    )

    date_order = ["TODAY","TOMORROW"] + sorted(
        [k for k in groups if k not in ("TODAY","TOMORROW")])

    for dl in date_order:
        if dl not in groups: continue
        content += (
            f'<div class="sec-hdr"><span class="sec-dot"></span>{dl}</div>'
            '<div class="fx-list">'
        )
        for c in groups[dl]:
            fid    = c["id"]
            ko_lbl = kickoff_label(c["kickoff"])

            if c["is_live"]:
                time_html = f'<div class="fx-time"><span class="state-live">&#9679; {c["state"]}</span></div>'
            elif c["is_ft"]:
                time_html = f'<div class="fx-time"><span class="state-ft">FT</span></div>'
            else:
                time_html = f'<div class="fx-time">{ko_lbl}</div>'

            if c["is_live"] or c["is_ft"]:
                sh = c["score_h"] if c["score_h"] is not None else "-"
                sa = c["score_a"] if c["score_a"] is not None else "-"
                right_html = f'<div class="fx-right"><div class="fx-score">{sh} - {sa}</div></div>'
            else:
                right_html = '<div class="fx-right"><div class="fx-prob">--</div><div class="fx-tag" style="color:var(--t3)">TAP</div></div>'

            content += (
                f'<a href="/match/{fid}" class="fx-row">'
                + time_html
                + f'<div class="fx-teams"><div class="fx-home">{c["home"]}</div><div class="fx-away">{c["away"]}</div></div>'
                + right_html
                + '</a>'
            )
        content += '</div>'

    return render(content)


@app.route("/match/<int:match_id>")
def match_page(match_id):
    try:
        # Find fixture card from cache
        all_cards = D.get_fixtures_window(3)
        card = next((c for c in all_cards if c["id"] == match_id), None)

        # Full enrichment
        e = D.enrich(match_id, card)

        h_name  = e["home_name"];   a_name  = e["away_name"]
        lg_name = e["league_name"] or (card["league"] if card else "")
        state   = e["state"];       kickoff = e["kickoff"]
        score_h = e["score_home"];  score_a = e["score_away"]

        hw   = e["home_win"];  dw  = e["draw"];    aw  = e["away_win"]
        o25  = e["over_25"];   o15 = e["over_15"]; btts= e["btts"]
        o35  = e["over_35"]
        xg_h = e["xg_home"];   xg_a= e["xg_away"]
        h_form = e["home_form"]; a_form = e["away_form"]
        h_std  = e["home_standing"]; a_std = e["away_standing"]
        h2h    = e["h2h"]
        h_lu   = e["home_lineup"]; a_lu = e["away_lineup"]
        goals  = e["goals"];        cards_ev = e["cards"]
        h_inj  = e["home_injuries"]; a_inj = e["away_injuries"]

        odds_h = e["odds_home"];  odds_d = e["odds_draw"]
        odds_a = e["odds_away"];  odds_o25 = e["odds_o25"]
        odds_o15= e["odds_o15"]

        # THREE-TIER TIPS
        ng = round(max(100-btts,4.0),1)
        rec_tip, rec_prob, rec_conv, rec_odds, _ = match_predictor._pick_recommended(
            hw,dw,aw,o15,o25,o35,btts,btts,ng,
            xg_h,xg_a,h_form,a_form,h_std,a_std,
            odds_h,odds_d,odds_a,odds_o15,odds_o25,odds_h)
        safe_tip, safe_prob, safe_odds = match_predictor._pick_safest(
            rec_tip,hw,dw,aw,o15,xg_h,xg_a,h_form,a_form,odds_h,odds_d,odds_a)
        risky = match_predictor._pick_risky(
            hw,dw,aw,o15,o25,btts,xg_h,xg_a,h_form,a_form,odds_h,odds_a,odds_o25,odds_h)

        reason = match_predictor._reason(
            rec_tip,xg_h,xg_a,h_form,a_form,h_std,a_std,rec_prob,rec_odds,h_name,a_name)

        # TAG
        fav_prob = max(hw,aw)
        inj_n    = len(h_inj)+len(a_inj)
        h_slump  = list(h_form[-3:]).count("L")>=3 if len(h_form)>=3 else False
        a_slump  = list(a_form[-3:]).count("L")>=3 if len(a_form)>=3 else False
        lg_low   = lg_name.lower()
        is_friendly = "friendly" in lg_low
        is_cup      = any(w in lg_low for w in ["cup","copa","carabao","pokal"])

        if fav_prob>=85 and inj_n==0 and not is_cup and not is_friendly:
            tag="SURE MATCH"; tc="sure"
        elif is_friendly:
            tag="VOLATILE"; tc="volatile"
        elif (h_slump and "HOME" in rec_tip) or (a_slump and "AWAY" in rec_tip) or inj_n>=3:
            tag="AVOID"; tc="avoid"
        elif rec_conv>=60 and rec_prob>=58:
            tag="RELIABLE"; tc="reliable"
        elif rec_conv>=42:
            tag="SOLID"; tc="solid"
        else:
            tag="MONITOR"; tc="monitor"

        tag_badge = {"SURE MATCH":"bg-green","RELIABLE":"bg-green","SOLID":"bg-blue",
                     "VOLATILE":"bg-orange","AVOID":"bg-red","MONITOR":"bg-muted"}.get(tag,"bg-muted")

        fair_odds = round(100/max(rec_prob,1),2)
        edge_val  = None
        if rec_odds and rec_odds>1:
            edge_val = round((rec_prob/100 - 1/rec_odds)*100,1)

        # Log
        try:
            database.log_prediction(
                match_id=match_id, league_id=e["league_id"],
                league_name=lg_name, home_team=h_name, away_team=a_name,
                match_date=kickoff[:16], market=rec_tip, probability=rec_prob,
                fair_odds=fair_odds, bookie_odds=rec_odds, edge=edge_val,
                confidence=rec_conv, xg_home=xg_h, xg_away=xg_a,
                likely_score="", tag=tag, reliability_score=rec_conv)
        except: pass

        # State badge
        is_live = any(s in state.upper() for s in ["H","HT","ET","'"]) or state.isdigit() if state else False
        is_ft   = state == "FT"
        if is_live:
            s_badge = '<span class="s-badge s-live"><span class="live-dot"></span>' + state + '</span>'
        elif is_ft:
            s_badge = '<span class="s-badge s-ft">Full Time</span>'
        else:
            s_badge = '<span class="s-badge s-ns">' + kickoff_label(kickoff) + '</span>'

        if score_h is not None and score_a is not None:
            vs_html = '<div class="vs-score">' + str(score_h) + ' - ' + str(score_a) + '</div>'
        else:
            vs_html = '<div class="vs-sep">VS</div>'

        conv_clr = "var(--g)" if rec_conv>=60 else "var(--w)" if rec_conv>=42 else "var(--r)"
        tc_main  = tip_color(rec_tip)
        bk_str   = (' &middot; Bookie: <span style="color:var(--gold);font-weight:900">' + str(rec_odds) + '</span>') if rec_odds else ""
        edge_str = ""
        if edge_val and edge_val>0:
            edge_str = '<span class="badge bg-green" style="margin-top:5px;display:inline-block">+'+str(edge_val)+'% EDGE</span>'
        elif edge_val and edge_val<-3:
            edge_str = '<span class="badge bg-red" style="margin-top:5px;display:inline-block">POOR VALUE</span>'

        content = '<a href="/league/' + str(e["league_id"]) + '" class="back">&#8592; ' + lg_name + '</a>'

        # MATCH HERO
        content += (
            '<div class="match-hero up">'
            + '<div class="match-league">' + lg_name + '</div>'
            + '<div style="margin:6px 0">' + s_badge + '</div>'
            + '<div class="match-teams">'
            + '<div><div class="team-name">' + h_name + '</div></div>'
            + '<div>' + vs_html + '</div>'
            + '<div><div class="team-name">' + a_name + '</div></div>'
            + '</div></div>'
        )

        # RECOMMENDED TIP
        content += (
            '<div class="pred-card ' + tc + ' up d1">'
            + '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">'
            + '<div>'
            + '<div style="font-size:.48rem;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--t3);margin-bottom:4px">RECOMMENDED TIP</div>'
            + '<div class="tip-main" style="color:' + tc_main + '">' + rec_tip + '</div>'
            + '<div class="tip-prob">' + str(rec_prob) + '% probability &middot; Fair: <span style="color:var(--gold)">' + str(fair_odds) + '</span>' + bk_str + '</div>'
            + edge_str
            + '</div>'
            + '<span class="badge ' + tag_badge + '">' + tag + '</span>'
            + '</div>'
            + '<div style="display:flex;gap:8px;margin-bottom:12px">'
            + '<div style="flex:1;background:rgba(0,0,0,.25);border-radius:8px;padding:8px 10px">'
            + '<div style="font-size:.48rem;color:var(--t3);margin-bottom:3px;text-transform:uppercase;letter-spacing:1px">Conviction</div>'
            + '<div style="font-size:1.1rem;font-weight:900;color:' + conv_clr + '">' + str(round(rec_conv)) + '<span style="font-size:.55rem;color:var(--t2)">/100</span></div>'
            + '</div>'
            + '<div style="flex:1;background:rgba(0,0,0,.25);border-radius:8px;padding:8px 10px">'
            + '<div style="font-size:.48rem;color:var(--t3);margin-bottom:3px;text-transform:uppercase;letter-spacing:1px">Signal</div>'
            + '<div style="font-size:.75rem;font-weight:800;color:var(--wh)">' + ("VALUE" if (edge_val or 0)>2 else "SAFE" if rec_prob>=65 else "STANDARD") + '</div>'
            + '</div></div>'
            + '<div class="tip-reason">' + reason + '</div>'
            + '</div>'
        )

        # SAFE + RISKY side by side
        r1 = risky[0] if risky else {"tip":"--","prob":0,"odds":"--"}
        content += (
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:0 12px 8px" class="up d2">'
            + '<div class="card" style="margin:0;border-color:rgba(79,142,247,.2)">'
            + '<div class="card-title">SAFEST TIP</div>'
            + '<div style="font-size:.95rem;font-weight:900;color:' + tip_color(safe_tip) + ';line-height:1.2">' + safe_tip + '</div>'
            + '<div style="font-size:.6rem;color:var(--t3);margin-top:4px">' + str(safe_prob) + '% probability</div>'
            + '<div style="font-size:.6rem;color:var(--gold);margin-top:2px">Fair: ' + str(round(100/max(safe_prob,1),2)) + '</div>'
            + '</div>'
            + '<div class="card" style="margin:0;border-color:rgba(191,90,242,.2)">'
            + '<div class="card-title">RISKY PICK</div>'
            + '<div style="font-size:.88rem;font-weight:900;color:' + tip_color(r1["tip"]) + ';line-height:1.2">' + str(r1["tip"]) + '</div>'
            + '<div style="font-size:.6rem;color:var(--t3);margin-top:4px">' + str(r1["prob"]) + '% &middot; ~' + str(r1["odds"]) + '</div>'
            + '</div></div>'
        )

        # More risky
        if len(risky)>1:
            content += '<div class="card up d2"><div class="card-title">More Risky Markets</div>'
            for r in risky[1:]:
                content += (
                    '<div class="info-row">'
                    + '<div style="font-size:.7rem;font-weight:700;color:' + tip_color(r["tip"]) + '">' + r["tip"] + '</div>'
                    + '<div><span style="font-size:.65rem;color:var(--t3)">' + str(r["prob"]) + '% &middot; </span>'
                    + '<span style="font-size:.65rem;color:var(--gold)">~' + str(r["odds"]) + '</span></div>'
                    + '</div>'
                )
            content += '</div>'

        # WIN PROBS
        content += '<div class="card up d2"><div class="card-title">WIN PROBABILITIES</div>'
        content += prob_bar("Home Win - " + h_name[:18], hw, "green")
        content += prob_bar("Draw", dw, "blue")
        content += prob_bar("Away Win - " + a_name[:18], aw, "orange")
        if odds_h or odds_d or odds_a:
            content += (
                '<div class="odds-strip">'
                + '<div class="odds-box"><div class="odds-lbl">Home</div><div class="odds-val" style="color:var(--g)">' + str(odds_h or "--") + '</div></div>'
                + '<div class="odds-box"><div class="odds-lbl">Draw</div><div class="odds-val" style="color:var(--b)">' + str(odds_d or "--") + '</div></div>'
                + '<div class="odds-box"><div class="odds-lbl">Away</div><div class="odds-val" style="color:var(--w)">' + str(odds_a or "--") + '</div></div>'
                + '</div>'
            )
        content += '</div>'

        # GOAL MARKETS
        content += '<div class="card up d3"><div class="card-title">GOAL MARKETS</div>'
        content += prob_bar("Over 1.5 Goals", o15, "green")
        content += prob_bar("Over 2.5 Goals", o25, "blue")
        content += prob_bar("Both Teams Score", btts, "cyan")
        content += prob_bar("Under 2.5 Goals", round(100-o25,1), "orange")
        if xg_h and xg_a:
            content += (
                '<div style="display:flex;gap:16px;margin-top:10px;padding-top:10px;border-top:1px solid var(--bdr)">'
                + '<div><div style="font-size:.48rem;color:var(--t3);text-transform:uppercase;letter-spacing:1px">Home xG</div>'
                + '<div style="font-size:1.2rem;font-weight:900;color:var(--g)">' + str(round(xg_h,2)) + '</div></div>'
                + '<div><div style="font-size:.48rem;color:var(--t3);text-transform:uppercase;letter-spacing:1px">Away xG</div>'
                + '<div style="font-size:1.2rem;font-weight:900;color:var(--b)">' + str(round(xg_a,2)) + '</div></div>'
                + '<div><div style="font-size:.48rem;color:var(--t3);text-transform:uppercase;letter-spacing:1px">Total xG</div>'
                + '<div style="font-size:1.2rem;font-weight:900;color:var(--wh)">' + str(round(xg_h+xg_a,2)) + '</div></div>'
                + '</div>'
            )
        if odds_o15 or odds_o25:
            content += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">'
            if odds_o15: content += '<div style="background:var(--s3);border-radius:8px;padding:6px 12px;font-size:.65rem"><div style="color:var(--t3)">O1.5</div><div style="font-weight:800;color:var(--g)">' + str(odds_o15) + '</div></div>'
            if odds_o25: content += '<div style="background:var(--s3);border-radius:8px;padding:6px 12px;font-size:.65rem"><div style="color:var(--t3)">O2.5</div><div style="font-weight:800;color:var(--b)">' + str(odds_o25) + '</div></div>'
            content += '</div>'
        content += '</div>'

        # FORM
        h_trend = match_predictor.form_trend(h_form)
        a_trend = match_predictor.form_trend(a_form)
        tc_ht   = "var(--g)" if h_trend=="RISING" else "var(--r)" if h_trend=="FALLING" else "var(--t3)"
        tc_at   = "var(--g)" if a_trend=="RISING" else "var(--r)" if a_trend=="FALLING" else "var(--t3)"
        h_pts   = sum(3 if r=="W" else 1 if r=="D" else 0 for r in h_form[-5:]) if h_form else 0
        a_pts   = sum(3 if r=="W" else 1 if r=="D" else 0 for r in a_form[-5:]) if a_form else 0
        content += (
            '<div class="card up d3"><div class="card-title">RECENT FORM</div>'
            + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'
            + '<div><div style="font-size:.75rem;font-weight:700">' + h_name[:20] + '</div>'
            + '<div style="font-size:.58rem;color:' + tc_ht + ';margin-top:2px">' + h_trend + ' &middot; ' + str(h_pts) + 'pts</div></div>'
            + form_dots(h_form) + '</div>'
            + '<div style="display:flex;justify-content:space-between;align-items:center">'
            + '<div><div style="font-size:.75rem;font-weight:700">' + a_name[:20] + '</div>'
            + '<div style="font-size:.58rem;color:' + tc_at + ';margin-top:2px">' + a_trend + ' &middot; ' + str(a_pts) + 'pts</div></div>'
            + form_dots(a_form) + '</div></div>'
        )

        # H2H
        if h2h and h2h.get("total",0)>0:
            tot = h2h["total"]
            hw_p = round(h2h["home_wins"]/tot*100)
            dr_p = round(h2h["draws"]/tot*100)
            aw_p = round(h2h["away_wins"]/tot*100)
            content += (
                '<div class="card up d3"><div class="card-title">HEAD TO HEAD &middot; LAST ' + str(tot) + '</div>'
                + '<div class="h2h-bar">'
                + '<div class="h2h-h" style="flex:' + str(max(hw_p,1)) + '"></div>'
                + '<div class="h2h-d" style="flex:' + str(max(dr_p,1)) + '"></div>'
                + '<div class="h2h-a" style="flex:' + str(max(aw_p,1)) + '"></div></div>'
                + '<div class="h2h-labels" style="margin-bottom:12px">'
                + '<span style="color:var(--g)">' + str(h2h["home_wins"]) + 'W (' + str(hw_p) + '%)</span>'
                + '<span style="color:var(--t3)">' + str(h2h["draws"]) + 'D</span>'
                + '<span style="color:var(--b)">' + str(h2h["away_wins"]) + 'W (' + str(aw_p) + '%)</span></div>'
                + '<div class="info-row"><div class="info-lbl">Avg Goals/Game</div><div class="info-val">' + str(h2h["avg_goals"]) + '</div></div>'
                + '<div class="info-row"><div class="info-lbl">Over 2.5 Rate</div><div class="info-val">' + str(h2h["over_25_pct"]) + '%</div></div>'
                + '<div class="info-row"><div class="info-lbl">Both Teams Score</div><div class="info-val">' + str(h2h["btts_pct"]) + '%</div></div>'
                + '</div>'
            )

        # INJURIES
        if h_inj or a_inj:
            content += '<div class="card up d3"><div class="card-title">INJURY REPORT</div>'
            for inj in h_inj[:3]:
                content += '<div class="info-row"><div class="info-lbl" style="color:var(--r)">' + inj["player"] + '</div><div class="info-val" style="color:var(--t3)">HOME</div></div>'
            for inj in a_inj[:3]:
                content += '<div class="info-row"><div class="info-lbl" style="color:var(--r)">' + inj["player"] + '</div><div class="info-val" style="color:var(--t3)">AWAY</div></div>'
            content += '</div>'

        # EVENTS
        if goals or cards_ev:
            content += '<div class="card up d4"><div class="card-title">MATCH EVENTS</div>'
            for g in goals:
                content += '<div class="ev-row"><div class="ev-min">' + str(g["minute"]) + "\'</div><div class=\"ev-icon\">&#9917;</div><div class=\"ev-name\">" + g["player"] + '</div><div class="ev-team">' + g["team"] + '</div></div>'
            for c_ev in cards_ev:
                ic = "&#129000;" if c_ev["color"]=="yellow" else "&#129001;"
                content += '<div class="ev-row"><div class="ev-min">' + str(c_ev["minute"]) + "\'</div><div class=\"ev-icon\">" + ic + '</div><div class="ev-name">' + c_ev["player"] + '</div></div>'
            content += '</div>'

        # LINEUPS
        if h_lu or a_lu:
            content += '<div class="card up d4"><div class="card-title">CONFIRMED LINEUPS</div><div class="lineup-grid">'
            content += '<div><div class="lu-team">' + h_name[:16] + '</div>'
            for p in h_lu[:11]:
                content += '<div class="lu-player">' + (str(p.get("number","")) + ". " if p.get("number") else "") + p["name"] + '</div>'
            content += '</div><div><div class="lu-team">' + a_name[:16] + '</div>'
            for p in a_lu[:11]:
                content += '<div class="lu-player">' + (str(p.get("number","")) + ". " if p.get("number") else "") + p["name"] + '</div>'
            content += '</div></div></div>'

        return render(content, "match")

    except Exception as ex:
        import traceback; traceback.print_exc()
        return render(
            '<a href="/" class="back">&#8592; Back</a>'
            '<div class="empty"><span class="empty-icon">&#9888;</span>'
            'Error loading match.<br><small style="color:var(--r)">' + str(ex)[:120] + '</small></div>',
            "match")


@app.route("/acca")
def acca_page():
    cards = D.get_fixtures_window(3)
    ns_cards = [c for c in cards if c["is_ns"]]
    picks = []

    for c in ns_cards[:40]:
        if len(picks) >= 5: break
        try:
            pred = get_quick_pred(c)
            if pred["conv"] >= 52 and pred["prob"] >= 58:
                # Get odds
                odds = D.get_odds(c["home"], c["away"])
                tip_key = ("home" if "HOME" in pred["tip"]
                           else "away" if "AWAY" in pred["tip"]
                           else "over_25" if "2.5" in pred["tip"]
                           else "over_15" if "1.5" in pred["tip"] else "home")
                bk_odds = odds.get(tip_key)
                picks.append({
                    "id":    c["id"],
                    "home":  c["home"],  "away":   c["away"],
                    "league":c["league"],"kickoff":c["kickoff"],
                    "tip":   pred["tip"],"prob":   pred["prob"],
                    "conv":  pred["conv"],"tag":   pred["tag"],
                    "odds":  bk_odds,
                })
        except: pass

    content = (
        '<div style="padding:20px 16px 8px">'
        '<div style="font-size:.5rem;font-weight:700;letter-spacing:3px;color:var(--t3);margin-bottom:6px">AUTO-SELECTED</div>'
        '<div style="font-size:2.4rem;font-weight:900;letter-spacing:-1.5px">ACCA <span style="color:var(--g)">BUILDER</span></div>'
        '<div style="font-size:.65rem;color:var(--t3);margin-top:4px">Top picks &middot; 3-day window</div>'
        '</div>'
    )

    if not picks:
        content += (
            '<div class="empty"><span class="empty-icon">&#127919;</span>'
            'No high-confidence picks yet.<br>'
            '<small>Open some fixture pages to generate predictions.</small></div>'
        )
    else:
        total_odds = 1.0
        for p in picks:
            if p["odds"]: total_odds *= p["odds"]

        content += (
            '<div class="card up">'
            '<div class="card-title">ACCUMULATOR</div>'
            '<div style="display:flex;justify-content:space-between;align-items:center">'
            + ('<div><div style="font-size:.65rem;color:var(--t3)">Combined Odds</div>'
               '<div style="font-size:1.8rem;font-weight:900;color:var(--gold)">' + (str(round(total_odds,2)) if total_odds>1 else "N/A") + '</div></div>')
            + ('<div><div style="font-size:.65rem;color:var(--t3)">Picks</div>'
               '<div style="font-size:1.8rem;font-weight:900;color:var(--g)">' + str(len(picks)) + '</div></div>')
            + '</div></div>'
        )
        for p in picks:
            ko = kickoff_label(p["kickoff"])
            odds_str = ('<span style="color:var(--gold);font-weight:800">' + str(p["odds"]) + '</span>') if p["odds"] else ""
            content += (
                '<div class="acca-pick up">'
                + '<div style="font-size:.5rem;color:var(--t3);margin-bottom:4px">' + p["league"] + ' &middot; ' + ko + '</div>'
                + '<div style="font-size:.8rem;font-weight:700;color:var(--wh)">' + p["home"] + ' vs ' + p["away"] + '</div>'
                + '<div class="acca-tip">' + p["tip"] + '</div>'
                + '<div style="display:flex;align-items:center;gap:8px;margin-top:4px">'
                + '<span style="font-size:.62rem;color:var(--t3)">' + str(p["prob"]) + '% &middot; Conv ' + str(round(p["conv"])) + '</span>'
                + odds_str + '</div></div>'
            )
        content += '<div style="font-size:.58rem;color:var(--t2);padding:8px 16px;text-align:center">Gamble responsibly. Predictions are not guaranteed.</div>'

    return render(content, "acca")


@app.route("/tracker")
def tracker_page():
    try: stats = database.get_tracker_stats()
    except:
        stats={"total":0,"wins":0,"losses":0,"hit_rate":0,"pending":0,
               "week_total":0,"week_wins":0,"week_hit_rate":0,
               "by_market":[],"recent":[],"pending_rows":[],
               "streak":{"type":"--","count":0},"roi":0}

    total=stats.get("total",0); wins=stats.get("wins",0)
    losses=stats.get("losses",0); hr=stats.get("hit_rate",0)
    pending=stats.get("pending",0); roi=stats.get("roi",0)
    streak=stats.get("streak",{}); week_hr=stats.get("week_hit_rate",0)
    week_t=stats.get("week_total",0)

    hr_clr  = "var(--g)" if hr>=60 else "var(--w)" if hr>=45 else "var(--r)"
    roi_clr = "var(--g)" if roi>=0 else "var(--r)"
    st_clr  = "var(--g)" if streak.get("type")=="WIN" else "var(--r)" if streak.get("type")=="LOSS" else "var(--t3)"

    content = (
        '<div class="tracker-hero up">'
        + '<div style="display:flex;justify-content:space-between;align-items:flex-start">'
        + '<div><div style="font-size:.48rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t3);margin-bottom:4px">Performance</div>'
        + '<div class="big-num" style="color:' + hr_clr + '">' + str(hr) + '%</div>'
        + '<div class="big-lbl">Hit Rate</div></div>'
        + '<div style="text-align:right">'
        + '<div class="big-num" style="font-size:2rem;color:' + roi_clr + '">' + ("+"+str(roi) if roi>=0 else str(roi)) + '%</div>'
        + '<div class="big-lbl">ROI</div></div></div>'
        + '<div style="display:flex;gap:16px;margin-top:16px;flex-wrap:wrap">'
        + '<div><div class="hstat-n">' + str(total) + '</div><div class="hstat-l">Settled</div></div>'
        + '<div><div class="hstat-n" style="color:var(--g)">' + str(wins) + '</div><div class="hstat-l">Wins</div></div>'
        + '<div><div class="hstat-n" style="color:var(--r)">' + str(losses) + '</div><div class="hstat-l">Losses</div></div>'
        + '<div><div class="hstat-n" style="color:var(--w)">' + str(pending) + '</div><div class="hstat-l">Pending</div></div>'
        + '</div></div>'
    )

    content += (
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:0 12px 8px" class="up d1">'
        + '<div class="card" style="margin:0"><div class="card-title">THIS WEEK</div>'
        + '<div style="font-size:1.8rem;font-weight:900;color:var(--wh)">' + str(week_hr) + '%</div>'
        + '<div style="font-size:.6rem;color:var(--t3);margin-top:2px">' + str(week_t) + ' settled</div></div>'
        + '<div class="card" style="margin:0;text-align:center"><div class="card-title">STREAK</div>'
        + '<div style="font-size:1.8rem;font-weight:900;color:' + st_clr + '">' + str(streak.get("count",0)) + '</div>'
        + '<div style="font-size:.6rem;color:' + st_clr + ';font-weight:700">' + str(streak.get("type","--")) + '</div></div>'
        + '</div>'
    )

    by_market = stats.get("by_market",[])
    if by_market:
        content += '<div class="card up d2"><div class="card-title">PERFORMANCE BY MARKET</div>'
        for m in by_market[:8]:
            mhr = round(m.get("wins",0)/max(m.get("total",1),1)*100,1)
            mc  = "var(--g)" if mhr>=60 else "var(--w)" if mhr>=45 else "var(--r)"
            content += (
                '<div class="perf-row">'
                + '<div><div style="font-size:.68rem;color:var(--t3);font-weight:700">' + str(m.get("market","")) + '</div>'
                + '<div style="height:3px;background:rgba(255,255,255,.05);border-radius:3px;margin-top:4px;width:120px">'
                + '<div style="height:100%;width:' + str(min(mhr,100)) + '%;background:' + mc + ';border-radius:3px"></div></div></div>'
                + '<div style="text-align:right">'
                + '<div style="font-size:.78rem;font-weight:800;color:' + mc + '">' + str(mhr) + '%</div>'
                + '<div style="font-size:.58rem;color:var(--t3)">' + str(m.get("total",0)) + ' bets</div></div>'
                + '</div>'
            )
        content += '</div>'

    recent = stats.get("recent",[])
    if recent:
        content += '<div class="card up d3"><div class="card-title">RECENT RESULTS</div>'
        for r in recent[:10]:
            win = r.get("result")=="WIN"
            dot = "var(--g)" if win else "var(--r)"
            sc  = (str(r.get("actual_home_score","")) + "-" + str(r.get("actual_away_score",""))) if r.get("actual_home_score") is not None else ""
            content += (
                '<div class="result-row">'
                + '<div class="win-dot" style="background:' + dot + '"></div>'
                + '<div style="flex:1;min-width:0">'
                + '<div style="font-size:.7rem;font-weight:700;color:var(--wh);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + str(r.get("home_team","")) + ' vs ' + str(r.get("away_team","")) + '</div>'
                + '<div style="font-size:.6rem;color:var(--t3);margin-top:1px">' + str(r.get("market","")) + ' &middot; ' + str(r.get("probability",0)) + '% &middot; ' + str(r.get("league_name",""))[:20] + '</div></div>'
                + '<div style="text-align:right"><div style="font-size:.7rem;font-weight:800;color:' + dot + '">' + str(r.get("result","")) + '</div>'
                + '<div style="font-size:.58rem;color:var(--t3)">' + sc + '</div></div>'
                + '</div>'
            )
        content += '</div>'

    pending_rows = stats.get("pending_rows",[])
    if pending_rows:
        content += '<div class="card up d4"><div class="card-title">PENDING (' + str(pending) + ')</div>'
        for p in pending_rows[:6]:
            content += (
                '<div class="result-row">'
                + '<div class="win-dot" style="background:var(--w)"></div>'
                + '<div style="flex:1;min-width:0">'
                + '<div style="font-size:.7rem;font-weight:700;color:var(--wh)">' + str(p.get("home_team","")) + ' vs ' + str(p.get("away_team","")) + '</div>'
                + '<div style="font-size:.6rem;color:var(--t3)">' + str(p.get("market","")) + ' &middot; ' + str(p.get("probability",0)) + '%</div></div>'
                + '<span class="badge bg-orange">PENDING</span></div>'
            )
        content += '</div>'

    if total==0 and pending==0:
        content += (
            '<div class="empty"><span class="empty-icon">&#128202;</span>'
            'No predictions tracked yet.<br>'
            'Open any fixture to generate a prediction.<br>'
            'Results settle automatically after matches finish.</div>'
        )

    return render(content, "tracker")


@app.route("/api/live-count")
def live_count():
    try:
        lives = D.get_live_fixtures()
        return jsonify({"count": len(lives)})
    except: return jsonify({"count": 0})


@app.route("/api/settle")
def settle():
    try:
        import scheduler
        result = scheduler.run_settlement_job()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status":"error","error":str(e)})


@app.route("/api/morning")
def morning():
    try:
        import scheduler
        result = scheduler.run_morning_job()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status":"error","error":str(e)})


@app.route("/manifest.json")
def manifest():
    return jsonify({
        "name":"ProPred NG","short_name":"ProPred",
        "start_url":"/","display":"standalone",
        "background_color":"#03050a","theme_color":"#03050a",
        "icons":[{"src":"/static/icon.png","sizes":"192x192","type":"image/png"}]
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
