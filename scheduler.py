"""
scheduler.py -- Automation Engine
"""
import sportmonks
import match_predictor
import database

def run_morning_job():
    print("Running GOD MODE Morning Analysis...")
    
    # 1. Get All Fixtures
    matches = sportmonks.get_fixtures_today()
    if not matches:
        return {"status": "empty", "message": "No matches today"}
        
    count = 0
    errors = 0
    
    for m in matches:
        try:
            # 2. Fetch The Super Packet
            data = sportmonks.get_match_details(m['id'])
            if not data: continue
            
            # 3. Analyze
            res = match_predictor.analyze_match(data)
            if not res: continue
            
            tips = res['tips']
            rec = tips.get('recommended')
            
            # 4. Save to DB (Primary Tip)
            # You can expand database.log_prediction to take safest/risky too if you want
            if rec:
                database.log_prediction(
                    match_id=m['id'],
                    league_id=m.get('league_id', 0),
                    league_name="Unknown", # You can fetch league name if needed
                    home_team=res['teams']['home'],
                    away_team="Away",
                    match_date=m.get('starting_at', ''),
                    market=rec['type'],
                    probability=rec['prob'],
                    fair_odds=rec['odds'],
                    confidence=rec['prob'], # Use prob as confidence
                    xg_home=0, xg_away=0, # Placeholder if no xG
                    tag="VALUE" if rec['ev'] > 0 else "STANDARD"
                )
                count += 1
                
        except Exception as e:
            print(f"Error on match {m.get('id')}: {e}")
            errors += 1
            
    return {"status": "success", "analyzed": count, "errors": errors}

def run_settlement_job():
    # Placeholder for settlement logic
    return {"status": "success", "message": "Settlement not implemented in this snippet"}
