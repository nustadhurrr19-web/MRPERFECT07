import requests
import time
import threading
import os
import urllib3
from collections import Counter
from flask import Flask, render_template_string, jsonify, redirect

# Disable SSL warnings if using verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
PLATFORM_URL = "https://example.com" 

app = Flask(__name__)

class ApexQuantum:
    def __init__(self):
        self.history = []
        self.max_depth = 1000
        self.high_loss_streak = 0
        self.wins = 0
        self.losses = 0

    def get_size(self, n): 
        return "BIG" if int(n) >= 5 else "SMALL"

    def sync_data(self):
        print("DEBUG: Attempting initial sync of 300 items...")
        try:
            # Added verify=False to bypass possible SSL blocks on Render
            r = requests.get(API_URL, params={"size": "300", "pageNo": "1"}, timeout=15, verify=False)
            print(f"DEBUG: Status Code: {r.status_code}")
            
            if r.status_code == 200:
                data = r.json()
                # Debug the keys to see where it fails
                raw_list = data.get('data', {}).get('list', [])
                print(f"DEBUG: Successfully fetched {len(raw_list)} items from API.")
                
                processed = []
                for item in raw_list:
                    try:
                        processed.append({
                            'n': int(item['number']), 
                            's': self.get_size(item['number']), 
                            'id': str(item['issueNumber'])
                        })
                    except Exception as e:
                        continue # Skip bad items
                
                processed.sort(key=lambda x: int(x['id']))
                self.history = processed
                return True
            else:
                print(f"DEBUG: API Error Response: {r.text[:100]}")
                return False
        except Exception as e:
            print(f"DEBUG: SYNC CRITICAL ERROR: {str(e)}")
            return False

    def analyze(self):
        if len(self.history) < 5: return None, "SYNCING..."
        
        # Standard Pattern Logic
        pred5, str5 = self.get_pattern_strength(5)
        pred3, str3 = self.get_pattern_strength(3)
        
        if pred5 and pred3 and pred5 != pred3:
            return (pred5, "SURESHOT") if str5 > 0.9 else (None, "WAITING... (CONFLICT)")
        
        best_pred = pred5 if pred5 else pred3
        return best_pred, "HIGH BET" if best_pred else (None, "WAITING...")

    def get_pattern_strength(self, depth):
        if len(self.history) < depth + 1: return None, 0
        last_seq = [x['s'] for x in self.history[-depth:]]
        matches = [self.history[i+depth]['s'] for i in range(len(self.history)-(depth+1)) 
                   if [x['s'] for x in self.history[i:i+depth]] == last_seq]
        if matches:
            c = Counter(matches)
            return c.most_common(1)[0][0], c.most_common(1)[0][1]/len(matches)
        return None, 0

engine = ApexQuantum()
global_state = {
    "period": "Loading...", "prediction": "--", "type": "WAITING...",
    "streak": 0, "win_count": 0, "loss_count": 0, "data_count": 0, "history_log": []
}

def background_worker():
    last_id = None
    while True:
        try:
            # Force re-sync if empty
            if not engine.history:
                engine.sync_data()
            
            # Polling latest
            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=10, verify=False)
            if r.status_code == 200:
                latest = r.json()['data']['list'][0]
                cid = str(latest['issueNumber'])
                
                if cid != last_id:
                    # Update data count and prediction
                    engine.history.append({'n': int(latest['number']), 's': engine.get_size(latest['number']), 'id': cid})
                    if len(engine.history) > 1000: engine.history.pop(0)
                    
                    p_size, p_type = engine.analyze()
                    global_state.update({
                        "period": str(int(cid) + 1),
                        "prediction": p_size if p_size else "--",
                        "type": p_type,
                        "data_count": len(engine.history)
                    })
                    last_id = cid
            time.sleep(3)
        except Exception as e:
            print(f"DEBUG: Worker error: {e}")
            time.sleep(5)

threading.Thread(target=background_worker, daemon=True).start()

# Frontend HTML (Condensed for speed)
HTML = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><title>TITAN PRO</title>
<style>
    body { background:#050505; color:white; font-family:monospace; text-align:center; padding:50px; }
    .card { background:#111; border:1px solid #333; padding:30px; border-radius:10px; display:inline-block; min-width:300px; }
    .prediction { font-size:70px; color:#00f2ff; margin:20px 0; }
    .status { color:#555; font-size:12px; }
</style></head>
<body>
    <h1>TITAN PRO</h1>
    <div class="card">
        <div id="period" style="color:#888">PERIOD: --</div>
        <div id="type" style="font-weight:bold; margin:10px 0;">WAITING...</div>
        <div id="pred" class="prediction">--</div>
        <div class="status">LIVE DATA: <span id="count">0</span> RECORDS</div>
    </div>
    <script>
        setInterval(() => {
            fetch('/api/status').then(r => r.json()).then(d => {
                document.getElementById('period').innerText = "PERIOD: " + d.period;
                document.getElementById('type').innerText = d.type;
                document.getElementById('pred').innerText = d.prediction;
                document.getElementById('count').innerText = d.data_count;
            });
        }, 2000);
    </script>
</body></html>
"""

@app.route('/')
def home(): return render_template_string(HTML)

@app.route('/api/status')
def status(): return jsonify(global_state)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5003))
    app.run(host='0.0.0.0', port=port)
