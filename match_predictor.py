"""
match_predictor.py -- God Mode Intelligence Engine
"""
import sportmonks

def get_h2h_dominance(h2h_list, h_id):
    if not h2h_list: return None
    h_wins = 0
    valid_games = 0
    for m in h2h_list:
        if m.get('winner_team_id'):
            valid_games += 1
            if m.get('winner_team_id') == h_id: h_wins += 1
    
    if valid_games == 0: return None
    rate = h_wins / valid_games
    if rate >= 0.60: return "HOME"
    if rate <= 0.20: return "AWAY"
    return None

def calculate_true_prob(sm_prob, dominance):
    """Adjusts API probability based on H2H reality."""
    base = sm_prob
    if dominance == "HOME": base += 10
    elif dominance == "AWAY": base -= 10
    return min(max(base, 5), 95)

def analyze_match(enriched_data):
    """
    Analyzes enriched data to produce the 3 golden tips.
    """
    fx = enriched_data.get('fixture', {})
    h2h = enriched_data.get('h2h', [])
    
    # 1. Basic Info
    h_id, h_name, a_id, a_name = sportmonks.extract_teams(fx)
    odds = sportmonks.parse_odds(fx)
    
    # 2. Get Sportmonks Predictions
    preds = fx.get('predictions', [])
    sm_probs = {"home": 33, "draw": 33, "away": 33, "over_25": 50, "btts": 50}
    
    for p in (preds if isinstance(preds, list) else []):
        # Sportmonks V3 prediction parsing
        if p.get('developer_name') == 'PROBABILITY':
            selections = p.get('predictions', {})
            try:
                if 'home' in selections: sm_probs['home'] = float(selections['home'].replace('%',''))
                if 'away' in selections: sm_probs['away'] = float(selections['away'].replace('%',''))
                if 'draw' in selections: sm_probs['draw'] = float(selections['draw'].replace('%',''))
            except: pass
        if p.get('type_id') == 237: # Over/Under 2.5
             try: sm_probs['over_25'] = float(p.get('predictions',{}).get('over', "50").replace('%',''))
             except: pass
             
    # 3. Intelligence Layer
    dominance = get_h2h_dominance(h2h, h_id)
    
    # Adjust probabilities
    true_home = calculate_true_prob(sm_probs['home'], dominance if dominance=="HOME" else None)
    true_away = calculate_true_prob(sm_probs['away'], dominance if dominance=="AWAY" else None)
    
    # 4. Select Tips
    tips = {"recommended": None, "safest": None, "risky": None}
    
    # -- ⚡ RECOMMENDED (Value) --
    # Find outcome with best Edge (EV)
    candidates = []
    
    # Check Home Win
    if odds.get('home'):
        ev = (true_home/100 * odds['home']) - 1
        candidates.append({"sel": h_name, "prob": true_home, "odds": odds['home'], "ev": ev, "type": "1X2"})
        
    # Check Away Win
    if odds.get('away'):
        ev = (true_away/100 * odds['away']) - 1
        candidates.append({"sel": a_name, "prob": true_away, "odds": odds['away'], "ev": ev, "type": "1X2"})
        
    # Check Over 2.5
    if odds.get('over_25'):
        ev = (sm_probs['over_25']/100 * odds['over_25']) - 1
        candidates.append({"sel": "Over 2.5 Goals", "prob": sm_probs['over_25'], "odds": odds['over_25'], "ev": ev, "type": "GOALS"})

    # Filter candidates for Value (Odds 1.30 - 2.20)
    rec_cands = [c for c in candidates if 1.30 <= c['odds'] <= 2.20 and c['prob'] > 45]
    if rec_cands:
        # Sort by best EV
        rec_cands.sort(key=lambda x: x['ev'], reverse=True)
        tips['recommended'] = rec_cands[0]
    else:
        # Fallback if no value found
        tips['recommended'] = {"sel": "No Value Bet", "prob": 0, "odds": 0, "ev": 0}

    # -- 🛡️ SAFEST (Banker) --
    # High prob (>70%), Low odds (1.15 - 1.45)
    safe_cands = []
    if odds.get('over_15') and sm_probs['over_25'] > 60: # Proxy for O1.5
        safe_cands.append({"sel": "Over 1.5 Goals", "prob": 80, "odds": odds['over_15']})
    
    # Double Chance proxies
    if true_home > 60 and odds.get('home',0) < 1.9:
        safe_cands.append({"sel": f"{h_name} or Draw", "prob": true_home+20, "odds": 1.25}) # Est odds
        
    safe_cands = [c for c in safe_cands if c['odds'] and 1.10 <= c['odds'] <= 1.50]
    if safe_cands:
        safe_cands.sort(key=lambda x: x['prob'], reverse=True)
        tips['safest'] = safe_cands[0]
    else:
        tips['safest'] = {"sel": "Skip", "prob": 0, "odds": 0}

    # -- 💣 RISKY (High Reward) --
    # Odds > 2.40
    risky_cands = []
    if odds.get('draw') and odds['draw'] > 2.80 and sm_probs['draw'] > 28:
        risky_cands.append({"sel": "Draw", "prob": sm_probs['draw'], "odds": odds['draw']})
        
    if risky_cands:
        tips['risky'] = risky_cands[0]
    else:
        tips['risky'] = {"sel": "None", "prob": 0, "odds": 0}

    # Analysis Text
    reason = f"Analysis: {h_name} vs {a_name}. "
    if dominance: reason += f"H2H data favors {dominance}. "
    if tips['recommended']['ev'] > 0.05: reason += f"Value detected on {tips['recommended']['sel']}."
    
    return {
        "teams": {"home": h_name, "away": a_name},
        "tips": tips,
        "analysis": reason
    }
