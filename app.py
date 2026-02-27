diff --git a/app.py b/app.py
index 2782f3981812a6453a4eae70394e4dbd83530646..f573d54d7868ae5efe93103c0628c30b1782e0f8 100644
--- a/app.py
+++ b/app.py
@@ -1032,159 +1032,164 @@ def match_page(match_id):
                 match_date=enriched.get("kickoff",""),
                 market=rec_tip, probability=rec_prob,
                 fair_odds=fair_odds, bookie_odds=bk_odds,
                 edge=None, confidence=conv,
                 xg_home=xg_h, xg_away=xg_a,
                 likely_score="", tag=tag, reliability_score=conv
             )
         except: pass
 
         return render_template_string(LAYOUT, content=content, page="match")
 
     except Exception as e:
         print(f"[match_page] {match_id}: {e}")
         import traceback; traceback.print_exc()
         return render_template_string(LAYOUT,
             content=f'<a href="/" class="back">← Back</a><div class="empty"><span class="empty-icon">⚠️</span>Could not load match.<br><small>{str(e)[:100]}</small></div>',
             page="match")
 
 # ─────────────────────────────────────────────────────────────
 # LIVE PAGE
 # ─────────────────────────────────────────────────────────────
 
 @app.route("/live")
 def live_page():
     lives = sportmonks.get_livescores()
-    content = '''<div class="hero up">
+    content = f'''<div class="hero up">
       <div class="hero-eyebrow">Real-Time</div>
       <div class="hero-title">LIVE <span>NOW</span></div>
     </div>'''
 
     if not lives:
         content += '<div class="empty"><span class="empty-icon">📡</span>No live matches right now.<br>Check back during matchday.</div>'
     else:
         # Group by league
         by_league = {}
         for fx in lives:
             c = build_fixture_card(fx)
             lg = c["league"] or "Unknown"
             by_league.setdefault(lg, []).append(c)
 
         for lg_name, lg_cards in by_league.items():
             meta = get_league_meta(lg_name)
             content += f'<div class="sec-hd">{meta["icon"]} {lg_name}</div>'
             content += '<div class="fx-wrap">'
             for c in lg_cards:
                 content += f'''<a href="/match/{c["id"]}" class="fx-row">
                   <div class="fx-time">
                     <div class="s-badge s-live">{live_dot()} {c["state"]}</div>
                     <div style="margin-top:3px">{score_display(c)}</div>
                   </div>
                   <div class="fx-teams">
                     <div class="fx-home">{c["home"]}</div>
                     <div class="fx-away">{c["away"]}</div>
                   </div>
                 </a>'''
             content += '</div>'
 
     return render_template_string(LAYOUT, content=content, page="live")
 
 # ─────────────────────────────────────────────────────────────
 # ACCA BUILDER
 # ─────────────────────────────────────────────────────────────
 
 @app.route("/acca")
 def acca_page():
     cards = get_all_today_cards()
+    safety_level = (request.args.get("safety") or "safe").lower().strip()
+    min_prob = 72 if safety_level == "safe" else 65
 
     # Only get predictions for fixtures not yet started
     ns_cards = [c for c in cards if c["is_ns"]]
 
     acca_picks = []
     for c in ns_cards[:30]:  # Limit to save API calls
         preds_raw = sportmonks.get_predictions(c["id"])
         preds = sportmonks.parse_predictions(preds_raw) if preds_raw else None
         tip, prob, tag = quick_predict(c, preds)
-        if tag == "RELIABLE" and prob >= 65:
+        if tag == "RELIABLE" and prob >= min_prob and tip != "DRAW":
             odds_raw = sportmonks.get_odds(c["id"])
             odds_parsed = sportmonks.parse_odds(odds_raw)
             bk_odds = odds_parsed.get(
                 "home" if "HOME" in tip else
                 "away" if "AWAY" in tip else
                 "over_25" if "2.5" in tip else
                 "over_15" if "1.5" in tip else "home")
+            if bk_odds and bk_odds < 1.25:
+                continue
             acca_picks.append({
                 "id": c["id"], "home": c["home"], "away": c["away"],
                 "tip": tip, "prob": prob, "odds": bk_odds, "tag": tag,
                 "league": c["league"], "icon": c["icon"]
             })
 
     # Sort by probability
     acca_picks.sort(key=lambda x: x["prob"], reverse=True)
     top5 = acca_picks[:5]
 
     # Calculate combined odds
     combined_odds = 1.0
     for p in top5:
         if p["odds"]: combined_odds *= p["odds"]
 
-    content = '''<div class="hero up">
+    content = f'''<div class="hero up">
       <div class="hero-eyebrow">Auto-Selected</div>
       <div class="hero-title">ACCA <span>BUILDER</span></div>
-      <div class="hero-sub">Top 5 high-confidence picks today</div>
+      <div class="hero-sub">Top 5 high-confidence picks today ({'SAFE' if safety_level=='safe' else 'VALUE'} mode)</div>
     </div>'''
 
     if not top5:
         content += '<div class="empty"><span class="empty-icon">🎯</span>No high-confidence picks found.<br>Check back when more fixtures have predictions.</div>'
     else:
         content += '<div class="card up d1">'
         for i, p in enumerate(top5):
             tc = tip_color(p["tip"])
             odds_str = f'@ {p["odds"]}' if p["odds"] else ""
             content += f'''<div class="acca-row">
               <div style="flex:1;min-width:0">
                 <div style="font-size:.6rem;color:var(--t2);margin-bottom:2px">{p["icon"]} {p["league"]}</div>
                 <div style="font-size:.74rem;font-weight:700;color:var(--wh)">{p["home"]} vs {p["away"]}</div>
                 <div style="font-size:.62rem;color:var(--t2);margin-top:2px">{p["prob"]}% confidence {odds_str}</div>
               </div>
               <div style="text-align:right;flex-shrink:0">
                 <div style="font-size:.72rem;font-weight:800;color:{tc}">{p["tip"]}</div>
                 <span class="badge bg-green" style="margin-top:3px">RELIABLE</span>
               </div>
             </div>'''
         content += '</div>'
 
         if combined_odds > 1:
             content += f'''<div class="acca-odds-box up d2">
               <div style="font-size:.6rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t2);margin-bottom:6px">Combined Odds</div>
               <div class="acca-odds-num">{combined_odds:.2f}</div>
               <div style="font-size:.6rem;color:var(--t2);margin-top:4px">5-fold accumulator</div>
             </div>'''
 
         content += f'''<div class="info-box up d3" style="background:var(--s2);border:1px solid var(--bdr);border-radius:14px;padding:13px;font-size:.65rem;color:var(--t2);line-height:1.8">
           ⚡ Picks auto-selected from {len(ns_cards)} upcoming fixtures.<br>
-          Only RELIABLE-tagged matches with 65%+ confidence included.<br>
+          Safety mode: {'Safe ACCA' if safety_level=='safe' else 'Value ACCA'} (switch using ?safety=safe or ?safety=value).<br>
+          Odds below 1.25 are filtered out as junk legs.<br>
           Always verify odds with your bookmaker before placing.
         </div>'''
 
     return render_template_string(LAYOUT, content=content, page="acca")
 
 # ─────────────────────────────────────────────────────────────
 # TRACKER
 # ─────────────────────────────────────────────────────────────
 
 @app.route("/tracker")
 def tracker_page():
     try:
         stats = database.get_tracker_stats()
     except:
         stats = {"total":0,"wins":0,"losses":0,"hit_rate":0,"pending":0,
                  "week_total":0,"week_wins":0,"week_hit_rate":0,
                  "by_market":[],"by_league":[],"recent":[],"pending_rows":[],
                  "streak":{"type":"--","count":0},"roi":0}
 
     total  = stats.get("total",0)
     wins   = stats.get("wins",0)
     hr     = stats.get("hit_rate",0)
     pending= stats.get("pending",0)
     streak = stats.get("streak",{})
     roi    = stats.get("roi",0)
