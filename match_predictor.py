import requests

# YOUR NEW KEY: 
API_KEY = 'YOUR_ALLSPORTS_API_KEY' 
BASE_URL = "https://apiv2.allsportsapi.com/football/"

def get_match_analysis(match_id):
    try:
        # We use 'Predictions' method and 'matchId' parameter
        params = {'met': 'Predictions', 'APIkey': API_KEY, 'matchId': match_id}
        r = requests.get(BASE_URL, params=params).json()
        
        # Check if the API actually returned a result
        if not r.get('result') or len(r['result']) == 0:
            return {"error": "Data Not Available"}
        
        data = r['result'][0]
        h_n, a_n = data.get('home_team_name', 'Home'), data.get('away_team_name', 'Away')
        
        # PROBABILITIES (Convert to float safely)
        h_p = float(data.get('prob_HW', 0))
        a_p = float(data.get('prob_AW', 0))
        o25_p = float(data.get('prob_O', 0))
        btts_p = float(data.get('prob_bts', 0))
        d_p = float(data.get('prob_D', 0))

        # LOGIC FOR TAGS
        tag = "BALANCED"
        if h_p > 70: tag = "STRONG HOME EDGE"
        elif a_p > 70: tag = "STRONG AWAY EDGE"
        elif o25_p > 75: tag = "HIGH SCORING MATCH"

        # TIERED TIPS
        rec = f"{h_n} WIN" if h_p > a_p else f"{a_n} WIN"
        alt = "OVER 1.5 GOALS" if o25_p > 45 else "DOUBLE CHANCE"
        risk = "DRAW" if d_p > 30 else f"{h_n} & GG"

        return {
            "h_name": h_n, "a_name": a_n,
            "h_logo": data.get('home_team_logo', ''), "a_logo": data.get('away_team_logo', ''),
            "tag": tag, "vol": "MODERATE",
            "rec": {"t": rec, "p": max(h_p, a_p), "r": ["Recent scoring trend", "Tactical advantage"]},
            "alt": {"t": alt, "p": o25_p + 15},
            "risk": {"t": risk, "p": d_p if d_p > 0 else 25},
            "h_form": ["W", "D", "W", "L", "W"], # Placeholder for visual
            "a_form": ["L", "L", "D", "W", "L"],
            "stats": {"h_avg": "1.7", "a_avg": "1.1"}
        }
    except Exception as e:
        return {"error": str(e)}
