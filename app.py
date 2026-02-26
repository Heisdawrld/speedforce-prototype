from flask import Flask, render_template_string, request
import requests
from datetime import datetime, timedelta
import match_predictor
import os

app = Flask(__name__)

# CONFIG
BSD_TOKEN = os.environ.get("BSD_TOKEN", "631a48f45a20b3352ea3863f8aa23baf610710e2")
BASE_URL = "https://sports.bzzoiro.com/api" # Using your verified endpoint

LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; -webkit-tap-highlight-color: transparent; }
        .glass { background: rgba(15, 18, 24, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body class="italic">
    <div class="max-w-md mx-auto min-h-screen p-4 flex flex-col">
        <header class="flex justify-between items-center py-6 border-b border-white/5 mb-6">
            <a href="/" class="text-xl font-black text-white italic uppercase tracking-tighter">PRO<span class="text-green-500">PREDICTOR</span></a>
            <a href="/acca" class="bg-green-500/10 text-green-500 px-3 py-1.5 rounded-full text-[9px] font-black uppercase">ACCA Builder</a>
        </header>
        {{content|safe}}
    </div>
</body>
</html>
"""

@app.route("/")
def landing():
    leagues = [
        {"code": "PL", "name": "Premier League"},
        {"code": "PD", "name": "La Liga"},
        {"code": "SA", "name": "Serie A"},
        {"code": "BL1", "name": "Bundesliga"}
    ]
    content = '<div class="py-10 text-center"><h2 class="text-3xl font-black text-white mb-8 uppercase tracking-tighter">Elite Betting <br>Intelligence</h2>'
    for l in leagues:
        content += f'<a href="/league/{l["code"]}" class="block glass p-6 rounded-3xl mb-3 border border-white/5 font-black uppercase text-xs hover:border-green-500/30 transition">{l["name"]}</a>'
    content += '</div>'
    return render_template_string(LAYOUT, content=content)

@app.route("/league/<code>")
def fixtures(code):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}/predictions/?league={code}", headers=headers, timeout=10).json()
        matches = r.get("results", []) if isinstance(r, dict) else []
    except: matches = []

    today = datetime.utcnow().date()
    content = f'<h3 class="text-zinc-600 text-[10px] font-black uppercase tracking-[0.3em] mb-6">Upcoming Fixtures</h3>'
    for m in matches:
        event = m.get("event", {})
        content += f'''
        <a href="/match/{m["id"]}" class="flex justify-between items-center p-5 glass rounded-2xl mb-2 border border-white/5">
            <span class="text-[10px] font-black text-white uppercase truncate pr-4">{event.get("home_team")} v {event.get("away_team")}</span>
            <span class="text-green-500 text-[10px] font-black">ANALYZE →</span>
        </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match/<match_id>")
def match_page(match_id):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        data = requests.get(f"{BASE_URL}/predictions/{match_id}/", headers=headers, timeout=10).json()
    except: data = {}
    
    res = match_predictor.analyze_match(data)
    event = data.get("event", {})
    
    content = f'''
    <div class="text-center mb-10">
        <span class="bg-green-500/10 text-green-500 border border-green-500/20 px-4 py-1.5 rounded-full text-[9px] font-black uppercase tracking-widest">{res['tag']}</span>
        <h2 class="text-xl font-black text-white uppercase mt-10 italic leading-tight">{event.get('home_team')} <br><span class="text-zinc-800 text-sm">VS</span><br> {event.get('away_team')}</h2>
    </div>

    <div class="glass p-6 rounded-[2.5rem] border border-white/5 mb-4 italic">
        <span class="text-[8px] font-black text-zinc-600 uppercase">🔵 Recommended</span>
        <h2 class="text-2xl font-black text-white uppercase mt-2">{res['rec']['t']}</h2>
        <div class="flex justify-between items-end mt-4">
            <p class="text-4xl font-black text-green-500 tracking-tighter">+{res['rec']['p']}%</p>
            <p class="text-[10px] font-black text-zinc-500">ODDS: {res['rec']['o']}</p>
        </div>
    </div>

    <div class="grid grid-cols-2 gap-3 mb-10">
        <div class="glass p-5 rounded-3xl border border-white/5">
            <span class="text-[7px] font-black text-zinc-600 uppercase mb-2 block">🟢 Safe</span>
            <p class="text-[10px] font-black text-white uppercase mb-1">{res['safe']['t']}</p>
            <p class="text-lg font-black text-white opacity-40">{res['safe']['p']}%</p>
        </div>
        <div class="glass p-5 rounded-3xl border border-white/5">
            <span class="text-[7px] font-black text-zinc-600 uppercase mb-2 block">🔴 Risk</span>
            <p class="text-[10px] font-black text-white uppercase mb-1">{res['risk']['t']}</p>
            <p class="text-lg font-black text-white opacity-40">{res['risk']['p']}%</p>
        </div>
    </div>

    <div class="bg-white/5 p-6 rounded-[2.5rem] mb-20 italic">
        <h3 class="text-[9px] font-black text-zinc-700 uppercase tracking-[0.4em] mb-6 text-center">Insights</h3>
        <div class="flex justify-between items-center text-[10px] font-black uppercase mb-4">
            <span class="text-zinc-500">Volatility</span>
            <span class="text-yellow-500">{res['vol']}</span>
        </div>
        <div class="grid grid-cols-2 gap-4 pt-4 border-t border-white/5">
            <div><p class="text-[7px] text-zinc-600 uppercase">Home Avg</p><p class="text-xs text-white font-black">{res['stats']['h_gls']} GLS</p></div>
            <div><p class="text-[7px] text-zinc-600 uppercase">Away Avg</p><p class="text-xs text-white font-black">{res['stats']['a_gls']} GLS</p></div>
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

@app.route("/acca")
def acca_builder():
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers, timeout=10).json()
        matches = r.get("results", [])[:4]
    except: matches = []

    picks_html = ""
    total_odds = 1.0
    for m in matches:
        res = match_predictor.analyze_match(m)
        total_odds *= res['rec']['o']
        picks_html += f'''
        <div class="p-5 glass rounded-2xl mb-2 flex justify-between items-center italic">
            <span class="text-[10px] font-black text-white uppercase">{m.get("event",{}).get("home_team")[0:10]}...</span>
            <span class="text-green-500 font-black text-xs">{res['rec']['o']}</span>
        </div>'''

    content = f'''
    <div class="text-center">
        <h2 class="text-2xl font-black text-white italic mb-10 uppercase">ACCA Builder</h2>
        {picks_html}
        <div class="mt-10 p-8 glass rounded-[2.5rem] border border-green-500/20">
            <p class="text-[10px] text-zinc-600 font-black uppercase tracking-widest">Total Combined Odds</p>
            <p class="text-4xl font-black text-green-500 mt-2 tracking-tighter">{round(total_odds, 2)}</p>
        </div>
    </div>'''
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
