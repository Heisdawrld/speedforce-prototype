import math

def calculate_edge(prob, odds=None):
    """Calculates value edge against market friction (simulated or real)"""
    if not odds:
        # Simulate a 5% margin bookmaker if live odds aren't passed
        odds = round((1 / prob) * 0.95, 2)
    edge = (prob * odds) - 1
    return round(edge * 100, 2), odds

def get_volatility(h_p, a_p, d_p):
    """Volatility Index: Based on the spread of outcomes"""
    spread = max(h_p, a_p, d_p) - min(h_p, a_p, d_p)
    if spread < 0.2: return "HIGH"
    if spread < 0.4: return "MODERATE"
    return "LOW"

def analyze_match(data):
    """Processes raw BetsAPI data into the Master Prompt format"""
    # Extract raw probabilities from the API confidence or defaults
    conf = data.get("confidence", 50) / 100
    h_p = data.get("prob_home", conf * 0.6)
    a_p = data.get("prob_away", (1-conf) * 0.4)
    d_p = 1 - (h_p + a_p)
    o25_p = data.get("prob_over_25", 0.50)
    
    # Tier 1: RECOMMENDED (Value Edge)
    edge, calculated_odds = calculate_edge(h_p if h_p > a_p else a_p)
    rec_tip = "HOME WIN" if h_p > a_p else "AWAY WIN"
    
    # Tier 2: SAFE (Highest Prob)
    safe_p = o25_p + (1 - o25_p) * 0.6 # Derived Over 1.5
    
    # Tier 3: HIGH RISK
    risk_tip = f"{rec_tip} & GG"
    
    return {
        "tag": "STRONG HOME EDGE" if h_p > 0.6 else "UPSET LIKELY" if d_p > 0.35 else "HIGH SCORING",
        "rec": {"t": rec_tip, "p": round(max(h_p, a_p)*100, 1), "o": calculated_odds, "e": edge},
        "safe": {"t": "OVER 1.5 GOALS", "p": round(safe_p*100, 1), "o": 1.28},
        "risk": {"t": risk_tip, "p": round((h_p * 0.5)*100, 1), "o": 3.85},
        "vol": get_volatility(h_p, a_p, d_p),
        "stats": {
            "h_gls": "2.1", "a_gls": "1.4", 
            "h_con": "0.9", "a_con": "1.8"
        }
    }
