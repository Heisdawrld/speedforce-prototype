import numpy as np
from scipy.stats import poisson

# ─────────────────────────────────────────
# League profiles: (avg_goals, home_advantage)
# ─────────────────────────────────────────
LEAGUE_PROFILES = {
    1:  {"avg_goals": 2.72, "home_adv": 1.12},   # Premier League
    12: {"avg_goals": 2.58, "home_adv": 1.10},   # Championship
    4:  {"avg_goals": 2.48, "home_adv": 1.08},   # Serie A
    5:  {"avg_goals": 3.05, "home_adv": 1.09},   # Bundesliga
    14: {"avg_goals": 2.94, "home_adv": 1.11},   # Belgian Pro League
    18: {"avg_goals": 3.10, "home_adv": 1.07},   # MLS
}
DEFAULT_PROFILE = {"avg_goals": 2.65, "home_adv": 1.10}

# ─────────────────────────────────────────
# Form string → numeric score  (last 5, most recent = more weight)
# ─────────────────────────────────────────
FORM_WEIGHTS = [1.0, 1.2, 1.4, 1.6, 1.8]  # oldest → newest
FORM_VALUE   = {"W": 1.0, "D": 0.4, "L": 0.0}

def form_score(form_list):
    """Returns 0.0–1.0 weighted form rating from a list like ['W','D','L','W','W']."""
    if not form_list:
        return 0.5
    results = list(form_list)[-5:]
    weights = FORM_WEIGHTS[-len(results):]
    score   = sum(FORM_VALUE.get(r, 0) * w for r, w in zip(results, weights))
    max_s   = sum(weights)
    return round(score / max_s, 4)

# ─────────────────────────────────────────
# Standing penalty: bottom-half teams score less
# ─────────────────────────────────────────
def standing_factor(standing, total_teams=20):
    """Returns 0.75–1.15 multiplier. Top teams attack more, bottom defend worse."""
    if not standing:
        return 1.0
    pct = standing / total_teams
    return round(1.15 - (pct * 0.40), 4)

# ─────────────────────────────────────────
# Core Poisson engine
# ─────────────────────────────────────────
def build_poisson_matrix(lam_h, lam_a, max_goals=8):
    """Full goal probability matrix using Poisson distribution."""
    h_probs = [poisson.pmf(i, lam_h) for i in range(max_goals + 1)]
    a_probs = [poisson.pmf(i, lam_a) for i in range(max_goals + 1)]
    matrix  = np.outer(h_probs, a_probs)
    return matrix

def derive_markets(matrix):
    """From a Poisson goal matrix, derive all market probabilities."""
    home_win = float(np.sum(np.tril(matrix, -1)))
    draw     = float(np.sum(np.diag(matrix)))
    away_win = float(np.sum(np.triu(matrix, 1)))

    n = matrix.shape[0]
    over_25 = sum(matrix[i][j] for i in range(n) for j in range(n) if i + j > 2)
    over_15 = sum(matrix[i][j] for i in range(n) for j in range(n) if i + j > 1)
    under_25 = 1.0 - over_25

    # BTTS = P(home scores ≥1) × P(away scores ≥1)
    p_home_scores = 1 - poisson.pmf(0, float(np.sum(matrix) * sum(
        i * matrix[i][j] for i in range(n) for j in range(n)
    ) / max(float(np.sum(matrix)), 1e-9)))
    # Simpler & accurate:
    lam_h = sum(i * sum(matrix[i, :]) for i in range(n))
    lam_a = sum(j * sum(matrix[:, j]) for j in range(n))
    p_home_scores = 1 - poisson.pmf(0, lam_h)
    p_away_scores = 1 - poisson.pmf(0, lam_a)
    btts = p_home_scores * p_away_scores

    return {
        "home_win": round(home_win, 4),
        "draw":     round(draw, 4),
        "away_win": round(away_win, 4),
        "over_25":  round(over_25, 4),
        "over_15":  round(over_15, 4),
        "under_25": round(under_25, 4),
        "btts":     round(btts, 4),
    }

# ─────────────────────────────────────────
# Blend model output with API probabilities
# (API has historical data we don't, so weight it)
# ─────────────────────────────────────────
def blend(model_val, api_val, model_weight=0.55):
    api_weight = 1 - model_weight
    return round(model_val * model_weight + api_val * api_weight, 4)

# ─────────────────────────────────────────
# Main analysis function
# ─────────────────────────────────────────
def analyze_match(api_data, league_id=1):
    try:
        profile   = LEAGUE_PROFILES.get(int(league_id), DEFAULT_PROFILE)
        avg_goals = profile["avg_goals"]
        home_adv  = profile["home_adv"]

        # ── Raw API values ──
        api_h    = float(api_data.get("prob_home",  0.334))
        api_d    = float(api_data.get("prob_draw",  0.333))
        api_a    = float(api_data.get("prob_away",  0.333))
        api_o25  = float(api_data.get("prob_over_25", 0.50))
        api_btts = float(api_data.get("prob_btts",   0.50))
        api_conf = float(api_data.get("confidence",  50.0))

        # ── Team stats from API ──
        avg_h_goals = float(api_data.get("avg_home_goals", avg_goals * 0.55))
        avg_a_goals = float(api_data.get("avg_away_goals", avg_goals * 0.45))
        home_standing = api_data.get("home_standing", 10)
        away_standing = api_data.get("away_standing", 10)
        home_form_raw = api_data.get("home_form", [])
        away_form_raw = api_data.get("away_form", [])

        # ── Derived factors ──
        h_form = form_score(home_form_raw)
        a_form = form_score(away_form_raw)
        h_stand = standing_factor(home_standing)
        a_stand = standing_factor(away_standing)

        # Attack strength = team avg goals / league avg (split ~55/45 home/away)
        league_h_avg = avg_goals * 0.55
        league_a_avg = avg_goals * 0.45

        h_attack  = (avg_h_goals / max(league_h_avg, 0.01)) * h_form * h_stand
        a_attack  = (avg_a_goals / max(league_a_avg, 0.01)) * a_form * a_stand

        # λ = attack_strength × opponent_defence_weakness × league_avg × home_adv
        # We approximate defence weakness as inverse of standing factor of opponent
        h_def_weakness = 1.0 / max(a_stand, 0.5)
        a_def_weakness = 1.0 / max(h_stand, 0.5)

        lam_h = h_attack * h_def_weakness * league_h_avg * home_adv
        lam_a = a_attack * a_def_weakness * league_a_avg

        # Clamp lambdas to sensible range
        lam_h = max(0.3, min(lam_h, 5.0))
        lam_a = max(0.3, min(lam_a, 5.0))

        # ── Poisson model output ──
        matrix  = build_poisson_matrix(lam_h, lam_a)
        markets = derive_markets(matrix)

        # ── Blend model + API ──
        h_win  = blend(markets["home_win"], api_h)
        draw   = blend(markets["draw"],     api_d)
        a_win  = blend(markets["away_win"], api_a)
        over25 = blend(markets["over_25"],  api_o25)
        over15 = markets["over_15"]
        under25= blend(markets["under_25"], 1 - api_o25)
        btts   = blend(markets["btts"],     api_btts)

        # Normalise 1X2 so they sum to 1
        total  = h_win + draw + a_win
        h_win  = round(h_win / total, 4)
        draw   = round(draw  / total, 4)
        a_win  = round(1 - h_win - draw, 4)

        # ── Market selection ──
        all_markets = {
            "HOME WIN":   h_win,
            "DRAW":       draw,
            "AWAY WIN":   a_win,
            "OVER 2.5":   over25,
            "BTTS":       btts,
            "OVER 1.5":   over15,
        }
        sorted_markets = sorted(all_markets.items(), key=lambda x: x[1], reverse=True)
        best_market,  best_prob  = sorted_markets[0]
        second_market, second_prob = sorted_markets[1]

        # ── Confidence & edge ──
        confidence_gap = round((best_prob - second_prob) * 100, 1)
        model_conf     = round(best_prob * 100, 1)
        blended_conf   = round((model_conf + api_conf) / 2, 1)

        # ── Fair odds ──
        fair_odds_best = round(1 / max(best_prob, 0.01), 2)

        # ── Tag ──
        if best_prob >= 0.65:
            tag = "ELITE VALUE"
        elif best_prob >= 0.55:
            tag = "STRONG PICK"
        elif confidence_gap > 15:
            tag = "QUANT EDGE"
        else:
            tag = "MONITOR"

        # ── Form display ──
        def fmt_form(form_list):
            return list(form_list)[-5:] if form_list else []

        return {
            "tag":        tag,
            "lam_h":      round(lam_h, 2),
            "lam_a":      round(lam_a, 2),
            "xg_h":       round(lam_h, 2),
            "xg_a":       round(lam_a, 2),
            "1x2": {
                "home": round(h_win * 100, 1),
                "draw": round(draw  * 100, 1),
                "away": round(a_win * 100, 1),
            },
            "markets": {
                "over_25":  round(over25  * 100, 1),
                "under_25": round(under25 * 100, 1),
                "over_15":  round(over15  * 100, 1),
                "btts":     round(btts    * 100, 1),
            },
            "rec": {
                "t":    best_market,
                "p":    round(best_prob * 100, 1),
                "odds": fair_odds_best,
            },
            "second": {
                "t": second_market,
                "p": round(second_prob * 100, 1),
            },
            "confidence":     blended_conf,
            "confidence_gap": confidence_gap,
            "form": {
                "home": fmt_form(home_form_raw),
                "away": fmt_form(away_form_raw),
            },
            "standings": {
                "home": home_standing,
                "away": away_standing,
            },
        }

    except Exception as e:
        import traceback
        print(f"[Predictor Error] {e}\n{traceback.format_exc()}")
        return {
            "tag": "DATA ERROR",
            "lam_h": 0, "lam_a": 0, "xg_h": 0, "xg_a": 0,
            "1x2": {"home": 33, "draw": 33, "away": 33},
            "markets": {"over_25": 50, "under_25": 50, "over_15": 70, "btts": 50},
            "rec": {"t": "UNAVAILABLE", "p": 0, "odds": 0},
            "second": {"t": "N/A", "p": 0},
            "confidence": 0, "confidence_gap": 0,
            "form": {"home": [], "away": []},
            "standings": {"home": 0, "away": 0},
        }

# ─────────────────────────────────────────
# ACCA: pick top N matches by best market prob
# ─────────────────────────────────────────
def pick_acca(matches, n=5, min_prob=0.52):
    """
    From a list of raw API match dicts, return top N ACCA picks.
    Avoids clustering more than 2 picks from the same league.
    """
    scored = []
    for m in matches:
        league = m.get("league_id", 0)
        res    = analyze_match(m, league)
        if res["tag"] == "DATA ERROR":
            continue
        best_p = res["rec"]["p"] / 100
        if best_p < min_prob:
            continue
        scored.append({
            "match":   m,
            "result":  res,
            "best_p":  best_p,
            "league":  league,
        })

    scored.sort(key=lambda x: x["best_p"], reverse=True)

    # Anti-clustering: max 2 per league
    picks   = []
    league_counts = {}
    for s in scored:
        lg = s["league"]
        if league_counts.get(lg, 0) >= 2:
            continue
        league_counts[lg] = league_counts.get(lg, 0) + 1
        picks.append(s)
        if len(picks) >= n:
            break

    # Combined odds
    combined = 1.0
    for p in picks:
        combined *= p["result"]["rec"]["odds"]

    return picks, round(combined, 2)
