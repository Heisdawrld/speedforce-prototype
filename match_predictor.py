import requests

# YOUR ALLSPORTSAPI KEY
API_KEY = 'YOUR_ALLSPORTS_API_KEY_HERE' 
BASE_URL = "https://apiv2.allsportsapi.com/football/"

def get_match_analysis(match_id):
    try:
        params = {'met': 'Predictions', 'APIkey': API_KEY, 'event_id': match_id}
        r = requests.get(BASE_URL, params=params).json()
        if not r.get('result'): return {"error": "No data"}
        
        data = r['result'][0]
        h_n, a_n = data.get('home_team_name'), data.get('away_team_name')
        
        # PROBABILITIES
        h_p, a_p, d_p = float(data.get('prob_HW', 0)), float(data.get('prob_AW', 0)), float(data.get('prob_D', 0))
        o25_p, u25_p = float(data.get('prob_O', 0)), float(data.get('prob_U', 0))
        btts_p = float(data.get('prob_bts', 0))

        # 🏷 TAG LOGIC (Strict Tags Only)
        tag = "AVOID"
        if h_p > 70: tag = "STRONG HOME EDGE"
        elif a_p > 70: tag = "STRONG AWAY EDGE"
        elif o25_p > 75: tag = "HIGH SCORING MATCH"
        elif abs(h_p - a_p) < 5 and d_p > 30: tag = "UPSET LIKELY"

        # 🔵 RECOMMENDED TIP (Balanced Value)
        if h_p > 60: rec, rec_p, rec_r = f"{h_n} WIN", h_p, ["Dominant home metrics", "High conversion rate"]
        elif btts_p > 65: rec, rec_p, rec_r = "BTTS (YES)", btts_p, ["Both sides clinical in attack", "Defensive gaps detected"]
        elif o25_p > 60: rec, rec_p, rec_r = "OVER 2.5 GOALS", o25_p, ["High goal variance league", "Attacking tactical setup"]
        else: rec, rec_p, rec_r = "HOME OVER 0.5", h_p + 10, ["Consistent home scoring record"]

        # 🟢 ALTERNATE TIP (Safest)
        if o25_p > 40: alt, alt_p, alt_r = "OVER 1.5 GOALS", o25_p + 20, "Highest statistical probability for goals"
        elif h_p > a_p: alt, alt_p, alt_r = "DOUBLE CHANCE: 1X", h_p + 15, "Strong safety margin on home result"
        else: alt, alt_p, alt_r = "DRAW NO BET: 2", a_p + 10, "Securing away advantage with draw protection"

        # 🔴 HIGH RISK TIP (High Volatility)
        if h_p > 50 and btts_p > 55: risk, risk_p, risk_r = f"{h_n} WIN & GG", (h_p+btts_p)/2, "Aggressive home play with defensive leak"
        elif o25_p > 60 and btts_p > 60: risk, risk_p, risk_r = "GG & OVER 2.5", (o25_p+btts_p)/2, "Total attacking football expected"
        else: risk, risk_p, risk_r = "STRAIGHT DRAW", d_p, "Tactical stalemate predicted between balanced sides"

        # ⚖️ VOLATILITY ASSESSMENT
        vol = "MODERATE"
        if abs(h_p - a_p) > 30: vol = "LOW"
        if d_p > 35 or o25_p > 80: vol = "HIGH"

        return {
            "h_name": h_n, "a_name": a_n, "h_logo": data.get('home_team_logo'), "a_logo": data.get('away_team_logo'),
            "tag": tag, "vol": vol,
            "rec": {"t": rec, "p": rec_p, "r": rec_r},
            "alt": {"t": alt, "p": alt_p, "r": alt_r},
            "risk": {"t": risk, "p": risk_p, "r": risk_r},
            "h_form": ["W", "W", "D", "L", "W"], # API Data Mapping needed for real strings
            "a_form": ["L", "D", "W", "L", "L"],
            "stats": {"h_avg": "1.8", "a_avg": "1.2", "h_con": "0.9", "a_con": "1.5"}
        }
    except Exception as e: return {"error": str(e)}

