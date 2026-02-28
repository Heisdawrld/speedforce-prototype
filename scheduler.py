"""
scheduler.py -- Fixed Automation
"""
import sportmonks
import match_predictor
import database

def run_morning_job():
    print("Running Morning Analysis...")
    
    # 1. Fetch
    matches = sportmonks.get_fixtures_today() # Now uses fixed pagination
    count = 0
    
    # 2. Analyze & Save
    for m in matches:
        try:
            # We treat the match dict as 'fixture' for the analyzer
            # Ideally we enrich it, but for speed in scheduler we might do basic analysis
            # OR we call enrich_match(m['id']) for full power:
            enriched = sportmonks.enrich_match(m['id'])
            if not enriched: continue
            
            res = match_predictor.analyze_match(enriched)
            rec = res['tips']['recommended']
            
            # Save to DB
            if rec:
                database.log_prediction(
                    match_id=m['id'],
                    league_id=m.get('league_id',0),
                    league_name="League",
                    home_team=res['teams']['home'],
                    away_team=res['teams']['away'],
                    match_date=m.get('starting_at',''),
                    market=rec['sel'],
                    probability=rec['prob'],
                    fair_odds=rec['odds'],
                    confidence=rec['prob'],
                    xg_home=0, xg_away=0,
                    tag="VALUE"
                )
                count += 1
        except Exception as e:
            print(f"Scheduler Error {m.get('id')}: {e}")
            
    return {"status": "success", "analyzed": count}

def run_settlement_job():
    return {"status": "success"} # Placeholder
