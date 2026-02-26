from flask import Flask, render_template_string, request, redirect, url_for
import match_predictor
import os

# 1. INITIALIZE APP (Must be before routes)
app = Flask(__name__)

# 2. BRANDED MOBILE LAYOUT
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
        .glass { background: rgba(15, 18, 24, 0.8); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.05); }
        .btn-glow:active { transform: scale(0.95); transition: 0.1s; }
    </style>
</head>
<body class="p-4 italic">
    <div class="max-w-md mx-auto min-h-screen flex flex-col">
        <header class="flex justify-between items-center py-4 mb-4 border-b border-white/5">
            <h1 class="text-xl font-black tracking-tighter text-white uppercase">PRO<span class="text-green-500">PREDICTOR</span></h1>
            <a href="/acca" class="text-[10px] font-black bg-green-500/10 text-green-500 px-3 py-1 rounded-full uppercase">ACCA Builder</a>
        </header>
        {{ content | safe }}
    </div>
</body>
</html>
"""

# 3. ROUTES
@app.route("/")
def hub():
    # Get fixtures from Bzzoiro
    events = match_predictor.get_data("events/", {"status": "NS"}) # Not Started
    
    if not events:
        return render_template_string(LAYOUT, content='<div class="text-center py-20 uppercase font-black opacity-20">No Upcoming Fixtures Found</div>')
    
    # Simple pagination index
    idx = int(request.args.get('i', 0))
    if idx < 0: idx = 0
    if idx >= len(events): idx = 0
    
    m = events[idx]
    analysis = match_predictor.get_structured_analysis(m['id'])
    
    if "error" in analysis:
        # If this match has no prediction yet, try the next one
        return redirect(url_for('hub', i=idx+1))

    content = f'''
    <div class="flex justify-between items-center mb-6">
        <span class="text-[10px] font-black text-zinc-500 uppercase tracking-widest">{analysis['league']}</span>
        <span class="text-[10px] font-black text-white bg-zinc-800 px-2 py-0.5 rounded">{analysis['time'][11:16]}</span>
    </div>

    <div class="flex justify-around items-center mb-8">
        <div class="text-center w-1/3">
            <div class="w-16 h-16 glass rounded-full mx-auto mb-2 flex items-center justify-center text-xl font-black text-white uppercase">{analysis['event']['home_team']['name'][0]}</div>
            <p class="text-[10px] font-black uppercase text-zinc-400 leading-tight">{analysis['event']['home_team']['name']}</p>
        </div>
        <div class="text-2xl font-black text-zinc-800 italic">VS</div>
        <div class="text-center w-1/3">
            <div class="w-16 h-16 glass rounded-full mx-auto mb-2 flex items-center justify-center text-xl font-black text-white uppercase">{analysis['event']['away_team']['name'][0]}</div>
            <p class="text-[10px] font-black uppercase text-zinc-400 leading-tight">{analysis['event']['away_team']['name']}</p>
        </div>
    </div>

    <div class="text-center mb-6">
        <span class="px-4 py-1 rounded-full bg-green-500/10 text-green-500 text-[9px] font-black uppercase tracking-widest border border-green-500/20">{analysis['tag']}</span>
    </div>

    <div class="glass p-6 rounded-[2.5rem] mb-4 shadow-2xl relative overflow-hidden">
        <div class="flex justify-between items-start mb-2">
            <span class="text-[9px] font-black text-zinc-600 uppercase tracking-widest">🔵 Recommended</span>
            <span class="text-2xl font-black text-green-500">{analysis['rec']['p']}%</span>
        </div>
        <h2 class="text-2xl font-black text-white uppercase tracking-tighter mb-4 leading-tight">{analysis['rec']['t']}</h2>
        <div class="flex items-center gap-2 mb-4">
             <span class="text-zinc-500 text-[10px] font-bold">EST. ODDS:</span>
             <span class="text-white font-black text-sm">{analysis['rec']['o']}</span>
        </div>
        <div class="space-y-1 border-t border-white/5 pt-4">
            {"".join([f'<p class="text-[9px] text-zinc-500 font-bold uppercase flex items-center gap-2"><span class="w-1 h-1 bg-green-500 rounded-full"></span>{r}</p>' for r in analysis['rec']['r']])}
        </div>
    </div>

    <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="glass p-5 rounded-[2rem]">
            <span class="text-[7px] font-black text-zinc-600 uppercase mb-2 block">🟢 Safest</span>
            <p class="text-[10px] font-black text-white uppercase mb-1">{analysis['alt']['t']}</p>
            <p class="text-lg font-black text-white opacity-30">{analysis['alt']['o']}</p>
        </div>
        <div class="glass p-5 rounded-[2rem]">
            <span class="text-[7px] font-black text-zinc-600 uppercase mb-2 block tracking-widest text-red-500/50">🔴 High Risk</span>
            <p class="text-[10px] font-black text-white uppercase mb-1">{analysis['risk']['t']}</p>
            <p class="text-lg font-black text-red-500 opacity-30">{analysis['risk']['o']}</p>
        </div>
    </div>

    <div class="glass p-6 rounded-[2.5rem] mb-10">
        <h3 class="text-[8px] font-black text-zinc-700 uppercase tracking-[0.4em] mb-4 text-center">Insights & Form</h3>
        <div class="flex justify-between text-[10px] mb-4 font-bold uppercase">
            <span class="text-zinc-500">Home Form</span>
            <div class="flex gap-1">{"".join([f'<span class="w-4 h-4 rounded-sm flex items-center justify-center {"bg-green-500 text-black" if f=="W" else "bg-zinc-800 text-zinc-600"}">{f}</span>' for f in analysis['form']['h']])}</div>
        </div>
        <div class="flex justify-between text-[10px] font-bold uppercase">
            <span class="text-zinc-500">Volatility</span>
            <span class="text-yellow-500">{analysis['stats']['vol']}</span>
        </div>
    </div>

    <div class="mt-auto flex gap-2 pb-10">
        <a href="/?i={idx-1}" class="flex-1 glass py-4 rounded-full text-center text-[10px] font-black uppercase text-zinc-400 btn-glow">Prev</a>
        <a href="/?i={idx+1}" class="flex-[2] bg-white text-black py-4 rounded-full text-center text-[10px] font-black uppercase btn-glow shadow-[0_0_20px_rgba(255,255,255,0.2)]">Next Match</a>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

@app.route("/acca")
def acca():
    content = '<div class="glass p-8 rounded-[3rem] text-center mt-10"><h2 class="text-2xl font-black text-white italic mb-4 uppercase">ACCA BUILDER</h2><p class="text-zinc-500 text-[10px] font-bold uppercase tracking-widest">Generating 5.00 Odds Ticket...</p><a href="/" class="text-green-500 text-[10px] mt-10 block uppercase">Back to Hub</a></div>'
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
