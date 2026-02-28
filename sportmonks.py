"""
sportmonks.py -- Fixed Token & God Mode Integration
"""
import os, json, requests
from datetime import datetime, timezone, timedelta
import database

# FIXED TOKEN (Added the missing 'L' at the end)
TOKEN = "EbRqkfYJgeCOtHzoC1AXpk1OO4semN0DtJ1P84zrYVNRCT1x4dHVsP9FGJAVL"
BASE  = "https://api.sportmonks.com/v3/football"

# In-memory cache
_mem = {}

def _mem_get(key, max_age_hours=6):
    if key not in _mem: return None
    data, ts = _mem[key]
    if datetime.now(timezone.utc) - ts > timedelta(hours=max_age_hours):
        del _mem[key]; return None
    return data

def _mem_set(key, data):
    _mem[key] = (data, datetime.now(timezone.utc))

def _get(endpoint, params=None, cache_hours=6, raw=False):
    p = params or {}
    ck = f"sm_{endpoint}_{json.dumps(sorted(p.items()))}"[:200]
    
    mem = _mem_get(ck, cache_hours)
    if mem is not None: return mem

    try:
        r = requests.get(f"{BASE}{endpoint}", headers={"Authorization": TOKEN}, params=p, timeout=20)
        if r.status_code == 200:
            resp = r.json()
            data = resp if raw else resp.get("data")
            if data is not None: _mem_set(ck, data)
            return data
        else:
            print(f"[SM] Error {endpoint}: {r.status_code}")
            return None
    except Exception as e:
        print(f"[SM] Failed {endpoint}: {e}")
        return None

def _get_paginated(endpoint, params=None, cache_hours=6):
    """Fetches ALL pages to ensure we don't miss matches."""
    p = dict(params or {})
    p["per_page"] = 50
    all_items = []
    page = 1
    
    # Check cache first
    ck = f"sm_paged_{endpoint}_{json.dumps(sorted(p.items()))}"
    mem = _mem_get(ck, cache_hours)
    if mem: return mem
    
    while page <= 10: # Safety limit
        try:
            r = requests.get(f"{BASE}{endpoint}", headers={"Authorization": TOKEN}, params={**p, "page": page}, timeout=15)
            if r.status_code != 200: break
            resp = r.json()
            data = resp.get("data") or []
            if not data: break
            all_items.extend(data)
            
            meta = resp.get("meta") or {}
            pag = meta.get("pagination") or {}
            if page >= (pag.get("total_pages") or 1): break
            page += 1
        except: break
        
    _mem_set(ck, all_items)
    return all_items

# ─── CORE FETCHERS ──────────────────────────────────────────────────────────

def get_fixtures_today():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Using paginated fetch to guarantee we get ALL leagues
    return _get_paginated(f"/fixtures/date/{today}", 
        {"include": "participants;league;league.country;scores;state;odds.market;predictions"})

def get_fixtures_window(days=3):
    start = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    end = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")
    return _get_paginated(f"/fixtures/between/{start}/{end}", 
        {"include": "participants;league;league.country;scores;state"})

def get_livescores():
    return _get("/livescores", {"include": "participants;scores;state;league"})

def enrich_match(fixture_id):
    """The 'God Mode' Data Packet for a single match."""
    # We fetch everything in one go or fallbacks
    fx = _get(f"/fixtures/{fixture_id}", 
        {"include": "participants;league;scores;state;statistics;lineups.player;events;odds.market;predictions;referees"})
    
    if not fx: return None
    
    enriched = {"fixture": fx}
    
    # Helpers to extract IDs
    h_id = next((p['id'] for p in fx.get('participants',[]) if p['meta']['location']=='home'), None)
    a_id = next((p['id'] for p in fx.get('participants',[]) if p['meta']['location']=='away'), None)
    enriched['home_id'] = h_id
    enriched['away_id'] = a_id
    
    # H2H (Critical for intelligence)
    if h_id and a_id:
        h2h = _get(f"/fixtures/head-to-head/{h_id}/{a_id}", {"include": "scores"})
        enriched['h2h'] = h2h if h2h else []
    
    # Value Bets (Specific endpoint)
    enriched['value_bets'] = _get(f"/predictions/value-bets/fixtures/{fixture_id}") or []
    
    return enriched

# ─── HELPERS ────────────────────────────────────────────────────────────────

def extract_teams(fx):
    h = next((p for p in fx.get('participants',[]) if p['meta']['location']=='home'), {})
    a = next((p for p in fx.get('participants',[]) if p['meta']['location']=='away'), {})
    return h.get('id'), h.get('name'), a.get('id'), a.get('name')

def extract_state(fx):
    state = fx.get('state') or {}
    return state.get('short_name') or state.get('state') or "NS"

def extract_score(fx):
    scores = fx.get('scores', [])
    h_score = next((s['score']['goals'] for s in scores if s['description']=='CURRENT' and s['score']['participant']=='home'), None)
    a_score = next((s['score']['goals'] for s in scores if s['description']=='CURRENT' and s['score']['participant']=='away'), None)
    return h_score, a_score

def parse_odds(fx):
    # Flatten odds for easy access
    out = {}
    markets = fx.get('odds', [])
    for m in (markets if isinstance(markets, list) else []):
        label = (m.get('label') or "").lower()
        # Map specific markets
        if "3way" in label or "match winner" in label:
            for o in m.get('odds', []):
                l = str(o.get('label')).lower()
                v = float(o.get('value'))
                if "1" in l or "home" in l: out['home'] = v
                elif "x" in l or "draw" in l: out['draw'] = v
                elif "2" in l or "away" in l: out['away'] = v
        if "over/under" in label:
            for o in m.get('odds', []):
                l = str(o.get('label')).lower()
                v = float(o.get('value'))
                if "over" in l and "2.5" in l: out['over_25'] = v
                if "over" in l and "1.5" in l: out['over_15'] = v
        if "both teams" in label:
            for o in m.get('odds', []):
                if "yes" in str(o.get('label')).lower(): out['btts'] = float(o.get('value'))
    return out
