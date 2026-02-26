@app.route("/acca")
def acca():
    all_matches = match_predictor.get_all_fixtures()
    all_preds = match_predictor.get_bzzoiro_predictions()
    
    analyzed_pool = []
    for f in all_matches[:30]:
        res = match_predictor.get_match_analysis(
            f['homeTeam']['name'], 
            f['awayTeam']['name'], 
            f['competition']['name'], 
            all_preds
        )
        analyzed_pool.append({
            "match": f"{f['homeTeam']['name']} v {f['awayTeam']['name']}",
            "tip": res['rec']['t'],
            "odds": res['rec']['o'],
            "edge": res['rec']['e'],
            "league": f['competition']['name'],
            "prob": res['rec']['p']
        })

    # RANK BY EDGE DESCENDING
    optimized_pool = sorted(analyzed_pool, key=lambda x: x['edge'], reverse=True)

    acca_selections = []
    current_odds = 1.0
    combined_prob = 1.0
    used_leagues = set()
    used_markets = set()

    for s in optimized_pool:
        # Diversification Filter: Max 1 pick per league/market type
        if s['league'] not in used_leagues and s['tip'] not in used_markets:
            acca_selections.append(s)
            current_odds *= s['odds'] # MULTIPLICATION FIXED
            combined_prob *= (s['prob'] / 100)
            used_leagues.add(s['league'])
            used_markets.add(s['tip'])
            if current_odds >= 5.0: break 

    # FALLBACK: If target not reached, use top 3 picks
    if current_odds < 2.0 and len(optimized_pool) >= 3:
        acca_selections = optimized_pool[:3]
        current_odds = 1.0
        for s in acca_selections: current_odds *= s['odds']

    picks_html = "".join([f'''
        <div class="glass p-5 rounded-3xl mb-3 border-l-2 border-green-500/50 italic">
            <div class="flex justify-between items-center">
                <div>
                    <p class="text-[7px] text-zinc-600 uppercase mb-1">{s['league']}</p>
                    <p class="text-[10px] font-black text-white">{s['match']}</p>
                    <p class="text-[9px] text-zinc-400 font-bold uppercase tracking-tighter">{s['tip']}</p>
                </div>
                <div class="text-right">
                    <p class="text-xs font-black text-green-500">{s['odds']}</p>
                    <p class="text-[7px] text-zinc-800 font-black uppercase">Edge: {s['edge']}%</p>
                </div>
            </div>
        </div>''' for s in acca_selections])

    # [RENDER THEME]
