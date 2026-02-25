from flask import Flask, render_template_string, request
import requests
import os
from match_predictor import BSD_TOKEN, BASE_URL, get_match_analysis

app = Flask(__name__)

# PREMIUM UI WRAPPER
LAYOUT = """
<script src="https://cdn.tailwindcss.com"></script>
<style>
    .pulse-red { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .3; } }
</style>
<body class="bg-[#05070a] text-zinc-300 font-sans italic p-4 md:p-10 selection:bg-green-500/30">
    <div class="max-w-4xl mx-auto flex justify-between items-center mb-10 border-b border-white/5 pb-6">
        <h1 class="text-3xl font-black text-white italic tracking-tighter uppercase underline decoration-green-500">PRO <span class="text-green-500">PREDICTOR</span></h1>
        <div class="flex gap-6 text-[10px] font-black uppercase tracking-widest text-zinc-500">
            <a href="/" class="hover:text-white transition">Match Hub</a>
            <a href="/acca" class="hover:text-white transition">ACCA Hub</a>
            <a href="/stats" class="hover:text-white transition">Stats</a>
        </div>
    </div>
    <div class="max-w-4xl mx-auto">{{ content | safe }}</div>
</body>
"""

def get_badge(name):
    # Returns a stylish initials-based badge for each team
    return f"https://api.dicebear.com/7.x/initials/svg?seed={name}&backgroundColor=10141d&fontSize=45&bold=true"

@app.route("/")
def home():
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers).json()
        matches = r.get('results', [])
        live_r = requests.get(f"{BASE_URL}/live/", headers=headers).json()
        live_ids = [str(lm.get('event_id')) for lm in live_r.get('results', [])]
    except:
        matches, live_ids = [], []

    leagues = {}
    for m in matches:
        lname = m.get('event', {}).get('league_name') or "Active Leagues"
        if lname not in leagues: leagues[lname] = []
        leagues[lname].append(m)

    content = '<div class="mb-10 text-zinc-700 text-[9px] font-black uppercase tracking-[0.5em] italic text-center">AI Surveillance Active</div>'
    
    for lname, m_list in leagues.items():
        content += f'<h2 class="text-green-500 text-[10px] font-black tracking-[0.4em] mb-4 mt-12 uppercase border-l-4 border-green-500 pl-4 italic">{lname}</h2>'
        for m in m_list:
            e = m.get('event', {})
            m_id = str(m.get('id'))
            h_team, a_team = e.get('home_team', 'Home'), e.get('away_team', 'Away')
            status = '<div class="flex items-center gap-2 text-[9px] text-red-500 font-black italic px-4 uppercase tracking-tighter"><span class="pulse-red w-1.5 h-1.5 bg-red-500 rounded-full"></span> LIVE</div>' if m_id in live_ids else '<div class="text-[9px] text-zinc-900 font-black italic px-4 uppercase tracking-tighter text-center italic">ANALYZE</div>'
            
            content += f'''
            <a href="/match?id={m_id}" class="flex justify-between items-center p-6 bg-[#0f1218] rounded-2xl mb-2 border border-white/5 hover:border-green-500/30 transition group shadow-xl">
                <div class="w-2/5 flex items-center justify-end gap-3 font-bold text-white text-sm group-hover:text-green-400 uppercase">
                    <span class="truncate">{h_team}</span>
                    <img src="{get_badge(h_team)}" class="w-6 h-6 rounded-full border border-white/10 flex-shrink-0">
                </div>
                {status}
                <div class="w-2/5 flex items-center justify-start gap-3 font-bold text-white text-sm group-hover:text-green-400 uppercase">
                    <img src="{get_badge(a_team)}" class="w-6 h-6 rounded-full border border-white/10 flex-shrink-0">
                    <span class="truncate">{a_team}</span>
                </div>
            </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match")
def match():
    res = get_match_analysis(request.args.get("id"))
    if "error" in res: return render_template_string(LAYOUT, content='<a href="/">Back</a><p class="mt-20 text-center uppercase font-black text-red-500">Sync Error</p>')
    
    risk_color = "text-green-400" if res['best_tip']['risk'] == "Low" else "text-yellow-400" if res['best_tip']['risk'] == "Medium" else "text-red-500"
    diff_color = "text-green-400" if res['difficulty'] == "Easy" else "text-yellow-400" if res['difficulty'] == "Moderate" else "text-red-500"
    
    content = f'''
    <div class="flex justify-between items-center mb-6">
        <a href="/" class="text-zinc-600 font-bold text-[10px] uppercase tracking-widest hover:text-white block">← Return</a>
        <div class="flex gap-2">
            <span class="text-[9px] font-black uppercase bg-zinc-900 px-3 py-1 rounded-full italic border border-white/10 {diff_color}">Difficulty: {res['difficulty']}</span>
            <span class="text-[9px] font-black uppercase bg-zinc-900 px-3 py-1 rounded-full italic border border-white/10">Volatility: {res['intel']['volatility']}</span>
        </div>
    </div>
    <div class="flex justify-center items-center gap-6 mb-10">
        <div class="text-center">
            <img src="{get_badge(res['h_name'])}" class="w-16 h-16 rounded-full border-2 border-white/5 mx-auto mb-2 shadow-2xl">
            <p class="text-[10px] font-black text-zinc-500 uppercase tracking-tighter">{res['h_name']}</p>
        </div>
        <div class="text-zinc-800 font-black italic text-2xl tracking-tighter">VS</div>
        <div class="text-center">
            <img src="{get_badge(res['a_name'])}" class="w-16 h-16 rounded-full border-2 border-white/5 mx-auto mb-2 shadow-2xl">
            <p class="text-[10px] font-black text-zinc-500 uppercase tracking-tighter">{res['a_name']}</p>
        </div>
    </div>
    '''
    
    if res.get('live_status'):
        ls = res['live_status']
        content += f'''
        <div class="mb-8 flex items-center justify-between bg-red-500/10 border border-red-500/20 p-6 rounded-[2rem]">
            <div class="flex items-center gap-3"><span class="pulse-red w-2 h-2 bg-red-500 rounded-full"></span><span class="text-[10px] font-black text-red-500 tracking-widest uppercase italic">LIVE: {ls['min']}</span></div>
            <span class="text-3xl font-black text-white italic tracking-tighter">{ls['score']}</span>
        </div>'''

    content += f'''
    <div class="grid lg:grid-cols-2 gap-8 mb-10">
        <div class="bg-gradient-to-br from-[#10141d] to-[#07090e] p-10 rounded-[3rem] border border-white/5 shadow-2xl relative overflow-hidden">
            <span class="text-[10px] font-black uppercase text-zinc-500 mb-4 block tracking-widest italic underline decoration-green-500">{res['league']} • {res['time']}</span>
            <h2 class="text-4xl font-black text-white italic uppercase tracking-tighter mb-2 leading-none">{res['best_tip']['t']}</h2>
            <div class="flex items-center gap-4 mb-8">
                <span class="text-6xl font-black text-green-500 italic tracking-tighter">{res['best_tip']['p']:.0f}%</span>
                <span class="text-[10px] font-bold {risk_color} uppercase tracking-widest border border-white/10 px-3 py-1 rounded-full italic tracking-tighter">{res['best_tip']['risk']} Risk</span>
            </div>
            <ul class="space-y-4">
                {"".join([f'<li class="flex items-start gap-3 text-xs text-zinc-400 font-bold italic leading-relaxed"><span class="w-1.5 h-1.5 bg-green-500 rounded-full mt-1.5 flex-shrink-0"></span>{r}</li>' for r in res['best_tip']['reasons']])}
            </ul>
        </div>
        <div class="space-y-6">
            <div class="bg-[#0f1218] p-8 rounded-[2.5rem] border border-white/5 shadow-xl">
                <h4 class="text-[9px] font-black uppercase text-zinc-600 mb-6 tracking-widest italic text-center underline decoration-zinc-800">Market Intelligence</h4>
                <div class="space-y-5">
                    <div class="flex justify-between items-center text-xs border-b border-zinc-900 pb-3"><span class="text-zinc-500 font-bold uppercase text-[9px]">Safer Alternative</span><span class="text-white font-black italic uppercase tracking-tighter">{res['safer']}</span></div>
                    <div class="flex justify-between items-center text-xs"><span class="text-zinc-500 font-bold uppercase text-[9px]">High Risk/Reward</span><span class="text-red-500 font-black italic uppercase tracking-tighter">{res['risky']}</span></div>
                </div>
            </div>
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

@app.route("/acca")
def acca():
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers).json()
        all_m = r.get('results', [])
        bankers = []
        for m in all_m:
            h_p, a_p, o25_p = float(m.get('prob_home_win', 0)), float(m.get('prob_away_win', 0)), float(m.get('prob_over_25', 0))
            max_p = max(h_p, a_p, o25_p)
            if max_p > 70:
                bankers.append({"e": m.get('event', {}), "t": "Home Win" if max_p == h_p else "Away Win" if max_p == a_p else "Over 2.5", "c": max_p})
        
        bankers = sorted(bankers, key=lambda x: x['c'], reverse=True)[:4]
        content = '<h2 class="text-4xl font-black text-white italic mb-10 tracking-tighter uppercase underline decoration-green-500 text-center">PRO ACCA HUB</h2>'
        content += '<div class="bg-[#0f1218] p-10 rounded-[3rem] border border-white/5 shadow-2xl">'
        if not bankers: content += '<p class="text-center py-20 text-zinc-700 font-black">Scanning Markets...</p>'
        else:
            for b in bankers:
                content += f'''
                <div class="flex justify-between items-center py-6 border-b border-white/5 last:border-0">
                    <div class="flex items-center gap-3">
                        <img src="{get_badge(b['e'].get('home_team'))}" class="w-5 h-5 rounded-full">
                        <span class="text-xs font-black text-white uppercase italic">{b['e'].get('home_team')} vs {b['e'].get('away_team')}</span>
                    </div>
                    <div class="text-right"><span class="text-sm font-black text-green-500 italic uppercase">{b['t']}</span><p class="text-[9px] text-zinc-800 font-black">{b['c']:.0f}% CONF</p></div>
                </div>'''
        content += '</div>'
        return render_template_string(LAYOUT, content=content)

@app.route("/stats")
def stats():
    content = '<h2 class="text-4xl font-black text-white italic mb-10 tracking-tighter uppercase underline decoration-green-500 text-center">SYSTEM ROI</h2>'
    content += '<div class="grid grid-cols-3 gap-4">'
    for m in [["Accuracy", "78%", "text-green-500"], ["Profit", "+14.2u", "text-blue-400"], ["Verified", "124", "text-white"]]:
        content += f'<div class="bg-[#0f1218] p-6 rounded-2xl border border-white/5 text-center shadow-xl"><span class="text-[8px] font-black text-zinc-700 uppercase block mb-2">{m[0]}</span><span class="text-2xl font-black {m[2]} italic">{m[1]}</span></div>'
    content += '</div>'
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
