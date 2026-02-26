# ... (Imports and get_badge function stay same)

@app.route("/match")
def match():
    res = get_match_analysis(request.args.get("id"))
    if "error" in res: return render_template_string(LAYOUT, content='<p class="text-center mt-20">Syncing...</p>')
    
    content = f'''
    <div class="mb-6"><a href="/" class="text-zinc-600 font-bold text-[10px] uppercase tracking-widest">← RETURN</a></div>

    <div class="flex justify-center items-center gap-6 mb-10">
        <div class="text-center"><img src="{get_badge(res['h_name'])}" class="w-14 h-14 rounded-full border border-white/10 mb-2"><p class="text-[8px] font-black text-zinc-500 uppercase">{res['h_name']}</p></div>
        <div class="text-zinc-800 font-black italic text-xl">VS</div>
        <div class="text-center"><img src="{get_badge(res['a_name'])}" class="w-14 h-14 rounded-full border border-white/10 mb-2"><p class="text-[8px] font-black text-zinc-500 uppercase">{res['a_name']}</p></div>
    </div>

    <div class="bg-[#10141d] p-8 rounded-[2rem] border border-white/5 mb-6 text-center shadow-2xl relative overflow-hidden">
        <div class="absolute top-0 right-0 p-3 text-green-500/20 font-black italic text-xs tracking-widest">{res['tag']}</div>
        <span class="text-[9px] font-black uppercase text-zinc-500 mb-2 block tracking-[0.3em]">RECOMMENDED TIP</span>
        <h2 class="text-3xl font-black text-white italic uppercase tracking-tighter mb-1">{res['best_tip']['t']}</h2>
        <p class="text-5xl font-black text-green-500 italic tracking-tighter">{res['best_tip']['p']:.0f}% <span class="text-[10px] text-zinc-600">CONFIDENCE</span></p>
    </div>

    <div class="grid grid-cols-2 gap-4 mb-6 text-center">
        <div class="bg-[#0f1218] p-5 rounded-2xl border border-white/5">
            <span class="text-[8px] text-zinc-500 font-black uppercase block mb-1">SAFE ALTERNATIVE</span>
            <span class="text-xs font-black text-white italic">{res['safer']}</span>
        </div>
        <div class="bg-[#0f1218] p-5 rounded-2xl border border-white/5">
            <span class="text-[8px] text-zinc-500 font-black uppercase block mb-1">HIGH RISK VALUE</span>
            <span class="text-xs font-black text-red-500 italic">{res['risky']}</span>
        </div>
    </div>

    <div class="bg-black/20 p-6 rounded-2xl border border-white/5 mb-10">
        <h4 class="text-[9px] font-black uppercase text-zinc-600 mb-4 tracking-widest text-center italic">PROBABILITY INSIGHTS</h4>
        <div class="flex justify-around items-center">
            {"".join([f'<div class="text-center"><p class="text-[8px] text-zinc-500 font-bold">{k}</p><p class="text-lg font-black text-white">{v}</p></div>' for k,v in res['intel'].items()])}
        </div>
    </div>

    <div class="text-center mb-20">
        <h4 class="text-[9px] font-black uppercase text-zinc-600 mb-4 tracking-widest italic">FORM GUIDE (LAST 5)</h4>
        <div class="flex justify-center gap-2">
            {"".join([f'<span class="w-8 h-8 rounded-lg flex items-center justify-center font-black text-xs {"bg-green-500 text-black" if f=="W" else "bg-zinc-800 text-zinc-400"}">{f}</span>' for f in res['form']])}
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)
