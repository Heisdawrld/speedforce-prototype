from flask import Flask, render_template_string, request, redirect, url_for
import match_predictor
import os

app = Flask(__name__)

THEME = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#05070a] text-zinc-300 font-sans italic p-4">
    <div class="max-w-md mx-auto min-h-screen">
        <header class="flex justify-between items-center py-6 border-b border-white/5 mb-6">
            <h1 class="text-xl font-black text-white italic uppercase tracking-tighter">PRO<span class="text-green-500">PREDICTOR</span></h1>
            <a href="/acca" class="bg-green-500/10 text-green-500 px-3 py-1.5 rounded-full text-[9px] font-black uppercase">ACCA Hub</a>
        </header>
        {{ content | safe }}
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    content = '<div class="py-20 text-center"><h2 class="text-3xl font-black text-white italic mb-10 uppercase">Match Intelligence</h2><a href="/leagues" class="bg-white text-black px-12 py-5 rounded-full font-black uppercase text-xs">Enter Hub</a></div>'
    return render_template_string(THEME, content=content)

@app.route("/leagues")
def leagues():
    leagues = [("PL", "Premier League"), ("PD", "La Liga"), ("SA", "Serie A"), ("BL1", "Bundesliga"), ("FL1", "Ligue 1")]
    cards = "".join([f'<a href="/fixtures?league={id}" class="bg-white/5 p-6 rounded-3xl border border-white/5 mb-3 flex justify-between items-center"><span class="text-xs font-black uppercase">{name}</span><span class="text-green-500">→</span></a>' for id, name in leagues])
    return render_template_string(THEME, content=f'<div class="space-y-4"><h3 class="text-white text-xs font-black uppercase mb-6">Select League</h3>{cards}</div>')

@app.route("/fixtures")
def fixtures():
    l_id = request.args.get('league')
    all_m = match_predictor.get_all_fixtures()
    matches = [m for m in all_m if m.get('competition', {}).get('code') == l_id]
    
    output = f'<a href="/leagues" class="text-zinc-600 text-[10px] uppercase font-black mb-8 block">← Back</a>'
    if not matches:
        output += '<p class="text-center opacity-20 py-10 uppercase font-black text-[10px]">No Fixtures Found</p>'
    else:
        for m in matches:
            t = m['utcDate'][11:16]
            output += f'''
            <a href="/analysis?h={m['homeTeam']['name']}&a={m['awayTeam']['name']}&l={l_id}&t={t}" class="flex items-center justify-between p-5 bg-white/5 rounded-2xl mb-2 border border-white/5 font-black uppercase text-[10px]">
                <span class="text-zinc-600">{t}</span><span class="text-white truncate px-4">{m['homeTeam']['name']} v {m['awayTeam']['name']}</span><span class="text-green-500">→</span>
            </a>'''
    return render_template_string(THEME, content=output)

@app.route("/analysis")
def analysis():
    h, a, l, t = request.args.get('h'), request.args.get('a'), request.args.get('l'), request.args.get('t')
    all_p = match_predictor.get_bzzoiro_predictions()
    res = match_predictor.get_match_analysis(h, a, l, all_p)
    return render_template_string(THEME, content=f'<div class="text-center italic font-black uppercase"><p class="text-green-500 mb-10 text-[9px]">{res["tag"]}</p><h2 class="text-white text-2xl mb-4 leading-none">{res["rec"]["t"]}</h2><p class="text-5xl text-white">+{res["rec"]["p"]}%</p><p class="mt-10 text-zinc-600 text-[10px]">Estimated Odds: {res["rec"]["o"]}</p></div>')

@app.route("/acca")
def acca():
    all_m = match_predictor.get_all_fixtures()
    all_p = match_predictor.get_bzzoiro_predictions()
    pool = []
    for f in all_m[:15]:
        try:
            res = match_predictor.get_match_analysis(f['homeTeam']['name'], f['awayTeam']['name'], f['competition']['name'], all_p)
            pool.append({"m": f"{f['homeTeam']['name']} v {f['awayTeam']['name']}", "t": res['rec']['t'], "o": res['rec']['o'], "e": res['rec']['e']})
        except: continue
    
    picks = sorted(pool, key=lambda x: x['e'], reverse=True)[:4]
    picks_html = "".join([f'<div class="p-5 bg-white/5 rounded-3xl mb-3 flex justify-between text-[10px] font-black uppercase italic"><span>{p["m"]}</span><span class="text-green-500">{p["o"]}</span></div>' for p in picks])
    debug = f'<div class="mt-20 p-4 border border-white/5 rounded-2xl text-[8px] text-zinc-800 font-mono">FLOW: Fx({len(all_m)}) | Pr({len(all_p)})</div>'
    return render_template_string(THEME, content=f'<div class="text-center"><h2 class="text-white text-2xl font-black mb-10 italic uppercase tracking-tighter">ACCA Optimizer</h2>{picks_html}{debug}</div>')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
