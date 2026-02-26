# (Keep all your imports and get_badge function the same at the top)

@app.route("/match")
def match():
    res = get_match_analysis(request.args.get("id"))
    if "error" in res: return render_template_string(LAYOUT, content='<p class="text-center mt-20">Syncing Data...</p>')
    
    # UI Logic for Risk and Intel
    intel_html = ""
    for label, val in res['intel'].items():
        if "prob" in label:
            clean_label = label.replace("_prob", "").replace("fh", "1st Half").upper()
            intel_html += f'''
            <div class="bg-white/5 p-4 rounded-2xl border border-white/5">
                <p class="text-[8px] text-zinc-500 font-black mb-1">{clean_label}</p>
                <p class="text-xl font-black text-white italic">{val}</p>
            </div>'''

    content = f'''
    <div class="flex justify-between items-center mb-8">
        <a href="/" class="text-zinc-600 font-bold text-[10px] uppercase tracking-widest hover:text-white">← BACK</a>
        <div class="flex gap-2 text-[8px] font-black uppercase italic text-green-500">
            <span class="bg-green-500/10 px-3 py-1 rounded-full border border-green-500/20">DIFF: {res['difficulty']}</span>
        </div>
    </div>

    <div class="flex justify-center items-center gap-8 mb-12">
        <div class="text-center"><img src="{get_badge(res['h_name'])}" class="w-16 h-16 rounded-full border-2 border-white/5 mb-2"><p class="text-[9px] font-black uppercase text-zinc-600 tracking-tighter">{res['h_name']}</p></div>
        <div class="text-zinc-800 font-black italic text-3xl italic">VS</div>
        <div class="text-center"><img src="{get_badge(res['a_name'])}" class="w-16 h-16 rounded-full border-2 border-white/5 mb-2"><p class="text-[9px] font-black uppercase text-zinc-600 tracking-tighter">{res['a_name']}</p></div>
    </div>

    <div class="bg-gradient-to-br from-[#10141d] to-[#07090e] p-10 rounded-[3rem] border border-white/5 shadow-2xl mb-8">
        <span class="text-[10px] font-black uppercase text-zinc-500 mb-4 block tracking-widest italic border-b border-white/5 pb-2">PRIMARY AI DIRECTIVE</span>
        <h2 class="text-4xl font-black text-white italic uppercase tracking-tighter mb-2 leading-none">{res['best_tip']['t']}</h2>
        <div class="flex items-center gap-4 mb-8">
            <span class="text-6xl font-black text-green-500 italic tracking-tighter">{res['best_tip']['p']:.0f}%</span>
            <span class="text-[10px] font-bold text-orange-500 uppercase tracking-widest border border-white/10 px-3 py-1 rounded-full italic">{res['best_tip']['risk']} RISK</span>
        </div>
        <ul class="space-y-4">
            {"".join([f'<li class="flex items-start gap-3 text-[11px] text-zinc-400 font-bold italic"><span class="w-1.5 h-1.5 bg-green-500 rounded-full mt-1.5"></span>{r}</li>' for r in res['best_tip']['reasons']])}
        </ul>
    </div>

    <h3 class="text-[10px] font-black text-zinc-700 uppercase tracking-[0.4em] mb-4 italic px-6 text-center">Tactical Intelligence Deep-Dive</h3>
    <div class="grid grid-cols-2 gap-4 mb-8">
        {intel_html}
    </div>

    <div class="bg-[#0f1218] p-8 rounded-[2.5rem] border border-white/5 mb-12">
        <h4 class="text-[9px] font-black uppercase text-zinc-600 mb-6 tracking-widest italic text-center underline decoration-zinc-800">MARKET DYNAMICS</h4>
        <div class="space-y-6">
            <div class="flex justify-between items-center"><span class="text-zinc-500 font-bold uppercase text-[9px]">Low-Risk Shield</span><span class="text-white font-black italic uppercase tracking-tighter text-sm">{res['safer']}</span></div>
            <div class="flex justify-between items-center"><span class="text-zinc-500 font-bold uppercase text-[9px]">High-Value Sniper</span><span class="text-red-500 font-black italic uppercase tracking-tighter text-sm">{res['risky']}</span></div>
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)
