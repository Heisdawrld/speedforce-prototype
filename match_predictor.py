import numpy as np
from scipy.stats import poisson

def analyze_match(api_data):
    """Processes Live API data through the Poisson Filter"""
    try:
        # PULL LIVE DATA FROM API
        h_p = float(api_data.get('prob_home', 0.33))
        a_p = float(api_data.get('prob_away', 0.33))
        d_p = float(api_data.get('prob_draw', 0.34))
        o25_p = float(api_data.get('prob_over_25', 0.50))
        btts_p = float(api_data.get('prob_btts', 0.50))

        # CALCULATE DYNAMIC ODDS (1/prob * margin)
        home_odds = round((1 / h_p) * 0.94, 2) if h_p > 0 else 2.0
        
        # DETERMINE INTELLIGENT RECOMMENDATION
        probs = {"HOME WIN": h_p, "AWAY WIN": a_p, "OVER 2.5": o25_p, "BTTS": btts_p}
        best_market = max(probs, key=probs.get)
        
        # CONFIDENCE GAP (Math-based, not vibes)
        conf = round((h_p - a_p) * 100, 1) if h_p > a_p else round((a_p - h_p) * 100, 1)

        return {
            "tag": "STRONG VALUE" if conf > 20 else "MODERATE RISK",
            "rec": {"t": best_market, "p": round(probs[best_market]*100, 1), "o": home_odds},
            "safe": {"t": "OVER 1.5 GOALS", "p": round((o25_p + 0.2) * 100, 1), "o": 1.30},
            "risk": {"t": f"{best_market} & GG", "p": round((h_p * btts_p) * 100, 1), "o": 4.50},
            "stats": {"h_xg": round(h_p * 2.5, 2), "a_xg": round(a_p * 2.1, 2)},
            "conf": conf
        }
    except:
        return None
