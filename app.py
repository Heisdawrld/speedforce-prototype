from flask import Flask, render_template_string, request
import requests
from datetime import datetime, timedelta
import match_predictor
import os

app = Flask(__name__)

# CONFIG
BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL = "https://sports.bzzoiro.com/api"

# League Catalog
LEAGUES = [
    {"id": 1, "name": "Premier League", "geo": "England"},
    {"id": 12, "name": "Championship", "geo": "England"},
    {"id": 4, "name": "Serie A", "geo": "Italy"},
    {"id": 5, "name": "Bundesliga", "geo": "Germany"},
    {"id": 14, "name": "Pro League", "geo": "Belgium"},
    {"id": 18, "name": "MLS", "geo": "USA"}
]

LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@900&display=swap');
        body { background: #05070a; color: #d4d4d8; font-family: 'Inter', sans-serif; }
        .glass { background: rgba(15, 18, 24, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body class="p-4 italic">
    <div class="max-w-md mx-auto min-h-screen">
        <header class="flex justify-between items-center py-6 mb-6">
            <h1 class="text-xl font-black text-white italic uppercase tracking-tighter">PRO<span class="text-green-500">PREDICTOR</span></h1>
            <a href="/acca" class="bg-green-500/10 text-green-500 px-3 py-1.5 rounded-full text-[9px] font-black uppercase">ACCA Builder</a>
        </header>
        {{content|safe}}
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    # This prevents the 404 by giving the root URL a Landing Page
    content = '<div class="py-10 text-center"><h2 class="text-3xl font-black text-white mb-10 uppercase tracking-tighter">Global Intelligence</h2>'
    for l in LEAGUES:
        content += f'''
        <a href="/league/{l['id']}?name={l['name']}" class="block glass p-8 rounded-[2.5rem] border border-white/5 mb-4 text-left shadow-2xl">
            <p class="text-[9px] text-zinc-500 font-black mb-1 uppercase tracking-widest">{l['geo']}</p>
            <p class="text-xl font-black text-white uppercase">{l['name']}</p>
        </a>'''
    content += '</div>'
    return render_template_string(LAYOUT, content=content)

@app.route("/league/<l_id>")
def league_page(l_id):
    l_name = request.args.get('name', 'League')
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    r = requests.get(f"{BASE_URL}/predictions/?league={l_id}", headers=headers).json()
    matches = r.get("results", [])

    content = f'<a href="/" class="text-zinc-600 text-[10px] font-black uppercase mb-10 block tracking-widest">← Back</a>'
    content += f'<h3 class="text-green-500 font-black uppercase text-2xl italic mb-10 tracking-tighter">{l_name}</h3>'
    
    for g in matches:
        event = g.get("event", {})
        h, a = event.get("home_team"), event.get("away_team")
        raw_time = event.get("start_time", "2026-02-28T19:00:00Z")
        dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00")) + timedelta(hours=1)
        
        content += f'''
        <a href="/match/{g["id"]}?h={h}&a={a}&l={l_id}" class="flex justify-between items-center p-6 glass rounded-[2.5rem] mb-3 border border-white/5 shadow-xl">
            <div class="flex flex-col"><span class="text-[8px] font-black text-zinc-600 uppercase">{dt.strftime("%d %b")}</span><span class="text-[11px] font-black text-white">{dt.strftime("%H:%M")}</span></div>
            <span class="text-[11px] font-black text-white uppercase truncate px-4">{h} v {a}</span>
            <span class="text-green-500 font-black text-[9px]">ANALYZE →</span>
        </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match/<match_id>")
def match_display(match_id):
    l_id = request.args.get('l', 1)
    h, a = request.args.get('h'), request.args.get('a')
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    data = requests.get(f"{BASE_URL}/predictions/{match_id}/", headers=headers).json()
    
    res = match_predictor.analyze_match(data, int(l_id))
    
    content = f'''
    <div class="text-center mb-10">
        <span class="bg-green-500/10 text-green-500 border border-green-500/20 px-6 py-2 rounded-full text-[9px] font-black uppercase tracking-widest">{res['tag']}</span>
        <h2 class="text-2xl font-black text-white uppercase mt-12 italic leading-tight">{h} <br><span class="text-zinc-800 text-sm opacity-50 not-italic">VS</span><br> {a}</h2>
    </div>

    <div class="glass p-8 rounded-[3rem] border border-white/5 mb-4 shadow-2xl italic">
        <span class="text-[9px] font-black text-zinc-600 uppercase tracking-widest">🔵 Recommended</span>
        <h2 class="text-2xl font-black text-white uppercase tracking-tighter mt-3">{res['rec']['t']}</h2>
        <p class="text-4xl font-black text-green-500 mt-4 tracking-tighter">+{res['rec']['p']}%</p>
    </div>

    <div class="grid grid-cols-2 gap-3 mb-10">
        <div class="glass p-6 rounded-[2rem] border border-white/5 font-black uppercase text-[10px]">
            <span class="text-blue-500 block mb-2 text-[8px]">🟢 Safe</span> {res['safe']['t']}
        </div>
        <div class="glass p-6 rounded-[2rem] border border-white/5 font-black uppercase text-[10px]">
            <span class="text-red-500 block mb-2 text-[8px]">🔴 Risk</span> {res['risk']['t']}
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

@app.route("/acca")
def acca():
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    r = requests.get(f"{BASE_URL}/predictions/", headers=headers).json()
    # Get top 4 picks based on Home Win probability
    picks = sorted(r.get("results", []), key=lambda x: x.get('prob_home', 0), reverse=True)[:4]
    
    picks_html = ""
    total_odds = 1.0
    for p in picks:
        odds = round((1 / p.get('prob_home', 0.5)) * 0.92, 2)
        total_odds *= odds
        picks_html += f'<div class="p-5 glass rounded-2xl mb-2 flex justify-between font-black uppercase text-[10px]"><span>{p["event"]["home_team"]}</span><span class="text-green-500">{odds}</span></div>'
    
    content = f'<div class="text-center"><h2 class="text-white text-2xl font-black mb-10 italic uppercase">Pro ACCA Slip</h2>{picks_html}<div class="mt-10 p-10 glass rounded-[3rem] border border-green-500/20 font-black"><p class="text-[10px] text-zinc-600 uppercase">Combined Odds</p><p class="text-5xl text-green-500 tracking-tighter">{round(total_odds, 2)}</p></div></div>'
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
