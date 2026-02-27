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

    for m in all_matches:
        try:
            event    = m.get("event", {})
            raw_ts   = event.get("event_timestamp") or event.get("event_date","")
            if not raw_ts:
                continue

            # Parse date
            try:
                if isinstance(raw_ts, (int, float)):
                    match_dt = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
                else:
                    raw_ts = str(raw_ts).replace("Z","+00:00")
                    match_dt = datetime.fromisoformat(raw_ts)
                    if match_dt.tzinfo is None:
                        match_dt = match_dt.replace(tzinfo=timezone.utc)
            except:
                continue

            match_date_wat = (match_dt + timedelta(hours=WAT_OFFSET)).date()

            # Only today and tomorrow
            if match_date_wat not in (today_wat, tomorrow_wat):
                continue

            match_id = m.get("id")
            if not match_id:
                continue

            league   = event.get("league", {})
            l_id     = league.get("id", 0)
            l_name   = league.get("name", "")
            h        = event.get("home_team", "Home")
            a        = event.get("away_team", "Away")

            # Run prediction (no enrichment -- saves API quota)
            res = match_predictor.analyze_match(m, l_id, None)
            if not res:
                errors += 1
                continue

            rec = res["recommended"]

            # Save to DB (INSERT OR IGNORE -- won't overwrite existing)
            database.log_prediction(
                match_id        = match_id,
                league_id       = l_id,
                league_name     = l_name,
                home_team       = h,
                away_team       = a,
                match_date      = match_dt.strftime("%Y-%m-%d %H:%M"),
                market          = rec["tip"],
                probability     = rec["prob"],
                fair_odds       = rec["odds"],
                bookie_odds     = None,
                edge            = rec.get("edge"),
                confidence      = res["confidence"],
                xg_home         = res["xg_h"],
                xg_away         = res["xg_a"],
                likely_score    = "",
                tag             = res.get("tag",""),
                reliability_score = res.get("confidence", 50)
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

    for match_id in match_ids:
        try:
            data = _bzz_get(f"/predictions/{match_id}/")
            if not data:
                not_ready += 1
                continue

            event  = data.get("event", {})
            status = event.get("status", "").lower()

            # Only settle finished matches
            if status not in ("ft", "finished", "aet", "pen", "awarded"):
                not_ready += 1
                continue

            # Get final score
            h_score = event.get("home_score") or event.get("ft_home_score")
            a_score = event.get("away_score") or event.get("ft_away_score")

            # Try nested score object
            if h_score is None:
                score = event.get("score", {})
                h_score = score.get("home") or score.get("ft_home")
                a_score = score.get("away") or score.get("ft_away")

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

            # Update team memory after settlement
            _update_team_memory(data, markets_for_match)

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


def _update_team_memory(match_data, settled_markets):
    """
    After a match settles, update team memory in DB.
    Stores per-team historical accuracy for calibration.
    """
    import database

    event  = match_data.get("event", {})
    h_team = event.get("home_team","")
    a_team = event.get("away_team","")
    league = event.get("league",{}).get("name","")

    if not h_team or not a_team:
        return

    for market_row in settled_markets:
        result = market_row.get("result")
        market = market_row.get("market","")
        prob   = market_row.get("probability", 50)

        if result not in ("WIN","LOSS"):
            continue

        win = 1 if result == "WIN" else 0
        database.update_team_memory(h_team, a_team, league, market, prob, win)
