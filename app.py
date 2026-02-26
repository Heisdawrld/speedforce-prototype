from flask import Flask, render_template_string, request
import requests
from datetime import datetime
import match_predictor
import os

app = Flask(__name__)

# ==========================================
# CONFIGURATION
# ==========================================
BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL = "https://sports.bzzoiro.com/api"

# League Keywords for Automatic Organization
LEAGUE_KEYWORDS = {
    "EPL": ["liverpool", "arsenal", "manchester", "chelsea", "wolves", "newcastle", "everton", "leeds", "bournemouth", "burnley", "brentford", "villa", "watford", "sheffield", "southampton", "ipswich", "leicester"],
    "PD": ["real madrid", "barcelona", "atletico", "rayo", "levante", "alaves", "villarreal", "sevilla", "athletic", "espanyol", "sociedad"],
    "SA": ["juventus", "milan", "inter", "parma", "cagliari", "como", "lecce", "roma", "napoli", "lazio", "fiorentina"],
    "BL1": ["bayern", "dortmund", "leverkusen", "augsburg", "koeln", "mainz", "st. pauli", "heidenheim", "union berlin", "hoffenheim", "stuttgart"]
}

# ==========================================
# PREMIUM MOBILE LAYOUT
# ==========================================
LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>PRO PREDICTOR | Elite Intelligence</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; -webkit-tap-highlight-color: transparent; }
        .glass { background: rgba(15, 18, 24, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); }
        .nav-btn:active { transform: scale(0.96); transition: 0.1s; }
    </style>
</head>
<body class="p-4 italic">
    <div class="max-w-md mx-auto min-h-screen flex flex-col">
        <header class="py-6 border-b border-white/5 mb-6 flex justify-between items-center">
            <a href="/" class="text-xl font-black text-white italic tracking-tighter uppercase">PRO<span class="text-green-500">PREDICTOR</span></a>
            <div class="flex items-center gap-2">
                <span class="text-[8px] font-black uppercase text-zinc-500 tracking-widest">Live Engine</span>
                <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            </div>
        </header>
        {{content|safe}}
        
        <footer class="mt-auto py-10 text-center opacity-20">
            <p class="text-[8px] font-black uppercase tracking-[0.4em]">Powered by Poisson Quant Model v2.0</p>
        </footer>
    </div>
</body>
</html>
"""

# ==========================================
# 🏠 LANDING PAGE
# ==========================================
@app.route("/")
def landing():
    leagues = [
        ("EPL", "Premier League"),
        ("PD", "La Liga"),
        ("SA", "Serie A"),
        ("BL1", "Bundesliga")
    ]
    
    content = '<div class="py-10 text-center"><h2 class="text-3xl font-black text-white italic mb-10 uppercase tracking-tighter leading-tight">Elite Betting <br>Intelligence</h2>'
    
    for code, name in leagues:
        content += f'''
        <a href="/league/{code}" class="block glass p-8 rounded-[2.5rem] border border-white/5 mb-4 text-left shadow-2xl nav-btn">
            <p class="text-[9px] text-zinc-500 font-black mb-1 uppercase tracking-widest">{code} Competition</p>
            <p class="text-xl font-black text-white uppercase tracking-tight">{name}</p>
        </a>'''
        
    content += f'''
    <a href="/acca" class="mt-6 block p-5 rounded-3xl bg-green-500/10 border border-green-500/20 text-green-500 font-black uppercase text-[10px] tracking-widest nav-btn text-center">
        Go to ACCA Builder →
    </a>
    </div>'''
    
    return render_template_string(LAYOUT, content=content)

# ==========================================
# 📅 FIXTURE LIST (FILTERED)
# ==========================================
@app.route("/league/<code>")
def league_page(code):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers, timeout=10).json()
        all_m = r.get("results", []) if isinstance(r, dict) else []
    except:
        all_m = []

    # STRICT FILTERING LOGIC
    keywords = LEAGUE_KEYWORDS.get(code, [])
    matches = [m for m in all_m if any(key in m.get('event', {}).get('home_team', '').lower() for key in keywords)]

    content = f'<a href="/" class="text-zinc-600 text-[10px] font-black uppercase tracking-[0.3em] mb-10 block">← Back to Hub</a>'
    content += f'<h3 class="text-green-500 font-black uppercase text-2xl italic mb-10 tracking-tighter">{code} Fixtures</h3>'
    
    if not matches:
        content += '<div class="py-20 text-center opacity-20 font-black text-xs uppercase italic">No upcoming fixtures detected for this competition.</div>'
    else:
        for g in matches:
            event = g.get("event", {})
            h, a = event.get("home_team"), event.get("away_team")
            # Format time from ISO
            try:
                raw_time = event.get("start_time", "2024-01-01T00:00:00Z")
                time_obj = datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%SZ")
                formatted_time = time_obj.strftime("%H:%M")
            except:
                formatted_time = "TBA"

            content += f'''
            <a href="/match/{g["id"]}?h={h}&a={a}" class="flex justify-between items-center p-6 glass rounded-[2rem] mb-3 border border-white/5 shadow-xl nav-btn">
                <span class="text-[10px] font-black text-zinc-600 tracking-tighter">{formatted_time}</span>
                <span class="text-[11px] font-black text-white uppercase truncate px-4">{h} v {a}</span>
                <span class="text-green-500 font-black text-[9px] italic">ANALYZE →</span>
            </a>'''
            
    return render_template_string(LAYOUT, content=content)

# ==========================================
# 📊 ANALYSIS PAGE (POISSON ENGINE)
# ==========================================
@app.route("/match/<match_id>")
def match_display(match_id):
    h = request.args.get('h', 'Home')
    a = request.args.get('a', 'Away')
    
    # Run the Poisson engine (Simulating team strengths for this demonstration)
    # In a fully connected build, these would pull from a stats API or database
    res = match_predictor.analyze_match(2.1, 1.4, 0.9, 1.7)
    
    content = f'''
    <div class="text-center mb-10">
        <span class="bg-green-500/10 text-green-500 border border-green-500/20 px-6 py-2 rounded-full text-[9px] font-black uppercase tracking-[0.3em] italic">{res['tag']}</span>
        <h2 class="text-2xl font-black text-white uppercase mt-12 italic leading-tight tracking-tighter">{h} <br><span class="text-zinc-800 text-sm opacity-50 not-italic">VS</span><br> {a}</h2>
    </div>

    <div class="glass p-8 rounded-[3rem] border border-white/5 mb-4 shadow-2xl">
        <div class="flex justify-between items-start mb-4">
            <span class="text-[9px] font-black text-zinc-600 uppercase tracking-widest italic">🔵 Recommended</span>
            <span class="text-2xl font-black text-green-500 tracking-tighter">+{res['conf']}% Gap</span>
        </div>
        <h2 class="text-3xl font-black text-white uppercase tracking-tighter leading-none mb-6">{res['rec']['t']}</h2>
        <div class="flex justify-between items-center pt-6 border-t border-white/5">
            <div>
                <p class="text-[8px] text-zinc-600 uppercase font-black tracking-widest mb-1">Probability</p>
                <p class="text-3xl font-black text-white tracking-tighter italic">{res['rec']['p']}%</p>
            </div>
            <div class="text-right">
                <p class="text-[8px] text-zinc-600 uppercase font-black tracking-widest mb-1">Fair Odds</p>
                <p class="text-3xl font-black text-green-500 tracking-tighter italic">{res['rec']['o']}</p>
            </div>
        </div>
    </div>

    <div class="grid grid-cols-2 gap-3 mb-10">
        <div class="glass p-6 rounded-[2.2rem] border border-white/5">
            <span class="text-[8px] font-black text-blue-500 uppercase mb-2 block tracking-widest">🟢 Safe</span>
            <p class="text-[10px] font-black text-white uppercase mb-1 leading-tight">{res['safe']['t']}</p>
            <p class="text-xl font-black text-zinc-600 italic">{res['safe']['p']}%</p>
        </div>
        <div class="glass p-6 rounded-[2.2rem] border border-white/5">
            <span class="text-[8px] font-black text-red-500 uppercase mb-2 block tracking-widest">🔴 Risk</span>
            <p class="text-[10px] font-black text-white uppercase mb-1 leading-tight">{res['risk']['t']}</p>
            <p class="text-xl font-black text-zinc-600 italic">{res['risk']['p']}%</p>
        </div>
    </div>

    <div class="glass p-7 rounded-[2.5rem] mb-20 italic">
        <h3 class="text-[9px] font-black text-zinc-700 uppercase tracking-[0.4em] mb-8 text-center underline decoration-zinc-900 underline-offset-8">Poisson Model Insights</h3>
        <div class="flex justify-between items-center text-[10px] font-black uppercase mb-6 tracking-tighter leading-none">
            <span class="text-zinc-500 italic">Expected Goals (xG)</span>
            <span class="text-white font-black">{res['xg']['h']} - {res['xg']['a']}</span>
        </div>
        <div class="flex justify-between items-center text-[10px] font-black uppercase mb-4 tracking-tighter leading-none">
            <span class="text-zinc-500 italic">Win Probability Spread</span>
            <span class="text-white font-black">{res['probs']['home']}% | {res['probs']['draw']}% | {res['probs']['away']}%</span>
        </div>
    </div>
    
    <a href="javascript:history.back()" class="block text-center text-zinc-700 text-[10px] font-black uppercase tracking-widest mt-10">← Back to Fixtures</a>
    '''
    return render_template_string(LAYOUT, content=content)

# ==========================================
# ACCA BUILDER
# ==========================================
@app.route("/acca")
def acca():
    return render_template_string(LAYOUT, content='<div class="py-40 text-center opacity-30 font-black uppercase tracking-[0.5em] text-xs leading-loose italic">ACCA Builder <br>Optimizing Data Portfolio...</div>')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
