"""
scheduler.py -- Settlement + Morning Job
Uses data.py (API-Football) for fixture results.
Triggered by UptimeRobot hitting /api/morning and /api/settle
"""
import time
from datetime import datetime, timezone, timedelta
import data as D, database

WAT = 1
def now_wat(): return datetime.now(timezone.utc)+timedelta(hours=WAT)

def run_morning_job():
    """Fetch today's fixtures and log predictions."""
    today = now_wat().date()
    print(f"[morning] Starting for {today}")
    fixtures = D.fixtures_for_date(str(today))
    print(f"[morning] {len(fixtures)} fixtures")

    saved=0; errors=0
    import match_predictor as mp
    for c in fixtures:
        if not c.get("is_ns"): continue
        try:
            h_id=c["home_id"]; a_id=c["away_id"]
            lg_id=c["league_id"]; season=c.get("season",2025)
            h_form = D.get_form(h_id, lg_id, season, last=5) if h_id else []
            a_form = D.get_form(a_id, lg_id, season, last=5) if a_id else []
            stds   = D.get_standings(lg_id, season)
            h_std  = stds.get(h_id) or stds.get(c["home"])
            a_std  = stds.get(a_id) or stds.get(c["away"])
            xg_h   = D.estimate_xg(h_form, h_std, True)
            xg_a   = D.estimate_xg(a_form, a_std, False)
            hw,dw,aw,o25,o15,bt = D.poisson_probs(xg_h, xg_a)
            o35    = round(max(o25-22,4),1)
            tip,prob,conv,odds,_ = mp._pick_recommended(
                hw,dw,aw,o15,o25,o35,bt,bt,round(100-bt,1),
                xg_h,xg_a,h_form,a_form,h_std,a_std,
                None,None,None,None,None,None)
            fair = round(100/max(prob,1),2)
            tag  = "RELIABLE" if conv>=55 else "SOLID" if conv>=40 else "MONITOR"
            database.log_prediction(
                match_id=c["id"], league_id=lg_id,
                league_name=c["league"], home_team=c["home"], away_team=c["away"],
                match_date=c["kickoff"][:16], market=tip, probability=prob,
                fair_odds=fair, bookie_odds=None, edge=None,
                confidence=conv, xg_home=xg_h, xg_away=xg_a,
                likely_score="", tag=tag, reliability_score=conv)
            saved+=1
        except Exception as e:
            print(f"[morning] {c.get('id')}: {e}"); errors+=1

    print(f"[morning] Done: {saved} saved, {errors} errors")
    return {"status":"ok","saved":saved,"errors":errors,"total":len(fixtures)}

def run_settlement_job():
    """Settle finished predictions."""
    pending = database.get_recent_pending(limit=100)
    if not pending: return {"status":"ok","settled":0}

    print(f"[settle] {len(pending)} pending")
    settled=not_ready=errors=0
    ids = list(set(p["match_id"] for p in pending))

    for mid in ids:
        try:
            raw = D.get_fixture_by_id(mid)
            if not raw: not_ready+=1; continue
            fx     = raw.get("fixture",{})
            status = fx.get("status",{}).get("short","NS")
            if status not in ("FT","AET","PEN"): not_ready+=1; continue
            gs     = raw.get("goals",{})
            h_sc   = gs.get("home"); a_sc = gs.get("away")
            if h_sc is None: not_ready+=1; continue

            for p in [x for x in pending if x["match_id"]==mid]:
                database.settle_prediction(mid, p["market"], int(h_sc), int(a_sc))
                settled+=1

            # Team memory
            teams = raw.get("teams",{})
            lg    = raw.get("league",{}).get("name","")
            h_nm  = teams.get("home",{}).get("name","")
            a_nm  = teams.get("away",{}).get("name","")
            if h_nm and a_nm:
                database.update_team_memory(h_nm,a_nm,lg,int(h_sc),int(a_sc))

            time.sleep(0.05)
        except Exception as e:
            print(f"[settle] {mid}: {e}"); errors+=1

    print(f"[settle] {settled} settled, {not_ready} not ready, {errors} errors")
    return {"status":"ok","settled":settled,"not_ready":not_ready,"errors":errors}
