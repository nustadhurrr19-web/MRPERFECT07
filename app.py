import os
import time
import threading
from flask import Flask, render_template_string, jsonify, redirect
from logic_core import ApexQuantum, OmegaStorage

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
PLATFORM_URL = "https://t.me/+UokUj32JokUwMzU1"  # Your Telegram Link
app = Flask(__name__)

# ==========================================
# 🔄 GLOBAL STATE & BACKGROUND WORKER
# ==========================================
# Initialize logic classes
engine = ApexQuantum()
db = OmegaStorage()

global_state = {
    "period": "Loading...",
    "prediction": "--",
    "type": "WAITING...",
    "streak": 0,
    "last_result": "--",
    "history_log": [],
    "win_count": 0,
    "loss_count": 0
}

# Variable to track active prediction state
active_bet_state = {
    "id": None,
    "pred": None,
    "type": None
}

def background_worker():
    """
    Runs in the background to fetch data and update predictions.
    Replicates the 'Live' feel of your local script.
    """
    last_processed_id = None
    
    # Internal streak tracking (since we don't have session persistence in a simple worker)
    worker_streak = 0
    worker_wins = 0
    worker_losses = 0

    while True:
        try:
            # 1. Sync Data
            db.sync_fast()
            history = db.get_history(500)
            
            if not history: 
                time.sleep(2)
                continue
            
            latest = history[0]
            curr_id = str(latest['issue'])
            real_size = latest['size']

            # 2. Process Logic (Check Win/Loss)
            if curr_id != last_processed_id:
                # Check previous bet outcome
                if active_bet_state['id'] == curr_id:
                    # Only count if it wasn't a WAITING bet
                    if active_bet_state['type'] not in ["WAITING...", "WAITING... (CONFLICT)", "SKIP (VOLATILE)"]:
                        is_win = (active_bet_state['pred'] == real_size)
                        
                        status = ""
                        if is_win:
                            worker_wins += 1
                            worker_streak = 0
                            status = "WIN"
                        else:
                            worker_losses += 1
                            worker_streak += 1
                            status = "LOSS"
                        
                        # Add to UI Log
                        global_state["history_log"].insert(0, {
                            "period": curr_id[-4:], 
                            "res": real_size, 
                            "status": status
                        })
                        global_state["history_log"] = global_state["history_log"][:10]

                # 3. Predict Next
                # Note: history[0] is current result. Prediction is for Next.
                next_id = str(int(curr_id) + 1)
                
                # Analyze using Apex V2
                p_size, p_type, _ = engine.analyze_bet_type(history, worker_streak)
                
                # Update Active Bet State
                active_bet_state['id'] = next_id
                active_bet_state['pred'] = p_size
                active_bet_state['type'] = p_type
                
                last_processed_id = curr_id
                
                # Update Global UI State
                global_state["period"] = next_id
                global_state["prediction"] = p_size if p_size else "--"
                global_state["type"] = p_type
                global_state["streak"] = worker_streak
                global_state["last_result"] = f"{real_size} ({curr_id[-4:]})"
                global_state["win_count"] = worker_wins
                global_state["loss_count"] = worker_losses

            time.sleep(2)
        except Exception as e:
            print(f"Worker Error: {e}")
            time.sleep(2)

# Start Background Thread
# Daemon=True ensures it dies when main app dies
t = threading.Thread(target=background_worker)
t.daemon = True
t.start()

# ==========================================
# 🌐 FLASK FRONTEND (EXACT UI FROM PP.PY)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TITAN PRO | ULTIMATE</title>
    <style>
        :root { --bg: #050505; --panel: #111; --border: #333; --accent: #00f2ff; --win: #00ff88; --loss: #ff0055; --text: #fff; }
        body { background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }
        
        .dashboard { display: grid; grid-template-columns: 1.5fr 1fr; gap: 20px; max-width: 1200px; width: 100%; }
        
        .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 20px; box-shadow: 0 0 20px rgba(0,0,0,0.5); position: relative; overflow: hidden; }
        .card::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, var(--accent), transparent); }
        
        .header { width: 100%; max-width: 1200px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
        h1 { margin: 0; font-size: 28px; letter-spacing: 2px; text-transform: uppercase; color: var(--accent); text-shadow: 0 0 10px var(--accent); }
        
        /* Signal Box */
        .signal-box { text-align: center; display: flex; flex-direction: column; justify-content: center; min-height: 350px; }
        .period { font-size: 20px; color: #888; margin-bottom: 20px; }
        
        .pred-type { font-size: 22px; font-weight: bold; padding: 8px 20px; border-radius: 4px; display: inline-block; margin-bottom: 10px; }
        .prediction { font-size: 80px; font-weight: 900; margin: 0; text-transform: uppercase; letter-spacing: 5px; }
        
        .streak-alert { background: rgba(255, 0, 85, 0.2); color: var(--loss); padding: 10px; border: 1px solid var(--loss); border-radius: 4px; margin-top: 20px; animation: pulse 1s infinite; font-weight: bold; }
        
        /* History Box */
        .history-box h3 { margin-top: 0; border-bottom: 1px solid var(--border); padding-bottom: 10px; display: flex; justify-content: space-between; }
        .log-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #222; font-size: 14px; }
        .log-item:last-child { border-bottom: none; }
        
        .stats { display: flex; gap: 10px; }
        .stat-pill { padding: 4px 10px; border-radius: 4px; font-size: 14px; font-weight: bold; }
        
        .btn { background: var(--accent); color: #000; padding: 12px 25px; text-decoration: none; font-weight: bold; border-radius: 4px; text-transform: uppercase; transition: 0.3s; }
        .btn:hover { background: #fff; box-shadow: 0 0 15px #fff; }

        /* Dynamic Classes */
        .type-WAITING... { color: #555; border: 1px solid #333; }
        .type-HIGH { background: #ffd700; color: #000; box-shadow: 0 0 20px rgba(255, 215, 0, 0.4); }
        .type-SURESHOT { background: #ff0055; color: #fff; box-shadow: 0 0 30px rgba(255, 0, 85, 0.6); }
        .type-RECOVERY { background: #00ff88; color: #000; box-shadow: 0 0 30px rgba(0, 255, 136, 0.6); }
        
        .pred-BIG { color: #ff4757; text-shadow: 0 0 20px rgba(255, 71, 87, 0.5); }
        .pred-SMALL { color: #2ed573; text-shadow: 0 0 20px rgba(46, 213, 115, 0.5); }
        .pred-None { color: #333; text-shadow: none; }

        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        @media (max-width: 768px) { .dashboard { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>MR PERFECT </h1>
            <div style="font-size: 20px; color: #666;">4 LEVEL MAINTAIN </div>
        </div>
        <a href="/go" target="_blank" class="btn">TELEGRAM ↗</a>
    </div>

    <div class="dashboard">
        <div class="card signal-box">
            <div class="period">PERIOD: <span id="period">Scanning...</span></div>
            
            <div id="type-wrapper">
                <div id="type-badge" class="pred-type type-WAITING...">WAITING...</div>
            </div>
            
            <div id="prediction" class="prediction pred-None">--</div>
            
            <div id="streak-warning" class="streak-alert" style="display: none;">
                ⚠️ STOP & RECOVER MODE (LEVEL <span id="streak-lvl">0</span>)
            </div>
        </div>

        <div class="card history-box">
            <h3>
                ACTIVITY LOG
                <div class="stats">
                    <span class="stat-pill" style="background:#003300; color:#00ff88">W: <span id="wins">0</span></span>
                    <span class="stat-pill" style="background:#330000; color:#ff0055">L: <span id="losses">0</span></span>
                </div>
            </h3>
            <div id="history-list">
                <div style="padding:20px; text-align:center; color:#444;">No active bets yet...</div>
            </div>
        </div>
    </div>

    <script>
        function update() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('period').innerText = data.period;
                    document.getElementById('wins').innerText = data.win_count;
                    document.getElementById('losses').innerText = data.loss_count;
                    
                    const typeBadge = document.getElementById('type-badge');
                    const predDiv = document.getElementById('prediction');
                    
                    // Handle Badge Styling
                    let safeType = data.type.split(' ')[0]; // Extract "HIGH" from "HIGH BET"
                    if (data.type.includes("SKIP")) safeType = "WAITING...";
                    if (data.type.includes("CONFLICT")) safeType = "WAITING...";
                    
                    typeBadge.innerText = data.type;
                    typeBadge.className = `pred-type type-${safeType}`;
                    
                    // Handle Prediction Display
                    if(data.type.includes("WAITING") || data.type.includes("SKIP")) {
                        predDiv.innerText = "--";
                        predDiv.className = "prediction pred-None";
                    } else {
                        predDiv.innerText = data.prediction;
                        predDiv.className = `prediction pred-${data.prediction}`;
                    }

                    // Recovery Alert
                    const warn = document.getElementById('streak-warning');
                    if(data.streak > 0) {
                        warn.style.display = 'block';
                        document.getElementById('streak-lvl').innerText = data.streak;
                    } else {
                        warn.style.display = 'none';
                    }

                    // History
                    const histList = document.getElementById('history-list');
                    if(data.history_log.length > 0) {
                        histList.innerHTML = data.history_log.map(item => `
                            <div class="log-item">
                                <span style="color:#666">#${item.period}</span>
                                <span style="font-weight:bold">${item.res}</span>
                                <span style="color: ${item.status === 'WIN' ? '#00ff88' : '#ff0055'}">${item.status}</span>
                            </div>
                        `).join('');
                    }
                });
        }
        setInterval(update, 1000); // 1 Second refresh rate
        update();
    </script>
</body>
</html>
"""

# ==========================================
# 🚀 FLASK ROUTES
# ==========================================
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def get_status():
    return jsonify(global_state)

@app.route('/go')
def go_platform():
    return redirect(PLATFORM_URL)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5004))
    app.run(host='0.0.0.0', port=port)
