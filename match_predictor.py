"""
match_predictor.py -- ProPredictor Conviction Engine v4

TIP STRUCTURE (as defined by user):
  RECOMMENDED TIP  -- 1X2, GG/NG, Overs/Unders, Team to Score
  SAFEST TIP       -- Over 1.5 Goals, Double Chance (1X/X2/12), Win Either Half
  RISKY MARKET     -- HT/FT, Combo (1X2+GG, 1X2+Overs, WIN+Overs)

Conviction engine scores each tip across:
  - Normalised probability
  - xG signal (independent creation data)
  - Form signal (from API Football real data)
  - Standing signal
  - Value edge vs bookmaker
"""

import math
try:
    import database as _db
    _HAS_DB = True
except ImportError:
    _HAS_DB = False

_calibration_cache = {"data": {}, "loaded_at": None}

def _get_calibration():
    """Load market calibration from DB. Cached 1 hour."""
    import time
    now = time.time()
    if (_calibration_cache["loaded_at"] is None or
            now - _calibration_cache["loaded_at"] > 3600):
        if _HAS_DB:
            try:
                _calibration_cache["data"] = _db.get_market_calibration()
                _calibration_cache["loaded_at"] = now
            except:
                pass
    return _calibration_cache["data"]

# -- Poisson -------------------------------------------------------------------

def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

# -- Form utilities ------------------------------------------------------------

FORM_WEIGHTS = [1.0, 1.2, 1.4, 1.6, 1.8]
FORM_VALUE   = {"W": 1.0, "D": 0.4, "L": 0.0}

def form_score(form_list):
    if not form_list:
        return 0.5
    results = [r.upper() for r in list(form_list)[-5:]]
    weights = FORM_WEIGHTS[-len(results):]
    score   = sum(FORM_VALUE.get(r, 0.5) * w for r, w in zip(results, weights))
    return round(score / sum(weights), 4)

def form_trend(form_list):
    if not form_list or len(form_list) < 3:
        return "STABLE"
    results = [r.upper() for r in list(form_list)[-5:]]
    vals    = [FORM_VALUE.get(r, 0.5) for r in results]
    recent  = sum(vals[-2:]) / 2
    earlier = sum(vals[:2]) / 2
    diff    = recent - earlier
    if diff >  0.25: return "RISING"
    if diff < -0.25: return "FALLING"
    return "STABLE"

def momentum_score(h_form, a_form, h_xg, a_xg):
    h_f = form_score(h_form)
    a_f = form_score(a_form)
    total_xg   = max(h_xg + a_xg, 0.1)
    h_xg_share = h_xg / total_xg
    a_xg_share = a_xg / total_xg
    h_mom = round((h_f * 0.6 + h_xg_share * 0.4) * 100, 1)
    a_mom = round((a_f * 0.6 + a_xg_share * 0.4) * 100, 1)
    h_trend = form_trend(h_form)
    a_trend = form_trend(a_form)
    gap = abs(h_mom - a_mom)
    if gap < 8:
        narrative = "Momentum evenly balanced -- neither side holds a clear edge"
    elif h_mom > a_mom:
        narrative = f"Home side carrying the momentum ({h_trend.lower()} form)"
    else:
        narrative = f"Away side the in-form team ({a_trend.lower()} trajectory)"
    return {
        "home": h_mom, "away": a_mom,
        "h_trend": h_trend, "a_trend": a_trend,
        "narrative": narrative
    }

def value_edge(market_prob, bookmaker_odds):
    if not bookmaker_odds or bookmaker_odds <= 1.0:
        return None
    implied = 1 / bookmaker_odds
    edge    = (market_prob / 100) - implied
    return round(edge * 100, 1)

def style_profile(h_xg, a_xg, btts):
    total = h_xg + a_xg
    if total >= 3.0:   s = "High-scoring encounter expected -- both teams creating freely"
    elif total >= 2.2: s = "Open game -- goals likely from both ends"
    elif total >= 1.5: s = "Balanced midfield contest -- goals possible but not guaranteed"
    else:              s = "Defensive game likely -- set pieces and moments of quality will decide"
    if btts >= 65:     s += " * Both teams likely to find the net"
    elif btts <= 35:   s += " * Clean sheet on the cards"
    return s

# -- xG / Form / Standing signals ---------------------------------------------

def _xg_signal(tip, h_xg, a_xg):
    total = max(h_xg + a_xg, 0.1)
    h_dom = h_xg / total
    a_dom = a_xg / total
    if tip == "HOME WIN":
        return min(h_dom / 0.6, 1.0) if h_dom > 0.5 else h_dom * 0.5
    elif tip == "AWAY WIN":
        return min(a_dom / 0.6, 1.0) if a_dom > 0.5 else a_dom * 0.5
    elif tip == "DRAW":
        return 1 - abs(h_dom - 0.5) * 2
    elif tip == "GG":
        return min(h_xg / 0.8, 1.0) * min(a_xg / 0.8, 1.0)
    elif tip == "NG":
        return max(0, 1 - min(h_xg / 0.8, 1.0) * min(a_xg / 0.8, 1.0))
    elif tip in ("OVER 1.5", "OVER 2.5", "OVER 3.5"):
        t = {"OVER 1.5": 1.8, "OVER 2.5": 2.4, "OVER 3.5": 3.2}[tip]
        return min(total / t, 1.0)
    elif tip == "UNDER 2.5":
        return max(0, 1 - total / 2.4)
    return 0.5

def _form_signal(tip, h_form, a_form):
    h_f = form_score(h_form)
    a_f = form_score(a_form)
    if tip == "HOME WIN":
        return h_f * (1 - a_f * 0.5)
    elif tip == "AWAY WIN":
        return a_f * (1 - h_f * 0.5)
    elif tip == "DRAW":
        return (1 - abs(h_f - a_f)) * (1 - abs((h_f + a_f)/2 - 0.5) * 2)
    elif tip in ("GG", "OVER 1.5", "OVER 2.5", "OVER 3.5"):
        return (h_f + a_f) / 2
    elif tip in ("NG", "UNDER 2.5"):
        return 1 - (h_f + a_f) / 2
    return 0.5

def _standing_signal(tip, h_stand, a_stand, total=20):
    if not h_stand or not a_stand:
        return 0.5
    h_str = 1 - h_stand / total
    a_str = 1 - a_stand / total
    if tip == "HOME WIN":
        return h_str * (1 - a_str * 0.5)
    elif tip == "AWAY WIN":
        return a_str * (1 - h_str * 0.5)
    elif tip == "DRAW":
        return 1 - abs(h_str - a_str)
    elif tip in ("OVER 1.5", "OVER 2.5", "GG"):
        return (h_str + a_str) / 2
    return 0.5

def _value_signal(prob, bookie_odds):
    edge = value_edge(prob, bookie_odds)
    if edge is None:
        return 0.5
    return max(0.0, min(1.0, 0.5 + edge / 20))

def _agreement_count(tip, h_xg, a_xg, h_form, a_form, h_stand, a_stand):
    signals = [
        _xg_signal(tip, h_xg, a_xg),
        min(_form_signal(tip, h_form, a_form), 1.0),
        _standing_signal(tip, h_stand, a_stand),
    ]
    return sum(1 for s in signals if s >= 0.55)

def conviction_score(tip, prob, bookie_odds, h_xg, a_xg, h_form, a_form, h_stand, a_stand):
    """
    Multi-signal conviction. Normalised probability per market category
    so Over 1.5 at 88% doesn't automatically beat Home Win at 55%.
    """
    s_xg       = _xg_signal(tip, h_xg, a_xg)
    s_form     = min(_form_signal(tip, h_form, a_form), 1.0)
    s_standing = _standing_signal(tip, h_stand, a_stand)
    s_value    = _value_signal(prob, bookie_odds)

    # Normalised probability per market category.
    # Goals markets have high baselines -- Over 1.5 at 88% is routine.
    # 1X2 tips at 55%+ are genuinely meaningful -- don't let Over 1.5 drown them.
    norm_map = {
        "OVER 1.5":  (78, 97),   # very high baseline -- only truly elite scores matter
        "OVER 2.5":  (48, 85),
        "OVER 3.5":  (22, 62),
        "UNDER 2.5": (22, 65),
        "GG":        (48, 82),
        "NG":        (25, 65),
        "HOME WIN":  (33, 82),   # 1X2 -- any conviction above 33% is signal
        "AWAY WIN":  (25, 75),
        "DRAW":      (22, 45),
    }
    lo, hi = norm_map.get(tip, (33, 90))
    s_prob = max(0.0, min(1.0, (prob - lo) / max(hi - lo, 1)))

    # Extra boost for 1X2 when independent signals strongly agree
    if tip in ("HOME WIN", "AWAY WIN") and s_xg > 0.62 and s_form > 0.58:
        s_prob = min(s_prob * 1.3, 1.0)
    elif tip == "DRAW" and s_xg > 0.7 and s_form > 0.65:
        s_prob = min(s_prob * 1.2, 1.0)

    raw = (s_prob * 0.30 + s_xg * 0.28 + s_form * 0.22 +
           s_standing * 0.12 + s_value * 0.08)
    score = round(raw * 100, 2)

    # Apply calibration factor from historical results
    # If HOME WIN has been hitting 72% when we say 65%, boost conviction
    # Only applied when 20+ samples exist (reliable signal)
    cal = _get_calibration()
    if tip in cal and cal[tip]["total"] >= 20:
        cf = cal[tip]["calibration_factor"]
        # Cap adjustment: max 20% boost or 20% reduction
        cf = max(0.80, min(1.20, cf))
        score = round(score * cf, 2)

    return min(100.0, score)

# -- Reason builder ------------------------------------------------------------

def _reason(tip, h_xg, a_xg, h_form, a_form, h_stand, a_stand, prob, odds, h_name, a_name):
    signals = {
        "xG":   _xg_signal(tip, h_xg, a_xg),
        "form": min(_form_signal(tip, h_form, a_form), 1.0),
        "pos":  _standing_signal(tip, h_stand, a_stand),
    }
    top = max(signals, key=signals.get)
    edge = value_edge(prob, odds)
    ev = f" -- bookmaker underpricing by {edge}%" if edge and edge > 3 else ""
    h = h_name.split()[0]; a = a_name.split()[0]
    total_xg = round(h_xg + a_xg, 2)

    templates = {
        ("xG","HOME WIN"):  f"{h} generating more xG ({h_xg:.2f} vs {a_xg:.2f}) -- clear home dominance in chance creation{ev}",
        ("xG","AWAY WIN"):  f"{a} creating more chances per game ({a_xg:.2f} xG vs {h_xg:.2f}) -- away threat is real{ev}",
        ("xG","DRAW"):      f"xG almost identical ({h_xg:.2f} vs {a_xg:.2f}) -- neither side pulling away in quality{ev}",
        ("xG","GG"):        f"Both teams generating real chances -- {h} {h_xg:.2f} xG, {a} {a_xg:.2f} xG. Both likely to score{ev}",
        ("xG","NG"):        f"Limited chance creation overall -- xG total only {total_xg}. Clean sheet possible{ev}",
        ("xG","OVER 1.5"):  f"Combined xG of {total_xg} strongly supports a goals game{ev}",
        ("xG","OVER 2.5"):  f"High combined xG ({total_xg}) -- multi-goal game on{ev}",
        ("xG","OVER 3.5"):  f"Both teams creating heavily -- {total_xg} combined xG backs goals{ev}",
        ("xG","UNDER 2.5"): f"Low combined xG ({total_xg}) -- tight match, under has edge{ev}",
        ("form","HOME WIN"):f"{h} in strong form recently * {a} not travelling well{ev}",
        ("form","AWAY WIN"):f"{a} arrive in excellent form * {h} poor run at home{ev}",
        ("form","DRAW"):    f"Both sides drawing frequently -- form points to a stalemate{ev}",
        ("form","GG"):      f"Both teams have been scoring consistently in recent fixtures{ev}",
        ("form","OVER 1.5"):f"Recent games for both sides have produced goals{ev}",
        ("form","OVER 2.5"):f"Both teams involved in high-scoring games recently{ev}",
        ("pos","HOME WIN"): f"{h} significantly superior in the table (#{h_stand} vs #{a_stand}){ev}",
        ("pos","AWAY WIN"):f"{a} punching above their odds -- #{a_stand} vs #{h_stand} in the table{ev}",
        ("pos","DRAW"):     f"Closely matched league positions -- #{h_stand} vs #{a_stand}{ev}",
        ("pos","GG"):       f"Both quality sides -- neither likely to keep a clean sheet{ev}",
    }
    return templates.get((top, tip), f"{prob:.0f}% probability -- multiple signals in agreement{ev}")

# -- THREE-TIER TIP SELECTION --------------------------------------------------

def _pick_recommended(h_win, draw, a_win, o15, o25, o35, btts, gg_p, ng_p,
                      h_xg, a_xg, h_form, a_form, h_stand, a_stand,
                      odds_h, odds_d, odds_a, odds_o15, odds_o25, odds_btts):
    """
    RECOMMENDED TIP -- Market hierarchy rules:
      - DRAW is BANNED from Recommended. Draws belong in Risky.
      - OVER 1.5 is BANNED from Recommended. Too basic -- belongs in Safest.
      - NG (No Goals) is BANNED. Rarely meaningful.
      - Minimum probability threshold: tip must be >= 45% to qualify.
      - If only Over 1.5 / Draw qualify, fall back to HOME WIN or AWAY WIN.
    Valid markets: HOME WIN, AWAY WIN, GG, OVER 2.5, OVER 3.5, UNDER 2.5
    """
    candidates = {
        "HOME WIN":  (h_win,  odds_h),
        "AWAY WIN":  (a_win,  odds_a),
        "GG":        (gg_p,   odds_btts),
        "OVER 2.5":  (o25,    odds_o25),
        "OVER 3.5":  (o35,    None),
        "UNDER 2.5": (100-o25, None),
    }
    scores = {}
    for tip, (prob, odds) in candidates.items():
        scores[tip] = conviction_score(tip, prob, odds, h_xg, a_xg,
                                       h_form, a_form, h_stand, a_stand)
    # Only consider tips with prob >= 40%
    valid = {t: s for t, s in scores.items() if candidates[t][0] >= 40}
    if not valid:
        valid = scores  # fallback: use all if none qualify
    best = max(valid, key=valid.get)
    prob, odds = candidates[best]
    return best, round(prob, 1), scores[best], odds, scores

def _pick_safest(rec_tip, h_win, draw, a_win, o15, h_xg, a_xg, h_form, a_form,
                 odds_h, odds_d, odds_a):
    """
    SAFEST TIP: Over 1.5 Goals, Double Chance (1X/X2/12), Win Either Half
    Always low-risk, high-probability options.
    """
    dc_1x  = round(h_win + draw, 1)    # 1X
    dc_x2  = round(draw + a_win, 1)    # X2
    dc_12  = round(h_win + a_win, 1)   # 12 (either team wins)

    # Double chance odds (approximate: 1 / implied_prob)
    odds_1x = round(1 / (dc_1x/100), 2) if dc_1x > 0 else None
    odds_x2 = round(1 / (dc_x2/100), 2) if dc_x2 > 0 else None
    odds_12 = round(1 / (dc_12/100), 2) if dc_12 > 0 else None

    candidates = [
        ("OVER 1.5 GOALS",    o15,   None),
        ("DOUBLE CHANCE 1X",  dc_1x, odds_1x),
        ("DOUBLE CHANCE X2",  dc_x2, odds_x2),
        ("DOUBLE CHANCE 12",  dc_12, odds_12),
    ]

    # Win Either Half -- approximate from 1X2
    # P(home wins either half) ≈ P(home win) * 1.4 capped at 92
    h_weh = min(round(h_win * 1.35, 1), 92.0)
    a_weh = min(round(a_win * 1.35, 1), 88.0)
    if h_win > a_win:
        candidates.append(("HOME WIN EITHER HALF", h_weh, None))
    else:
        candidates.append(("AWAY WIN EITHER HALF", a_weh, None))

    # Remove if same as recommended
    candidates = [(t, p, o) for t, p, o in candidates if t != rec_tip]

    # Pick highest-probability safe tip (this slot is for stake protection)
    best = max(candidates, key=lambda x: x[1])
    # Always round probability to 1 decimal
    return best[0], round(best[1], 1), best[2]

def _pick_risky(h_win, draw, a_win, o15, o25, btts,
                h_xg, a_xg, h_form, a_form,
                odds_h, odds_a, odds_o25, odds_btts):
    """
    RISKY MARKET: DRAW, HT/FT, Combo tips (1X2+GG, 1X2+Overs, WIN+Overs)
    Draws live here -- they are specialist high-risk selections.
    """
    combos = []

    # DRAW in risky ONLY when genuinely competitive:
    # - Draw probability >= 28% (truly contested match)
    # - AND draw is within 12% of the leading outcome (not just a side result)
    # This stops DRAW polluting every single risky section
    leading_win = max(h_win, a_win)
    draw_competitive = draw >= 28 and (leading_win - draw) <= 14
    if draw_competitive:
        draw_odds = round(1 / (draw/100), 2)
        combos.append({
            "tip":  "DRAW",
            "prob": round(draw, 1),
            "odds": round(draw_odds, 2),
        })

    # 1X2 + GG combos
    if h_win > a_win:
        combos.append({
            "tip":  "HOME WIN & GG",
            "prob": round(h_win/100 * btts/100 * 100, 1),
            "odds": round((1/(h_win/100)) * (1/(btts/100)), 2),
        })
        combos.append({
            "tip":  "HOME WIN & OVER 2.5",
            "prob": round(h_win/100 * o25/100 * 100, 1),
            "odds": round((1/(h_win/100)) * (1/(o25/100)), 2),
        })
    else:
        combos.append({
            "tip":  "AWAY WIN & GG",
            "prob": round(a_win/100 * btts/100 * 100, 1),
            "odds": round((1/(a_win/100)) * (1/(btts/100)), 2),
        })
        combos.append({
            "tip":  "AWAY WIN & OVER 2.5",
            "prob": round(a_win/100 * o25/100 * 100, 1),
            "odds": round((1/(a_win/100)) * (1/(o25/100)), 2),
        })

    combos.append({
        "tip":  "GG & OVER 2.5",
        "prob": round(btts/100 * o25/100 * 100, 1),
        "odds": round((1/(btts/100)) * (1/(o25/100)), 2),
    })

    # HT/FT - most common: home team leads at HT and wins FT
    if h_win > a_win:
        ht_ft_prob = round(h_win * 0.55, 1)   # rough: home HT/FT ≈ 55% of home win prob
        combos.append({"tip": f"HT/FT: HOME / HOME", "prob": ht_ft_prob, "odds": round(100/max(ht_ft_prob,1), 2)})
    else:
        ht_ft_prob = round(a_win * 0.52, 1)
        combos.append({"tip": f"HT/FT: AWAY / AWAY", "prob": ht_ft_prob, "odds": round(100/max(ht_ft_prob,1), 2)})

    # Filter: keep combos with prob > 15% and reasonable odds
    draw_entry = next((c for c in combos if c["tip"] == "DRAW"), None)
    other_combos = [c for c in combos if c["tip"] != "DRAW"
                    and c["prob"] >= 15 and c["odds"] <= 25]
    other_combos.sort(key=lambda x: x["prob"], reverse=True)

    # Show DRAW first in risky only if it genuinely qualified (>= 28% + competitive)
    result = []
    if draw_entry and draw_entry["prob"] >= 28:
        result.append(draw_entry)
    result.extend(other_combos[:3])  # up to 3 combos after draw

    if not result:
        result = [{"tip": "GG & OVER 1.5",
                   "prob": round(btts/100 * o15/100 * 100, 1),
                   "odds": round(1/(btts/100) * 1/(o15/100), 2)}]
    return result[:4]


def _goals_from_xg(h_xg, a_xg):
    """
    Recalculate Over 2.5, Over 1.5, BTTS probabilities from adjusted xG
    using Poisson distribution. Called when squad/rolling adjustments change xG.
    """
    o25 = o15 = 0.0
    btts_h = btts_a = 0.0
    for hg in range(10):
        ph = poisson_pmf(hg, h_xg)
        for ag in range(10):
            pa    = poisson_pmf(ag, a_xg)
            joint = ph * pa
            total = hg + ag
            if total > 2: o25  += joint
            if total > 1: o15  += joint
        if hg > 0: btts_h += ph
    for ag in range(10):
        pa = poisson_pmf(ag, a_xg)
        if ag > 0: btts_a += pa
    btts = btts_h * btts_a
    return round(o25*100,2), round(o15*100,2), round(btts*100,2)

# -- MAIN ANALYSIS -------------------------------------------------------------

def analyze_match(api_data, league_id=None, enriched=None):
    """
    Core analysis with three enrichment layers wired in:

    LAYER 1 -- Squad Strength Index
      enriched["home_squad"] / ["away_squad"] -> penalty multiplier on xG
      A team missing 2 key attackers gets an 84% xG multiplier (-16%)
      Attack/defense scores shift home/away win probabilities

    LAYER 2 -- Rolling xG
      enriched["home_rolling_xg"] / ["away_rolling_xg"]
      Replaces season-average xG with last-5-match goals average
      Trend momentum factor: RISING->x1.12, FALLING->x0.88

    LAYER 3 -- Home/Away Splits
      enriched["home_stats"]["splits"] / ["away_stats"]["splits"]
      Home win rate at home, away win rate on the road -- venue-specific
      Boosts or dampens 1X2 conviction based on actual venue record
    """
    try:
        event  = api_data.get("event", {})
        l_id   = league_id or event.get("league", {}).get("id", 1)
        h_name = event.get("home_team", "Home")
        a_name = event.get("away_team", "Away")

        h_win  = float(api_data.get("prob_home_win",  33.3))
        draw   = float(api_data.get("prob_draw",      33.3))
        a_win  = float(api_data.get("prob_away_win",  33.3))
        o15    = float(api_data.get("prob_over_15",   70.0))
        o25    = float(api_data.get("prob_over_25",   50.0))
        o35    = float(api_data.get("prob_over_35",   25.0))
        btts   = float(api_data.get("prob_btts_yes",  50.0))
        h_xg   = float(api_data.get("expected_home_goals", 1.2))
        a_xg   = float(api_data.get("expected_away_goals", 1.0))
        conf   = float(api_data.get("confidence",     40.0))
        gg_p   = btts
        ng_p   = round(100 - btts, 1)

        # Form: prefer API Football real data over Bzzoiro's
        h_form = (enriched.get("home_form") if enriched else None) or api_data.get("home_form", [])
        a_form = (enriched.get("away_form") if enriched else None) or api_data.get("away_form", [])
        h_stand = api_data.get("home_standing")
        a_stand = api_data.get("away_standing")

        # Bookmaker odds
        odds_h    = event.get("odds_home")
        odds_d    = event.get("odds_draw")
        odds_a    = event.get("odds_away")
        odds_o15  = event.get("odds_over_15")
        odds_o25  = event.get("odds_over_25")
        odds_btts = event.get("odds_btts_yes")

        # ==================================================
        # TEAM PROFILE INTELLIGENCE
        # Read real per-team performance from our own tracker.
        # Arsenal at home: W8 D1 L1, scores 2.3/game, concedes 0.8/game
        # This data comes purely from our settled results -- zero API calls.
        # Blended carefully: 5 matches = 10% weight, 20+ matches = 40% weight
        # So the model is humble early, confident after real evidence.
        # ==================================================
        h_profile = None; a_profile = None
        if _HAS_DB:
            try:
                h_profile = _db.get_team_profile(h_name, venue="home", min_matches=5)
                a_profile = _db.get_team_profile(a_name, venue="away", min_matches=5)
            except:
                pass

        if h_profile:
            played = h_profile["played"]
            blend  = min(0.40, played * 0.02)  # 5 matches=10%, 20=40%
            # Blend real avg goals scored into h_xg
            h_xg = round(h_xg * (1 - blend) + h_profile["avg_scored"] * blend, 3)
            # Blend real avg goals conceded into a_xg (strong defence = fewer away goals)
            def_blend = min(0.30, played * 0.015)
            a_xg = round(a_xg * (1 - def_blend) + h_profile["avg_conceded"] * def_blend, 3)
            # Adjust home win probability from real win rate
            if played >= 8:
                prob_blend = min(0.25, played * 0.01)
                h_win = round(h_win * (1 - prob_blend) + h_profile["win_rate"] * prob_blend, 2)

        if a_profile:
            played = a_profile["played"]
            blend  = min(0.40, played * 0.02)
            a_xg = round(a_xg * (1 - blend) + a_profile["avg_scored"] * blend, 3)
            def_blend = min(0.30, played * 0.015)
            h_xg = round(h_xg * (1 - def_blend) + a_profile["avg_conceded"] * def_blend, 3)
            if played >= 8:
                prob_blend = min(0.25, played * 0.01)
                a_win = round(a_win * (1 - prob_blend) + a_profile["win_rate"] * prob_blend, 2)

        # Re-normalise after team profile adjustments
        _tot = h_win + draw + a_win
        if _tot > 0:
            h_win = round(h_win / _tot * 100, 2)
            draw  = round(draw  / _tot * 100, 2)
            a_win = round(a_win / _tot * 100, 2)

        # ==================================================
        # LAYER 2 -- Rolling xG adjustment
        # Replaces base xG with recent-form goals average.
        # Falls back to Bzzoiro xG if no rolling data.
        # ==================================================
        h_rxg = enriched.get("home_rolling_xg") if enriched else None
        a_rxg = enriched.get("away_rolling_xg") if enriched else None

        if h_rxg and h_rxg["rolling_for"] > 0:
            # Blend: 60% rolling, 40% season xG -- don't fully abandon season data
            h_xg = round(h_rxg["rolling_for"] * 0.60 + h_xg * 0.40, 3)
            h_xg *= h_rxg["momentum_factor"]  # RISING->x1.12, FALLING->x0.88
            h_xg = round(max(0.3, h_xg), 3)

        if a_rxg and a_rxg["rolling_for"] > 0:
            a_xg = round(a_rxg["rolling_for"] * 0.60 + a_xg * 0.40, 3)
            a_xg *= a_rxg["momentum_factor"]
            a_xg = round(max(0.3, a_xg), 3)

        # ==================================================
        # LAYER 1 -- Squad Strength: xG penalty + prob adjustment
        # Applied AFTER rolling xG so both layers stack.
        # ==================================================
        h_sq = enriched.get("home_squad") if enriched else None
        a_sq = enriched.get("away_squad") if enriched else None

        squad_intel = {"home_score": 0, "away_score": 0,
                       "home_atk": 0, "away_atk": 0,
                       "home_penalty": 1.0, "away_penalty": 1.0,
                       "home_missing": 0, "away_missing": 0}

        if h_sq and h_sq["player_count"] > 0:
            # Injury penalty reduces attacking xG
            h_xg = round(h_xg * h_sq["penalty"], 3)
            squad_intel["home_score"]   = h_sq["score"]
            squad_intel["home_atk"]     = h_sq["attack"]
            squad_intel["home_penalty"] = h_sq["penalty"]
            squad_intel["home_missing"] = h_sq["key_missing"]
            # Squad attack differential nudges win probability
            # A team with 80 attack vs opponent 40 defense gets a small boost
            if a_sq and a_sq["player_count"] > 0:
                atk_edge = (h_sq["attack"] - a_sq["defense"]) / 100
                h_win = min(98, h_win + atk_edge * 4)   # max 4% swing per direction
                h_win = max(5,  h_win)

        if a_sq and a_sq["player_count"] > 0:
            a_xg = round(a_xg * a_sq["penalty"], 3)
            squad_intel["away_score"]   = a_sq["score"]
            squad_intel["away_atk"]     = a_sq["attack"]
            squad_intel["away_penalty"] = a_sq["penalty"]
            squad_intel["away_missing"] = a_sq["key_missing"]
            if h_sq and h_sq["player_count"] > 0:
                atk_edge = (a_sq["attack"] - h_sq["defense"]) / 100
                a_win = min(98, a_win + atk_edge * 4)
                a_win = max(5,  a_win)

        # Re-normalise 1X2 after adjustments
        total_1x2 = h_win + draw + a_win
        if total_1x2 > 0 and abs(total_1x2 - 100) > 1:
            h_win = round(h_win / total_1x2 * 100, 2)
            draw  = round(draw  / total_1x2 * 100, 2)
            a_win = round(a_win / total_1x2 * 100, 2)

        # ==================================================
        # LAYER 3 -- Home/Away splits: venue conviction boost
        # Applied to xG signals used in conviction scoring.
        # ==================================================
        venue_boost_h = 1.0
        venue_boost_a = 1.0
        h_stats = enriched.get("home_stats") if enriched else None
        a_stats = enriched.get("away_stats") if enriched else None

        if h_stats and h_stats.get("splits"):
            sp = h_stats["splits"]
            hwr = sp.get("home_win_rate", 0.5)
            # If home team wins at home > 60%, boost home xG signal slightly
            # If < 30%, penalise -- they're genuinely bad at home
            if hwr >= 0.60:   venue_boost_h = 1.10
            elif hwr >= 0.50: venue_boost_h = 1.05
            elif hwr <= 0.30: venue_boost_h = 0.90
            h_xg = round(h_xg * venue_boost_h, 3)

        if a_stats and a_stats.get("splits"):
            sp = a_stats["splits"]
            awr = sp.get("away_win_rate", 0.3)
            # Away teams winning on the road > 40% -> genuinely dangerous away
            if awr >= 0.40:   venue_boost_a = 1.08
            elif awr >= 0.30: venue_boost_a = 1.02
            elif awr <= 0.15: venue_boost_a = 0.90
            a_xg = round(a_xg * venue_boost_a, 3)

        # Team profile GG/Over25 blend from real data
        if h_profile and a_profile and h_profile["played"] >= 5 and a_profile["played"] >= 5:
            n = min(h_profile["played"], a_profile["played"])
            blend = min(0.30, n * 0.015)
            real_gg  = (h_profile["gg_rate"]     + a_profile["gg_rate"])     / 2
            real_o25 = (h_profile["over25_rate"]  + a_profile["over25_rate"]) / 2
            gg_p = round(gg_p * (1 - blend) + real_gg  * blend, 1)
            btts = gg_p
            o25  = round(o25  * (1 - blend) + real_o25 * blend, 1)
            ng_p = round(100 - gg_p, 1)

        # Recalculate goal market probabilities from adjusted xG using Poisson
        if (h_sq or h_rxg or h_profile) and (
                h_xg != float(api_data.get("expected_home_goals", 1.2)) or
                a_xg != float(api_data.get("expected_away_goals", 1.0))):
            o25_adj, o15_adj, btts_adj = _goals_from_xg(h_xg, a_xg)
            # Blend: 50% model recalc, 50% Bzzoiro original (don't fully override)
            o25  = round(o25  * 0.5 + o25_adj  * 0.5, 2)
            o15  = round(o15  * 0.5 + o15_adj  * 0.5, 2)
            btts = round(btts * 0.5 + btts_adj * 0.5, 2)
            gg_p = btts
            ng_p = round(100 - btts, 1)

        # -- RECOMMENDED TIP --
        rec_tip, rec_prob, rec_conv, rec_odds, all_scores = _pick_recommended(
            h_win, draw, a_win, o15, o25, o35, btts, gg_p, ng_p,
            h_xg, a_xg, h_form, a_form, h_stand, a_stand,
            odds_h, odds_d, odds_a, odds_o15, odds_o25, odds_btts
        )
        rec_fair_odds = round(100 / max(rec_prob, 1), 2)
        rec_edge      = value_edge(rec_prob, {
            "HOME WIN": odds_h, "DRAW": odds_d, "AWAY WIN": odds_a,
            "GG": odds_btts, "OVER 1.5": odds_o15, "OVER 2.5": odds_o25,
        }.get(rec_tip))
        rec_agree = _agreement_count(rec_tip, h_xg, a_xg, h_form, a_form, h_stand, a_stand)
        rec_reason = _reason(rec_tip, h_xg, a_xg, h_form, a_form, h_stand, a_stand,
                             rec_prob, {
                                 "HOME WIN": odds_h, "DRAW": odds_d, "AWAY WIN": odds_a,
                                 "GG": odds_btts, "OVER 2.5": odds_o25,
                             }.get(rec_tip), h_name, a_name)

        # -- SAFEST TIP --
        safe_tip, safe_prob, safe_fair_odds = _pick_safest(
            rec_tip, h_win, draw, a_win, o15, h_xg, a_xg, h_form, a_form,
            odds_h, odds_d, odds_a
        )

        # -- RISKY COMBOS --
        risky_list = _pick_risky(
            h_win, draw, a_win, o15, o25, btts,
            h_xg, a_xg, h_form, a_form,
            odds_h, odds_a, odds_o25, odds_btts
        )
        risky_main = risky_list[0]

        # -- Smart tagging system --
        # Slump detection: 3+ consecutive losses
        h_slump = (list(h_form[-3:]).count("L") >= 3) if len(h_form) >= 3 else False
        a_slump = (list(a_form[-3:]).count("L") >= 3) if len(a_form) >= 3 else False
        fav_win = max(h_win, a_win)
        has_injuries = enriched and (enriched.get("home_injuries") or enriched.get("away_injuries"))

        # SURE MATCH: dominant favourite (>85%), signals mostly agree, no slump
        if fav_win >= 85 and rec_agree >= 1 and not h_slump and not a_slump and rec_conv >= 60:
            tag = "✅ SURE MATCH"
        # AVOID: slump OR key injuries AND low conviction
        elif (h_slump or a_slump) and has_injuries and rec_conv < 55:
            tag = "⚠️ AVOID"
        # AVOID: match is too unpredictable (all probs close to 33%)
        elif abs(h_win - draw) < 5 and abs(draw - a_win) < 5 and rec_conv < 45:
            tag = "⚠️ AVOID"
        # RELIABLE: all 3 signals agree, high conviction
        elif rec_agree >= 3 and rec_conv >= 60:
            tag = "🛡️ RELIABLE"
        elif rec_conv >= 65 and rec_agree >= 2:
            tag = "ELITE PICK"
        elif rec_conv >= 55 and rec_agree >= 1:
            tag = "STRONG PICK"
        elif rec_conv >= 42:
            tag = "SOLID TIP"
        else:
            tag = "MONITOR"

        return {
            "tag":       tag,
            "xg_h":      round(h_xg, 2),
            "xg_a":      round(a_xg, 2),
            "squad_intel": squad_intel,
            "1x2":       {"home": round(h_win,1), "draw": round(draw,1), "away": round(a_win,1)},
            "markets":   {"over_15": round(o15,1), "over_25": round(o25,1),
                          "over_35": round(o35,1), "under_25": round(100-o25,1),
                          "btts": round(btts,1), "gg": round(gg_p,1), "ng": round(ng_p,1)},
            # Tip tiers
            "recommended": {
                "tip":    rec_tip,
                "prob":   round(rec_prob, 1),
                "odds":   rec_fair_odds,
                "edge":   rec_edge,
                "conv":   round(rec_conv, 1),
                "agree":  rec_agree,
                "reason": rec_reason,
            },
            "safest": {
                "tip":    safe_tip,
                "prob":   safe_prob,
                "odds":   safe_fair_odds,
            },
            "risky":      risky_list,
            "risky_main": risky_main,
            # Legacy compatibility
            "rec":     {"t": rec_tip, "p": rec_prob, "odds": rec_fair_odds, "edge": rec_edge},
            "second":  {"t": safe_tip, "p": safe_prob},
            "confidence":   round(conf, 1),
            "momentum":     momentum_score(h_form, a_form, h_xg, a_xg),
            "style":        style_profile(h_xg, a_xg, btts),
            "form":         {"home": list(h_form)[-5:], "away": list(a_form)[-5:]},
            "standings":    {"home": h_stand, "away": a_stand},
        }
    except Exception as e:
        import traceback
        print(f"[Predictor] {e}\n{traceback.format_exc()}")
        return None

def pick_acca(matches, n=5, min_conv=45.0):
    """
    Professional ACCA builder with strict quality gates.

    Rules (hard gates - all must pass):
      - Fair odds >= 1.25 per leg   (no junk odds)
      - No AVOID or VERSATILE tags  (reliability required)
      - No OVER 1.5 tips            (too low value)
      - No DRAW tips                (specialist bet, kills accas)
      - 1 pick per league max       (diversification)
      - 1 pick per tip type max     (diversification)
      - Minimum conviction 45
    """
    BLOCKED_TIPS = {"OVER 1.5", "DRAW"}
    BLOCKED_TAGS = {"⚠️ AVOID", "🔄 VERSATILE"}
    MIN_ODDS     = 1.25

    scored = []
    for m in matches:
        l_id = m.get("event", {}).get("league", {}).get("id", 0)
        res  = analyze_match(m, l_id)
        if not res:
            continue
        rec  = res["recommended"]
        if rec["conv"] < min_conv:       continue
        if rec["odds"] < MIN_ODDS:       continue
        if rec["tip"] in BLOCKED_TIPS:   continue
        if res.get("tag","") in BLOCKED_TAGS: continue
        scored.append({"match": m, "result": res, "conv": rec["conv"], "league_id": l_id})

    scored.sort(key=lambda x: x["conv"], reverse=True)

    picks = []; league_used = set(); tip_used = {}
    for s in scored:
        lg  = s["league_id"]
        tip = s["result"]["recommended"]["tip"]
        if lg in league_used:          continue
        if tip_used.get(tip, 0) >= 1:  continue
        league_used.add(lg)
        tip_used[tip] = tip_used.get(tip, 0) + 1
        picks.append(s)
        if len(picks) >= n: break

    combined = 1.0
    for p in picks:
        combined *= p["result"]["recommended"]["odds"]
    return picks, round(combined, 2)