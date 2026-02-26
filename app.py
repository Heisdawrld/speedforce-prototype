from flask import Flask, render_template_string, request
import requests
import os
from datetime import datetime, timedelta
from match_predictor import API_KEY, BASE_URL, get_match_analysis

app = Flask(__name__)

LAYOUT = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#05070a] text-zinc-300 font-sans italic p-4 md:p-10 selection:bg-green-500/30">
    <div class="max-w-4xl mx-auto flex justify-between items-center mb-10 border-b border-white/5 pb-6 uppercase font-black">
        <h1 class="text-2xl text-white italic tracking-tighter uppercase">PRO <span class="text-green-500">PREDICTOR</span></h1>
        <div class="flex gap-4 text-[10px] text-zinc-500 tracking-widest"><a href="/">HUB</a> <a href="/acca">ACCA HUB</a></div>
    </div>
    <div class="max-w-4xl mx-auto">{{ content | safe }}</div>
</body>
"""

def get_badge(name):
    return f"https://api.dicebear.com/7.x/initials/svg?seed={name}&backgroundColor=10141d&bold=true"

@app.route("/")
def home():
    # Wider range to ensure matches are found
    s_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    e_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
    
    params = {'met': 'Fixtures', 'APIkey': API_KEY, 'from': s_date, 'to': e_date}
    try:
        r = requests.get(BASE_URL, params=params).json()
        matches = r.get('result', [])
    except: matches = []
    
    content = '<h2 class="text-green-500 text-[10px] font-black tracking-[0.4em] mb-8 uppercase text-center italic">ELITE DATA STREAM</h2>'
    if not matches:
        content += '<div class="text-center py-20 text-zinc-700 font-black uppercase tracking-widest">No Fixtures Found</div>'
    
    for m in matches:
        m_id = str(m.get('event_key'))
        h_t, a_t = m.get('event_home_team'), m.get('event_away_team')
        h_l, a_l = m.get('home_team_logo', ''), m.get('away_team_logo', '')
        content += f'''
        <a href="/match?id={m_id}" class="flex justify-between items-center p-6 bg-[#0f1218] rounded-2xl mb-3 border border-white/5 hover:border-green-500/30 transition shadow-xl">
            <div class="w-2/5 flex items-center justify-end gap-3 font-bold text-white text-xs uppercase text-right"><span class="truncate">{h_t}</span><img src="{h_l if h_l else get_badge(h_t)}" class="w-7 h-7 object-contain"></div>
            <div class="text-[8px] text-zinc-900 font-black italic px-4 uppercase">ANALYZE</div>
            <div class="w-2/5 flex items-center justify-start gap-3 font-bold text-white text-xs uppercase"><img src="{a_l if a_l else get_badge(a_t)}" class="w-7 h-7 object-contain"><span class="truncate">{a_t}</span></div>
        </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match")
def match():
    res = get_match_analysis(request.args.get("id"))
    if "error" in res:
        return render_template_string(LAYOUT, content='<div class="text-center mt-20 font-black text-zinc-600 uppercase">Analysis Not Available Yet</div>')
    
    content = f'''
    <div class="mb-6"><a href="/" class="text-zinc-600 font-bold text-[10px] uppercase tracking-widest">← RETURN</a></div>
    <div class="flex justify-center items-center gap-10 mb-10">
        <div class="text-center"><img src="{res['h_logo'] if res['h_logo'] else get_badge(res['h_name'])}" class="w-16 h-16 object-contain mb-2"><p class="text-[9px] font-black text-zinc-500 uppercase">{res['h_name']}</p></div>
        <div class="text-zinc-800 font-black italic text-2xl uppercase opacity-20 tracking-tighter">VS</div>
        <div class="text-center"><img src="{res['a_logo'] if res['a_logo'] else get_badge(res['a_name'])}" class="w-16 h-16 object-contain mb-2"><p class="text-[9px] font-black text-zinc-500 uppercase">{res['a_name']}</p></div>
    </div>
    <div class="text-center mb-8"><span class="bg-green-500/10 text-green-500 border border-green-500/20 px-4 py-1 rounded-full text-[9px] font-black tracking-[0.3em] uppercase italic">{res['tag']}</span></div>

    <div class="bg-gradient-to-br from-[#10141d] to-[#07090e] p-8 rounded-[2.5rem] border border-white/5 mb-6 shadow-2xl relative overflow-hidden">
        <div class="flex justify-between items-start mb-4">
            <span class="text-[9px] font-black text-zinc-500 tracking-widest uppercase italic">🔵 Recommended Tip</span>
            <span class="text-4xl font-black text-green-500 italic tracking-tighter">{res['rec']['p']:.0f}%</span>
        </div>
        <h2 class="text-3xl font-black text-white italic uppercase tracking-tighter mb-4 leading-none">{res['rec']['t']}</h2>
        <ul class="space-y-2 border-t border-white/5 pt-4">
            {"".join([f'<li class="text-[10px] text-zinc-400 font-bold italic uppercase flex items-center gap-2"><span class="w-1 h-1 bg-green-500 rounded-full"></span>{r}</li>' for r in res['rec']['r']])}
        </ul>
    </div>

    <div class="grid grid-cols-2 gap-4 mb-10">
        <div class="bg-[#0f1218] p-6 rounded-[2rem] border border-white/5 shadow-lg text-center">
            <span class="text-[8px] text-zinc-600 font-black uppercase block mb-2 italic">🟢 Alternate (Safest)</span>
            <h4 class="text-sm font-black text-white italic uppercase mb-1">{res['alt']['t']}</h4>
            <p class="text-2xl font-black text-white italic opacity-40">{res['alt']['p']:.0f}%</p>
        </div>
        <div class="bg-[#0f1218] p-6 rounded-[2rem] border border-white/5 shadow-lg text-center">
            <span class="text-[8px] text-zinc-600 font-black uppercase block mb-2 italic">🔴 High Risk</span>
            <h4 class="text-sm font-black text-red-500 italic uppercase mb-1">{res['risk']['t']}</h4>
            <p class="text-2xl font-black text-red-500 italic opacity-40">{res['risk']['p']:.0f}%</p>
        </div>
    </div>

    <div class="bg-black/20 p-8 rounded-[2.5rem] border border-white/5 mb-20 shadow-inner">
        <h3 class="text-[10px] font-black text-zinc-700 uppercase tracking-[0.4em] mb-8 text-center italic underline decoration-zinc-800">Match Insights & Form</h3>
        <div class="grid grid-cols-2 gap-10 mb-10 text-center border-b border-white/5 pb-8">
            <div><p class="text-[8px] text-zinc-600 font-black uppercase mb-2">Avg Goals</p><p class="text-xl font-black text-white">{res['stats']['h_avg']} vs {res['stats']['a_avg']}</p></div>
            <div><p class="text-[8px] text-zinc-600 font-black uppercase mb-2">Volatility</p><p class="text-xl font-black text-yellow-500">{res['vol']}</p></div>
        </div>
        <div class="space-y-4">
            <div class="flex justify-between items-center text-[9px] font-black uppercase tracking-widest"><span class="text-zinc-500 italic">Home Form</span><div class="flex gap-1">{"".join([f'<span class="w-5 h-5 rounded flex items-center justify-center {"bg-green-500 text-black" if f=="W" else "bg-red-500/20 text-red-500" if f=="L" else "bg-zinc-800 text-zinc-500"}">{f}</span>' for f in res['h_form']])}</div></div>
            <div class="flex justify-between items-center text-[9px] font-black uppercase tracking-widest"><span class="text-zinc-500 italic">Away Form</span><div class="flex gap-1">{"".join([f'<span class="w-5 h-5 rounded flex items-center justify-center {"bg-green-500 text-black" if f=="W" else "bg-red-500/20 text-red-500" if f=="L" else "bg-zinc-800 text-zinc-500"}">{f}</span>' for f in res['a_form']])}</div></div>
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
