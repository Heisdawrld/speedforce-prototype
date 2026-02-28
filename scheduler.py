"""
scheduler.py -- Autonomous Prediction + Settlement Engine

TWO JOBS:
  morning_job()   -- 6am WAT -- predict every match today
  settlement_job() -- every 3hrs -- settle finished matches

Both are triggered via /api/morning and /api/settle endpoints.
Set up as Render Cron Jobs:
  0 5 * * *   curl https://your-site.onrender.com/api/morning
  0 */3 * * * curl https://your-site.onrender.com/api/settle
"""

import json, time, requests
from datetime import datetime, timezone, timedelta

BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL  = "https://sports.bzzoiro.com/api"
WAT_OFFSET = 1

def now_wat():
    return datetime.now(timezone.utc) + timedelta(hours=WAT_OFFSET)

def _bzz_get(path, params=None):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=headers,
                        params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[scheduler] {path} -> {e}")
        return {}

def _fetch_all_matches():
    """Fetch all predictions from Bzzoiro (all pages)."""
    all_matches = []
    page_url = f"{BASE_URL}/predictions/"
    headers  = {"Authorization": f"Token {BSD_TOKEN}"}
    page = 1

    while page_url and page <= 25:
        try:
            r = requests.get(page_url, headers=headers, timeout=15)
            r.raise_for_status()
            data    = r.json()
            results = data.get("results", [])
            all_matches.extend(results)
            page_url = data.get("next")
            page += 1
        except Exception as e:
            print(f"[scheduler] fetch stopped page {page}: {e}")
            break

    return all_matches

def run_morning_job():
    """
    Predict every match today + tomorrow.
    Saves all predictions to DB automatically.
    Returns summary dict.
    """
    import database, match_predictor

    today_wat    = now_wat().date()
    tomorrow_wat = today_wat + timedelta(days=1)

    print(f"[morning] Starting for {today_wat} WAT")

    all_matches = _fetch_all_matches()
    print(f"[morning] Fetched {len(all_matches)} total matches")

    saved = 0; skipped = 0; errors = 0

    import sportmonks as sm
    for m in all_matches:
        try:
            match_id = m.get("id")
            if not match_id: continue

            h_id, h_name, a_id, a_name = sm.extract_teams(m)
            if not h_name: continue

            league = m.get("league") or {}
            l_id   = league.get("id",0) if isinstance(league,dict) else 0
            l_name = league.get("name","") if isinstance(league,dict) else ""
            raw_ko = m.get("starting_at") or m.get("date","")

            # Get Sportmonks predictions
            preds_raw = sm.get_predictions(match_id)
            preds = sm.parse_predictions(preds_raw) if preds_raw else {}

            hw   = preds.get("home_win", 33.3)
            dw   = preds.get("draw", 33.3)
            aw   = preds.get("away_win", 33.3)
            o25  = preds.get("over_25", 45.0)
            btts = preds.get("btts", 45.0)

            best = max([("HOME WIN",hw),("DRAW",dw),("AWAY WIN",aw),
                        ("OVER 2.5",o25),("GG",btts)], key=lambda x: x[1])
            tip, prob = best
            fair_odds = round(100/max(prob,1), 2)

            try:
                match_dt = datetime.fromisoformat(
                    str(raw_ko).replace("Z","+00:00"))
                if match_dt.tzinfo is None:
                    match_dt = match_dt.replace(tzinfo=timezone.utc)
            except:
                match_dt = datetime.now(timezone.utc)

            database.log_prediction(
                match_id=match_id, league_id=l_id, league_name=l_name,
                home_team=h_name or "Home", away_team=a_name or "Away",
                match_date=match_dt.strftime("%Y-%m-%d %H:%M"),
                market=tip, probability=prob, fair_odds=fair_odds,
                bookie_odds=None, edge=None, confidence=prob,
                xg_home=None, xg_away=None, likely_score="",
                tag="MONITOR", reliability_score=prob
            )
            saved += 1

        except Exception as e:
            print(f"[morning] error on match {m.get('id')}: {e}")
            errors += 1

    result = {
        "status":   "ok",
        "date":     str(today_wat),
        "saved":    saved,
        "skipped":  skipped,
        "errors":   errors,
        "total_checked": len(all_matches),
    }
    print(f"[morning] Done: {saved} saved, {errors} errors")
    return result


def run_settlement_job():
    """
    Check all unsettled predictions and settle finished matches.
    Fetches final scores from Bzzoiro.
    Returns summary dict.
    """
    import database

    pending = database.get_recent_pending(limit=100)
    if not pending:
        return {"status": "ok", "settled": 0, "message": "no pending predictions"}

    print(f"[settle] Checking {len(pending)} pending predictions")

    settled = 0; not_ready = 0; errors = 0

    # Group by match_id to avoid duplicate API calls
    match_ids = list(set(p["match_id"] for p in pending))

    import sportmonks as sm
    for match_id in match_ids:
        try:
            data = sm.get_fixture_detail(match_id)
            if not data:
                not_ready += 1
                continue

            status = sm.extract_state(data)

            # Only settle finished matches
            if status.upper() not in ("FT","AET","PEN","FIN","FINISHED","AWARDED"):
                not_ready += 1
                continue

            # Get final score
            h_score, a_score = sm.extract_score(data)

            if h_score is None or a_score is None:
                not_ready += 1
                continue

            # Find all markets for this match and settle them
            markets_for_match = [p for p in pending if p["match_id"] == match_id]
            for p in markets_for_match:
                database.settle_prediction(
                    match_id   = match_id,
                    market     = p["market"],
                    home_score = int(h_score),
                    away_score = int(a_score)
                )
                settled += 1

            # Update team memory with real scores
            _update_team_memory(data, markets_for_match, h_score, a_score)

            time.sleep(0.1)  # be gentle with the API

        except Exception as e:
            print(f"[settle] error on match {match_id}: {e}")
            errors += 1

    result = {
        "status":    "ok",
        "settled":   settled,
        "not_ready": not_ready,
        "errors":    errors,
        "checked":   len(match_ids),
    }
    print(f"[settle] Done: {settled} settled, {not_ready} not ready, {errors} errors")
    return result


def _update_team_memory(match_data, settled_markets, h_score, a_score):
    """
    After a match settles, record REAL performance for both teams.
    Arsenal 3-1 Wolves:
      Arsenal  -> home WIN, scored 3, conceded 1
      Wolves   -> away LOSS, scored 1, conceded 3
    This is the real team intelligence -- not prediction accuracy.
    """
    import database

    event      = match_data.get("event", {})
    h_team     = event.get("home_team","")
    a_team     = event.get("away_team","")
    league     = event.get("league",{}).get("name","")
    raw_date   = event.get("event_date","")[:10]

    if not h_team or not a_team:
        return

    try:
        database.update_team_memory(
            home_team   = h_team,
            away_team   = a_team,
            league      = league,
            home_score  = int(h_score),
            away_score  = int(a_score),
            match_date  = raw_date
        )
        print(f"[memory] {h_team} {h_score}-{a_score} {a_team} -> stored")
    except Exception as e:
        print(f"[memory] error: {e}")

    # Also update market calibration (global hit rates per market type)
    try:
        for market_row in settled_markets:
            result = market_row.get("result")
            market = market_row.get("market","")
            prob   = market_row.get("probability", 50)
            if result not in ("WIN","LOSS"):
                continue
            win = 1 if result == "WIN" else 0
            database.update_market_calibration(market, prob, win)
    except Exception as e:
        print(f"[memory] calibration error: {e}")
