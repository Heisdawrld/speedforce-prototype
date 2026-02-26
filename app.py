from flask import Flask, render_template_string, request
import match_predictor
import os

app = Flask(__name__)

# Use your previous high-end LAYOUT variable here...

@app.route("/")
def hub():
    # Fetch fixtures from the NEW reliable source
    matches = match_predictor.get_fixtures()
    
    if not matches:
        return render_template_string(LAYOUT, content='''
            <div class="text-center py-20 opacity-30">
                <p class="text-[10px] font-black uppercase tracking-[0.3em]">Establishing Connection...</p>
                <p class="text-[8px] mt-2">Football-Data.org is syncing league tiers</p>
            </div>
        ''')

    idx = int(request.args.get('i', 0))
    idx = max(0, min(idx, len(matches) - 1))
    
    m = matches[idx]
    match_name = f"{m['homeTeam']['name']} {m['awayTeam']['name']}"
    analysis = match_predictor.get_structured_analysis(match_name, m['id'])

    content = f'''
    <div class="flex justify-between items-center mb-6">
        <span class="text-[9px] font-black text-zinc-600 uppercase tracking-widest">{m['competition']['name']}</span>
        <span class="text-[9px] font-black text-white bg-zinc-900 px-2 py-1 rounded-md">{m['utcDate'][11:16]}</span>
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

    <div class="text-center mb-8"><span class="px-5 py-1.5 rounded-full bg-green-500/10 text-green-500 text-[8px] font-black uppercase border border-green-500/20">{analysis['tag']}</span></div>

    <div class="glass p-6 rounded-[2.5rem] mb-4 border-t border-white/10">
        <span class="text-[8px] font-black text-zinc-600 uppercase block mb-2 tracking-widest">🔵 Recommended</span>
        <h2 class="text-2xl font-black text-white uppercase mb-4">{analysis['rec']['t']}</h2>
        <p class="text-3xl font-black text-green-500">+{analysis['rec']['p']}%</p>
    </div>

    <div class="mt-auto flex gap-3 pb-10">
        <a href="/?i={idx-1}" class="w-1/3 glass py-5 rounded-3xl text-center text-[9px] font-black uppercase text-zinc-600">Prev</a>
        <a href="/?i={idx+1}" class="w-2/3 bg-white text-black py-5 rounded-3xl text-center text-[9px] font-black uppercase shadow-xl">Next Match</a>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
