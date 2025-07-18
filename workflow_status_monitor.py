import os
import time
import json
from glob import glob
import threading
from datetime import datetime

WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), "workflows")
CHECK_INTERVAL = 5  # seconds
RUNNING_THRESHOLD = 10  # seconds: if log file updated within this, workflow is running


def get_workflow_dirs():
    return [d for d in os.listdir(WORKFLOWS_DIR) if os.path.isdir(os.path.join(WORKFLOWS_DIR, d))]

def get_latest_log_file(log_dir):
    log_files = glob(os.path.join(log_dir, "*.log"))
    if not log_files:
        return None
    return max(log_files, key=os.path.getmtime)

def get_script_file(workflow_path, workflow_name):
    # Look for main script file
    script_path = os.path.join(workflow_path, f"{workflow_name}.py")
    return script_path if os.path.exists(script_path) else None

def get_config_file(workflow_path):
    config_path = os.path.join(workflow_path, "config.json")
    return config_path if os.path.exists(config_path) else None

def update_workflow_status():
    while True:
        for workflow in get_workflow_dirs():
            workflow_path = os.path.join(WORKFLOWS_DIR, workflow)
            log_dir = os.path.join(workflow_path, "logs")
            state_file = os.path.join(workflow_path, ".workflow_state.json")
            status = "stopped"
            latest_log = get_latest_log_file(log_dir)
            if latest_log and (time.time() - os.path.getmtime(latest_log) < RUNNING_THRESHOLD):
                status = "running"
            # Gather info
            script = get_script_file(workflow_path, workflow)
            config = get_config_file(workflow_path)
            state = {
                "name": workflow,
                "status": status,
                "script": os.path.basename(script) if script else None,
                "config": os.path.basename(config) if config else None,
                "last_updated": datetime.utcnow().isoformat() + "Z"
            }
            # If file exists, preserve any extra fields
            if os.path.exists(state_file):
                try:
                    with open(state_file, "r") as f:
                        existing = json.load(f)
                    # Only update known fields, preserve others
                    existing.update(state)
                    state = existing
                except Exception:
                    pass
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
        time.sleep(CHECK_INTERVAL)

def start_status_monitor_thread():
    t = threading.Thread(target=update_workflow_status, daemon=True)
    t.start()

if __name__ == "__main__":
    update_workflow_status() 