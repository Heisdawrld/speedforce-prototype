from flask import Flask, render_template_string, request
import requests
from datetime import datetime
import match_predictor
import os

app = Flask(__name__)

# CONFIG
BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL = "https://sports.bzzoiro.com/api"

# [ROUTER LOGIC] Mapping teams to folders
LEAGUE_KEYWORDS = {
    "EPL": ["liverpool", "arsenal", "manchester", "chelsea", "wolves", "newcastle", "everton", "leeds", "bournemouth", "burnley", "brentford", "villa", "watford", "sheffield"],
    "PD": ["real madrid", "barcelona", "atletico", "rayo", "levante", "alaves", "villarreal", "sevilla"],
    "SA": ["juventus", "milan", "inter", "parma", "cagliari", "como", "lecce", "roma", "napoli", "lazio"],
    "BL1": ["bayern", "dortmund", "leverkusen", "augsburg", "koeln", "mainz", "st. pauli", "heidenheim"]
}

LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; }
        .glass { background: rgba(15, 18, 24, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body class="p-4 italic">
    <div class="max-w-md mx-auto min-h-screen">
        <header class="py-6 border-b border-white/5 mb-6 flex justify-between items-center">
            <a href="/" class="text-xl font-black text-white italic tracking-tighter">ELITE<span class="text-green-500">EDGE</span></a>
            <a href="/acca" class="bg-green-500/10 text-green-500 px-4 py-1.5 rounded-full text-[9px] font-black uppercase">Builder</a>
        </header>
        {{content|safe}}
    </div>
</body>
</html>
"""

@app.route("/")
def landing():
    leagues = [("EPL", "Premier League"), ("PD", "La Liga"), ("SA", "Serie A"), ("BL1", "Bundesliga")]
    content = '<div class="py-10 text-center"><h2 class="text-3xl font-black text-white mb-10 uppercase tracking-tighter">Quant-Based <br>Intelligence</h2>'
    for code, name in leagues:
        content += f'''
        <a href="/league/{code}" class="block glass p-8 rounded-[2.5rem] border border-white/5 mb-4 text-left shadow-2xl">
            <p class="text-[9px] text-zinc-500 font-black mb-1 uppercase tracking-widest">{code} Tier</p>
            <p class="text-xl font-black text-white uppercase">{name}</p>
        </a>'''
    content += '</div>'
    return render_template_string(LAYOUT, content=content)

@app.route("/league/<code>")
def league_page(code):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers, timeout=10).json()
        all_m = r.get("results", []) if isinstance(r, dict) else []
    except: all_m = []

    # Filtering matches into groups
    matches = []
    keywords = LEAGUE_KEYWORDS.get(code, [])
    for m in all_m:
        h = m.get('event', {}).get('home_team', '').lower()
        if any(key in h for key in keywords):
            matches.append(m)

    content = f'<a href="/" class="text-zinc-600 text-[10px] font-black uppercase tracking-[0.3em] mb-10 block">← Competition Hub</a>'
    
    if not matches:
        content += f'<div class="py-20 text-center opacity-20 font-black uppercase text-xs">No {code} fixtures syncing...</div>'
    else:
        # Group by Time for organization
        content += f'<h3 class="text-green-500 font-black uppercase text-xl italic mb-10 tracking-tighter">{code} Analysis</h3>'
        for g in matches:
            event = g.get("event", {})
            h, a = event.get("home_team"), event.get("away_team")
            t = event.get("start_time")[11:16]
            content += f'''
            <a href="/match/{g["id"]}?h={h}&a={a}" class="flex justify-between items-center p-6 glass rounded-[2rem] mb-3 border border-white/5 shadow-xl transition-all active:scale-95">
                <span class="text-[10px] font-black text-zinc-600">{t}</span>
                <span class="text-[11px] font-black text-white uppercase truncate px-4">{h} v {a}</span>
                <span class="text-green-500 font-black text-[9px]">ANALYZE →</span>
            </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match/<match_id>")
def match_view(match_id):
    h, a = request.args.get('h'), request.args.get('a')
    # Using the Engine with high-quality simulated stats (In production these pull from a form API)
    res = match_predictor.analyze_match(2.2, 1.3, 0.8, 1.9)
    
    content = f'''
    <div class="text-center mb-10">
        <span class="bg-green-500/10 text-green-500 border border-green-500/20 px-6 py-2 rounded-full text-[9px] font-black uppercase tracking-widest">{res['tag']}</span>
        <h2 class="text-2xl font-black text-white uppercase mt-12 italic leading-tight tracking-tighter">{h} <br><span class="text-zinc-800 text-sm opacity-50 font-black not-italic">VS</span><br> {a}</h2>
    </div>

    <div class="glass p-7 rounded-[3rem] border border-white/5 mb-4 shadow-2xl relative">
        <div class="flex justify-between items-start mb-2">
            <span class="text-[9px] font-black text-zinc-600 uppercase tracking-widest">🔵 Recommended</span>
            <span class="text-2xl font-black text-green-500">+{res['conf']}% Gap</span>
        </div>
        <h2 class="text-2xl font-black text-white uppercase tracking-tighter leading-none mb-6">{res['rec']['t']}</h2>
        <div class="flex justify-between items-center pt-6 border-t border-white/5">
            <div class="flex flex-col"><p class="text-[8px] text-zinc-600 uppercase font-black">Probability</p><p class="text-2xl font-black text-white tracking-tighter">{res['rec']['p']}%</p></div>
            <div class="text-right flex flex-col"><p class="text-[8px] text-zinc-600 uppercase font-black">Fair Odds</p><p class="text-2xl font-black text-green-500 tracking-tighter">{res['rec']['o']}</p></div>
        </div>
    </div>

    <div class="grid grid-cols-2 gap-3 mb-10">
        <div class="glass p-6 rounded-[2rem] border border-white/5"><span class="text-[8px] font-black text-blue-500 uppercase mb-2 block">🟢 Safe</span><p class="text-[10px] font-black text-white uppercase mb-1">{res['safe']['t']}</p><p class="text-xl font-black text-zinc-600">{res['safe']['p']}%</p></div>
        <div class="glass p-6 rounded-[2rem] border border-white/5"><span class="text-[8px] font-black text-red-500 uppercase mb-2 block">🔴 Risk</span><p class="text-[10px] font-black text-white uppercase mb-1">{res['risk']['t']}</p><p class="text-xl font-black text-zinc-600">{res['risk']['p']}%</p></div>
    </div>

    <div class="glass p-6 rounded-[2.5rem] mb-20 italic">
        <h3 class="text-[8px] font-black text-zinc-700 uppercase tracking-[0.4em] mb-6 text-center">Quant Model Metrics</h3>
        <div class="flex justify-between items-center text-[10px] font-black uppercase mb-4 tracking-widest"><span class="text-zinc-500 italic">Expected Goals (xG)</span><span class="text-white">{res['xg']['h']} - {res['xg']['a']}</span></div>
        <div class="flex justify-between items-center text-[10px] font-black uppercase tracking-widest"><span class="text-zinc-500 italic">Home Form Index</span><div class="flex gap-1"><span class="bg-green-500 w-3 h-3 rounded-full"></span><span class="bg-green-500 w-3 h-3 rounded-full"></span><span class="bg-zinc-800 w-3 h-3 rounded-full"></span></div></div>
    </div>
    <a href="javascript:history.back()" class="block text-center text-zinc-800 text-[10px] font-black uppercase tracking-widest mt-10">← Return to Fixtures</a>
    '''
    return render_template_string(LAYOUT, content=content)

@app.route("/acca")
def acca_page():
    return render_template_string(LAYOUT, content='<div class="py-40 text-center opacity-30 font-black uppercase tracking-[0.5em] text-xs">ACCA Builder <br>Optimizing Data...</div>')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
