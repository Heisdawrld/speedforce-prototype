from flask import Flask, render_template_string, request, redirect, url_for
import match_predictor
import os

app = Flask(__name__)

THEME = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#05070a] text-zinc-300 font-sans italic p-4">
    <div class="max-w-md mx-auto min-h-screen">
        <header class="flex justify-between items-center py-6 mb-6">
            <h1 class="text-xl font-black text-white italic tracking-tighter uppercase">PRO<span class="text-green-500">PREDICTOR</span></h1>
            <a href="/acca" class="bg-green-500/10 text-green-500 px-3 py-1.5 rounded-full text-[9px] font-black uppercase border border-green-500/20">ACCA Hub</a>
        </header>
        {{ content | safe }}
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    content = '<div class="py-20 text-center"><h2 class="text-3xl font-black text-white italic mb-10 uppercase tracking-tighter">Match Intelligence</h2><a href="/leagues" class="bg-white text-black px-12 py-5 rounded-full font-black uppercase text-xs tracking-widest shadow-xl">Enter App</a></div>'
    return render_template_string(THEME, content=content)

@app.route("/leagues")
def leagues():
    leagues = [("PL", "Premier League"), ("PD", "La Liga"), ("SA", "Serie A"), ("BL1", "Bundesliga"), ("FL1", "Ligue 1")]
    cards = "".join([f'<a href="/fixtures?league={id}" class="bg-white/5 p-6 rounded-3xl border border-white/5 mb-3 flex justify-between items-center"><span class="text-xs font-black uppercase tracking-tight">{name}</span><span class="text-green-500">→</span></a>' for id, name in leagues])
    return render_template_string(THEME, content=f'<div class="space-y-4"><h3 class="text-white text-xs font-black uppercase mb-6 tracking-widest">Select League</h3>{cards}</div>')

@app.route("/fixtures")
def fixtures():
    l_id = request.args.get('league')
    all_m = match_predictor.get_all_fixtures()
    matches = [m for m in all_m if m['competition']['code'] == l_id]
    
    output = f'<a href="/leagues" class="text-zinc-600 text-[10px] uppercase font-black mb-8 block tracking-widest">← Back</a>'
    if not matches:
        output += '<p class="text-center opacity-20 py-10 uppercase font-black text-[10px]">No Fixtures Found</p>'
    else:
        for m in matches:
            t = m['utcDate'][11:16]
            output += f'''
            <a href="/analysis?h={m['homeTeam']['name']}&a={m['awayTeam']['name']}&l={l_id}&t={t}" class="flex items-center justify-between p-5 bg-white/5 rounded-2xl mb-2 border border-white/5 font-black uppercase text-[10px] tracking-tight">
                <span class="text-zinc-600">{t}</span><span class="text-white truncate px-4">{m['homeTeam']['name']} v {m['awayTeam']['name']}</span><span class="text-green-500">→</span>
            </a>'''
    return render_template_string(THEME, content=output)

@app.route("/analysis")
def analysis():
    h, a, l, t = request.args.get('h'), request.args.get('a'), request.args.get('l'), request.args.get('t')
    all_preds = match_predictor.get_bzzoiro_predictions()
    res = match_predictor.get_match_analysis(h, a, l, all_preds)
    
    content = f'''
    <div class="text-center mb-10">
        <span class="bg-green-500/10 text-green-500 border border-green-500/20 px-4 py-1.5 rounded-full text-[9px] font-black uppercase tracking-[0.3em]">{res['tag']}</span>
        <div class="flex justify-between items-center mt-12 font-black uppercase text-[10px] tracking-tight px-4">
            <div class="w-1/3"><div class="w-14 h-14 bg-white/5 rounded-full mx-auto mb-3 flex items-center justify-center italic">{h[0]}</div>{h}</div>
            <div class="opacity-10 text-2xl italic font-black">VS</div>
            <div class="w-1/3"><div class="w-14 h-14 bg-white/5 rounded-full mx-auto mb-3 flex items-center justify-center italic">{a[0]}</div>{a}</div>
        </div>
    </div>
    <div class="bg-white/5 p-8 rounded-[2.5rem] border border-white/5 mb-6 italic shadow-2xl border-t border-white/10">
        <span class="text-[8px] font-black text-zinc-600 uppercase tracking-widest">🔵 Recommended</span>
        <h2 class="text-2xl font-black text-white uppercase tracking-tighter mt-3 leading-none">{res['rec']['t']}</h2>
        <p class="text-4xl font-black text-green-500 mt-4 tracking-tighter italic">+{res['rec']['p']}%</p>
    </div>
    <a href="javascript:history.back()" class="block text-center text-zinc-700 text-[10px] font-black uppercase tracking-widest mt-10 italic">Close Analysis</a>
    '''
    return render_template_string(THEME, content=content)

@app.route("/acca")
def acca():
    all_m = match_predictor.get_all_fixtures()
    all_p = match_predictor.get_bzzoiro_predictions()
    pool = []
    for f in all_m[:15]:
        res = match_predictor.get_match_analysis(f['homeTeam']['name'], f['awayTeam']['name'], f['competition']['name'], all_p)
        pool.append({"m": f"{f['homeTeam']['name']} v {f['awayTeam']['name']}", "t": res['rec']['t'], "o": res['rec']['o'], "e": res['rec']['e']})
    
    picks = sorted(pool, key=lambda x: x['e'], reverse=True)[:4]
    picks_html = "".join([f'<div class="p-5 bg-white/5 rounded-3xl mb-3 flex justify-between text-[10px] font-black uppercase italic tracking-tight"><span>{p["m"]}</span><span class="text-green-500">{p["o"]}</span></div>' for p in picks])
    
    # DEBUG FLOW
    debug = f'<div class="mt-20 p-4 border border-white/5 rounded-2xl text-[8px] text-zinc-800 font-mono tracking-widest uppercase">Flow: Fixtures({len(all_m)}) | Predictions({len(all_p)})</div>'
    
    return render_template_string(THEME, content=f'<div class="text-center"><h2 class="text-white text-2xl font-black mb-10 italic uppercase tracking-tighter">ACCA Optimizer</h2>{picks_html}{debug}</div>')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
