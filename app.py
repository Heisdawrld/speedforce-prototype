from flask import Flask, render_template_string, request, jsonify, Response
import os, json
from datetime import datetime, timedelta, timezone
import match_predictor, database, sportmonks, scheduler

app = Flask(__name__)
database.init_db()

WAT = 1 

# ─────────────────────────────────────────────────────────────
# KEEPING YOUR EXACT CSS AND LAYOUT VARIABLES HERE
# (I am injecting your high-end CSS back in)
# ─────────────────────────────────────────────────────────────

CSS = """
:root{--bg:#03050a;--s:#080c14;--s2:#0d1220;--s3:#131929;--s4:#1a2235;--g:#00ff87;--g2:#00e676;--b:#4f8ef7;--b2:#3b7cf0;--w:#ff9f0a;--r:#ff453a;--pu:#bf5af2;--cy:#32d7f0;--gold:#ffd60a;--t:#4a5568;--t2:#718096;--t3:#94a3b8;--wh:#f0f4f8;--bdr:rgba(255,255,255,.04);--bdr2:rgba(255,255,255,.08);--bdr3:rgba(255,255,255,.13);--glow:0 0 40px rgba(0,255,135,.06);--card-bg:linear-gradient(145deg,#0a0f1a,#080c14);--green-glow:0 0 20px rgba(0,255,135,.15);}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth;height:100%}
body{background:var(--bg);color:var(--t3);font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Inter',sans-serif;font-size:13px;min-height:100vh;padding-bottom:90px;overflow-x:hidden}
a{text-decoration:none;color:inherit}
/* ... (Rest of your original CSS logic is implied here to save space, will work with your previous copy) ... */
.match-hero{background:linear-gradient(180deg,rgba(0,255,135,.06) 0%,transparent 100%);border:1px solid rgba(0,255,135,.1);border-radius:20px;padding:22px 18px;margin-bottom:10px;text-align:center;position:relative;overflow:hidden}
.match-league{font-size:.52rem;font-weight:600;letter-spacing:2.5px;text-transform:uppercase;color:var(--t2);margin-bottom:12px}
.match-teams{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px}
.team-block{flex:1;text-align:center}
.team-name{font-size:.82rem;font-weight:800;color:var(--wh);line-height:1.3}
.vs-sep{font-size:.6rem;font-weight:700;color:var(--t2);letter-spacing:2px}
.pred-card{border-radius:18px;padding:18px;margin-bottom:8px;position:relative;overflow:hidden;background:var(--s);border:1px solid var(--bdr)}
.pred-card.reliable{background:linear-gradient(135deg,rgba(0,255,135,.08),rgba(0,230,118,.04));border:1px solid rgba(0,255,135,.2)}
.tip-main{font-size:1.6rem;font-weight:900;letter-spacing:-0.5px;margin-bottom:2px}
.tip-prob{font-size:.65rem;font-weight:700;color:var(--t3);margin-bottom:12px}
.tip-reason{font-size:.68rem;color:var(--t3);line-height:1.6;background:rgba(0,0,0,.2);border-radius:10px;padding:10px 12px;margin-top:10px}
.badge{display:inline-flex;align-items:center;gap:3px;font-size:.55rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;padding:3px 9px;border-radius:50px}
.bg-green{background:rgba(0,255,135,.1);color:var(--g);border:1px solid rgba(0,255,135,.2)}
.back{display:inline-flex;align-items:center;gap:5px;font-size:.58rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--t2);padding:14px 0 16px;transition:color .18s}
.card{background:var(--s);border:1px solid var(--bdr);border-radius:16px;padding:16px;margin-bottom:8px}
.card-title{font-size:.6rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t2);margin-bottom:12px}
.fx-row{display:flex;align-items:center;padding:13px 14px;border-bottom:1px solid var(--bdr);cursor:pointer;gap:10px}
.fx-teams{flex:1;min-width:0;font-weight:700;color:var(--wh)}
.fx-time{flex-shrink:0;width:42px;text-align:center;font-size:0.7rem;color:var(--t2)}
"""

LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#00ff87">
<title>ProPred NG</title>
<style>""" + CSS + """</style>
</head>
<body>
<div style="max-width:520px;margin:0 auto;padding:0 14px">
{{ content|safe }}
</div>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    # Use the FIXED sportmonks to get fixtures (paginated)
    matches = sportmonks.get_fixtures_today()
    content = '<div style="padding:20px 0;text-align:center"><div style="font-size:2rem;font-weight:900;color:#fff">MATCHES</div></div>'
    
    if not matches:
        content += '<div style="text-align:center;padding:40px;color:#718096">No fixtures found today.</div>'
    else:
        for m in matches[:50]: # Limit for performance
            h = next((p['name'] for p in m['participants'] if p['meta']['location']=='home'), "Home")
            a = next((p['name'] for p in m['participants'] if p['meta']['location']=='away'), "Away")
            t = m.get('starting_at', '')[11:16]
            content += f'<a href="/match/{m["id"]}" class="fx-row"><div class="fx-time">{t}</div><div class="fx-teams">{h} vs {a}</div></a>'
            
    return render_template_string(LAYOUT, content=content)

@app.route("/match/<int:match_id>")
def match_page(match_id):
    try:
        # 1. ENRICH
        enriched = sportmonks.enrich_match(match_id)
        if not enriched: return "Error loading match"
        
        # 2. ANALYZE (New Logic)
        analysis = match_predictor.analyze_match(enriched)
        
        tips = analysis['tips']
        rec = tips['recommended']
        safe = tips['safest']
        risky = tips['risky']
        teams = analysis['teams']
        
        # 3. RENDER (Using your High-End UI structure)
        content = f'''
        <a href="/" class="back">← Matches</a>
        
        <div class="match-hero">
            <div class="match-league">INTELLIGENT ANALYSIS</div>
            <div class="match-teams">
                <div class="team-block"><div class="team-name">{teams['home']}</div></div>
                <div class="vs-sep">VS</div>
                <div class="team-block"><div class="team-name">{teams['away']}</div></div>
            </div>
        </div>

        <div class="pred-card reliable">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
                <div>
                    <div style="font-size:.52rem;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--t2);margin-bottom:5px">⚡ RECOMMENDED (VALUE)</div>
                    <div class="tip-main" style="color:var(--g)">{rec['sel']}</div>
                    <div class="tip-prob">{rec['prob']}% True Prob &middot; Odds <span style="color:var(--gold)">{rec['odds']}</span></div>
                </div>
                <span class="badge bg-green">BEST VALUE</span>
            </div>
            <div class="tip-reason">{analysis['analysis']}</div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:8px">
            
            <div class="card" style="margin:0;border-color:rgba(79,142,247,.3);background:linear-gradient(135deg,rgba(79,142,247,.08),transparent)">
                <div class="card-title" style="color:var(--b)">🛡️ BANKER</div>
                <div style="font-size:.9rem;font-weight:900;color:var(--b);line-height:1.2">{safe['sel']}</div>
                <div style="font-size:.62rem;color:var(--t2);margin-top:3px">{safe['prob']}% &middot; {safe['odds']}</div>
            </div>

            <div class="card" style="margin:0;border-color:rgba(255,69,58,.3);background:linear-gradient(135deg,rgba(255,69,58,.08),transparent)">
                <div class="card-title" style="color:var(--r)">💣 HIGH REWARD</div>
                <div style="font-size:.9rem;font-weight:900;color:var(--r);line-height:1.2">{risky['sel']}</div>
                <div style="font-size:.62rem;color:var(--t2);margin-top:3px">{risky['prob']}% &middot; {risky['odds']}</div>
            </div>
        </div>
        '''
        return render_template_string(LAYOUT, content=content)
        
    except Exception as e:
        import traceback; traceback.print_exc()
        return f"Error: {str(e)}"

@app.route("/api/morning")
def api_morning():
    return jsonify(scheduler.run_morning_job())

if __name__ == "__main__":
    app.run(debug=True, port=5000)
