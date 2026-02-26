from flask import Flask, render_template_string, request
import requests
from datetime import datetime
import match_predictor
import os

app = Flask(__name__)
BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL = "https://sports.bzzoiro.com/api/predictions/"

# MAPPING API CODES TO YOUR CATEGORIES
LEAGUE_IDS = {
    "EPL": [1, 1630], # Premier League IDs
    "ELC": [2, 1631], # Championship IDs
    "PD": [3, 1632],  # La Liga
    "SA": [4, 1633],  # Serie A
}

LAYOUT = """ [YOUR PREVIOUS GLASS UI HTML HERE] """

@app.route("/")
def landing():
    leagues = [("EPL", "Premier League"), ("ELC", "Championship"), ("PD", "La Liga"), ("SA", "Serie A")]
    content = '<div class="py-10 text-center"><h2 class="text-3xl font-black text-white italic mb-10 uppercase">Live Intelligence</h2>'
    for code, name in leagues:
        content += f'<a href="/league/{code}" class="block glass p-8 rounded-[2rem] border border-white/5 mb-4 text-left shadow-2xl"> <p class="text-[9px] text-zinc-500 font-black mb-1 uppercase tracking-widest">{code}</p> <p class="text-xl font-black text-white uppercase">{name}</p></a>'
    return render_template_string(LAYOUT, content=content)

@app.route("/league/<code>")
def league_page(code):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    r = requests.get(BASE_URL, headers=headers).json()
    all_results = r.get("results", [])
    
    # FILTER BY REAL API LEAGUE ID (Separates EPL from Championship)
    target_ids = LEAGUE_IDS.get(code, [])
    matches = [m for m in all_results if m.get('league_id') in target_ids or code in str(m.get('league_name'))]

    content = f'<a href="/" class="text-zinc-600 text-[10px] font-black uppercase mb-10 block">← Hub</a>'
    for g in matches:
        event = g.get("event", {})
        # REAL TIME PARSING
        raw_time = event.get("start_time", "2024-01-01T00:00:00Z")
        dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        f_date = dt.strftime("%d %b")
        f_time = dt.strftime("%H:%M")

        content += f'''
        <a href="/match/{g["id"]}" class="flex justify-between items-center p-6 glass rounded-[2rem] mb-3 border border-white/5 shadow-xl">
            <div class="flex flex-col"><span class="text-[8px] font-black text-zinc-600 uppercase">{f_date}</span><span class="text-[10px] font-black text-zinc-400">{f_time}</span></div>
            <span class="text-[11px] font-black text-white uppercase truncate px-4">{event.get("home_team")} v {event.get("away_team")}</span>
            <span class="text-green-500 font-black text-[9px]">VIEW →</span>
        </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match/<match_id>")
def match_display(match_id):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    data = requests.get(f"{BASE_URL}{match_id}/", headers=headers).json()
    res = match_predictor.analyze_match(data)
    
    # [YOUR DETAILED ANALYSIS HTML HERE - USING res['rec'], res['probs'], etc]
    return render_template_string(LAYOUT, content=f"Match analysis for {match_id}")

@app.route("/acca")
def acca():
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    r = requests.get(BASE_URL, headers=headers).json()
    results = sorted(r.get("results", []), key=lambda x: x.get('prob_home', 0), reverse=True)[:4]
    
    picks = ""
    total_odds = 1.0
    for p in results:
        odds = round((1 / p.get('prob_home', 0.5)) * 0.9, 2)
        total_odds *= odds
        picks += f'<div class="p-4 glass rounded-2xl mb-2 flex justify-between"><span>{p["event"]["home_team"]}</span><span class="text-green-500">{odds}</span></div>'
    
    content = f'<div class="text-center"><h2 class="text-white font-black mb-10">LIVE ACCA</h2>{picks}<div class="mt-10 p-6 glass rounded-3xl border border-green-500/20"><p class="text-xs uppercase text-zinc-500">Total Odds</p><p class="text-4xl font-black text-green-500">{round(total_odds, 2)}</p></div></div>'
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
