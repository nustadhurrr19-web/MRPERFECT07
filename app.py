import requests
import time
import threading
import os
import sqlite3
from flask import Flask, render_template_string, jsonify, redirect
from logic import TitanLogic

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
PLATFORM_URL = "https://example.com"
DB_FILE = "/tmp/titan_core_v3.db" 

app = Flask(__name__)
engine = TitanLogic()

# ==========================================
# 💾 DATABASE LAYER
# ==========================================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS history 
                        (issue TEXT PRIMARY KEY, num INTEGER, size TEXT)''')
        conn.commit()

def save_data(data_list):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            for item in data_list:
                num = int(item['number'])
                size = "BIG" if num >= 5 else "SMALL"
                issue = str(item['issueNumber'])
                conn.execute("INSERT OR IGNORE INTO history VALUES (?,?,?)", (issue, num, size))
        return True
    except: return False

def load_history(limit=600):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute(f"SELECT issue, num, size FROM history ORDER BY issue DESC LIMIT {limit}")
            rows = cursor.fetchall()
        data = [{"id": r[0], "n": r[1], "s": r[2]} for r in rows]
        return list(reversed(data))
    except: return []

# ==========================================
# 🔄 BACKGROUND WORKER
# ==========================================
global_state = {
    "period": "Loading...", "prediction": "--", "type": "WAITING...",
    "streak": 0, "win_count": 0, "loss_count": 0, "db_count": 0, "logs": []
}

def worker():
    init_db()
    # Force Initial Sync
    try:
        r = requests.get(API_URL, params={"size": "300", "pageNo": "1"}, timeout=15)
        if r.status_code == 200: save_data(r.json()['data']['list'])
    except: pass

    last_id = None
    active_bet = None

    while True:
        try:
            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=5)
            if r.status_code == 200:
                latest = r.json()['data']['list'][0]
                curr_id = str(latest['issueNumber'])
                save_data([latest])
                
                history = load_history(600)
                global_state['db_count'] = len(history)

                if curr_id != last_id:
                    # Validate
                    if active_bet and active_bet['id'] == curr_id:
                        real_size = "BIG" if int(latest['number']) >= 5 else "SMALL"
                        if "SKIP" not in active_bet['type'] and "WAITING" not in active_bet['type']:
                            if active_bet['size'] == real_size:
                                engine.update_stats(True)
                                status = "WIN"
                            else:
                                engine.update_stats(False)
                                status = "LOSS"
                            global_state['logs'].insert(0, {"id": curr_id[-4:], "res": real_size, "s": status})
                            global_state['logs'] = global_state['logs'][:8]

                    # Predict
                    next_id = str(int(curr_id) + 1)
                    pred, p_type = engine.analyze(history)
                    
                    active_bet = {'id': next_id, 'size': pred, 'type': p_type}
                    last_id = curr_id
                    
                    global_state.update({
                        "period": next_id, "prediction": pred if pred else "--", "type": p_type,
                        "streak": engine.streak, "win_count": engine.wins, "loss_count": engine.losses
                    })
            time.sleep(2)
        except: time.sleep(5)

threading.Thread(target=worker, daemon=True).start()

# ==========================================
# 🌐 UI TEMPLATE
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TITAN PRO V3</title>
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
        <div class="h-row"><span>TITAN PRO V3</span><span style="color:#00f2ff">DB: <span id="db">0</span></span></div>
        <div style="text-align: center;">
            <div style="color:#888">PERIOD: <span id="p">...</span></div>
            <div style="margin-top:10px;"><span id="t" class="tag WAITING...">WAITING...</span></div>
            <div id="pred" class="big-txt">--</div>
            <div id="alert" style="display:none; color:#ff0055; font-weight:bold;">⚠️ RECOVERY MODE</div>
        </div>
        <a href="/go" class="btn">OPEN PLATFORM</a>
    </div>
    <div class="box">
        <div class="h-row"><span>HISTORY</span><span>W:<span id="w">0</span> L:<span id="l">0</span></span></div>
        <div id="logs"></div>
    </div>
    <script>
        setInterval(() => {
            fetch('/api/state').then(r => r.json()).then(d => {
                document.getElementById('db').innerText = d.db_count;
                document.getElementById('p').innerText = d.period;
                document.getElementById('t').innerText = d.type;
                document.getElementById('t').className = 'tag ' + d.type.split(' ')[0];
                document.getElementById('pred').innerText = d.prediction;
                document.getElementById('pred').className = 'big-txt ' + d.prediction;
                document.getElementById('w').innerText = d.win_count;
                document.getElementById('l').innerText = d.loss_count;
                if (d.streak > 0) document.getElementById('alert').style.display = 'block';
                else document.getElementById('alert').style.display = 'none';
                document.getElementById('logs').innerHTML = d.logs.map(l => `
                    <div class="log-row"><span>#${l.id}</span><span class="${l.res}">${l.res}</span><span style="color:${l.s=='WIN'?'#00ff88':'#ff0055'}">${l.s}</span></div>
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
