from flask import Flask, render_template_string, request
import requests
import os
from datetime import datetime
from match_predictor import API_KEY, BASE_URL, get_match_analysis

app = Flask(__name__)

# Same LAYOUT as before...

@app.route("/")
def home():
    # AUTO-DATE: Gets today's date so the site never looks empty
    today = datetime.now().strftime('%Y-%m-%d')
    params = {'met': 'Fixtures', 'APIkey': API_KEY, 'from': today, 'to': today}
    
    try:
        r = requests.get(BASE_URL, params=params).json()
        matches = r.get('result', [])
    except:
        matches = []
    
    content = '<h2 class="text-green-500 text-[10px] font-black tracking-[0.4em] mb-8 uppercase text-center italic">LIVE DATA STREAM</h2>'
    if not matches:
        content += '<p class="text-center text-zinc-700 mt-20 uppercase font-black tracking-widest">No Matches Scheduled for Today</p>'
    
    for m in matches:
        m_id = str(m.get('event_key'))
        h_t, a_t = m.get('event_home_team'), m.get('event_away_team')
        h_l, a_l = m.get('home_team_logo', ''), m.get('away_team_logo', '')
        
        content += f'''
        <a href="/match?id={m_id}" class="flex justify-between items-center p-6 bg-[#0f1218] rounded-2xl mb-3 border border-white/5 hover:border-green-500/30 transition shadow-xl">
            <div class="w-2/5 flex items-center justify-end gap-3 font-bold text-white text-xs uppercase"><span class="truncate">{h_t}</span><img src="{h_l}" class="w-7 h-7"></div>
            <div class="text-[8px] text-zinc-900 font-black px-4 uppercase">ANALYZE</div>
            <div class="w-2/5 flex items-center justify-start gap-3 font-bold text-white text-xs uppercase"><img src="{a_l}" class="w-7 h-7"><span class="truncate">{a_t}</span></div>
        </a>'''
    return render_template_string(LAYOUT, content=content)

# ... (Keep the /match route exactly as I sent in the Master Prompt)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
