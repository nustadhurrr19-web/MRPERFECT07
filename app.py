import os
import requests
import sqlite3
import threading
import time
from datetime import datetime
from collections import Counter
from flask import Flask, render_template_string, jsonify, redirect

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
PLATFORM_URL = "https://example.com" 

app = Flask(__name__)

# ==========================================
# 🧠 LOGIC ENGINE (FROM YOUR WORKING FILE)
# ==========================================
class TitanLogic:
    def __init__(self):
        self.streak = 0
        self.wins = 0
        self.losses = 0

    def analyze(self, history):
        # history: list of dicts [{'n': 1, 's': 'SMALL', 'id': '123'}] (Oldest -> Newest)
        if len(history) < 15: return None, "SYNCING..."

        # 1. VIOLET CHECK (0/5)
        last_n = history[-1]['n']
        is_violet = (last_n == 0 or last_n == 5)

        # 2. PATTERN SCAN
        pred5, str5 = self.get_pattern(history, 5)
        pred3, str3 = self.get_pattern(history, 3)

        if pred5 and pred3 and pred5 != pred3:
            if str5 > 0.90: best_pred, strength = pred5, str5
            elif str3 > 0.90: best_pred, strength = pred3, str3
            else: return None, "WAITING... (CONFLICT)"
        else:
            best_pred = pred5 if str5 >= str3 else pred3
            strength = max(str5, str3)

        if not best_pred:
             best_pred = history[-1]['s']
             strength = 0.5

        # 3. DECISION
        n1, n2 = history[-1]['n'], history[-2]['n']
        is_symmetric = (n1 + n2 == 9 or n1 == n2)

        if is_violet:
            if strength > 0.90 and is_symmetric: return best_pred, "SURESHOT (VIOLET SAFE)"
            else: return None, "SKIP (0/5 DETECTED)"

        if self.streak >= 2: return best_pred, "RECOVERY"
        if strength > 0.85 and is_symmetric: return best_pred, "SURESHOT"
        if strength > 0.65: return best_pred, "HIGH BET"
        
        return None, "WAITING..."

    def get_pattern(self, history, depth):
        if len(history) < depth + 1: return None, 0
        last_seq = [x['s'] for x in history[-depth:]]
        matches = [history[i+depth]['s'] for i in range(len(history)-(depth+1)) 
                   if [x['s'] for x in history[i:i+depth]] == last_seq]
        if matches:
            c = Counter(matches)
            top = c.most_common(1)[0]
            return top[0], top[1]/len(matches)
        return None, 0

engine = TitanLogic()

# ==========================================
# 💾 MEMORY DATABASE (The Fix)
# ==========================================
# We use a global list instead of a file. fast & reliable.
DB_MEMORY = [] 

def sync_data():
    """Forces 100 items download on startup"""
    global DB_MEMORY
    print("🔄 SYNCING DATA...")
    temp_data = []
    # Loop exactly like your working code
    for p in range(1, 6):
        try:
            r = requests.get(API_URL, params={"size": "20", "pageNo": str(p)}, timeout=5)
            if r.status_code == 200:
                items = r.json().get('data', {}).get('list', [])
                for item in items:
                    temp_data.append({
                        'n': int(item['number']),
                        's': "BIG" if int(item['number']) >= 5 else "SMALL",
                        'id': str(item['issueNumber'])
                    })
        except: pass
    
    # Sort Oldest -> Newest
    temp_data.sort(key=lambda x: int(x['id']))
    
    # Update Global DB (remove duplicates)
    seen = set()
    new_db = []
    for d in temp_data:
        if d['id'] not in seen:
            new_db.append(d)
            seen.add(d['id'])
    
    DB_MEMORY = new_db
    print(f"✅ SYNC DONE. RECORDS: {len(DB_MEMORY)}")

# ==========================================
# 🔄 WORKER LOOP
# ==========================================
global_state = {
    "period": "Loading...", "prediction": "--", "type": "WAITING...",
    "streak": 0, "w": 0, "l": 0, "count": 0, "logs": []
}

def worker():
    sync_data() # Initial Load
    
    last_id = None
    active_bet = None

    while True:
        try:
            # Poll latest
            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=5)
            if r.status_code == 200:
                raw = r.json()['data']['list'][0]
                curr_id = str(raw['issueNumber'])
                
                # Add to memory
                new_item = {
                    'n': int(raw['number']),
                    's': "BIG" if int(raw['number']) >= 5 else "SMALL",
                    'id': curr_id
                }
                
                if not DB_MEMORY or DB_MEMORY[-1]['id'] != curr_id:
                    DB_MEMORY.append(new_item)
                    if len(DB_MEMORY) > 1000: DB_MEMORY.pop(0)

                if curr_id != last_id:
                    # Check Win/Loss
                    if active_bet and active_bet['id'] == curr_id:
                        real = new_item['s']
                        if "SKIP" not in active_bet['type'] and "WAITING" not in active_bet['type']:
                            if active_bet['pred'] == real:
                                engine.wins += 1
                                engine.streak = 0
                                res = "WIN"
                            else:
                                engine.losses += 1
                                engine.streak += 1
                                res = "LOSS"
                            global_state['logs'].insert(0, {"id":curr_id[-4:], "r":real, "s":res})
                    
                    # Predict Next
                    next_id = str(int(curr_id) + 1)
                    pred, p_type = engine.analyze(DB_MEMORY)
                    
                    active_bet = {'id': next_id, 'pred': pred, 'type': p_type}
                    last_id = curr_id
                    
                    global_state.update({
                        "period": next_id, "prediction": pred if pred else "--", "type": p_type,
                        "streak": engine.streak, "w": engine.wins, "l": engine.losses,
                        "count": len(DB_MEMORY)
                    })
            time.sleep(2)
        except: time.sleep(5)

threading.Thread(target=worker, daemon=True).start()

# ==========================================
# 🌐 UI
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TITAN PRO V5</title>
    <style>
        body { background: #000; color: #fff; font-family: monospace; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .box { border: 1px solid #333; padding: 20px; width: 100%; max-width: 600px; margin-bottom: 20px; border-radius: 8px; background: #090909; }
        .h-row { display: flex; justify-content: space-between; border-bottom: 1px solid #222; padding-bottom: 10px; margin-bottom: 20px; }
        .big-txt { font-size: 60px; font-weight: bold; margin: 20px 0; }
        .tag { padding: 5px 10px; border-radius: 4px; font-weight: bold; }
        .SURESHOT { background: #ff0055; color: white; }
        .HIGH { background: #ffd700; color: black; }
        .RECOVERY { background: #00ff88; color: black; }
        .SKIP { border: 1px solid #555; color: #888; }
        .WAITING... { color: #555; }
        .BIG { color: #ff4757; } .SMALL { color: #2ed573; }
        .log-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #111; }
        .btn { display: block; width: 100%; background: #00f2ff; color: #000; padding: 15px; text-align: center; text-decoration: none; font-weight: bold; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="box">
        <div class="h-row">
            <span>TITAN PRO V5</span>
            <span style="color:#00f2ff">DB: <span id="db">0</span></span>
        </div>
        <div style="text-align: center;">
            <div style="color:#888">PERIOD: <span id="p">Scanning...</span></div>
            <div style="margin-top:10px;"><span id="t" class="tag WAITING...">WAITING...</span></div>
            <div id="pred" class="big-txt">--</div>
            <div id="alert" style="display:none; color:#ff0055; font-weight:bold;">⚠️ RECOVERY MODE</div>
        </div>
        <a href="/go" class="btn">OPEN PLATFORM</a>
    </div>

    <div class="box">
        <div class="h-row">
            <span>HISTORY</span>
            <span>W:<span id="w">0</span> L:<span id="l">0</span></span>
        </div>
        <div id="logs"></div>
    </div>

    <script>
        setInterval(() => {
            fetch('/api/state').then(r => r.json()).then(d => {
                document.getElementById('db').innerText = d.count;
                document.getElementById('p').innerText = d.period;
                document.getElementById('t').innerText = d.type;
                document.getElementById('t').className = 'tag ' + d.type.split(' ')[0];
                document.getElementById('pred').innerText = d.prediction;
                document.getElementById('pred').className = 'big-txt ' + d.prediction;
                document.getElementById('w').innerText = d.w;
                document.getElementById('l').innerText = d.l;
                
                if (d.streak > 0) document.getElementById('alert').style.display = 'block';
                else document.getElementById('alert').style.display = 'none';

                document.getElementById('logs').innerHTML = d.logs.map(l => `
                    <div class="log-row">
                        <span>#${l.id}</span>
                        <span class="${l.r}">${l.r}</span>
                        <span style="color:${l.s=='WIN'?'#00ff88':'#ff0055'}">${l.s}</span>
                    </div>
                `).join('');
            });
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(HTML)

@app.route('/api/state')
def state(): return jsonify(global_state)

@app.route('/go')
def go(): return redirect(PLATFORM_URL)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5003))
    app.run(host='0.0.0.0', port=port)
