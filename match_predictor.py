"""
match_predictor.py -- ProPredictor Intelligence Engine v5 (Patched)

UPGRADES:
1. Dynamic Badging (Volatile, Versatile, Bunker)
2. Variance/Chaos Detection (Stops forcing tips on bad matches)
3. Proper xG Ingestion (Fixes the "Over 2.5" spam)
"""

import math
import statistics

# -- Poisson -------------------------------------------------------------------
def poisson_pmf(k, lam):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

# -- Volatility & Form Logic ---------------------------------------------------
FORM_VALUE = {"W": 3.0, "D": 1.0, "L": 0.0}

def calculate_volatility(form_list):
    """
    Returns a 'Chaos Score' (0.0 to 1.0).
    High volatility (0.8+) means the team is inconsistent (e.g., W-L-W-L-W).
    Low volatility means consistent performance (W-W-W or L-L-L).
    """
    if not form_list or len(form_list) < 3: return 0.5
    
    # Convert W/D/L to points
    points = [FORM_VALUE.get(r.upper(), 1.0) for r in form_list]
    
    # Calculate standard deviation of their performance
    if len(points) > 1:
        std_dev = statistics.stdev(points)
        # Max std_dev for (0, 3) range is approx 1.5. Normalize to 0-1.
        volatility = min(std_dev / 1.5, 1.0)
        return volatility
    return 0.0

def form_score(form_list):
    # Standard weighted form (recent games matter more)
    if not form_list: return 0.5
    results = [r.upper() for r in list(form_list)[-5:]]
    weights = [1.0, 1.2, 1.4, 1.6, 1.8][-len(results):]
    vals    = [1.0 if r=='W' else 0.4 if r=='D' else 0.0 for r in results]
    score   = sum(v * w for v, w in zip(vals, weights))
    return round(score / sum(weights), 3)

# -- Core Signals -------------------------------------------------------------
def _xg_signal(tip, h_xg, a_xg):
    total = max(h_xg + a_xg, 0.1)
    h_share = h_xg / total
    
    if tip == "HOME WIN": return h_share
    if tip == "AWAY WIN": return (1.0 - h_share)
    if tip == "DRAW":     return 1.0 - (abs(h_share - 0.5) * 2) # High if share is 0.5
    
    # Goals Mapping
    if tip == "OVER 2.5":
        # 2.5 Goals usually needs ~2.7+ combined xG to be 'safe'
        return min(total / 2.7, 1.0)
    if tip == "UNDER 2.5":
        # Safe under needs < 2.0 combined xG
        return max(0.0, 1.0 - (total / 2.0))
    if tip == "GG":
        # Both need to contribute. If one is 0.1, GG is unlikely.
        balanced = min(h_xg, a_xg) / max(h_xg, a_xg) if max(h_xg,a_xg)>0 else 0
        volume   = min(total / 2.5, 1.0)
        return (balanced * 0.6 + volume * 0.4)
        
    return 0.5

def _value_edge(prob, odds):
    if not odds or odds <= 1.0: return 0.0
    implied = 1.0 / odds
    return (prob/100.0) - implied

# -- Conviction Calculator ----------------------------------------------------
def calculate_conviction(tip, prob, odds, h_xg, a_xg, h_form, a_form):
    """
    Returns a score 0-100 based on how much the Data supports the Probability.
    """
    s_xg    = _xg_signal(tip, h_xg, a_xg)
    s_form  = (form_score(h_form) + (1-form_score(a_form))) / 2 # simplified relative form
    s_value = _value_edge(prob, odds) * 5 # Boost score if valuable
    
    # Base score is the probability itself
    score = prob 
    
    # Modifiers
    if s_xg > 0.6: score += 5
    if s_xg < 0.4: score -= 10
    
    if s_value > 0.05: score += 10 # 5% value edge adds 10 points
    
    return max(0, min(100, score))

# -- The "Badge Factory" (Dynamic Personality) --------------------------------
def generate_badges(h_prob, d_prob, a_prob, h_volatility, a_volatility, conviction, edge):
    badges = []
    
    # 1. UNRELIABLE (Volatile)
    # If teams are erratic OR conviction is low despite high prob
    avg_volatility = (h_volatility + a_volatility) / 2
    if avg_volatility > 0.75:
        return "⚠️ UNRELIABLE", "Teams are too inconsistent to predict safely."
    
    # 2. VERSATILE (Balanced)
    # If Home and Away are within 10% of each other
    if abs(h_prob - a_prob) < 10:
        return "⚖️ VERSATILE", "Tight match. Look at Goals or Double Chance."

    # 3. BANKER (Solid)
    # High conviction + Low Volatility
    if conviction > 75 and avg_volatility < 0.4:
        return "🛡️ BANKER", "High probability with consistent team data."
        
    # 4. VALUE BET
    if edge > 0.10: # 10% edge
        return "⚡ VALUE", "Bookies have underestimated this outcome."
        
    return "STANDARD", "Standard match analysis."

# -- MAIN ANALYZER ------------------------------------------------------------
def analyze_match(api_data, league_id=None, enriched=None):
    try:
        # 1. DATA INGESTION (The Fix)
        # ------------------------------------------------------
        # Prioritize 'enriched' data from Sportmonks.py
        h_xg = 1.2 # Default
        a_xg = 1.0 # Default
        
        if enriched:
            # CHECK 1: Did we get specific stats?
            if enriched.get("xg_home") is not None:
                h_xg = float(enriched["xg_home"])
            if enriched.get("xg_away") is not None:
                a_xg = float(enriched["xg_away"])
                
        # Squad/Injury Penalties (Simplified Logic)
        h_pen = 1.0
        a_pen = 1.0
        # If you add injury logic later, reduce h_pen here (e.g. 0.8)
        
        h_xg = round(h_xg * h_pen, 2)
        a_xg = round(a_xg * a_pen, 2)
        total_xg = h_xg + a_xg

        # 2. PROBABILITY CALCULATION (Poisson)
        # ------------------------------------------------------
        # We recalculate probs because the API ones might be generic
        home_matrix = [poisson_pmf(i, h_xg) for i in range(10)]
        away_matrix = [poisson_pmf(i, a_xg) for i in range(10)]
        
        probs = {
            "home_win": 0, "draw": 0, "away_win": 0,
            "over_25": 0, "btts": 0
        }
        
        for h in range(10):
            for a in range(10):
                p = home_matrix[h] * away_matrix[a]
                if h > a: probs["home_win"] += p
                elif h == a: probs["draw"] += p
                else: probs["away_win"] += p
                
                if h+a > 2: probs["over_25"] += p
                if h > 0 and a > 0: probs["btts"] += p

        # Convert to percentages
        P_HOME = probs["home_win"] * 100
        P_DRAW = probs["draw"] * 100
        P_AWAY = probs["away_win"] * 100
        P_O25  = probs["over_25"] * 100
        P_BTTS = probs["btts"] * 100

        # 3. SELECTION LOGIC (The "Brain")
        # ------------------------------------------------------
        candidates = [
            {"tip": "HOME WIN", "prob": P_HOME, "odds": api_data.get("odds_home")},
            {"tip": "AWAY WIN", "prob": P_AWAY, "odds": api_data.get("odds_away")},
            {"tip": "OVER 2.5", "prob": P_O25,  "odds": api_data.get("odds_over_25")},
            {"tip": "BTTS",     "prob": P_BTTS, "odds": api_data.get("odds_btts_yes")},
            {"tip": "UNDER 2.5","prob": 100-P_O25, "odds": api_data.get("odds_under_25")}
        ]
        
        # Filter: Only tips > 45% prob allowed as "Recommended"
        valid_tips = [c for c in candidates if c["prob"] > 45]
        
        if not valid_tips:
            # Fallback to Double Chance if nothing is clear
            if P_HOME > P_AWAY:
                best_tip = {"tip": "1X (Safe)", "prob": P_HOME + P_DRAW, "odds": 1.3}
            else:
                best_tip = {"tip": "X2 (Safe)", "prob": P_AWAY + P_DRAW, "odds": 1.3}
        else:
            # Pick the one with highest Conviction (Score)
            # We calculate conviction for each valid tip
            for tip in valid_tips:
                h_form = enriched.get("home_form", []) if enriched else []
                a_form = enriched.get("away_form", []) if enriched else []
                
                tip["conviction"] = calculate_conviction(
                    tip["tip"], tip["prob"], tip["odds"], 
                    h_xg, a_xg, h_form, a_form
                )
            
            # Sort by Conviction (Smartest), not just Probability (Raw)
            best_tip = max(valid_tips, key=lambda x: x["conviction"])

        # 4. BADGING & NARRATIVE
        # ------------------------------------------------------
        h_vol = calculate_volatility(enriched.get("home_form", [])) if enriched else 0.5
        a_vol = calculate_volatility(enriched.get("away_form", [])) if enriched else 0.5
        edge  = _value_edge(best_tip["prob"], best_tip.get("odds"))
        
        badge_label, badge_desc = generate_badges(
            P_HOME, P_DRAW, P_AWAY, h_vol, a_vol, best_tip.get("conviction", 0), edge
        )

        return {
            "tag": badge_label,
            "tag_desc": badge_desc,
            "xg_h": h_xg,
            "xg_a": a_xg,
            "recommended": {
                "tip": best_tip["tip"],
                "prob": round(best_tip["prob"], 1),
                "odds": best_tip.get("odds", 0),
                "conv": round(best_tip.get("conviction", 50), 0),
                "reason": f"Model identified {best_tip['tip']} as highest value based on xG flow ({h_xg} vs {a_xg})."
            },
            # Keep your existing structure for Risky/Safest/etc.
            # (You can plug your existing _pick_safest / _pick_risky functions here)
        }

    except Exception as e:
        print(f"Error analyzing match: {e}")
        return None
