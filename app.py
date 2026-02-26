from flask import Flask, render_template_string, request, redirect, url_for
import match_predictor
import os

app = Flask(__name__)

LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; -webkit-font-smoothing: antialiased; }
        .glass { background: rgba(15, 18, 24, 0.85); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,0.05); }
        .btn-active:active { transform: scale(0.96); opacity: 0.9; }
    </style>
</head>
<body class="p-4 italic">
    <div class="max-w-md mx-auto min-h-screen flex flex-col">
        <header class="flex justify-between items-center py-6 mb-4 border-b border-white/5">
            <h1 class="text-xl font-black tracking-tighter text-white uppercase italic">PRO<span class="text-green-500">PREDICTOR</span></h1>
            <div class="flex items-center gap-2">
                <a href="/acca" class="text-[9px] font-black bg-zinc-900 border border-white/5 text-zinc-400 px-3 py-1.5 rounded-full uppercase">ACCA Builder</a>
                <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            </div>
        </header>
        {{ content | safe }}
    </div>
</body>
</html>
"""

@app.route("/")
def hub():
    try:
        matches = match_predictor.get_fixtures()
        
        if not matches:
            return render_template_string(LAYOUT, content='<div class="text-center py-20 opacity-30 text-[10px] font-black uppercase">Syncing Live Fixtures...</div>')

        idx = int(request.args.get('i', 0))
        idx = max(0, min(idx, len(matches) - 1))
        
        m = matches[idx]
        match_name = f"{m['homeTeam']['name']} {m['awayTeam']['name']}"
        analysis = match_predictor.get_structured_analysis(match_name, m['id'])

        content = f'''
        <div class="flex justify-between items-center mb-6">
            <span class="text-[9px] font-black text-zinc-600 uppercase tracking-widest">{m['competition']['name']}</span>
            <span class="text-[9px] font-black text-white bg-zinc-900 border border-white/10 px-2 py-1 rounded-md">{m['utcDate'][11:16]} GMT</span>
        </div>

        <div class="flex justify-around items-center mb-10">
            <div class="text-center w-1/3">
                <div class="w-14 h-14 glass rounded-2xl mx-auto mb-3 flex items-center justify-center text-xl font-black text-white">{m['homeTeam']['name'][0]}</div>
                <p class="text-[9px] font-black uppercase text-zinc-400 leading-tight">{m['homeTeam']['name']}</p>
            </div>
            <div class="text-xl font-black text-zinc-800 opacity-30 italic">VS</div>
            <div class="text-center w-1/3">
                <div class="w-14 h-14 glass rounded-2xl mx-auto mb-3 flex items-center justify-center text-xl font-black text-white">{m['awayTeam']['name'][0]}</div>
                <p class="text-[9px] font-black uppercase text-zinc-400 leading-tight">{m['awayTeam']['name']}</p>
            </div>
        </div>

        <div class="text-center mb-8">
            <span class="px-5 py-1.5 rounded-full bg-green-500/10 text-green-500 text-[8px] font-black uppercase tracking-[0.3em] border border-green-500/20">{analysis.get('tag', 'BALANCED')}</span>
        </div>

        <div class="glass p-6 rounded-[2.5rem] mb-4 shadow-2xl border-t border-white/10">
            <span class="text-[8px] font-black text-zinc-600 uppercase block mb-2 tracking-widest italic">🔵 Recommended Tip</span>
            <h2 class="text-2xl font-black text-white uppercase tracking-tighter mb-4 leading-none">{analysis['rec']['t']}</h2>
            <p class="text-3xl font-black text-green-500">+{analysis['rec']['p']}%</p>
        </div>

        <div class="mt-auto flex gap-3 pb-10">
            <a href="/?i={idx-1}" class="w-1/3 glass py-5 rounded-3xl text-center text-[9px] font-black uppercase text-zinc-600 btn-active border border-white/5">Prev</a>
            <a href="/?i={idx+1}" class="w-2/3 bg-white text-black py-5 rounded-3xl text-center text-[9px] font-black uppercase btn-active shadow-xl shadow-white/5">Next Match</a>
        </div>
        '''
        return render_template_string(LAYOUT, content=content)
    except Exception as e:
        return render_template_string(LAYOUT, content=f'<p class="text-center text-red-500 text-[10px] uppercase">{str(e)}</p>')

@app.route("/acca")
def acca():
    content = '<div class="glass p-10 rounded-[3rem] text-center mt-10"><h2 class="text-2xl font-black text-white italic mb-4 uppercase">ACCA BUILDER</h2><p class="text-zinc-600 text-[9px] font-bold uppercase tracking-[0.3em] mb-10">Compiling Odds Ticket...</p><a href="/" class="inline-block bg-zinc-800 text-white px-8 py-4 rounded-full text-[9px] font-black uppercase">Return to Hub</a></div>'
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
