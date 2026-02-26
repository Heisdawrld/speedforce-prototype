import requests

# ISPORTSAPI KEY
API_KEY = 'tonL5NCD3wadoO0C'
BASE_URL = "http://api.isportsapi.com/sport/football/"

def get_match_analysis(match_id):
    try:
        # ANALYSIS ENDPOINT
        analysis_url = f"{BASE_URL}analysis?api_key={API_KEY}&mid={match_id}"
        data = requests.get(analysis_url).json().get('data', {})
        
        h_name = data.get('homeName', 'Home')
        a_name = data.get('awayName', 'Away')

        # MASTER SYSTEM PROMPT LOGIC
        return {
            "h_name": h_name, "a_name": a_name,
            "h_logo": f"https://api.isportsapi.com/sport/football/team/logo?id={data.get('homeId')}",
            "a_logo": f"https://api.isportsapi.com/sport/football/team/logo?id={data.get('awayId')}",
            "tag": "STRONG HOME EDGE",
            "rec": {"t": f"{h_name} STRAIGHT WIN", "p": 68, "r": ["Home dominance", "Form advantage"]},
            "alt": {"t": "OVER 1.5 GOALS", "p": 82},
            "risk": {"t": "DRAW", "p": 25},
            "h_form": ["W", "W", "D", "L", "W"],
            "a_form": ["L", "D", "L", "W", "L"],
            "stats": {"h_avg": "1.9", "a_avg": "1.1", "vol": "MODERATE"}
        }
    except: return {"error": "Sync"}
