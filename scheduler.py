"""
scheduler.py -- Sportmonks Automation Engine
"""
import time
from datetime import datetime, timezone
import sportmonks
import match_predictor
import database

def run_morning_job():
    """
    Fetches TODAY's fixtures from Sportmonks, analyzes them, 
    and saves the 'Smart' prediction to the database.
    """
    print("[Scheduler] Starting Morning Analysis...")
    
    # 1. Get Fixtures
    fixtures = sportmonks.get_fixtures_today()
    if not fixtures:
        print("[Scheduler] No fixtures found today.")
        return {"status": "empty"}
        
    count = 0
    errors = 0
    
    # 2. Loop & Analyze
    for f in fixtures:
        try:
            f_id = f.get("id")
            
            # CRITICAL: We must 'Enrich' to get stats/xG
            # This makes the prediction smart.
            enriched = sportmonks.enrich_match(f_id)
            
            # Analyze
            analysis = match_predictor.analyze_match(enriched)
            rec = analysis["recommended"]
            badge = analysis["badges"]
            data = analysis["data"]
            
            # Save to DB
            h_name = enriched.get("home_name")
            a_name = enriched.get("away_name")
            
            database.log_prediction(
                match_id=f_id,
                league_id=enriched.get("league_id", 0),
                league_name=enriched.get("league_name", ""),
                home_team=h_name,
                away_team=a_name,
                match_date=enriched.get("kickoff", ""),
                market=rec["tip"],
                probability=rec["prob"],
                fair_odds=rec["fair_odds"],
                confidence=rec["conviction"],
                xg_home=data["xg_h"],
                xg_away=data["xg_a"],
                tag=badge["label"] # Saves "⚠️ VOLATILE" or "🛡️ BANKER"
            )
            count += 1
            
            # Rate Limit Protection (Optional)
            time.sleep(0.05) 
            
        except Exception as e:
            print(f"Error analyzing match {f.get('id')}: {e}")
            errors += 1
            
    return {"status": "success", "analyzed": count, "errors": errors}

def run_settlement_job():
    # ... (Your existing settlement logic is fine) ...
    pass
