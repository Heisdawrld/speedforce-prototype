from flask import Flask, render_template_string, request, jsonify, Response
import os, math, json, requests
from datetime import datetime, timedelta, timezone
import match_predictor, database, sportmonks, scheduler

app = Flask(__name__)
database.init_db()

WAT = 1  # UTC+1 Nigeria

# ─────────────────────────────────────────────────────────────
# TIME HELPERS
# ─────────────────────────────────────────────────────────────

def now_wat():
    return datetime.now(timezone.utc) + timedelta(hours=WAT)

def parse_kickoff(raw):
    if not raw: return now_wat()
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z","+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt + timedelta(hours=WAT)
    except:
        return now_wat()

def kickoff_label(raw):
    dt = parse_kickoff(raw)
    today = now_wat().date()
    if dt.date() == today: return dt.strftime("%H:%M")
    return dt.strftime("%H:%M %d %b")

# ─────────────────────────────────────────────────────────────
# LEAGUE METADATA
# ─────────────────────────────────────────────────────────────

LEAGUE_META = {
    "Premier League":         {"icon":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","country":"England","tier":1},
    "La Liga":                {"icon":"🇪🇸","country":"Spain","tier":1},
    "Serie A":                {"icon":"🇮🇹","country":"Italy","tier":1},
    "Bundesliga":             {"icon":"🇩🇪","country":"Germany","tier":1},
    "Ligue 1":                {"icon":"🇫🇷","country":"France","tier":1},
    "UEFA Champions League":  {"icon":"🏆","country":"Europe","tier":1},
    "UEFA Europa League":     {"icon":"🏆","country":"Europe","tier":1},
    "UEFA Conference League": {"icon":"🏆","country":"Europe","tier":2},
    "Championship":           {"icon":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","country":"England","tier":2},
    "Eredivisie":             {"icon":"🇳🇱","country":"Netherlands","tier":2},
    "Primeira Liga":          {"icon":"🇵🇹","country":"Portugal","tier":2},
    "Super Lig":              {"icon":"🇹🇷","country":"Turkey","tier":2},
    "Scottish Premiership":   {"icon":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","country":"Scotland","tier":2},
    "Belgian Pro League":     {"icon":"🇧🇪","country":"Belgium","tier":2},
    "Jupiler Pro League":     {"icon":"🇧🇪","country":"Belgium","tier":2},
    "MLS":                    {"icon":"🇺🇸","country":"USA","tier":2},
    "Liga MX":                {"icon":"🇲🇽","country":"Mexico","tier":2},
    "Brasileirao":            {"icon":"🇧🇷","country":"Brazil","tier":2},
    "Saudi Professional League":{"icon":"🇸🇦","country":"Saudi Arabia","tier":2},
    "Eliteserien":            {"icon":"🇳🇴","country":"Norway","tier":3},
    "Allsvenskan":            {"icon":"🇸🇪","country":"Sweden","tier":3},
    "Ekstraklasa":            {"icon":"🇵🇱","country":"Poland","tier":3},
    "Czech Liga":             {"icon":"🇨🇿","country":"Czech Rep","tier":3},
    "Greek Super League":     {"icon":"🇬🇷","country":"Greece","tier":3},
    "J1 League":              {"icon":"🇯🇵","country":"Japan","tier":3},
    "Chinese Super League":   {"icon":"🇨🇳","country":"China","tier":3},
    "NPFL":                   {"icon":"🇳🇬","country":"Nigeria","tier":2},
    # Tier 2
    "Primeira Liga":          {"icon":"🇵🇹","country":"Portugal","tier":2},
    "Süper Lig":              {"icon":"🇹🇷","country":"Turkey","tier":2},
    "Scottish Premiership":   {"icon":"🏴72334f","country":"Scotland","tier":2},
    "Russian Premier League": {"icon":"🇷🇺","country":"Russia","tier":2},
    "Ukrainian Premier League":{"icon":"🇺🇦","country":"Ukraine","tier":2},
    "Argentine Primera":      {"icon":"🇦🇷","country":"Argentina","tier":2},
    "Serie A (Brazil)":       {"icon":"🇧🇷","country":"Brazil","tier":2},
    "Brasileirao Serie A":    {"icon":"🇧🇷","country":"Brazil","tier":2},
    # Tier 3
    "Ekstraklasa":            {"icon":"🇵🇱","country":"Poland","tier":3},
    "Czech Liga":             {"icon":"🇨🇿","country":"Czech Rep","tier":3},
    "Greek Super League":     {"icon":"🇬🇷","country":"Greece","tier":3},
    "Super Liga Serbia":      {"icon":"🇷🇸","country":"Serbia","tier":3},
    "Eliteserien":            {"icon":"🇳🇴","country":"Norway","tier":3},
    "Allsvenskan":            {"icon":"🇸🇪","country":"Sweden","tier":3},
    "Veikkausliiga":          {"icon":"🇫🇮","country":"Finland","tier":3},
    "Fortuna Liga":           {"icon":"🇨🇿","country":"Slovakia","tier":3},
    "1. HNL":                 {"icon":"🇭🇷","country":"Croatia","tier":3},
    "Bundesliga Austria":     {"icon":"🇦🇹","country":"Austria","tier":3},
    "J1 League":              {"icon":"🇯🇵","country":"Japan","tier":3},
    "K League 1":             {"icon":"🇰🇷","country":"South Korea","tier":3},
    "Chinese Super League":   {"icon":"🇨🇳","country":"China","tier":3},
    "A-League":               {"icon":"🇦🇺","country":"Australia","tier":3},
    "Saudi Pro League":       {"icon":"🇸🇦","country":"Saudi Arabia","tier":3},
    "Indian Super League":    {"icon":"🇮🇳","country":"India","tier":3},
    "Botola Pro":             {"icon":"🇲🇦","country":"Morocco","tier":3},
    "NPSL":                   {"icon":"🇳🇬","country":"Nigeria","tier":3},
    "Ligue Professionnelle 1":{"icon":"🇩🇿","country":"Algeria","tier":3},
    "South African PSL":      {"icon":"🇿🇦","country":"South Africa","tier":3},
    "Egyptian Premier League":{"icon":"🇪🇬","country":"Egypt","tier":3},
    "Ghanaian Premier League":{"icon":"🇬🇭","country":"Ghana","tier":3},
    "CAF Champions League":   {"icon":"🏆","country":"Africa","tier":2},
}

def get_league_meta(name):
    if not name: return {"icon":"🌐","country":"World","tier":3}
    n = name.strip()
    if n in LEAGUE_META: return LEAGUE_META[n]
    nl = n.lower()
    for k, v in LEAGUE_META.items():
        if k.lower() in nl or nl in k.lower(): return v
    return {"icon":"🌐","country":"World","tier":3}

# ─────────────────────────────────────────────────────────────
# FIXTURE PARSING
# ─────────────────────────────────────────────────────────────

def build_fixture_card(fx):
    """Convert Sportmonks fixture into our standard card format."""
    h_id, h_name, a_id, a_name = sportmonks.extract_teams(fx)
    state  = sportmonks.extract_state(fx)
    h_g, a_g = sportmonks.extract_score(fx)
    league = fx.get("league") or {}
    l_name = league.get("name","") if isinstance(league, dict) else ""
    l_id   = league.get("id",0) if isinstance(league, dict) else 0
    # Get country directly from Sportmonks league.country
    l_country_raw = ""
    if isinstance(league, dict):
        c_obj = league.get("country") or {}
        if isinstance(c_obj, dict): l_country_raw = c_obj.get("name","")
    meta = get_league_meta(l_name)
    if l_country_raw: meta = dict(meta); meta["country"] = l_country_raw
    raw_ko = fx.get("starting_at") or fx.get("date","")

    live_states = {"1H","2H","HT","ET","PEN","LIVE","INPLAY"}
    is_live = state.upper() in live_states or state.isdigit()
    is_ft   = state.upper() in ("FT","AET","PEN","FIN","FINISHED","AWARDED")
    is_ns   = not is_live and not is_ft

    ko_dt = parse_kickoff(raw_ko)
    _today = now_wat().date(); _tmrw = _today + timedelta(days=1)
    if ko_dt.date() == _today:  date_label = "TODAY"
    elif ko_dt.date() == _tmrw: date_label = "TOMORROW"
    else:                       date_label = ko_dt.strftime("%a %-d %b").upper()
    return {
        "id":         fx.get("id"),
        "home_id":    h_id, "home": h_name or "Home",
        "away_id":    a_id, "away": a_name or "Away",
        "league":     l_name, "league_id": l_id,
        "country":    meta["country"], "icon": meta["icon"], "tier": meta["tier"],
        "kickoff":    raw_ko,
        "date_label": date_label,
        "state":      state,
        "is_live":    is_live,
        "is_ft":      is_ft,
        "is_ns":      is_ns,
        "score_h":    h_g, "score_a": a_g,
    }

def get_all_cards(days=3):
    """Get fixtures for next N days as standard cards."""
    ck = f"window_cards_v2_{days}"
    cached = database.cache_get("h2h_cache", ck, max_age_hours=0.4)
    if cached:
        try: return json.loads(cached)
        except: pass
    fixtures = sportmonks.get_fixtures_window(days)
    cards = [build_fixture_card(f) for f in fixtures]
    cards.sort(key=lambda c: c["kickoff"] or "")
    database.cache_set("h2h_cache", ck, json.dumps(cards))
    return cards

def get_all_today_cards():
    return get_all_cards(3)

# ─────────────────────────────────────────────────────────────
# QUICK PREDICTION (for list views -- no API calls)
# ─────────────────────────────────────────────────────────────

def quick_predict(card, preds=None):
    """
    Fast prediction from Sportmonks probabilities.
    Called for fixture list -- uses predictions endpoint data.
    Returns: tip, prob, tag
    """
    if not preds: return "--", 0, "MONITOR"

    hw = preds.get("home_win", 33.3)
    dw = preds.get("draw", 33.3)
    aw = preds.get("away_win", 33.3)
    o25 = preds.get("over_25", 45)
    btts = preds.get("btts", 45)

    best_tip = max([
        ("HOME WIN", hw),
        ("DRAW", dw),
        ("AWAY WIN", aw),
        ("OVER 2.5", o25),
        ("GG", btts),
    ], key=lambda x: x[1])

    tip, prob = best_tip
    if prob >= 70 and tip not in ("DRAW",):
        tag = "RELIABLE"
    elif prob >= 58:
        tag = "SOLID"
    else:
        tag = "MONITOR"

    return tip, round(prob, 1), tag

# ─────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────

def tip_color(tip):
    if "WIN" in tip:     return "var(--g)"
    if "OVER" in tip:    return "var(--b)"
    if "GG" in tip:      return "var(--cy)"
    if "UNDER" in tip:   return "var(--gold)"
    if "DRAW" in tip:    return "var(--w)"
    return "var(--t2)"

def form_dot(r):
    cls = {"W":"w","D":"d","L":"l"}.get(r.upper(),"d")
    return f'<span class="fd fd-{cls}">{r.upper()}</span>'

def form_dots(fl):
    if not fl: return '<span class="no-data">--</span>'
    return "".join(form_dot(r) for r in list(fl)[-5:])

def prob_bar(label, pct, color="green", icon=""):
    c = {"green":"var(--g)","blue":"var(--b)","orange":"var(--w)","red":"var(--r)","cyan":"var(--cy)"}.get(color,"var(--g)")
    pct = min(round(float(pct),1), 100)
    return f'''<div class="pb-row">
      <div class="pb-top"><span class="pb-label">{icon} {label}</span><span class="pb-val" style="color:{c}">{pct}%</span></div>
      <div class="pb-track"><div class="pb-fill" style="width:{pct}%;background:{c}"></div></div>
    </div>'''

def live_dot():
    return '<span class="live-pulse"></span>'

def state_badge(card):
    if card["is_live"]:
        s = card["state"]
        min_str = f"{s}'" if str(s).isdigit() else s
        return f'<span class="s-badge s-live">{live_dot()} {min_str}</span>'
    if card["is_ft"]:
        return '<span class="s-badge s-ft">FT</span>'
    return f'<span class="s-badge s-ns">{kickoff_label(card["kickoff"])}</span>'

def score_display(card):
    if card["score_h"] is not None and card["score_a"] is not None:
        return f'<span class="score">{card["score_h"]} - {card["score_a"]}</span>'
    return ""

# ─────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────

CSS = """
:root{
  --bg:#03050a;--s:#080c14;--s2:#0d1220;--s3:#131929;--s4:#1a2235;
  --g:#00ff87;--g2:#00e676;--b:#4f8ef7;--b2:#3b7cf0;
  --w:#ff9f0a;--r:#ff453a;--pu:#bf5af2;--cy:#32d7f0;--gold:#ffd60a;
  --t:#4a5568;--t2:#718096;--t3:#94a3b8;--wh:#f0f4f8;
  --bdr:rgba(255,255,255,.04);--bdr2:rgba(255,255,255,.08);--bdr3:rgba(255,255,255,.13);
  --glow:0 0 40px rgba(0,255,135,.06);
  --card-bg:linear-gradient(145deg,#0a0f1a,#080c14);
  --green-glow:0 0 20px rgba(0,255,135,.15);
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth;height:100%}
body{background:var(--bg);color:var(--t3);font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Inter',sans-serif;font-size:13px;min-height:100vh;padding-bottom:90px;overflow-x:hidden}
a{text-decoration:none;color:inherit}
::selection{background:rgba(0,255,135,.15)}
::-webkit-scrollbar{width:2px;height:2px}
::-webkit-scrollbar-thumb{background:var(--bdr3);border-radius:2px}

/* ── NAV ── */
nav{position:sticky;top:0;z-index:300;background:rgba(3,5,10,.88);backdrop-filter:blur(32px) saturate(180%);-webkit-backdrop-filter:blur(32px) saturate(180%);border-bottom:1px solid var(--bdr)}
.nav-inner{max-width:520px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;padding:13px 16px}
.logo{display:flex;align-items:baseline;gap:1px}
.logo-pro{font-size:1.05rem;font-weight:900;color:var(--wh);letter-spacing:-.5px}
.logo-pred{font-size:1.05rem;font-weight:900;color:var(--g);letter-spacing:-.5px}
.logo-ng{font-size:.48rem;font-weight:600;letter-spacing:2px;color:var(--t2);text-transform:uppercase;margin-left:3px;margin-bottom:1px}
.nav-right{display:flex;align-items:center;gap:6px}
.npill{font-size:.56rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;padding:5px 11px;border-radius:50px;border:1px solid var(--bdr2);color:var(--t2);transition:all .18s;white-space:nowrap}
.npill:active,.npill.on{border-color:var(--g);color:var(--g);background:rgba(0,255,135,.07)}
.live-count{font-size:.5rem;font-weight:800;padding:3px 7px;border-radius:50px;background:rgba(255,69,58,.15);color:var(--r);border:1px solid rgba(255,69,58,.25);letter-spacing:.5px}

/* ── SHELL ── */
.shell{max-width:520px;margin:0 auto;padding:0 14px}

/* ── HERO ── */
.hero{padding:22px 0 16px;position:relative}
.hero-eyebrow{font-size:.52rem;font-weight:600;letter-spacing:3px;text-transform:uppercase;color:var(--t2);margin-bottom:8px}
.hero-title{font-size:2.8rem;font-weight:900;color:var(--wh);line-height:.95;letter-spacing:-1.5px;margin-bottom:6px}
.hero-title span{color:var(--g)}
.hero-sub{font-size:.65rem;color:var(--t2);letter-spacing:.3px}
.hero-stats{display:flex;gap:16px;margin-top:14px}
.hstat{display:flex;flex-direction:column;gap:2px}
.hstat-n{font-size:1.6rem;font-weight:900;color:var(--wh);letter-spacing:-1px;line-height:1}
.hstat-l{font-size:.5rem;font-weight:600;letter-spacing:1.8px;text-transform:uppercase;color:var(--t2)}

/* ── SEARCH ── */
.search-wrap{position:relative;margin-bottom:14px}
.search-inp{width:100%;background:var(--s2);border:1px solid var(--bdr2);border-radius:14px;padding:11px 14px 11px 40px;color:var(--wh);font-size:.78rem;outline:none;transition:all .2s;-webkit-appearance:none}
.search-inp:focus{border-color:rgba(0,255,135,.35);background:var(--s3);box-shadow:0 0 0 3px rgba(0,255,135,.06)}
.search-inp::placeholder{color:var(--t)}
.s-icon{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--t);pointer-events:none;font-size:.85rem}
.s-clear{position:absolute;right:12px;top:50%;transform:translateY(-50%);color:var(--t);cursor:pointer;display:none;font-size:.72rem;padding:4px;background:var(--s3);border-radius:50%;width:20px;height:20px;align-items:center;justify-content:center}
.s-clear.vis{display:flex}

/* ── SECTION HEADERS ── */
.sec-hd{font-size:.52rem;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--t2);padding:18px 0 10px;display:flex;align-items:center;gap:10px}
.sec-hd::after{content:'';flex:1;height:1px;background:var(--bdr)}
.sec-hd-dot{width:5px;height:5px;border-radius:50%;background:var(--g);flex-shrink:0}

/* ── LEAGUE GRID ── */
.lg-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:6px}
.lg-tile{background:var(--card-bg);border:1px solid var(--bdr);border-radius:16px;padding:15px 13px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;display:block}
.lg-tile::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,rgba(0,255,135,.03),transparent);opacity:0;transition:opacity .2s;border-radius:16px}
.lg-tile:active,.lg-tile:hover{border-color:rgba(0,255,135,.2);transform:scale(.975);box-shadow:var(--green-glow)}
.lg-tile:active::before,.lg-tile:hover::before{opacity:1}
.lg-tile.dim{opacity:.3;pointer-events:none}
.lt-icon{font-size:1.5rem;margin-bottom:7px;display:block}
.lt-name{font-size:.73rem;font-weight:800;color:var(--wh);line-height:1.2;margin-bottom:3px}
.lt-country{font-size:.54rem;letter-spacing:1.2px;text-transform:uppercase;color:var(--t2)}
.lt-fixtures{position:absolute;top:10px;right:10px;font-size:.52rem;font-weight:700;color:var(--g);background:rgba(0,255,135,.1);border:1px solid rgba(0,255,135,.15);border-radius:50px;padding:2px 7px;letter-spacing:.5px}
.lt-sure{position:absolute;bottom:10px;right:10px;font-size:.52rem;color:var(--g);font-weight:700}

/* ── FIXTURE LIST ── */
.fx-wrap{border-radius:18px;overflow:hidden;border:1px solid var(--bdr);background:var(--s)}
.fx-row{display:flex;align-items:center;padding:13px 14px;border-bottom:1px solid var(--bdr);cursor:pointer;transition:background .15s;gap:10px;text-decoration:none;color:inherit}
.fx-row:last-child{border-bottom:none}
.fx-row:active,.fx-row:hover{background:rgba(255,255,255,.025)}
.fx-time{flex-shrink:0;width:42px;text-align:center}
.fx-teams{flex:1;min-width:0}
.fx-home{font-size:.74rem;font-weight:700;color:var(--wh);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:2px}
.fx-away{font-size:.7rem;color:var(--t3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fx-right{flex-shrink:0;text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:3px}
.fx-tip{font-size:.62rem;font-weight:800;letter-spacing:.8px}
.fx-prob{font-size:.58rem;color:var(--t2);font-weight:600}
.fx-tag{font-size:.52rem;font-weight:700;letter-spacing:.8px}

/* ── STATE BADGES ── */
.s-badge{display:inline-flex;align-items:center;gap:3px;font-size:.56rem;font-weight:700;letter-spacing:.8px;padding:3px 7px;border-radius:50px}
.s-live{background:rgba(255,69,58,.12);color:var(--r);border:1px solid rgba(255,69,58,.25)}
.s-ft{background:rgba(74,85,104,.15);color:var(--t2);border:1px solid var(--bdr2)}
.s-ns{background:transparent;color:var(--t2);font-size:.62rem;border:none;padding:0}
.score{font-size:.9rem;font-weight:900;color:var(--wh);letter-spacing:-0.5px}

/* ── LIVE PULSE ── */
.live-pulse{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--r);animation:pulse 1.4s ease-in-out infinite;flex-shrink:0}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(255,69,58,.4)}50%{opacity:.7;box-shadow:0 0 0 4px rgba(255,69,58,0)}}

/* ── TABS ── */
.tabs{display:flex;gap:5px;overflow-x:auto;padding:2px 0 10px;scrollbar-width:none;margin-bottom:2px}
.tabs::-webkit-scrollbar{display:none}
.tab{flex-shrink:0;font-size:.58rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;padding:6px 13px;border-radius:50px;border:1px solid var(--bdr2);color:var(--t2);white-space:nowrap;transition:all .18s;cursor:pointer;display:flex;align-items:center;gap:5px}
.tab.on,.tab:active{border-color:var(--g);color:var(--g);background:rgba(0,255,135,.07)}
.tab-n{font-size:.52rem;background:rgba(0,255,135,.12);color:var(--g);border-radius:50px;padding:1px 5px;font-weight:800}

/* ── MATCH PAGE ── */
.match-hero{background:linear-gradient(180deg,rgba(0,255,135,.06) 0%,transparent 100%);border:1px solid rgba(0,255,135,.1);border-radius:20px;padding:22px 18px;margin-bottom:10px;text-align:center;position:relative;overflow:hidden}
.match-hero::before{content:'';position:absolute;top:-40px;left:50%;transform:translateX(-50%);width:200px;height:200px;background:radial-gradient(circle,rgba(0,255,135,.08),transparent 70%);pointer-events:none}
.match-league{font-size:.52rem;font-weight:600;letter-spacing:2.5px;text-transform:uppercase;color:var(--t2);margin-bottom:12px}
.match-teams{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px}
.team-block{flex:1;text-align:center}
.team-name{font-size:.82rem;font-weight:800;color:var(--wh);line-height:1.3}
.vs-block{flex-shrink:0;text-align:center}
.vs-score{font-size:2.4rem;font-weight:900;color:var(--wh);letter-spacing:-2px;line-height:1}
.vs-sep{font-size:.6rem;font-weight:700;color:var(--t2);letter-spacing:2px}
.match-meta{display:flex;justify-content:center;gap:10px;flex-wrap:wrap}

/* ── PREDICTION CARD ── */
.pred-card{border-radius:18px;padding:18px;margin-bottom:8px;position:relative;overflow:hidden}
.pred-card.reliable{background:linear-gradient(135deg,rgba(0,255,135,.08),rgba(0,230,118,.04));border:1px solid rgba(0,255,135,.2)}
.pred-card.solid{background:linear-gradient(135deg,rgba(79,142,247,.07),rgba(59,124,240,.03));border:1px solid rgba(79,142,247,.18)}
.pred-card.avoid{background:linear-gradient(135deg,rgba(255,69,58,.07),rgba(244,67,54,.03));border:1px solid rgba(255,69,58,.18)}
.pred-card.monitor{background:var(--s);border:1px solid var(--bdr)}
.tip-main{font-size:1.6rem;font-weight:900;letter-spacing:-0.5px;margin-bottom:2px}
.tip-prob{font-size:.65rem;font-weight:700;color:var(--t3);margin-bottom:12px}
.tip-reason{font-size:.68rem;color:var(--t3);line-height:1.6;background:rgba(0,0,0,.2);border-radius:10px;padding:10px 12px;margin-top:10px}

/* ── PROB BARS ── */
.pb-row{margin-bottom:10px}
.pb-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.pb-label{font-size:.64rem;color:var(--t3);font-weight:600}
.pb-val{font-size:.68rem;font-weight:800}
.pb-track{height:5px;background:rgba(255,255,255,.04);border-radius:50px;overflow:hidden}
.pb-fill{height:100%;border-radius:50px;transition:width .8s cubic-bezier(.4,0,.2,1)}

/* ── FORM DOTS ── */
.form-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.fd{width:24px;height:24px;border-radius:7px;display:inline-flex;align-items:center;justify-content:center;font-size:.57rem;font-weight:800;flex-shrink:0}
.fd-w{background:rgba(0,255,135,.14);color:var(--g)}
.fd-d{background:rgba(79,142,247,.14);color:var(--b)}
.fd-l{background:rgba(255,69,58,.14);color:var(--r)}
.no-data{font-size:.6rem;color:var(--t)}

/* ── H2H ── */
.h2h-bar{display:flex;border-radius:50px;overflow:hidden;height:8px;margin:10px 0}
.h2h-h{background:var(--g);transition:flex .6s ease}
.h2h-d{background:var(--t)}
.h2h-a{background:var(--b)}
.h2h-labels{display:flex;justify-content:space-between;font-size:.6rem;font-weight:700}

/* ── STATS GRID ── */
.stats-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.stat-cell{background:var(--s2);border:1px solid var(--bdr);border-radius:12px;padding:11px;text-align:center}
.stat-val{font-size:1.3rem;font-weight:900;color:var(--wh);letter-spacing:-0.5px;line-height:1;margin-bottom:2px}
.stat-lbl{font-size:.52rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:var(--t2)}

/* ── VALUE BETS ── */
.vbet{background:linear-gradient(135deg,rgba(191,90,242,.08),rgba(168,85,247,.04));border:1px solid rgba(191,90,242,.2);border-radius:14px;padding:13px 14px;margin-bottom:6px}
.vbet-label{font-size:.58rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:var(--pu)}
.vbet-val{font-size:1.1rem;font-weight:900;color:var(--wh);margin:2px 0}
.vbet-sub{font-size:.6rem;color:var(--t3)}

/* ── REFEREE ── */
.ref-card{background:var(--s2);border:1px solid var(--bdr);border-radius:14px;padding:13px 14px}
.ref-signal{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:50px;font-size:.58rem;font-weight:700;letter-spacing:.8px}
.ref-hot{background:rgba(255,69,58,.1);color:var(--r);border:1px solid rgba(255,69,58,.2)}
.ref-ok{background:rgba(0,255,135,.08);color:var(--g);border:1px solid rgba(0,255,135,.15)}

/* ── LINEUP ── */
.lineup-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
.lineup-col{}
.lineup-team{font-size:.58rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--t2);margin-bottom:6px}
.lineup-player{font-size:.68rem;color:var(--t3);padding:4px 0;border-bottom:1px solid var(--bdr);line-height:1.4}
.lineup-player:last-child{border-bottom:none}

/* ── EVENTS ── */
.event-row{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--bdr);font-size:.68rem}
.event-row:last-child{border-bottom:none}
.ev-min{width:28px;font-size:.62rem;font-weight:700;color:var(--t2);flex-shrink:0}
.ev-icon{font-size:.8rem;flex-shrink:0}
.ev-name{flex:1;color:var(--t3)}
.ev-side{font-size:.56rem;color:var(--t2)}

/* ── CARDS (generic) ── */
.card{background:var(--s);border:1px solid var(--bdr);border-radius:16px;padding:16px;margin-bottom:8px}
.card-title{font-size:.6rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t2);margin-bottom:12px;display:flex;align-items:center;gap:6px}
.card-title-icon{font-size:.85rem}

/* ── BADGES ── */
.badge{display:inline-flex;align-items:center;gap:3px;font-size:.55rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;padding:3px 9px;border-radius:50px}
.bg-green{background:rgba(0,255,135,.1);color:var(--g);border:1px solid rgba(0,255,135,.2)}
.bg-blue{background:rgba(79,142,247,.1);color:var(--b);border:1px solid rgba(79,142,247,.2)}
.bg-red{background:rgba(255,69,58,.1);color:var(--r);border:1px solid rgba(255,69,58,.2)}
.bg-orange{background:rgba(255,159,10,.1);color:var(--w);border:1px solid rgba(255,159,10,.2)}
.bg-muted{background:rgba(74,85,104,.1);color:var(--t2);border:1px solid var(--bdr2)}
.bg-pu{background:rgba(191,90,242,.1);color:var(--pu);border:1px solid rgba(191,90,242,.2)}

/* ── TRACKER ── */
.tracker-hero{background:linear-gradient(135deg,rgba(0,255,135,.07),rgba(79,142,247,.04));border:1px solid rgba(0,255,135,.14);border-radius:20px;padding:22px;margin-bottom:10px}
.big-num{font-size:3.5rem;font-weight:900;line-height:1;letter-spacing:-2px;color:var(--wh)}
.big-label{font-size:.52rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--t2);margin-top:3px}
.perf-row{display:flex;justify-content:space-between;align-items:center;padding:11px 0;border-bottom:1px solid var(--bdr);font-size:.72rem}
.perf-row:last-child{border-bottom:none}
.result-row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--bdr)}
.result-row:last-child{border-bottom:none}
.win-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}

/* ── ACCA ── */
.acca-row{display:flex;justify-content:space-between;align-items:center;padding:13px 14px;border-bottom:1px solid var(--bdr);gap:10px}
.acca-row:last-child{border-bottom:none}
.acca-odds-box{background:linear-gradient(135deg,rgba(0,255,135,.12),rgba(0,230,118,.06));border:1px solid rgba(0,255,135,.2);border-radius:14px;padding:14px;text-align:center;margin-top:10px}
.acca-odds-num{font-size:2rem;font-weight:900;color:var(--g);letter-spacing:-1px}

/* ── MISC ── */
.back{display:inline-flex;align-items:center;gap:5px;font-size:.58rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--t2);padding:14px 0 16px;transition:color .18s}
.back:hover{color:var(--wh)}
.empty{text-align:center;padding:60px 20px;color:var(--t2);font-size:.75rem;line-height:2}
.empty-icon{font-size:2.5rem;display:block;margin-bottom:12px;opacity:.4}
.divider{height:1px;background:var(--bdr);margin:12px 0}
.expand-toggle{display:flex;justify-content:space-between;align-items:center;cursor:pointer;padding:12px 0;font-size:.7rem;font-weight:700;color:var(--t3);user-select:none;transition:color .18s}
.expand-toggle:hover{color:var(--wh)}
.expand-arrow{transition:transform .3s;font-size:.7rem;color:var(--t2)}
.expand-arrow.open{transform:rotate(180deg)}
.expand-body{overflow:hidden;max-height:0;transition:max-height .45s ease}
.expand-body.open{max-height:3000px}
.info-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--bdr);font-size:.69rem}
.info-row:last-child{border-bottom:none}
.info-lbl{color:var(--t2)}
.info-val{color:var(--wh);font-weight:700}

/* ── ANIMATIONS ── */
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes spin{to{transform:rotate(360deg)}}
.up{animation:fadeUp .3s ease both}
.d1{animation-delay:.05s}.d2{animation-delay:.1s}.d3{animation-delay:.15s}.d4{animation-delay:.2s}
.spin{animation:spin .8s linear infinite}
"""

# ─────────────────────────────────────────────────────────────
# HTML LAYOUT
# ─────────────────────────────────────────────────────────────

def get_live_count():
    try:
        lives = sportmonks.get_livescores()
        return len(lives) if lives else 0
    except: return 0

LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ProPred">
<meta name="theme-color" content="#00ff87">
<link rel="manifest" href="/manifest.json">
<title>ProPred NG</title>
<style>""" + CSS + """</style>
</head>
<body>
<nav>
  <div class="nav-inner">
    <div class="logo">
      <span class="logo-pro">PRO</span><span class="logo-pred">PRED</span>
      <span class="logo-ng">NG</span>
    </div>
    <div class="nav-right">
      <a href="/live" class="live-count" id="live-count" style="display:none">● LIVE</a>
      <a href="/" class="npill {{ 'on' if page=='home' else '' }}">Leagues</a>
      <a href="/acca" class="npill {{ 'on' if page=='acca' else '' }}">ACCA</a>
      <a href="/tracker" class="npill {{ 'on' if page=='tracker' else '' }}">Tracker</a>
    </div>
  </div>
</nav>
<div class="shell">{{ content|safe }}</div>
<script>
// Expandable sections
document.querySelectorAll('.expand-toggle').forEach(el=>{
  el.addEventListener('click',()=>{
    const b=el.nextElementSibling,ar=el.querySelector('.expand-arrow');
    if(b){b.classList.toggle('open');}
    if(ar){ar.classList.toggle('open');}
  });
});

// Animate prob bars on scroll
const io=new IntersectionObserver(es=>{
  es.forEach(e=>{
    if(e.isIntersecting){
      const el=e.target;
      el.style.width=el.dataset.w+'%';
      io.unobserve(el);
    }
  });
},{threshold:0.1});
document.querySelectorAll('.pb-fill').forEach(el=>{
  el.dataset.w=parseFloat(el.style.width)||0;
  el.style.width='0%';
  io.observe(el);
});

// Live match count
fetch('/api/live-count').then(r=>r.json()).then(d=>{
  if(d.count>0){
    const el=document.getElementById('live-count');
    if(el){el.textContent='● '+d.count+' LIVE';el.style.display='';}
  }
}).catch(()=>{});

// Search
const si=document.getElementById('lsearch');
if(si){
  const sc=document.querySelector('.s-clear');
  si.addEventListener('input',function(){
    const q=this.value.toLowerCase().trim();
    if(sc) sc.classList.toggle('vis',q.length>0);
    document.querySelectorAll('.lg-tile').forEach(t=>{
      const n=(t.dataset.n||'').toLowerCase();
      t.style.display=(!q||n.includes(q))?'':'none';
    });
    document.querySelectorAll('.sec-hd').forEach(h=>{
      const g=h.nextElementSibling;
      if(g&&g.classList.contains('lg-grid')){
        const vis=[...g.querySelectorAll('.lg-tile')].some(t=>t.style.display!=='none');
        h.style.display=vis?'':'none';
        g.style.display=vis?'':'none';
      }
    });
  });
  if(sc) sc.addEventListener('click',()=>{
    si.value='';sc.classList.remove('vis');
    document.querySelectorAll('.lg-tile,.sec-hd').forEach(e=>e.style.display='');
  });
}
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────
# HOME PAGE
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    cards = get_all_cards(3)

    # Group by league -- key by id+country to separate same-named leagues
    leagues = {}
    name_count = {}
    for c in cards:
        lkey = f'{c["league_id"]}_{c["country"]}'
        if lkey not in leagues:
            leagues[lkey] = {
                "id": c["league_id"],
                "name": c["league"], "icon": c["icon"],
                "country": c["country"], "tier": c["tier"],
                "fixtures": [], "live": 0,
                "has_today": False, "has_tomorrow": False
            }
            name_count[c["league"]] = name_count.get(c["league"], 0) + 1
        leagues[lkey]["fixtures"].append(c)
        if c["is_live"]:                     leagues[lkey]["live"] += 1
        if c.get("date_label") == "TODAY":   leagues[lkey]["has_today"] = True
        if c.get("date_label") == "TOMORROW":leagues[lkey]["has_tomorrow"] = True

    # Build display names -- if >1 league shares same name, add country
    for lkey, lg in leagues.items():
        if name_count.get(lg["name"], 1) > 1:
            lg["display_name"] = f'{lg["name"]} ({lg["country"]})'
        else:
            lg["display_name"] = lg["name"]

    total_fx   = len(cards)
    total_live = sum(1 for c in cards if c["is_live"])
    total_lg   = len(leagues)
    today_fx   = sum(1 for c in cards if c.get("date_label") == "TODAY")
    tmrw_fx    = sum(1 for c in cards if c.get("date_label") == "TOMORROW")

    content = f'''
    <div class="hero up">
      <div class="hero-eyebrow">Football Intelligence · 3-Day View</div>
      <div class="hero-title">LEAGUES<br><span>AHEAD</span></div>
      <div class="hero-stats">
        <div class="hstat">
          <div class="hstat-n">{today_fx}</div>
          <div class="hstat-l">Today</div>
        </div>
        <div class="hstat">
          <div class="hstat-n">{tmrw_fx}</div>
          <div class="hstat-l">Tomorrow</div>
        </div>
        <div class="hstat">
          <div class="hstat-n" style="color:var(--r)">{total_live}</div>
          <div class="hstat-l">Live</div>
        </div>
        <div class="hstat">
          <div class="hstat-n">{total_lg}</div>
          <div class="hstat-l">Leagues</div>
        </div>
      </div>
    </div>

    <div class="search-wrap up d1">
      <span class="s-icon">🔍</span>
      <input id="lsearch" class="search-inp" type="text" placeholder="Search league or country...">
      <span class="s-clear">✕</span>
    </div>'''

    # Sort: live first, then has_today, then tier
    sorted_leagues = sorted(leagues.items(),
        key=lambda x: (x[1]["tier"], -x[1]["live"],
                       -(1 if x[1]["has_today"] else 0),
                       -len(x[1]["fixtures"])))

    tiers = {}
    for lkey, lg in sorted_leagues:
        tiers.setdefault(lg["tier"], []).append((lkey, lg))

    tier_labels = {1:"⭐ Top Leagues", 2:"🌍 Major Leagues", 3:"🔭 More Leagues"}

    for tier in sorted(tiers.keys()):
        label = tier_labels.get(tier, "More")
        content += f'<div class="sec-hd up d2"><span class="sec-hd-dot"></span>{label}</div>'
        content += '<div class="lg-grid up d3">'
        for lkey, lg in tiers[tier]:
            fx_count  = len(lg["fixtures"])
            live_str  = f'<span style="color:var(--r);font-size:.5rem;font-weight:700;display:block">● {lg["live"]} LIVE</span>' if lg["live"] else ""
            day_badge = '<span style="color:var(--g);font-size:.5rem;font-weight:700">TODAY</span>' if lg["has_today"] else ('<span style="color:var(--b);font-size:.5rem;font-weight:700">TMR</span>' if lg["has_tomorrow"] else "")
            content += f'''<a href="/league/{lg["id"]}" class="lg-tile" data-n="{lg["name"].lower()} {lg["country"].lower()}">
              <span class="lt-fixtures">{fx_count}</span>
              <span class="lt-icon">{lg["icon"]}</span>
              <div class="lt-name">{lg.get("display_name", lg["name"])}</div>
              <div class="lt-country">{lg["country"]}</div>
              {live_str}{day_badge}
            </a>'''
        content += '</div>'

    if not leagues:
        content += '<div class="empty"><span class="empty-icon">⚽</span>No fixtures found for today.<br>Check back soon.</div>'

    return render_template_string(LAYOUT, content=content, page="home")

# ─────────────────────────────────────────────────────────────
# LEAGUE PAGE
# ─────────────────────────────────────────────────────────────

@app.route("/league/<int:l_id>")
def league_page(l_id):
    cards = get_all_today_cards()
    lg_cards = [c for c in cards if c["league_id"] == l_id]

    if not lg_cards:
        meta = {"name":"League","icon":"🌐","country":""}
        return render_template_string(LAYOUT,
            content=f'<a href="/" class="back">← Leagues</a><div class="empty"><span class="empty-icon">📭</span>No fixtures for this league today.</div>',
            page="league")

    lg_name = lg_cards[0]["league"]
    lg_icon = lg_cards[0]["icon"]
    lg_country = lg_cards[0]["country"]

    # Group by date_label
    groups = {}
    for c in lg_cards:
        key = c.get("date_label","TODAY")
        groups.setdefault(key, []).append(c)
    for k in groups:
        groups[k].sort(key=lambda c: c["kickoff"] or "")

    active = request.args.get("tab", list(groups.keys())[0])

    content = f'<a href="/" class="back">← Leagues</a>'
    content += f'''<div class="hero up" style="padding:14px 0 16px">
      <div class="hero-eyebrow">{lg_icon} {lg_country}</div>
      <div class="hero-title" style="font-size:2rem">{lg_name}</div>
      <div class="hero-sub" style="margin-top:6px">{len(lg_cards)} fixtures today</div>
    </div>'''

    # Date tabs
    content += '<div class="tabs up d1">'
    for k in groups:
        n = len(groups[k])
        active_cls = "on" if k == active else ""
        content += f'<a href="/league/{l_id}?tab={k}" class="tab {active_cls}">{k}<span class="tab-n">{n}</span></a>'
    content += '</div>'

    content += '<div class="fx-wrap up d2">'
    for c in groups.get(active, []):
        # Get quick prediction
        preds_raw = sportmonks.get_predictions(c["id"])
        preds = sportmonks.parse_predictions(preds_raw) if preds_raw else None
        tip, prob, tag = quick_predict(c, preds)

        tc = tip_color(tip)
        tag_color = {"RELIABLE":"var(--g)","SOLID":"var(--b)","MONITOR":"var(--t2)"}.get(tag,"var(--t2)")

        sb = state_badge(c)
        sc_disp = score_display(c)

        content += f'''<a href="/match/{c["id"]}" class="fx-row">
          <div class="fx-time">{sb}{sc_disp if c["is_live"] or c["is_ft"] else ""}</div>
          <div class="fx-teams">
            <div class="fx-home">{c["home"]}</div>
            <div class="fx-away">{c["away"]}</div>
          </div>
          <div class="fx-right">
            <div class="fx-tip" style="color:{tc}">{tip}</div>
            <div class="fx-prob">{prob}%</div>
            <div class="fx-tag" style="color:{tag_color}">{tag}</div>
          </div>
        </a>'''
    content += '</div>'

    return render_template_string(LAYOUT, content=content, page="league")

# ─────────────────────────────────────────────────────────────
# MATCH PAGE -- THE MAIN EVENT
# ─────────────────────────────────────────────────────────────

@app.route("/match/<int:match_id>")
def match_page(match_id):
    try:
        enriched   = sportmonks.enrich_match(match_id)
        h_name     = enriched["home_name"] or "Home"
        a_name     = enriched["away_name"] or "Away"
        state      = enriched["state"]
        score_h    = enriched.get("score_home")
        score_a    = enriched.get("score_away")
        preds      = enriched.get("predictions") or {}
        odds       = enriched.get("odds") or {}
        h_form     = enriched.get("home_form") or []
        a_form     = enriched.get("away_form") or []
        xg_h_raw   = enriched.get("xg_home")
        xg_a_raw   = enriched.get("xg_away")
        referee    = enriched.get("referee")
        h2h        = enriched.get("h2h_summary")
        h_lineup   = enriched.get("home_lineup") or []
        a_lineup   = enriched.get("away_lineup") or []
        events     = enriched.get("events") or {}
        value_bets = enriched.get("value_bets") or []
        league_nm  = enriched.get("league_name","")
        kickoff    = enriched.get("kickoff","")

        # Probabilities -- Sportmonks first, Poisson fallback
        hw   = float(preds.get("home_win") or 0)
        dw   = float(preds.get("draw")     or 0)
        aw   = float(preds.get("away_win") or 0)
        o25  = float(preds.get("over_25")  or 0)
        o15  = float(preds.get("over_15")  or 0)
        btts = float(preds.get("btts")     or 0)

        xg_h = float(xg_h_raw) if xg_h_raw else None
        xg_a = float(xg_a_raw) if xg_a_raw else None

        # Poisson from xG when Sportmonks gives no probs
        if xg_h and xg_a:
            p_o25, p_o15, p_btts = match_predictor._goals_from_xg(xg_h, xg_a)
            if o25 == 0:  o25  = round(p_o25 * 100, 1)
            if o15 == 0:  o15  = round(p_o15 * 100, 1)
            if btts == 0: btts = round(p_btts * 100, 1)
            if hw == 0:
                hw_p = dw_p = aw_p = 0.0
                for hg in range(10):
                    ph = match_predictor.poisson_pmf(hg, xg_h)
                    for ag in range(10):
                        pa = match_predictor.poisson_pmf(ag, xg_a)
                        j  = ph * pa
                        if hg > ag: hw_p += j
                        elif hg == ag: dw_p += j
                        else: aw_p += j
                hw = round(hw_p*100,1); dw = round(dw_p*100,1); aw = round(aw_p*100,1)

        # Absolute fallback
        if hw==0 and dw==0 and aw==0: hw,dw,aw = 33.3,33.3,33.3
        if o15==0: o15=65.0
        if o25==0: o25=45.0
        if btts==0: btts=45.0

        # Renorm 1X2
        tot = hw+dw+aw
        if tot>0 and abs(tot-100)>2: hw=round(hw/tot*100,1); dw=round(dw/tot*100,1); aw=round(aw/tot*100,1)

        o35 = round(max(o25-22,5.0),1)
        ng  = round(max(100-btts,5.0),1)

        # Team profile intelligence
        try:
            h_prof = database.get_team_profile(h_name,"home",min_matches=5)
            a_prof = database.get_team_profile(a_name,"away",min_matches=5)
        except: h_prof = a_prof = None
        if h_prof and h_prof.get("played",0)>=5:
            b = min(0.3, h_prof["played"]*0.015)
            if xg_h: xg_h = round(xg_h*(1-b)+h_prof["avg_scored"]*b,2)
        if a_prof and a_prof.get("played",0)>=5:
            b = min(0.3, a_prof["played"]*0.015)
            if xg_a: xg_a = round(xg_a*(1-b)+a_prof["avg_scored"]*b,2)

        # Odds
        odds_h    = odds.get("home")
        odds_d    = odds.get("draw")
        odds_a    = odds.get("away")
        odds_o15  = odds.get("over_15")
        odds_o25  = odds.get("over_25")
        odds_btts = odds.get("btts_yes")

        # THREE-TIER TIPS
        rec_tip,rec_prob,rec_conv,rec_odds,all_scores = match_predictor._pick_recommended(
            hw,dw,aw,o15,o25,o35,btts,btts,ng,
            xg_h or 1.2,xg_a or 1.0,h_form,a_form,None,None,
            odds_h,odds_d,odds_a,odds_o15,odds_o25,odds_btts)
        safe_tip,safe_prob,safe_odds = match_predictor._pick_safest(
            rec_tip,hw,dw,aw,o15,xg_h or 1.2,xg_a or 1.0,h_form,a_form,
            odds_h,odds_d,odds_a)
        risky_list = match_predictor._pick_risky(
            hw,dw,aw,o15,o25,btts,xg_h or 1.2,xg_a or 1.0,h_form,a_form,
            odds_h,odds_a,odds_o25,odds_btts)

        analyst_reason = match_predictor._reason(
            rec_tip,xg_h or 1.2,xg_a or 1.0,h_form,a_form,None,None,
            rec_prob,rec_odds,h_name,a_name)

        # TAG LOGIC
        fav_prob = max(hw,aw)
        inj_total = len(enriched.get("home_injuries",[]))+len(enriched.get("away_injuries",[]))
        h_slump = list(h_form[-3:]).count("L")>=3 if len(h_form)>=3 else False
        a_slump = list(a_form[-3:]).count("L")>=3 if len(a_form)>=3 else False
        lg_lower = league_nm.lower()
        is_friendly = "friendly" in lg_lower or "international" in lg_lower
        is_derby    = h_name.split()[0][:4].lower()==a_name.split()[0][:4].lower()
        is_cup      = any(w in lg_lower for w in ["cup","copa","coupe","pokal","carabao"])

        if fav_prob>=85 and inj_total==0 and not is_cup and not is_friendly:
            tag="SURE MATCH"; tag_cls="sure"
        elif is_friendly or (is_derby and fav_prob<60):
            tag="VOLATILE";   tag_cls="volatile"
        elif (h_slump and "HOME" in rec_tip) or (a_slump and "AWAY" in rec_tip) or inj_total>=3:
            tag="AVOID";      tag_cls="avoid"
        elif rec_conv>=62 and rec_prob>=58:
            tag="RELIABLE";   tag_cls="reliable"
        elif rec_conv>=45:
            tag="SOLID";      tag_cls="solid"
        else:
            tag="MONITOR";    tag_cls="monitor"

        tag_icons = {"SURE MATCH":"checkmark","RELIABLE":"shield","SOLID":"shield",
                     "VOLATILE":"arrow.2.circlepath","AVOID":"exclamationmark.triangle","MONITOR":"eye"}
        tag_display = {"SURE MATCH":"SURE MATCH","RELIABLE":"RELIABLE","SOLID":"SOLID TIP",
                       "VOLATILE":"VOLATILE","AVOID":"AVOID","MONITOR":"MONITOR"}

        fair_odds = round(100/max(rec_prob,1),2)
        edge_val  = None
        if rec_odds and rec_odds>1:
            edge_val = round((rec_prob/100-1/rec_odds)*100,1)

        # Value category
        if edge_val and edge_val>3: val_cat="VALUE"
        elif rec_prob>=65: val_cat="SAFE"
        else: val_cat="STANDARD"

        live_states = {"1H","2H","HT","ET","PEN","LIVE","INPLAY"}
        is_live = state.upper() in live_states or (isinstance(state,str) and state.isdigit())
        is_ft   = state.upper() in ("FT","AET","PEN","FIN","FINISHED","AWARDED")

        # Log
        try:
            database.log_prediction(
                match_id=match_id, league_id=enriched.get("league_id",0),
                league_name=league_nm, home_team=h_name, away_team=a_name,
                match_date=kickoff[:16], market=rec_tip, probability=rec_prob,
                fair_odds=fair_odds, bookie_odds=rec_odds, edge=edge_val,
                confidence=rec_conv, xg_home=xg_h, xg_away=xg_a,
                likely_score="", tag=tag, reliability_score=rec_conv)
        except: pass

        # Page build
        if is_live:
            s_html = '<span class="s-badge s-live">' + live_dot() + " " + state + "</span>"
        elif is_ft:
            s_html = '<span class="s-badge s-ft">Full Time</span>'
        else:
            s_html = '<span class="s-badge s-ns">' + kickoff_label(kickoff) + "</span>"

        if score_h is not None and score_a is not None:
            vs_html = '<div class="vs-score">' + str(score_h) + '<span style="color:var(--t2);font-size:1.6rem;margin:0 3px">-</span>' + str(score_a) + "</div>"
        else:
            vs_html = '<div class="vs-sep">VS</div>'

        tc       = tip_color(rec_tip)
        safe_tc  = tip_color(safe_tip)
        conv_clr = "var(--g)" if rec_conv>=62 else "var(--w)" if rec_conv>=45 else "var(--r)"

        tag_badge_map = {
            "SURE MATCH":"bg-green","RELIABLE":"bg-green","SOLID":"bg-blue",
            "VOLATILE":"bg-orange","AVOID":"bg-red","MONITOR":"bg-muted"
        }
        tag_badge_cls = tag_badge_map.get(tag,"bg-muted")
        tag_label = tag_display.get(tag, tag)

        edge_badge = ""
        if edge_val and edge_val>0:
            edge_badge = '<span class="badge bg-green" style="margin-top:5px">+' + str(edge_val) + '% EDGE</span>'
        elif edge_val and edge_val<-3:
            edge_badge = '<span class="badge bg-red" style="margin-top:5px">POOR VALUE</span>'

        bk_str = (' Bookie: <span style="color:var(--gold);font-weight:800">' + str(rec_odds) + "</span>") if rec_odds else ""

        content = '<a href="/" class="back">← Leagues</a>'

        content += ('<div class="match-hero up">'
            + '<div class="match-league">' + league_nm + '</div>'
            + '<div style="margin:6px 0">' + s_html + '</div>'
            + '<div class="match-teams">'
            + '<div class="team-block"><div class="team-name">' + h_name + '</div></div>'
            + '<div class="vs-block">' + vs_html + '</div>'
            + '<div class="team-block"><div class="team-name">' + a_name + '</div></div>'
            + '</div></div>')

        # RECOMMENDED
        content += ('<div class="pred-card ' + tag_cls + ' up d1">'
            + '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">'
            + '<div>'
            + '<div style="font-size:.52rem;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--t2);margin-bottom:5px">RECOMMENDED TIP</div>'
            + '<div class="tip-main" style="color:' + tc + '">' + rec_tip + '</div>'
            + '<div class="tip-prob">' + str(rec_prob) + '% probability &middot; Fair odds: <span style="color:var(--gold)">' + str(fair_odds) + '</span>' + bk_str + '</div>'
            + edge_badge
            + '</div>'
            + '<span class="badge ' + tag_badge_cls + '" style="white-space:nowrap;flex-shrink:0">' + tag_label + '</span>'
            + '</div>'
            + '<div style="display:flex;gap:8px;margin-bottom:10px">'
            + '<div style="flex:1;background:rgba(0,0,0,.2);border-radius:8px;padding:8px 10px">'
            + '<div style="font-size:.52rem;color:var(--t2);margin-bottom:2px;letter-spacing:1px;text-transform:uppercase">Conviction</div>'
            + '<div style="font-size:1rem;font-weight:900;color:' + conv_clr + '">' + str(round(rec_conv)) + '<span style="font-size:.6rem;color:var(--t2)">/100</span></div>'
            + '</div>'
            + '<div style="flex:1;background:rgba(0,0,0,.2);border-radius:8px;padding:8px 10px">'
            + '<div style="font-size:.52rem;color:var(--t2);margin-bottom:2px;letter-spacing:1px;text-transform:uppercase">Signal</div>'
            + '<div style="font-size:.75rem;font-weight:800;color:var(--wh)">' + val_cat + '</div>'
            + '</div>'
            + '</div>'
            + '<div class="tip-reason">' + analyst_reason + '</div>'
            + '</div>')

        # SAFE + RISKY side by side
        safe_odds_str = ('<div style="font-size:.62rem;color:var(--gold);margin-top:3px">Fair: '
                         + str(round(100/max(safe_prob,1),2)) + '</div>') if safe_prob else ""
        r1 = risky_list[0] if risky_list else {"tip":"--","prob":0,"odds":"--"}
        r1_tc = tip_color(r1["tip"])

        content += ('<div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:8px" class="up d2">'
            + '<div class="card" style="margin:0;border-color:rgba(79,142,247,.25);background:linear-gradient(135deg,rgba(79,142,247,.07),transparent)">'
            + '<div class="card-title">SAFEST TIP</div>'
            + '<div style="font-size:.9rem;font-weight:900;color:' + safe_tc + ';line-height:1.2">' + safe_tip + '</div>'
            + '<div style="font-size:.62rem;color:var(--t2);margin-top:3px">' + str(safe_prob) + '% probability</div>'
            + safe_odds_str
            + '</div>'
            + '<div class="card" style="margin:0;border-color:rgba(191,90,242,.25);background:linear-gradient(135deg,rgba(191,90,242,.07),transparent)">'
            + '<div class="card-title">RISKY PICK</div>'
            + '<div style="font-size:.9rem;font-weight:900;color:' + r1_tc + ';line-height:1.2">' + r1["tip"] + '</div>'
            + '<div style="font-size:.62rem;color:var(--t2);margin-top:3px">' + str(r1["prob"]) + '% &middot; ~' + str(r1["odds"]) + '</div>'
            + '</div></div>')

        # More risky
        if len(risky_list)>1:
            content += '<div class="card up d2"><div class="card-title">More Risky Markets</div>'
            for r in risky_list[1:]:
                rtc = tip_color(r["tip"])
                content += ('<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--bdr)">'
                    + '<div style="font-size:.72rem;font-weight:700;color:' + rtc + '">' + r["tip"] + '</div>'
                    + '<div style="text-align:right">'
                    + '<div style="font-size:.65rem;color:var(--t2)">' + str(r["prob"]) + '%</div>'
                    + '<div style="font-size:.62rem;color:var(--gold)">~' + str(r["odds"]) + '</div>'
                    + '</div></div>')
            content += '</div>'

        # WIN PROBABILITIES
        content += '<div class="card up d2"><div class="card-title">Win Probabilities</div>'
        content += prob_bar("Home Win - " + h_name[:16], hw, "green")
        content += prob_bar("Draw", dw, "blue")
        content += prob_bar("Away Win - " + a_name[:16], aw, "orange")
        if odds_h or odds_d or odds_a:
            content += ('<div style="display:flex;gap:8px;margin-top:10px;padding-top:10px;border-top:1px solid var(--bdr)">'
                + '<div style="flex:1;text-align:center"><div style="font-size:.5rem;color:var(--t2);margin-bottom:2px">HOME</div>'
                + '<div style="font-size:.9rem;font-weight:900;color:var(--g)">' + str(odds_h or "--") + '</div></div>'
                + '<div style="flex:1;text-align:center"><div style="font-size:.5rem;color:var(--t2);margin-bottom:2px">DRAW</div>'
                + '<div style="font-size:.9rem;font-weight:900;color:var(--b)">' + str(odds_d or "--") + '</div></div>'
                + '<div style="flex:1;text-align:center"><div style="font-size:.5rem;color:var(--t2);margin-bottom:2px">AWAY</div>'
                + '<div style="font-size:.9rem;font-weight:900;color:var(--w)">' + str(odds_a or "--") + '</div></div>'
                + '</div>')
        content += '</div>'

        # GOAL MARKETS
        content += '<div class="card up d3"><div class="card-title">Goal Markets</div>'
        content += prob_bar("Over 1.5 Goals", o15, "green")
        content += prob_bar("Over 2.5 Goals", o25, "blue")
        content += prob_bar("Both Teams Score (GG)", btts, "cyan")
        content += prob_bar("Under 2.5 Goals", round(100-o25,1), "orange")
        if xg_h and xg_a:
            content += ('<div style="display:flex;gap:16px;margin-top:10px;padding-top:10px;border-top:1px solid var(--bdr)">'
                + '<div><div style="font-size:.5rem;color:var(--t2);text-transform:uppercase;letter-spacing:1.5px">Home xG</div>'
                + '<div style="font-size:1.2rem;font-weight:900;color:var(--g)">' + str(xg_h) + '</div></div>'
                + '<div><div style="font-size:.5rem;color:var(--t2);text-transform:uppercase;letter-spacing:1.5px">Away xG</div>'
                + '<div style="font-size:1.2rem;font-weight:900;color:var(--b)">' + str(xg_a) + '</div></div>'
                + '<div><div style="font-size:.5rem;color:var(--t2);text-transform:uppercase;letter-spacing:1.5px">Total xG</div>'
                + '<div style="font-size:1.2rem;font-weight:900;color:var(--wh)">' + str(round(xg_h+xg_a,2)) + '</div></div>'
                + '</div>')
        if odds_o15 or odds_o25 or odds_btts:
            content += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">'
            if odds_o15:  content += '<div style="background:var(--s3);border-radius:8px;padding:6px 10px;font-size:.65rem"><div style="color:var(--t2)">O1.5</div><div style="font-weight:800;color:var(--g)">' + str(odds_o15) + '</div></div>'
            if odds_o25:  content += '<div style="background:var(--s3);border-radius:8px;padding:6px 10px;font-size:.65rem"><div style="color:var(--t2)">O2.5</div><div style="font-weight:800;color:var(--b)">' + str(odds_o25) + '</div></div>'
            if odds_btts: content += '<div style="background:var(--s3);border-radius:8px;padding:6px 10px;font-size:.65rem"><div style="color:var(--t2)">GG</div><div style="font-weight:800;color:var(--cy)">' + str(odds_btts) + '</div></div>'
            content += '</div>'
        content += '</div>'

        # FORM
        h_trend = match_predictor.form_trend(h_form)
        a_trend = match_predictor.form_trend(a_form)
        h_form_pts = sum(3 if r=="W" else 1 if r=="D" else 0 for r in h_form[-5:]) if h_form else 0
        a_form_pts = sum(3 if r=="W" else 1 if r=="D" else 0 for r in a_form[-5:]) if a_form else 0
        trend_clr = lambda t: "var(--g)" if t=="RISING" else "var(--r)" if t=="FALLING" else "var(--t2)"
        content += ('<div class="card up d3"><div class="card-title">Recent Form</div>'
            + '<div class="info-row">'
            + '<div><div class="info-lbl">' + h_name[:20] + '</div>'
            + '<div style="font-size:.58rem;color:' + trend_clr(h_trend) + ';margin-top:2px">' + h_trend + ' - ' + str(h_form_pts) + 'pts</div></div>'
            + '<div class="form-row">' + form_dots(h_form) + '</div></div>'
            + '<div class="info-row">'
            + '<div><div class="info-lbl">' + a_name[:20] + '</div>'
            + '<div style="font-size:.58rem;color:' + trend_clr(a_trend) + ';margin-top:2px">' + a_trend + ' - ' + str(a_form_pts) + 'pts</div></div>'
            + '<div class="form-row">' + form_dots(a_form) + '</div></div>'
            + '</div>')

        # H2H
        if h2h and h2h.get("total",0)>0:
            tot_h2h = h2h["total"]
            hw_p = round(h2h["home_wins"]/tot_h2h*100) if tot_h2h else 0
            dr_p = round(h2h["draws"]/tot_h2h*100) if tot_h2h else 0
            aw_p = round(h2h["away_wins"]/tot_h2h*100) if tot_h2h else 0
            content += ('<div class="card up d3"><div class="card-title">Head to Head - Last ' + str(tot_h2h) + '</div>'
                + '<div class="h2h-bar"><div class="h2h-h" style="flex:' + str(max(hw_p,1)) + '"></div>'
                + '<div class="h2h-d" style="flex:' + str(max(dr_p,1)) + '"></div>'
                + '<div class="h2h-a" style="flex:' + str(max(aw_p,1)) + '"></div></div>'
                + '<div class="h2h-labels" style="margin-bottom:12px">'
                + '<span style="color:var(--g)">' + str(h2h["home_wins"]) + 'W (' + str(hw_p) + '%)</span>'
                + '<span style="color:var(--t2)">' + str(h2h["draws"]) + 'D</span>'
                + '<span style="color:var(--b)">' + str(h2h["away_wins"]) + 'W (' + str(aw_p) + '%)</span></div>'
                + '<div class="info-row"><div class="info-lbl">Avg Goals/Game</div><div class="info-val">' + str(h2h["avg_goals"]) + '</div></div>'
                + '<div class="info-row"><div class="info-lbl">Over 2.5 Rate</div><div class="info-val">' + str(h2h["over_25_pct"]) + '%</div></div>'
                + '<div class="info-row"><div class="info-lbl">Both Score Rate</div><div class="info-val">' + str(h2h["btts_pct"]) + '%</div></div>'
                + '</div>')

        # REFEREE
        if referee:
            ref_name = referee.get("name","Unknown")
            avg_yc   = referee.get("avg_yellow",0)
            pen_r    = referee.get("penalty_rate",0)
            hot      = referee.get("high_card_game",False)
            pen_p    = referee.get("pen_prone",False)
            yc_clr   = "var(--r)" if hot else "var(--g)"
            pen_clr  = "var(--pu)" if pen_p else "var(--t3)"
            sig_cls  = "ref-hot" if hot else "ref-ok"
            sig_txt  = "High Card Risk" if hot else "Fair Official"
            note_str = ('<div class="tip-reason" style="margin-top:8px">This referee averages ' + str(avg_yc) + ' yellows/game - factor into booking markets.</div>') if hot else ""
            content += ('<div class="card up d4"><div class="card-title">Referee Intelligence</div>'
                + '<div class="info-row"><div class="info-lbl">Official</div><div class="info-val">' + ref_name + '</div></div>'
                + '<div class="info-row"><div class="info-lbl">Avg Yellow Cards</div><div class="info-val" style="color:' + yc_clr + '">' + str(avg_yc) + '/game</div></div>'
                + '<div class="info-row"><div class="info-lbl">Penalty Rate</div><div class="info-val" style="color:' + pen_clr + '">' + str(pen_r) + ' per game</div></div>'
                + '<div style="margin-top:8px;display:flex;gap:6px">'
                + '<span class="ref-signal ' + sig_cls + '">' + sig_txt + '</span>'
                + ('<span class="ref-signal ref-hot">Pen Prone</span>' if pen_p else "")
                + '</div>' + note_str + '</div>')

        # EVENTS
        goals   = events.get("goals",[])
        cards_e = events.get("cards",[])
        if goals or cards_e:
            content += '<div class="card up d4"><div class="card-title">Match Events</div>'
            for g in goals:
                side_i = "Home" if g["side"]=="home" else "Away"
                content += ('<div class="event-row"><div class="ev-min">' + str(g["minute"]) + "'</div>"
                    + '<div class="ev-icon">Goal</div><div class="ev-name">' + g["player"] + '</div>'
                    + '<div class="ev-side">' + side_i + '</div></div>')
            for c_ev in cards_e:
                col = "Yellow" if c_ev["color"]=="yellow" else "Red"
                content += ('<div class="event-row"><div class="ev-min">' + str(c_ev["minute"]) + "'</div>"
                    + '<div class="ev-icon">' + col + '</div><div class="ev-name">' + c_ev["player"] + '</div></div>')
            content += '</div>'

        # LINEUPS
        if h_lineup or a_lineup:
            content += ('<div class="card up d4"><div class="card-title">Lineups</div>'
                + '<div class="lineup-grid"><div>'
                + '<div class="lineup-team">' + h_name[:16] + '</div>')
            for p in h_lineup[:11]:
                content += '<div class="lineup-player">' + p["name"] + '</div>'
            content += ('<br></div><div><div class="lineup-team">' + a_name[:16] + '</div>')
            for p in a_lineup[:11]:
                content += '<div class="lineup-player">' + p["name"] + '</div>'
            content += '</div></div></div>'

        # VALUE BETS
        if value_bets:
            content += '<div class="card up d4"><div class="card-title">Value Bets (Sportmonks)</div>'
            for vb in value_bets[:3]:
                content += ('<div class="vbet">'
                    + '<div class="vbet-label">' + str(vb.get("name") or vb.get("market","")) + '</div>'
                    + '<div class="vbet-val">' + str(vb.get("odds") or vb.get("value","")) + '</div>'
                    + '<div class="vbet-sub">Model prob: ' + str(vb.get("probability") or vb.get("percentage","")) + '%</div>'
                    + '</div>')
            content += '</div>'

        return render_template_string(LAYOUT, content=content, page="match")

    except Exception as e:
        import traceback; traceback.print_exc()
        return render_template_string(LAYOUT,
            content='<a href="/" class="back">Back</a><div class="empty"><span class="empty-icon">Error</span>Could not load match.<br><small style="color:var(--r)">' + str(e)[:120] + '</small></div>',
            page="match")

@app.route("/live")
def live_page():
    lives = sportmonks.get_livescores()
    content = '''<div class="hero up">
      <div class="hero-eyebrow">Real-Time</div>
      <div class="hero-title">LIVE <span>NOW</span></div>
    </div>'''

    if not lives:
        content += '<div class="empty"><span class="empty-icon">📡</span>No live matches right now.<br>Check back during matchday.</div>'
    else:
        # Group by league
        by_league = {}
        for fx in lives:
            c = build_fixture_card(fx)
            lg = c["league"] or "Unknown"
            by_league.setdefault(lg, []).append(c)

        for lg_name, lg_cards in by_league.items():
            meta = get_league_meta(lg_name)
            content += f'<div class="sec-hd">{meta["icon"]} {lg_name}</div>'
            content += '<div class="fx-wrap">'
            for c in lg_cards:
                content += f'''<a href="/match/{c["id"]}" class="fx-row">
                  <div class="fx-time">
                    <div class="s-badge s-live">{live_dot()} {c["state"]}</div>
                    <div style="margin-top:3px">{score_display(c)}</div>
                  </div>
                  <div class="fx-teams">
                    <div class="fx-home">{c["home"]}</div>
                    <div class="fx-away">{c["away"]}</div>
                  </div>
                </a>'''
            content += '</div>'

    return render_template_string(LAYOUT, content=content, page="live")

# ─────────────────────────────────────────────────────────────
# ACCA BUILDER
# ─────────────────────────────────────────────────────────────

@app.route("/acca")
def acca_page():
    cards = get_all_cards(3)  # 3-day window

    # Only get predictions for fixtures not yet started
    ns_cards = [c for c in cards if c["is_ns"]]

    acca_picks = []
    for c in ns_cards[:50]:
        preds_raw = sportmonks.get_predictions(c["id"])
        preds = sportmonks.parse_predictions(preds_raw) if preds_raw else None
        tip, prob, tag = quick_predict(c, preds)
        if tag in ("RELIABLE","SOLID") and prob >= 55:
            odds_raw = sportmonks.get_odds(c["id"])
            odds_parsed = sportmonks.parse_odds(odds_raw)
            bk_odds = odds_parsed.get(
                "home" if "HOME" in tip else
                "away" if "AWAY" in tip else
                "over_25" if "2.5" in tip else
                "over_15" if "1.5" in tip else "home")
            acca_picks.append({
                "id": c["id"], "home": c["home"], "away": c["away"],
                "tip": tip, "prob": prob, "odds": bk_odds, "tag": tag,
                "league": c["league"], "icon": c["icon"]
            })

    # Sort by probability
    acca_picks.sort(key=lambda x: x["prob"], reverse=True)
    top5 = acca_picks[:5]

    # Calculate combined odds
    combined_odds = 1.0
    for p in top5:
        if p["odds"]: combined_odds *= p["odds"]

    content = '''<div class="hero up">
      <div class="hero-eyebrow">Auto-Selected</div>
      <div class="hero-title">ACCA <span>BUILDER</span></div>
      <div class="hero-sub">Top 5 high-confidence picks today</div>
    </div>'''

    if not top5:
        content += '<div class="empty"><span class="empty-icon">🎯</span>No high-confidence picks found.<br>Check back when more fixtures have predictions.</div>'
    else:
        content += '<div class="card up d1">'
        for i, p in enumerate(top5):
            tc = tip_color(p["tip"])
            odds_str = f'@ {p["odds"]}' if p["odds"] else ""
            content += f'''<div class="acca-row">
              <div style="flex:1;min-width:0">
                <div style="font-size:.6rem;color:var(--t2);margin-bottom:2px">{p["icon"]} {p["league"]}</div>
                <div style="font-size:.74rem;font-weight:700;color:var(--wh)">{p["home"]} vs {p["away"]}</div>
                <div style="font-size:.62rem;color:var(--t2);margin-top:2px">{p["prob"]}% confidence {odds_str}</div>
              </div>
              <div style="text-align:right;flex-shrink:0">
                <div style="font-size:.72rem;font-weight:800;color:{tc}">{p["tip"]}</div>
                <span class="badge bg-green" style="margin-top:3px">RELIABLE</span>
              </div>
            </div>'''
        content += '</div>'

        if combined_odds > 1:
            content += f'''<div class="acca-odds-box up d2">
              <div style="font-size:.6rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t2);margin-bottom:6px">Combined Odds</div>
              <div class="acca-odds-num">{combined_odds:.2f}</div>
              <div style="font-size:.6rem;color:var(--t2);margin-top:4px">5-fold accumulator</div>
            </div>'''

        content += f'''<div class="info-box up d3" style="background:var(--s2);border:1px solid var(--bdr);border-radius:14px;padding:13px;font-size:.65rem;color:var(--t2);line-height:1.8">
          ⚡ Picks auto-selected from {len(ns_cards)} upcoming fixtures.<br>
          Only RELIABLE-tagged matches with 65%+ confidence included.<br>
          Always verify odds with your bookmaker before placing.
        </div>'''

    return render_template_string(LAYOUT, content=content, page="acca")

# ─────────────────────────────────────────────────────────────
# TRACKER
# ─────────────────────────────────────────────────────────────

@app.route("/tracker")
def tracker_page():
    try:
        stats = database.get_tracker_stats()
    except Exception as e:
        print(f"[tracker] {e}")
        stats = {"total":0,"wins":0,"losses":0,"hit_rate":0,"pending":0,
                 "week_total":0,"week_wins":0,"week_hit_rate":0,
                 "by_market":[],"by_league":[],"recent":[],"pending_rows":[],
                 "streak":{"type":"--","count":0},"roi":0}

    total   = stats.get("total",0)
    wins    = stats.get("wins",0)
    losses  = stats.get("losses",0)
    hr      = stats.get("hit_rate",0)
    pending = stats.get("pending",0)
    streak  = stats.get("streak",{})
    roi     = stats.get("roi",0)
    week_hr = stats.get("week_hit_rate",0)
    week_t  = stats.get("week_total",0)

    hr_color     = "var(--g)" if hr >= 60 else "var(--w)" if hr >= 45 else "var(--r)"
    roi_color    = "var(--g)" if roi >= 0 else "var(--r)"
    streak_color = "var(--g)" if streak.get("type")=="WIN" else "var(--r)" if streak.get("type")=="LOSS" else "var(--t2)"

    content = f'''<div class="tracker-hero up">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div style="font-size:.52rem;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--t2);margin-bottom:4px">Performance</div>
          <div class="big-num" style="color:{hr_color}">{hr}%</div>
          <div class="big-label">Hit Rate</div>
        </div>
        <div style="text-align:right">
          <div class="big-num" style="font-size:2.2rem;color:{roi_color}">{roi:+.1f}%</div>
          <div class="big-label">ROI</div>
        </div>
      </div>
      <div style="display:flex;gap:14px;margin-top:16px;flex-wrap:wrap">
        <div class="hstat"><div class="hstat-n">{total}</div><div class="hstat-l">Settled</div></div>
        <div class="hstat"><div class="hstat-n" style="color:var(--g)">{wins}</div><div class="hstat-l">Wins</div></div>
        <div class="hstat"><div class="hstat-n" style="color:var(--r)">{losses}</div><div class="hstat-l">Losses</div></div>
        <div class="hstat"><div class="hstat-n" style="color:var(--w)">{pending}</div><div class="hstat-l">Pending</div></div>
      </div>
    </div>'''

    # Week + Streak
    content += f'''<div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:8px" class="up d1">
      <div class="card" style="margin:0">
        <div class="card-title">This Week</div>
        <div style="font-size:1.8rem;font-weight:900;color:var(--wh);letter-spacing:-1px">{week_hr}%</div>
        <div style="font-size:.6rem;color:var(--t2);margin-top:2px">{week_t} settled</div>
      </div>
      <div class="card" style="margin:0;text-align:center">
        <div class="card-title">Streak</div>
        <div style="font-size:1.8rem;font-weight:900;color:{streak_color};letter-spacing:-1px">{streak.get("count",0)}</div>
        <div style="font-size:.6rem;color:{streak_color};margin-top:2px;font-weight:700">{streak.get("type","--")}</div>
      </div>
    </div>'''

    # By market
    by_market = stats.get("by_market", [])
    if by_market:
        content += '''<div class="card up d2">
          <div class="card-title"><span class="card-title-icon">📈</span> Performance by Market</div>'''
        for m_row in by_market[:8]:
            mhr = round(m_row.get("wins",0)/max(m_row.get("total",1),1)*100,1)
            clr = "var(--g)" if mhr>=60 else "var(--w)" if mhr>=45 else "var(--r)"
            bar_w = min(mhr, 100)
            content += f'''<div class="perf-row">
              <div>
                <div style="font-size:.7rem;color:var(--t3);font-weight:700">{m_row.get("market","")}</div>
                <div style="height:3px;background:rgba(255,255,255,.04);border-radius:3px;margin-top:5px;width:100px">
                  <div style="height:100%;width:{bar_w}%;background:{clr};border-radius:3px"></div>
                </div>
              </div>
              <div style="text-align:right">
                <div style="font-size:.78rem;font-weight:800;color:{clr}">{mhr}%</div>
                <div style="font-size:.58rem;color:var(--t2)">{m_row.get("total",0)} bets</div>
              </div>
            </div>'''
        content += '</div>'

    # Recent results
    recent = stats.get("recent",[])
    if recent:
        content += '''<div class="card up d3">
          <div class="card-title"><span class="card-title-icon">🕐</span> Recent Results</div>'''
        for r in recent[:10]:
            win  = r.get("result")=="WIN"
            loss = r.get("result")=="LOSS"
            dot  = "var(--g)" if win else "var(--r)" if loss else "var(--t2)"
            score_str = ""
            if r.get("actual_home_score") is not None:
                score_str = f'{r["actual_home_score"]}-{r["actual_away_score"]}'
            content += f'''<div class="result-row">
              <div class="win-dot" style="background:{dot}"></div>
              <div style="flex:1;min-width:0">
                <div style="font-size:.7rem;color:var(--wh);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{r.get("home_team","")} vs {r.get("away_team","")}</div>
                <div style="font-size:.6rem;color:var(--t2);margin-top:1px">{r.get("market","")} · {r.get("probability",0):.0f}% · {r.get("league_name","")[:20]}</div>
              </div>
              <div style="text-align:right;flex-shrink:0">
                <div style="font-size:.7rem;font-weight:800;color:{dot}">{r.get("result","")}</div>
                <div style="font-size:.58rem;color:var(--t2)">{score_str}</div>
              </div>
            </div>'''
        content += '</div>'

    # Pending predictions
    pending_rows = stats.get("pending_rows",[])
    if pending_rows:
        content += f'''<div class="card up d4">
          <div class="card-title"><span class="card-title-icon">⏳</span> Pending ({pending})</div>'''
        for p in pending_rows[:8]:
            mdate = (p.get("match_date") or "")[:16]
            content += f'''<div class="result-row">
              <div class="win-dot" style="background:var(--w)"></div>
              <div style="flex:1;min-width:0">
                <div style="font-size:.7rem;color:var(--wh);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{p.get("home_team","")} vs {p.get("away_team","")}</div>
                <div style="font-size:.6rem;color:var(--t2);margin-top:1px">{p.get("market","")} · {p.get("probability",0):.0f}% · {mdate}</div>
              </div>
              <span class="badge bg-orange">PENDING</span>
            </div>'''
        content += '</div>'

    if total == 0 and pending == 0:
        content += '''<div class="empty"><span class="empty-icon">📊</span>
          No predictions tracked yet.<br>
          Open any fixture to generate a prediction.<br>
          Results settle automatically after matches finish.
        </div>'''

    return render_template_string(LAYOUT, content=content, page="tracker")

@app.route("/api/live-count")
def api_live_count():
    lives = sportmonks.get_livescores()
    return jsonify({"count": len(lives) if lives else 0})

@app.route("/api/morning")
def api_morning():
    result = scheduler.run_morning_job()
    return jsonify(result)

@app.route("/api/settle")
def api_settle():
    result = scheduler.run_settlement_job()
    return jsonify(result)

@app.route("/api/calibration")
def api_calibration():
    cal = database.get_market_calibration()
    return jsonify({"calibration": cal, "markets": len(cal)})

@app.route("/manifest.json")
def pwa_manifest():
    manifest = {
        "name": "ProPred NG", "short_name": "ProPred",
        "description": "Football Prediction Intelligence",
        "start_url": "/", "display": "standalone",
        "background_color": "#03050a", "theme_color": "#00ff87",
        "orientation": "portrait",
        "icons": [
            {"src": "/static/icon.png","sizes":"192x192","type":"image/png"},
            {"src": "/static/icon.png","sizes":"512x512","type":"image/png"}
        ]
    }
    return Response(json.dumps(manifest), mimetype="application/json")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
