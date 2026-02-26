@app.route("/match")
def match():
    m_id = request.args.get("id")
    # Always get the result, even if it's the fallback
    res = get_match_analysis(m_id)
    
    # WE REMOVED THE "IF ERROR" RETURN TO PREVENT THE LOOP
    
    content = f'''
    <div class="mb-6"><a href="/" class="text-zinc-600 font-bold text-[10px] uppercase tracking-widest">← RETURN TO HUB</a></div>
    
    <div class="flex justify-center items-center gap-10 mb-10 italic">
        <div class="text-center"><p class="text-xs font-black text-white uppercase">{res['h_name']}</p></div>
        <div class="text-zinc-800 font-black text-2xl opacity-20 italic uppercase tracking-tighter">VS</div>
        <div class="text-center"><p class="text-xs font-black text-white uppercase">{res['a_name']}</p></div>
    </div>

    <div class="text-center mb-8">
        <span class="bg-green-500/10 text-green-500 border border-green-500/20 px-4 py-1 rounded-full text-[9px] font-black tracking-[0.3em] uppercase">{res['tag']}</span>
    </div>

    <div class="bg-gradient-to-br from-[#10141d] to-[#07090e] p-8 rounded-[2.5rem] border border-white/5 mb-6 shadow-2xl relative overflow-hidden italic">
        <span class="text-[9px] font-black text-zinc-500 tracking-widest uppercase mb-4 block">🔵 Recommended Tip (Best Value)</span>
        <h2 class="text-3xl font-black text-white uppercase tracking-tighter mb-4 leading-none">{res['rec']['t']}</h2>
        <p class="text-5xl font-black text-green-500 tracking-tighter mb-6">{res['rec']['p']}% <span class="text-[10px] text-zinc-600 uppercase">PROBABILITY</span></p>
        <ul class="space-y-2 border-t border-white/5 pt-4">
            {"".join([f'<li class="text-[10px] text-zinc-400 font-bold uppercase flex items-center gap-2"><span class="w-1 h-1 bg-green-500 rounded-full"></span>{r}</li>' for r in res['rec']['r']])}
        </ul>
    </div>

    <div class="grid grid-cols-2 gap-4 mb-10 italic">
        <div class="bg-[#0f1218] p-6 rounded-[2rem] border border-white/5">
            <span class="text-[8px] text-zinc-600 font-black uppercase block mb-2 italic">🟢 Alternate (Safest)</span>
            <h4 class="text-sm font-black text-white uppercase mb-1">{res['alt']['t']}</h4>
            <p class="text-2xl font-black text-white italic opacity-40">{res['alt']['p']}%</p>
        </div>
        <div class="bg-[#0f1218] p-6 rounded-[2rem] border border-white/5">
            <span class="text-[8px] text-zinc-600 font-black uppercase block mb-2 italic tracking-widest">🔴 High Risk</span>
            <h4 class="text-sm font-black text-red-500 uppercase mb-1">{res['risk']['t']}</h4>
            <p class="text-2xl font-black text-red-500 italic opacity-40">{res['risk']['p']}%</p>
        </div>
    </div>

    <div class="bg-black/20 p-8 rounded-[2.5rem] border border-white/5 mb-20 italic">
        <h3 class="text-[10px] font-black text-zinc-700 uppercase tracking-[0.4em] mb-8 text-center underline decoration-zinc-800">Match Insights & Form</h3>
        <div class="grid grid-cols-2 gap-10 mb-10 text-center border-b border-white/5 pb-8">
            <div><p class="text-[8px] text-zinc-600 font-black uppercase mb-2">Avg Goals</p><p class="text-xl font-black text-white">{res['stats']['h_avg']} vs {res['stats']['a_avg']}</p></div>
            <div><p class="text-[8px] text-zinc-600 font-black uppercase mb-2">Volatility</p><p class="text-xl font-black text-yellow-500">{res['stats']['vol']}</p></div>
        </div>
        <div class="space-y-4">
            <div class="flex justify-between items-center text-[9px] font-black uppercase tracking-widest">
                <span class="text-zinc-500">Home Form</span>
                <div class="flex gap-1">{"".join([f'<span class="w-5 h-5 rounded flex items-center justify-center {"bg-green-500 text-black" if f=="W" else "bg-red-500/20 text-red-500" if f=="L" else "bg-zinc-800 text-zinc-500"}">{f}</span>' for f in res['h_form']])}</div>
            </div>
            <div class="flex justify-between items-center text-[9px] font-black uppercase tracking-widest">
                <span class="text-zinc-500">Away Form</span>
                <div class="flex gap-1">{"".join([f'<span class="w-5 h-5 rounded flex items-center justify-center {"bg-green-500 text-black" if f=="W" else "bg-red-500/20 text-red-500" if f=="L" else "bg-zinc-800 text-zinc-500"}">{f}</span>' for f in res['a_form']])}</div>
            </div>
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)
