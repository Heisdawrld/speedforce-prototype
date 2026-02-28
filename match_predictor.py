import math
import statistics

# ─── MATH HELPERS ─────────────────────────────────────────────────────────────

def poisson_pmf(k, lam):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def calculate_volatility(form_str):
    """
    Returns 0.0 (Stable) to 1.0 (Chaos).
    Input: "WLDWL"
    """
    if not form_str or len(form_str) < 3: return 0.5
    # Map results to points: W=3, D=1, L=0
    points = [3 if c.upper() == 'W' else 1 if c.upper() == 'D' else 0 for c in form_str]
    if len(points) < 2: return 0.0
    
    # Standard Deviation implies inconsistency
    dev = statistics.stdev(points)
    # Max dev for [0,3] range is ~1.5. Normalize to 0-1.
    return min(dev / 1.5, 1.0)

def get_form_score(form_str):
    if not form_str: return 0.5
    # Weighted recent form (most recent game counts more)
    points = [3 if c.upper() == 'W' else 1 if c.upper() == 'D' else 0 for c in form_str]
    weights = [1.0, 1.2, 1.4, 1.6, 1.8][-len(points):]
    
    weighted_sum = sum(p * w for p, w in zip(points, weights))
    max_sum = sum(3 * w for w in weights)
    
    return weighted_sum / max_sum if max_sum > 0 else 0.5

# ─── CORE ANALYSIS ────────────────────────────────────────────────────────────

def analyze_match(enriched):
    """
    The Single Source of Truth.
    Accepts 'enriched' data from Sportmonks.
    Returns a dictionary with 'recommended', 'safest', 'risky', and 'badges'.
    """
    # 1. Extract Data
    h_name = enriched.get("home_name", "Home")
    a_name = enriched.get("away_name", "Away")
    
    # xG (The most important metric)
    # Default to 1.25/1.05 (slightly home favored) if data is missing
    xg_h = float(enriched.get("xg_home") or 1.25)
    xg_a = float(enriched.get("xg_away") or 1.05)
    
    # Adjust xG based on League Tier/Quality if needed (Optional)
    # For now, we trust Sportmonks xG data.

    # 2. Run Poisson Simulation (The "Thinking" Part)
    # We calculate our OWN probabilities. We do not trust the bookie blind.
    probs = {"1": 0, "X": 0, "2": 0, "O15": 0, "O25": 0, "BTTS": 0}
    
    home_dist = [poisson_pmf(i, xg_h) for i in range(10)]
    away_dist = [poisson_pmf(i, xg_a) for i in range(10)]
    
    for h in range(10):
        for a in range(10):
            p = home_dist[h] * away_dist[a]
            
            if h > a: probs["1"] += p
            elif h == a: probs["X"] += p
            else: probs["2"] += p
            
            if h + a > 1: probs["O15"] += p
            if h + a > 2: probs["O25"] += p
            if h > 0 and a > 0: probs["BTTS"] += p

    # Convert to %
    P_HOME = probs["1"] * 100
    P_DRAW = probs["X"] * 100
    P_AWAY = probs["2"] * 100
    P_O25  = probs["O25"] * 100
    P_BTTS = probs["BTTS"] * 100

    # 3. Analyze Volatility (The "Chaos" Check)
    h_form = enriched.get("home_form", [])
    a_form = enriched.get("away_form", [])
    
    # Convert list ["W","L"] to string "WL" if needed
    h_form_str = "".join(h_form) if isinstance(h_form, list) else str(h_form)
    a_form_str = "".join(a_form) if isinstance(a_form, list) else str(a_form)
    
    vol_h = calculate_volatility(h_form_str)
    vol_a = calculate_volatility(a_form_str)
    avg_vol = (vol_h + vol_a) / 2
    
    # 4. Generate Badges
    badge_type = "STANDARD" # Default
    badge_label = "MONITOR"
    badge_desc = "Standard match analysis."
    
    # BADGE LOGIC TREE
    if avg_vol > 0.70:
        badge_type = "VOLATILE"
        badge_label = "⚠️ VOLATILE"
        badge_desc = "Teams are inconsistent. High risk of upset."
    elif abs(P_HOME - P_AWAY) < 10:
        badge_type = "VERSATILE"
        badge_label = "⚖️ VERSATILE"
        badge_desc = "Very tight match. Avoid Winner market."
    elif P_HOME > 75 and avg_vol < 0.4:
        badge_type = "BANKER"
        badge_label = "🛡️ BANKER"
        badge_desc = f"High confidence in {h_name}."
    elif P_AWAY > 70 and avg_vol < 0.4:
        badge_type = "BANKER"
        badge_label = "🛡️ BANKER"
        badge_desc = f"High confidence in {a_name}."
    elif P_O25 > 65 and probs["BTTS"] > 0.60:
        badge_type = "GOAL_FEST"
        badge_label = "🔥 GOALS"
        badge_desc = "High xG stats suggest an open game."

    # 5. Select Tips
    # We create a candidate list and pick the best one based on Conviction
    
    candidates = []
    
    # Helper to calc conviction (0-100)
    def calc_conviction(prob, volatility_penalty=True):
        score = prob
        if volatility_penalty:
            score -= (avg_vol * 20) # Penalize chaos
        return min(max(score, 0), 100)

    # Home Win
    candidates.append({
        "tip": "HOME WIN",
        "market": "1X2",
        "prob": P_HOME,
        "conviction": calc_conviction(P_HOME),
        "min_prob": 45
    })
    
    # Away Win
    candidates.append({
        "tip": "AWAY WIN",
        "market": "1X2",
        "prob": P_AWAY,
        "conviction": calc_conviction(P_AWAY),
        "min_prob": 45
    })
    
    # Over 2.5 (Less sensitive to winner volatility, so less penalty)
    candidates.append({
        "tip": "OVER 2.5",
        "market": "GOALS",
        "prob": P_O25,
        "conviction": calc_conviction(P_O25, volatility_penalty=False) - 5, # slight handicap
        "min_prob": 50
    })
    
    # BTTS
    candidates.append({
        "tip": "GG (BTTS)",
        "market": "GOALS",
        "prob": P_BTTS,
        "conviction": calc_conviction(P_BTTS, volatility_penalty=False),
        "min_prob": 52
    })

    # Filter by minimum probability
    valid_candidates = [c for c in candidates if c["prob"] >= c["min_prob"]]
    
    # Fallback if nothing is good
    if not valid_candidates:
        if P_HOME >= P_AWAY:
            best_tip = {"tip": "1X (DC)", "prob": P_HOME + P_DRAW, "conviction": 60}
        else:
            best_tip = {"tip": "X2 (DC)", "prob": P_AWAY + P_DRAW, "conviction": 60}
        reason = "Match is too tight for a straight win. Playing it safe."
    else:
        # Sort by Conviction
        best_tip = max(valid_candidates, key=lambda x: x["conviction"])
        reason = f"Model calculates {best_tip['prob']:.1f}% probability based on xG flow."

    # 6. Safest & Risky Tips
    
    # Safest: Look for Over 1.5 or Double Chance
    safe_candidates = [
        {"tip": "OVER 1.5", "prob": probs["O15"] * 100},
        {"tip": "1X", "prob": P_HOME + P_DRAW},
        {"tip": "X2", "prob": P_AWAY + P_DRAW}
    ]
    # Filter out the Recommended Tip if it's the same
    safe_candidates = [s for s in safe_candidates if s["tip"] not in best_tip["tip"]]
    safest_tip = max(safe_candidates, key=lambda x: x["prob"])
    
    # Risky: Draw or Combos
    risky_tip = {"tip": "DRAW", "prob": P_DRAW}
    if P_HOME > 60 and P_O25 > 60:
        risky_tip = {"tip": "1 & O2.5", "prob": P_HOME * 0.7} # rough approx
    elif P_AWAY > 60 and P_O25 > 60:
        risky_tip = {"tip": "2 & O2.5", "prob": P_AWAY * 0.7}

    # 7. Final Payload
    return {
        "recommended": {
            "tip": best_tip["tip"],
            "prob": round(best_tip["prob"], 1),
            "conviction": round(best_tip.get("conviction", 50), 0),
            "reason": reason,
            "fair_odds": round(100/max(best_tip["prob"],1), 2)
        },
        "safest": {
            "tip": safest_tip["tip"],
            "prob": round(safest_tip["prob"], 1),
            "fair_odds": round(100/max(safest_tip["prob"],1), 2)
        },
        "risky": {
            "tip": risky_tip["tip"],
            "prob": round(risky_tip["prob"], 1),
            "fair_odds": round(100/max(risky_tip["prob"],1), 2)
        },
        "badges": {
            "label": badge_label,
            "type": badge_type,
            "desc": badge_desc,
            "volatility": round(avg_vol, 2)
        },
        "data": {
            "xg_h": round(xg_h, 2),
            "xg_a": round(xg_a, 2),
            "home_win_prob": round(P_HOME, 1),
            "away_win_prob": round(P_AWAY, 1),
            "draw_prob": round(P_DRAW, 1)
        }
    }
