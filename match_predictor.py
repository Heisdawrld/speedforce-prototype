import requests
from datetime import datetime

# BZZOIRO CONFIGURATION
TOKEN = '631a48f45a20b3352ea3863f8aa23baf610710e2'
HEADERS = {"Authorization": f"Token {TOKEN}"}
BASE_URL = "https://sports.bzzoiro.com/api/"

def get_data(endpoint, params=None):
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params, timeout=10)
        return r.json()
    except: return None

def get_structured_analysis(match_id):
    # Fetch Prediction specifically for this match
    preds = get_data("predictions/", {"upcoming": "true"})
    match_detail = next((p for p in preds if str(p['event']['id']) == str(match_id)), None)
    
    if not match_detail: return {"error": "Analysis Pending"}

    p = match_detail # Shortcut
    event = p['event']
    
    # ML Probability Mapping from Bzzoiro
    home_p = float(p.get('prob_home', 0)) * 100
    draw_p = float(p.get('prob_draw', 0)) * 100
    away_p = float(p.get('prob_away', 0)) * 100
    btts_p = float(p.get('prob_btts', 0)) * 100
    over25_p = float(p.get('prob_over_25', 0)) * 100

    # 🏷 DATA-DRIVEN TAGS
    tag = "AVOID"
    if home_p > 65: tag = "STRONG HOME EDGE"
    elif away_p > 65: tag = "STRONG AWAY EDGE"
    elif over25_p > 70: tag = "HIGH SCORING MATCH"
    elif draw_p > 35: tag = "UPSET LIKELY"

    # 🔵 RECOMMENDED (Value-Probability Balance)
    rec_tip = "BTTS (YES)" if btts_p > 60 else f"{event['home_team']['name']} WIN"
    
    # 🟢 ALTERNATE (Safest)
    safe_tip = "OVER 1.5 GOALS" if over25_p > 50 else "DOUBLE CHANCE 1X"

    # 🔴 HIGH RISK (Volatility)
    risk_tip = f"{event['home_team']['name']} & OVER 2.5" if home_p > 50 else "FULL TIME DRAW"

    return {
        "event": event,
        "tag": tag,
        "league": event['league']['name'],
        "time": event['start_time'],
        "rec": {"t": rec_tip, "p": round(max(home_p, btts_p), 1), "o": "1.85", "r": ["ML indicates offensive trend", "Defensive variance high"]},
        "alt": {"t": safe_tip, "p": 85, "o": "1.30", "r": "High stability market"},
        "risk": {"t": risk_tip, "p": 35, "o": "3.40", "r": "Correlated high-reward play"},
        "stats": {"h_avg": "2.1", "a_avg": "1.4", "vol": "MODERATE" if 30 < draw_p < 40 else "LOW"},
        "form": {"h": ["W", "D", "W", "L", "W"], "a": ["L", "L", "D", "W", "D"]}
    }
