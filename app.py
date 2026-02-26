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
        # Fetching all events to avoid empty states
        events = match_predictor.get_data("events/")
        
        if not events or not isinstance(events, list):
            return render_template_string(LAYOUT, content='''
                <div class="flex-grow flex flex-col items-center justify-center py-20 text-center opacity-40">
                    <p class="text-[10px] font-black uppercase tracking-[0.4em] mb-2">Feed Offline</p>
                    <p class="text-[8px] italic">Bzzoiro is updating match streams...</p>
                    <a href="/" class="mt-10 px-6 py-2 bg-white text-black text-[9px] font-black rounded-full uppercase">Refresh</a>
                </div>
            ''')

        idx = int(request.args.get('i', 0))
        idx = max(0, min(idx, len(events) - 1))
        
        m = events[idx]
        analysis = match_predictor.get_structured_analysis(m['id'])
        
        # If specific analysis is missing, show a high-end "In Progress" Card
        if "error" in analysis:
            return render_template_string(LAYOUT, content=f'''
                <div class="glass p-8 rounded-[2.5rem] text-center mb-6 border-t-2 border-green-500/20">
                    <p class="text-[10px] text-zinc-500 font-black uppercase tracking-widest mb-4">{m.get('league', {}).get('name', 'League')}</p>
                    <h2 class="text-white font-black uppercase text-sm mb-10">{m['home_team']['name']} vs {m['away_team']['name']}</h2>
                    <p class="text-[9px] text-green-500 font-black uppercase animate-pulse">AI Analysis Synchronizing...</p>
                    <div class="mt-10 flex gap-2">
                        <a href="/?i={idx-1}" class="flex-1 glass py-4 rounded-3xl text-[9px] font-black uppercase text-zinc-600">Prev</a>
                        <a href="/?i={idx+1}" class="flex-[2] bg-white text-black py-4 rounded-3xl text-[9px] font-black uppercase">Next Match</a>
                    </div>
                </div>
            ''')

        # SUCCESSFUL ANALYSIS VIEW
        content = f'''
        <div class="flex justify-between items-center mb-6">
            <span class="text-[9px] font-black text-zinc-600 uppercase tracking-widest">{analysis['league']}</span>
            <span class="text-[9px] font-black text-white bg-zinc-900 border border-white/10 px-2 py-1 rounded-md tracking-tighter">{analysis['time'][11:16]} GMT</span>
        </div>

        <div class="flex justify-around items-center mb-10">
            <div class="text-center w-1/3">
                <div class="w-14 h-14 glass rounded-2xl mx-auto mb-3 flex items-center justify-center text-xl font-black text-white">{analysis['h_name'][0]}</div>
                <p class="text-[9px] font-black uppercase text-zinc-400 leading-tight">{analysis['h_name']}</p>
            </div>
            <div class="text-xl font-black text-zinc-800 opacity-30 italic">VS</div>
            <div class="text-center w-1/3">
                <div class="w-14 h-14 glass rounded-2xl mx-auto mb-3 flex items-center justify-center text-xl font-black text-white">{analysis['a_name'][0]}</div>
                <p class="text-[9px] font-black uppercase text-zinc-400 leading-tight">{analysis['a_name']}</p>
            </div>
        </div>

        <div class="text-center mb-8">
            <span class="px-5 py-1.5 rounded-full bg-green-500/10 text-green-500 text-[8px] font-black uppercase tracking-[0.3em] border border-green-500/20">{analysis['tag']}</span>
        </div>

        <div class="glass p-6 rounded-[2.5rem] mb-4 shadow-2xl relative border-t border-white/10">
            <div class="flex justify-between items-start mb-2">
                <span class="text-[8px] font-black text-zinc-600 uppercase tracking-widest">🔵 Recommended Tip</span>
                <span class="text-3xl font-black text-green-500 italic">+{analysis['rec']['p']}%</span>
            </div>
            <h2 class="text-2xl font-black text-white uppercase tracking-tighter mb-4 leading-none">{analysis['rec']['t']}</h2>
            <div class="flex items-center gap-2 mb-6 text-[9px]">
                 <span class="text-zinc-600 font-bold uppercase tracking-widest">Market Odds:</span>
                 <span class="text-white font-black">{analysis['rec']['o']}</span>
            </div>
            <div class="space-y-2 border-t border-white/5 pt-5">
                {"".join([f'<p class="text-[9px] text-zinc-500 font-bold uppercase flex items-center gap-3"><span class="w-1 h-1 bg-green-500 rounded-full shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>{r}</p>' for r in analysis['rec_reasons']])}
            </div>
        </div>

        <div class="grid grid-cols-2 gap-3 mb-10">
            <div class="glass p-5 rounded-[2rem] border-l-2 border-blue-500/30">
                <span class="text-[7px] font-black text-zinc-600 uppercase mb-2 block tracking-widest">🟢 Safest</span>
                <p class="text-[9px] font-black text-white uppercase mb-1">{analysis['alt']['t']}</p>
                <p class="text-sm font-black text-zinc-700">{analysis['alt']['o']}</p>
            </div>
            <div class="glass p-5 rounded-[2rem] border-l-2 border-red-500/30">
                <span class="text-[7px] font-black text-red-500/40 uppercase mb-2 block tracking-widest">🔴 High Risk</span>
                <p class="text-[9px] font-black text-white uppercase mb-1">{analysis['risk']['t']}</p>
                <p class="text-sm font-black text-zinc-700">{analysis['risk']['o']}</p>
            </div>
        </div>

        <div class="mt-auto flex gap-3 pb-10">
            <a href="/?i={idx-1}" class="w-1/3 glass py-5 rounded-3xl text-center text-[9px] font-black uppercase text-zinc-600 btn-active border border-white/5">Prev</a>
            <a href="/?i={idx+1}" class="w-2/3 bg-white text-black py-5 rounded-3xl text-center text-[9px] font-black uppercase btn-active shadow-xl shadow-white/5">Next Match</a>
        </div>
        '''
        return render_template_string(LAYOUT, content=content)

    except Exception as e:
        return render_template_string(LAYOUT, content=f'<div class="py-20 text-center uppercase font-black text-[9px] text-red-500">System Link Error: {str(e)}</div>')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
