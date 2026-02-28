"""
match_predictor.py -- God Mode Intelligence Engine
"""
import math

# ─── 1. INTELLIGENCE ENGINE ──────────────────────────────────────────────────

def get_h2h_dominance(h2h_list, h_id):
    """Analyzes history. Returns 'HOME', 'AWAY', or 'None'."""
    if not h2h_list: return None
    h_wins = 0
    for m in h2h_list:
        winner = m.get('winner_team_id')
        if winner == h_id: h_wins += 1
    
    win_rate = h_wins / len(h2h_list)
    if win_rate >= 0.6: return "HOME" # Domination
    if win_rate <= 0.2: return "AWAY" # Domination
    return None

def calculate_true_probability(sm_prediction_prob, dominance):
    """
    Adjusts Sportmonks' raw probability based on our own H2H analysis.
    """
    prob = sm_prediction_prob
    if dominance == "HOME": prob += 10 # Boost logic
    elif dominance == "AWAY": prob -= 10
    return min(max(prob, 1), 99)

def find_best_odds(odds_list, market_name, selection_label):
    """Scans all bookmakers to find the best available price."""
    best_price = 0
    for market in odds_list:
        if market['label'] == market_name:
            for outcome in market['odds']:
                # Fuzzy match for labels like "1", "Home", "Over 2.5"
                lbl = str(outcome['label']).lower()
                target = str(selection_label).lower()
                if lbl == target or (target == "1" and "home" in lbl) or (target == "2" and "away" in lbl):
                    try:
                        val = float(outcome['value'])
                        if val > best_price: best_price = val
                    except: pass
    return best_price

# ─── 2. CATEGORY SORTER ──────────────────────────────────────────────────────

def analyze_match(enriched_data):
    """
    Main Analysis Function.
    Input: The 'God Mode' data packet.
    Output: Recommended, Safest, Risky tips + Analysis.
    """
    if not enriched_data: return None
    
    match = enriched_data['match']
    h2h = enriched_data['h2h']
    odds = enriched_data['odds']
    preds = enriched_data['predictions']
    
    # 1. Setup Teams
    h_id = next((p['id'] for p in match.get('participants') if p['meta']['location']=='home'), 0)
    h_name = next((p['name'] for p in match.get('participants') if p['meta']['location']=='home'), "Home")
    
    # 2. Intelligence Factors
    dominance = get_h2h_dominance(h2h, h_id)
    
    # 3. Parse Sportmonks Predictions
    # We look for the main probability prediction
    sm_probs = {}
    for p in preds:
        if p.get('developer_name') == 'PROBABILITY':
            # Map their predictions to our keys
            try:
                # Example structure adjustment based on SM v3
                selections = p.get('predictions', {})
                # This part depends on SM specific JSON structure, defaulting to safe parse
                if 'home' in selections: sm_probs['1'] = float(selections['home'].replace('%',''))
                if 'away' in selections: sm_probs['2'] = float(selections['away'].replace('%',''))
                if 'draw' in selections: sm_probs['X'] = float(selections['draw'].replace('%',''))
            except: pass
            
    # Default if SM prediction missing (fallback to 33/33/33)
    p_home = sm_probs.get('1', 33)
    p_away = sm_probs.get('2', 33)
    p_draw = sm_probs.get('X', 33)
    
    # 4. Generate Candidate Tips with EV
    candidates = []
    
    # -- Home Win --
    true_p1 = calculate_true_probability(p_home, dominance if dominance=="HOME" else None)
    odds_1 = find_best_odds(odds, "3Way Result", "1") or 1.01
    candidates.append({
        "type": "HOME WIN", "selection": h_name, "prob": true_p1, "odds": odds_1,
        "ev": (true_p1/100 * odds_1) - 1, "cat": "WIN"
    })
    
    # -- Away Win --
    true_p2 = calculate_true_probability(p_away, dominance if dominance=="AWAY" else None)
    odds_2 = find_best_odds(odds, "3Way Result", "2") or 1.01
    candidates.append({
        "type": "AWAY WIN", "selection": "Away Win", "prob": true_p2, "odds": odds_2,
        "ev": (true_p2/100 * odds_2) - 1, "cat": "WIN"
    })
    
    # -- Draw --
    odds_x = find_best_odds(odds, "3Way Result", "X") or 1.01
    candidates.append({
        "type": "DRAW", "selection": "Draw", "prob": p_draw, "odds": odds_x,
        "ev": (p_draw/100 * odds_x) - 1, "cat": "RISKY"
    })
    
    # -- Over 2.5 --
    # Simplified logic: If home+away prob > 70, likely goals
    p_o25 = (p_home + p_away) / 2 # Crude approx, ideally fetch specific market
    odds_o25 = find_best_odds(odds, "Over/Under Goals", "Over 2.5") or 1.01
    candidates.append({
        "type": "OVER 2.5", "selection": "Over 2.5 Goals", "prob": p_o25, "odds": odds_o25,
        "ev": (p_o25/100 * odds_o25) - 1, "cat": "GOALS"
    })

    # 5. STRICT CATEGORIZATION
    
    rec_tip = None
    safe_tip = None
    risky_tip = None
    
    # ⚡ Recommended (Value): Odds 1.30-1.70, Positive EV preferred
    rec_candidates = [c for c in candidates if 1.30 <= c['odds'] <= 2.20 and c['prob'] > 45]
    if rec_candidates:
        # Sort by EV (Value)
        rec_candidates.sort(key=lambda x: x['ev'], reverse=True)
        rec_tip = rec_candidates[0]
        
    # 🛡️ Safest (Banker): High Prob (>75%), Low Odds (1.15-1.45)
    safe_candidates = [c for c in candidates if c['prob'] > 70 and 1.15 <= c['odds'] <= 1.50]
    if safe_candidates:
        safe_candidates.sort(key=lambda x: x['prob'], reverse=True)
        safe_tip = safe_candidates[0]
        
    # 💣 Risky: High Odds (2.40+), but some probability base
    risky_candidates = [c for c in candidates if c['odds'] >= 2.40 and c['prob'] > 25]
    if risky_candidates:
        # Sort by EV to ensure it's a "Smart" risk, not a dumb one
        risky_candidates.sort(key=lambda x: x['ev'], reverse=True)
        risky_tip = risky_candidates[0]
        
    # Analysis Text
    analysis = f"{h_name} vs Away. "
    if dominance: analysis += f"H2H history strongly favors {dominance}. "
    if rec_tip and rec_tip['ev'] > 0.05: analysis += f"Value detected on {rec_tip['selection']}."
    elif safe_tip: analysis += f"Safest path is {safe_tip['selection']} based on probability."
    
    return {
        "teams": {"home": h_name},
        "tips": {
            "recommended": rec_tip,
            "safest": safe_tip,
            "risky": risky_tip
        },
        "analysis": analysis
    }
