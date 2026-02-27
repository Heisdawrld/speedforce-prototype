diff --git a/match_predictor.py b/match_predictor.py
index 31d25db409521485d6aa7afecd2d8231b5d2eca7..2afa701832b0634c0a59dd983eead4ba27a6073b 100644
--- a/match_predictor.py
+++ b/match_predictor.py
@@ -266,100 +266,111 @@ def _reason(tip, h_xg, a_xg, h_form, a_form, h_stand, a_stand, prob, odds, h_nam
 
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
-    # Only consider tips with prob >= 40%
-    valid = {t: s for t, s in scores.items() if candidates[t][0] >= 40}
+    # Value lane: avoid weak signals and keep odds in the practical 1.50-2.20 band
+    # when bookmaker prices are known. Never allow DRAW in recommended.
+    valid = {}
+    for tip, score in scores.items():
+        prob, odds = candidates[tip]
+        if prob < 40:
+            continue
+        if odds is not None and not (1.50 <= odds <= 2.20):
+            continue
+        valid[tip] = score
+
     if not valid:
-        valid = scores  # fallback: use all if none qualify
+        # Fallback still avoids DRAW/OVER1.5 because they are not in candidate set.
+        valid = {t: s for t, s in scores.items() if candidates[t][0] >= 35} or scores
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
-                odds_h, odds_a, odds_o25, odds_btts):
+                odds_h, odds_a, odds_o25, odds_btts,
+                blocked_tips=None):
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
@@ -374,91 +385,113 @@ def _pick_risky(h_win, draw, a_win, o15, o25, btts,
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
 
+    blocked_tips = blocked_tips or set()
+
     # Filter: keep combos with prob > 15% and reasonable odds
     draw_entry = next((c for c in combos if c["tip"] == "DRAW"), None)
     other_combos = [c for c in combos if c["tip"] != "DRAW"
-                    and c["prob"] >= 15 and c["odds"] <= 25]
+                    and c["prob"] >= 15 and c["odds"] >= 2.50 and c["odds"] <= 25
+                    and c["tip"] not in blocked_tips]
     other_combos.sort(key=lambda x: x["prob"], reverse=True)
 
     # Show DRAW first in risky only if it genuinely qualified (>= 28% + competitive)
     result = []
-    if draw_entry and draw_entry["prob"] >= 28:
+    if draw_entry and draw_entry["prob"] >= 28 and draw_entry["tip"] not in blocked_tips:
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
 
+
+def _loss_streak(form, n=3):
+    if not form or len(form) < n:
+        return False
+    return list(form[-n:]).count("L") >= n
+
+
+def _is_volatile_match(event):
+    league_name = ((event or {}).get("league") or {}).get("name", "")
+    round_name = (event or {}).get("round", "")
+    stage_name = (event or {}).get("stage", "")
+    info = " ".join(str(x).lower() for x in [league_name, round_name, stage_name])
+    return any(k in info for k in ["derby", "final", "semi-final", "knockout", "cup"])
+
+
+def _is_friendly_match(event):
+    league_name = ((event or {}).get("league") or {}).get("name", "")
+    return "friendly" in str(league_name).lower()
+
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
@@ -653,148 +686,159 @@ def analyze_match(api_data, league_id=None, enriched=None):
 
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
 
+        # -- Smart tagging system (reliability hierarchy) --
+        h_slump = _loss_streak(h_form, 3)
+        a_slump = _loss_streak(a_form, 3)
+        fav_win = max(h_win, a_win)
+        has_injuries = bool(enriched and (enriched.get("home_injuries") or enriched.get("away_injuries")))
+        home_missing = squad_intel.get("home_missing", 0)
+        away_missing = squad_intel.get("away_missing", 0)
+        full_squad = (home_missing + away_missing) == 0
+        strong_h2h = bool(enriched and enriched.get("h2h") and len(enriched.get("h2h", [])) >= 3)
+        is_friendly = _is_friendly_match(event)
+        is_volatile = _is_volatile_match(event)
+
+        if fav_win > 85 and full_squad and strong_h2h:
+            tag = "✅ SURE MATCH"
+        elif has_injuries or h_slump or a_slump or is_friendly:
+            tag = "⚠️ AVOID"
+        elif is_volatile:
+            tag = "🔄 VOLATILE"
+        else:
+            tag = "🛡️ RELIABLE"
+
         # -- RISKY COMBOS --
         risky_list = _pick_risky(
             h_win, draw, a_win, o15, o25, btts,
             h_xg, a_xg, h_form, a_form,
-            odds_h, odds_a, odds_o25, odds_btts
+            odds_h, odds_a, odds_o25, odds_btts,
+            blocked_tips={rec_tip, safe_tip}
         )
         risky_main = risky_list[0]
 
-        # -- Smart tagging system --
-        # Slump detection: 3+ consecutive losses
-        h_slump = (list(h_form[-3:]).count("L") >= 3) if len(h_form) >= 3 else False
-        a_slump = (list(a_form[-3:]).count("L") >= 3) if len(a_form) >= 3 else False
-        fav_win = max(h_win, a_win)
-        has_injuries = enriched and (enriched.get("home_injuries") or enriched.get("away_injuries"))
-
-        # SURE MATCH: dominant favourite (>85%), signals mostly agree, no slump
-        if fav_win >= 85 and rec_agree >= 1 and not h_slump and not a_slump and rec_conv >= 60:
-            tag = "✅ SURE MATCH"
-        # AVOID: slump OR key injuries AND low conviction
-        elif (h_slump or a_slump) and has_injuries and rec_conv < 55:
-            tag = "⚠️ AVOID"
-        # AVOID: match is too unpredictable (all probs close to 33%)
-        elif abs(h_win - draw) < 5 and abs(draw - a_win) < 5 and rec_conv < 45:
-            tag = "⚠️ AVOID"
-        # RELIABLE: all 3 signals agree, high conviction
-        elif rec_agree >= 3 and rec_conv >= 60:
-            tag = "🛡️ RELIABLE"
-        elif rec_conv >= 65 and rec_agree >= 2:
-            tag = "ELITE PICK"
-        elif rec_conv >= 55 and rec_agree >= 1:
-            tag = "STRONG PICK"
-        elif rec_conv >= 42:
-            tag = "SOLID TIP"
-        else:
-            tag = "MONITOR"
-
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
+                "suppressed": tag == "⚠️ AVOID",
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
 
-def pick_acca(matches, n=5, min_conv=45.0):
+def pick_acca(matches, n=5, min_conv=45.0, safety_level="safe"):
     """
-    Professional ACCA builder with strict quality gates.
-
-    Rules (hard gates - all must pass):
-      - Fair odds >= 1.25 per leg   (no junk odds)
-      - No AVOID or VERSATILE tags  (reliability required)
-      - No OVER 1.5 tips            (too low value)
-      - No DRAW tips                (specialist bet, kills accas)
-      - 1 pick per league max       (diversification)
-      - 1 pick per tip type max     (diversification)
-      - Minimum conviction 45
+    Professional ACCA builder with quality gates and safety profiles.
+
+    safety_level:
+      - "safe":    stricter conviction, safer tags only
+      - "value":   allows more variance while still blocking weak/junk picks
     """
     BLOCKED_TIPS = {"OVER 1.5", "DRAW"}
-    BLOCKED_TAGS = {"⚠️ AVOID", "🔄 VERSATILE"}
+    BLOCKED_TAGS = {"⚠️ AVOID", "🔄 VOLATILE"}
     MIN_ODDS     = 1.25
 
+    profile = (safety_level or "safe").lower().strip()
+    if profile == "value":
+        min_conv = max(min_conv, 50.0)
+    else:
+        min_conv = max(min_conv, 58.0)
+
     scored = []
     for m in matches:
         l_id = m.get("event", {}).get("league", {}).get("id", 0)
         res  = analyze_match(m, l_id)
         if not res:
             continue
+
         rec  = res["recommended"]
-        if rec["conv"] < min_conv:       continue
-        if rec["odds"] < MIN_ODDS:       continue
-        if rec["tip"] in BLOCKED_TIPS:   continue
-        if res.get("tag","") in BLOCKED_TAGS: continue
+        tag  = res.get("tag", "")
+
+        if rec["conv"] < min_conv:
+            continue
+        if rec["odds"] < MIN_ODDS:
+            continue
+        if rec["tip"] in BLOCKED_TIPS:
+            continue
+        if tag in BLOCKED_TAGS:
+            continue
+        if profile == "safe" and tag != "✅ SURE MATCH" and rec["prob"] < 65:
+            continue
+
         scored.append({"match": m, "result": res, "conv": rec["conv"], "league_id": l_id})
 
     scored.sort(key=lambda x: x["conv"], reverse=True)
 
-    picks = []; league_used = set(); tip_used = {}
-    for s in scored:
-        lg  = s["league_id"]
-        tip = s["result"]["recommended"]["tip"]
-        if lg in league_used:          continue
-        if tip_used.get(tip, 0) >= 1:  continue
+    picks = []
+    league_used = set()
+    tip_used = {}
+    for srow in scored:
+        lg  = srow["league_id"]
+        tip = srow["result"]["recommended"]["tip"]
+        if lg in league_used:
+            continue
+        if tip_used.get(tip, 0) >= 1:
+            continue
         league_used.add(lg)
         tip_used[tip] = tip_used.get(tip, 0) + 1
-        picks.append(s)
-        if len(picks) >= n: break
+        picks.append(srow)
+        if len(picks) >= n:
+            break
 
     combined = 1.0
-    for p in picks:
-        combined *= p["result"]["recommended"]["odds"]
+    for pick in picks:
+        combined *= pick["result"]["recommended"]["odds"]
     return picks, round(combined, 2)
