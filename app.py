from flask import Flask, render_template_string, request, redirect, url_for
import match_predictor
import os

app = Flask(__name__)

LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; }
        .glass { background: rgba(15, 18, 24, 0.85); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body class="p-4 italic">
    <div class="max-w-md mx-auto min-h-screen flex flex-col">
        <header class="flex justify-between items-center py-6 mb-4 border-b border-white/5">
            <h1 class="text-xl font-black tracking-tighter text-white uppercase italic">PRO<span class="text-green-500">PREDICTOR</span></h1>
            <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
        </header>
        {{ content | safe }}
    </div>
</body>
</html>
"""

@app.route("/")
def hub():
    try:
        # 1. Check Leagues First (To see what you have access to)
        leagues = match_predictor.get_data("leagues/")
        
        # 2. Check Events
        events = match_predictor.get_data("events/")
        
        # DIAGNOSTIC VIEW: If empty, show the status of your leagues
        if not events or len(events) == 0:
            league_list = ", ".join([l.get('name', 'Unknown') for l in leagues]) if isinstance(leagues, list) else "None"
            return render_template_string(LAYOUT, content=f'''
                <div class="flex-grow flex flex-col items-center justify-center py-10 text-center">
                    <p class="text-[10px] font-black uppercase tracking-[0.4em] text-red-500 mb-6">System Diagnostic</p>
                    <div class="glass p-6 rounded-2xl w-full text-left mb-6">
                        <p class="text-[8px] font-bold text-zinc-500 uppercase mb-2">Connected Leagues:</p>
                        <p class="text-[10px] text-white font-mono mb-4">{league_list}</p>
                        <p class="text-[8px] font-bold text-zinc-500 uppercase mb-2">API Raw Response:</p>
                        <p class="text-[9px] text-zinc-400 font-mono">Status: Connected<br>Events Count: 0</p>
                    </div>
                    <p class="text-[9px] text-zinc-600 px-6 leading-relaxed">
                        If "Connected Leagues" is empty, go to <span class="text-white font-black">sports.bzzoiro.com</span> and verify you have active leagues in your dashboard.
                    </p>
                    <a href="/" class="mt-10 px-8 py-3 bg-white text-black text-[9px] font-black rounded-full uppercase">Retry Connection</a>
                </div>
            ''')

        # If we have events, show the first one
        idx = int(request.args.get('i', 0))
        idx = max(0, min(idx, len(events) - 1))
        m = events[idx]
        
        # Display match logic...
        return render_template_string(LAYOUT, content=f'<div class="glass p-8 rounded-3xl text-center"><p class="font-black uppercase text-white">{m["home_team"]["name"]} vs {m["away_team"]["name"]}</p></div>')

    except Exception as e:
        return render_template_string(LAYOUT, content=f'<div class="p-6 text-red-500 font-mono text-[10px]">DIAGNOSTIC ERROR: {str(e)}</div>')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
