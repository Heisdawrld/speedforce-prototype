from flask import Flask, render_template_string, request
import requests
from datetime import datetime, timedelta
import match_predictor
import os

app = Flask(__name__)

# CONFIG
BSD_TOKEN = os.environ.get("BSD_TOKEN", "631a48f45a20b3352ea3863f8aa23baf610710e2")
BASE_URL = "https://sports.bzzoiro.com/api"

# [LEAGUE MAPPING - Crucial for organization]
LEAGUE_MAP = {
    "EPL": ["Liverpool", "Arsenal", "Manchester", "Chelsea", "Wolverhampton", "Newcastle", "Everton", "Leeds"],
    "PD": ["Real Madrid", "Barcelona", "Atletico", "Rayo Vallecano", "Levante", "Alaves"],
    "SA": ["Juventus", "Milan", "Inter", "Parma", "Cagliari", "Como", "Lecce"],
    "BL1": ["Bayer", "Bayern", "Dortmund", "Augsburg", "Hoffenheim", "St. Pauli", "Mainz"]
}

LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; }
        .glass { background: rgba(15, 18, 24, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body class="p-4 italic">
    <div class="max-w-md mx-auto min-h-screen">
        <header class="py-6 border-b border-white/5 mb-6 flex justify-between items-center">
            <a href="/" class="text-xl font-black text-white italic tracking-tighter">ELITE<span class="text-green-500">EDGE</span></a>
            <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
        </header>
        {{content|safe}}
    </div>
</body>
</html>
"""

@app.route("/")
def landing():
    leagues = [("EPL", "Premier League"), ("PD", "La Liga"), ("SA", "Serie A"), ("BL1", "Bundesliga")]
    content = '<div class="py-10 text-center"><h2 class="text-3xl font-black text-white italic mb-10 uppercase tracking-tighter leading-tight">Quant-Based <br>Intelligence</h2>'
    for code, name in leagues:
        content += f'<a href="/league/{code}" class="block glass p-8 rounded-[2rem] border border-white/5 mb-4 text-left nav-btn shadow-xl"><p class="text-xs text-zinc-500 font-bold mb-1 uppercase tracking-widest">{code}</p><p class="text-lg font-black text-white uppercase">{name}</p></a>'
    content += '</div>'
    return render_template_string(LAYOUT, content=content)

@app.route("/league/<code>")
def league_page(code):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers, timeout=10).json()
        all_matches = r.get("results", []) if isinstance(r, dict) else []
    except: all_matches = []

    # Filter by League Map
    matches = []
    allowed_teams = LEAGUE_MAP.get(code, [])
    for m in all_matches:
        h_team = m.get('event', {}).get('home_team', '')
        if any(name in h_team for name in allowed_teams):
            matches.append(m)

    content = f'<a href="/" class="text-zinc-600 text-[10px] font-black uppercase tracking-widest mb-10 block">← Competition Hub</a>'
    content += f'<h3 class="text-green-500 font-black uppercase text-xl italic mb-8 tracking-tighter">{code} Analysis</h3>'
    
    # GROUPING BY DATE
    today = datetime.now().strftime("%Y-%m-%d")
    grouped = {"TODAY": [], "LATER": []}
    
    for m in matches:
        start_time = m.get('event', {}).get('start_time', '')
        if today in start_time: grouped["TODAY"].append(m)
        else: grouped["LATER"].append(m)

    for section, games in grouped.items():
        if games:
            content += f'<p class="text-[9px] font-black text-zinc-700 uppercase tracking-[0.5em] mb-4 mt-10">{section}</p>'
            for g in games:
                h, a = g['event']['home_team'], g['event']['away_team']
                t = g['event']['start_time'][11:16]
                content += f'''
                <a href="/match/{g['id']}?h={h}&a={a}&l={code}" class="flex justify-between items-center p-6 glass rounded-3xl mb-3 border border-white/5 shadow-lg">
                    <span class="text-[10px] font-black text-zinc-500">{t}</span>
                    <span class="text-[11px] font-black text-white uppercase truncate px-4">{h} v {a}</span>
                    <span class="text-green-500 font-black text-[9px]">VIEW →</span>
                </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match/<match_id>")
def match_analysis(match_id):
    h, a, l = request.args.get('h'), request.args.get('a'), request.args.get('l')
    # Dummy stat inputs for the model (In production, pull these from a stats API)
    res = match_predictor.analyze_match(2.1, 1.4, 0.9, 1.8) 
    
    content = f'''
    <div class="text-center mb-10">
        <span class="bg-green-500/10 text-green-500 border border-green-500/20 px-5 py-2 rounded-full text-[9px] font-black uppercase tracking-widest">{res['tag']}</span>
        <h2 class="text-2xl font-black text-white uppercase mt-12 italic leading-tight tracking-tighter">{h} <span class="text-zinc-800 mx-2 text-sm italic opacity-50">vs</span> {a}</h2>
    </div>

    <div class="grid grid-cols-3 gap-2 mb-8">
        <div class="glass p-4 rounded-2xl text-center"><p class="text-[7px] text-zinc-500 uppercase font-black mb-1">Home</p><p class="text-xs font-black text-white">{res['probs']['home']}%</p></div>
        <div class="glass p-4 rounded-2xl text-center"><p class="text-[7px] text-zinc-500 uppercase font-black mb-1">Draw</p><p class="text-xs font-black text-white">{res['probs']['draw']}%</p></div>
        <div class="glass p-4 rounded-2xl text-center"><p class="text-[7px] text-zinc-500 uppercase font-black mb-1">Away</p><p class="text-xs font-black text-white">{res['probs']['away']}%</p></div>
    </div>

    <div class="glass p-6 rounded-[2.5rem] border border-white/5 mb-4 shadow-2xl">
        <div class="flex justify-between items-start mb-2"><span class="text-[8px] font-black text-zinc-600 uppercase">🔵 Recommended</span><span class="text-2xl font-black text-green-500">+{res['conf']}% Conf</span></div>
        <h2 class="text-2xl font-black text-white uppercase tracking-tighter">{res['rec']['t']}</h2>
        <div class="flex justify-between items-end mt-4 pt-4 border-t border-white/5">
            <p class="text-3xl font-black text-white tracking-tighter italic">{res['rec']['p']}%</p>
            <p class="text-[10px] font-black text-zinc-500 uppercase italic">Expected Edge: +8.4%</p>
        </div>
    </div>

    <div class="grid grid-cols-2 gap-3 mb-10">
        <div class="glass p-5 rounded-3xl border border-white/5"><span class="text-[7px] font-black text-zinc-600 uppercase mb-2 block tracking-widest text-blue-500">🟢 Safe</span><p class="text-[10px] font-black text-white uppercase mb-1">{res['safe']['t']}</p><p class="text-lg font-black text-white opacity-40">{res['safe']['p']}%</p></div>
        <div class="glass p-5 rounded-3xl border border-white/5"><span class="text-[7px] font-black text-red-500 uppercase mb-2 block tracking-widest">🔴 Risk</span><p class="text-[10px] font-black text-white uppercase mb-1">{res['risk']['t']}</p><p class="text-lg font-black text-white opacity-40">{res['risk']['p']}%</p></div>
    </div>

    <div class="bg-zinc-950 p-6 rounded-[2.5rem] mb-20 italic">
        <h3 class="text-[8px] font-black text-zinc-700 uppercase tracking-[0.4em] mb-6 text-center underline decoration-zinc-800">Quant Model Insights</h3>
        <div class="flex justify-between items-center text-[10px] font-black uppercase mb-4 tracking-widest"><span class="text-zinc-500">Expected Goals (xG)</span><span class="text-white">{res['stats']['h_xg']} - {res['stats']['a_xg']}</span></div>
        <div class="flex justify-between items-center text-[10px] font-black uppercase tracking-widest"><span class="text-zinc-500">Volatility Rank</span><span class="text-yellow-500 italic">MODERATE</span></div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
