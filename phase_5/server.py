import os
import json
import http.server
import socketserver
from datetime import datetime, timedelta
import threading
import time
import subprocess
import sys

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(DIRECTORY)

# Global variables to manage the background review sync
is_fetching = False
last_fetch_time = 0

def run_bg_fetch():
    global is_fetching, last_fetch_time
    is_fetching = True
    print("[SERVER] Starting automatic background data fetch (limit=1800) and clustering...")
    try:
        # Resolve python executable dynamically from the current running interpreter
        # or fall back to any available virtual environment in the workspace.
        venv_python = sys.executable
        if not any(x in venv_python.lower() for x in ["venv", "env"]):
            for phase in ["phase_3", "phase_1", "phase_4"]:
                win_py = os.path.join(WORKSPACE_ROOT, phase, "venv", "Scripts", "python.exe")
                unix_py = os.path.join(WORKSPACE_ROOT, phase, "venv", "bin", "python")
                if os.path.exists(win_py):
                    venv_python = win_py
                    break
                elif os.path.exists(unix_py):
                    venv_python = unix_py
                    break
            else:
                venv_python = "python"
            
        phase1_script = os.path.join(WORKSPACE_ROOT, "phase_1", "pipeline.py")
        phase2_script = os.path.join(WORKSPACE_ROOT, "phase_2", "pipeline.py")
        
        # 1. Run Phase 1 Ingestion with limit 1800 to guarantee >= 500 cleaned reviews
        print(f"[SERVER] Ingesting reviews: {venv_python} {phase1_script} --limit 1800")
        subprocess.run([venv_python, phase1_script, "--limit", "1800"], check=True, cwd=WORKSPACE_ROOT)
        
        # 2. Run Phase 2 Clustering
        print(f"[SERVER] Clustering reviews: {venv_python} {phase2_script}")
        subprocess.run([venv_python, phase2_script], check=True, cwd=WORKSPACE_ROOT)
        
        print("[SERVER] Background fetch and clustering completed successfully!")
        last_fetch_time = time.time()
    except Exception as e:
        print(f"[SERVER] Background fetch failed: {e}")
    finally:
        is_fetching = False

def trigger_background_fetch():
    global is_fetching, last_fetch_time
    
    # 5-minute cooldown to prevent spamming APIs and API token limits
    if is_fetching or (time.time() - last_fetch_time <= 300):
        return

    # Check if there is already a recent run (less than 24 hours old)
    has_recent_run = False
    data_dir = os.path.join(WORKSPACE_ROOT, "Data")
    if os.path.exists(data_dir):
        run_files = []
        for f in os.listdir(data_dir):
            if f.endswith(".json") and (f.startswith("cluster_results_") or f.startswith("realtime_clusters_")):
                parts = f.split("_")
                if len(parts) >= 3:
                    timestamp_str = parts[-2] + "_" + parts[-1].replace(".json", "")
                    try:
                        dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        run_files.append((dt, f))
                    except ValueError:
                        pass
        if run_files:
            run_files.sort(key=lambda x: x[0], reverse=True)
            newest_dt, newest_file = run_files[0]
            if datetime.utcnow() - newest_dt < timedelta(hours=24):
                has_recent_run = True

    # Only auto-trigger the sync if there is no recent run
    if not has_recent_run:
        threading.Thread(target=run_bg_fetch, daemon=True).start()

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        if self.path in ["/", "/index.html"]:
            trigger_background_fetch()
            super().do_GET()
        elif self.path == "/api/sync-status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"is_fetching": is_fetching}).encode("utf-8"))
        elif self.path == "/api/runs":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            data_dir = os.path.join(WORKSPACE_ROOT, "Data")
            runs = []
            if os.path.exists(data_dir):
                for f in os.listdir(data_dir):
                    if f.endswith(".json") and f != "growth_experiments.json" and (f.startswith("cluster_results_") or f.startswith("realtime_clusters_")):
                        path = os.path.join(data_dir, f)
                        try:
                            with open(path, "r", encoding="utf-8") as file_handle:
                                run_data = json.load(file_handle)
                                
                                timestamp = ""
                                run_type = "other"
                                if "realtime_clusters_" in f:
                                    timestamp = f.replace("realtime_clusters_", "").replace(".json", "")
                                    run_type = "Real-Time Clusters"
                                elif "cluster_results_" in f:
                                    timestamp = f.replace("cluster_results_", "").replace(".json", "")
                                    run_type = "Static Clusters"
                                elif "cleaned_reviews_" in f:
                                    timestamp = f.replace("cleaned_reviews_", "").replace(".json", "")
                                    run_type = "Cleaned Reviews"
                                elif "raw_ingested_" in f:
                                    timestamp = f.replace("raw_ingested_", "").replace(".json", "")
                                    run_type = "Raw Reviews"
                                else:
                                    timestamp = f.replace(".json", "")
                                
                                # Try parsing timestamp to pretty string
                                try:
                                    dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                                    pretty_time = dt.strftime("%b %d, %Y %I:%M %p")
                                except:
                                    pretty_time = timestamp
                                    
                                runs.append({
                                    "filename": f,
                                    "timestamp": timestamp,
                                    "pretty_time": pretty_time,
                                    "type": run_type,
                                    "data": run_data
                                })
                        except Exception:
                            pass
            runs.sort(key=lambda x: x["timestamp"], reverse=True)
            self.wfile.write(json.dumps(runs).encode("utf-8"))
            
        elif self.path == "/api/growth":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            growth_file = os.path.join(WORKSPACE_ROOT, "Data", "growth_experiments.json")
            experiments = []
            if os.path.exists(growth_file):
                try:
                    with open(growth_file, "r", encoding="utf-8") as f:
                        experiments = json.load(f)
                except Exception:
                    pass
            self.wfile.write(json.dumps(experiments).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/growth":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                new_card = json.loads(post_data.decode('utf-8'))
                growth_file = os.path.join(WORKSPACE_ROOT, "Data", "growth_experiments.json")
                
                experiments = []
                if os.path.exists(growth_file):
                    try:
                        with open(growth_file, "r", encoding="utf-8") as f:
                            experiments = json.load(f)
                    except Exception:
                        pass
                
                new_card["id"] = f"card_{int(datetime.utcnow().timestamp())}"
                new_card["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                
                experiments.append(new_card)
                
                os.makedirs(os.path.dirname(growth_file), exist_ok=True)
                with open(growth_file, "w", encoding="utf-8") as f:
                    json.dump(experiments, f, indent=2)
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "card": new_card}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

if __name__ == "__main__":
    os.chdir(DIRECTORY)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"Serving Spotify Pulse Dashboard at http://localhost:{PORT}")
        httpd.serve_forever()
