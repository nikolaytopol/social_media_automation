import os
import subprocess
import threading
import time
import json
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import signal
import logging
import glob

app = Flask(__name__)
CORS(app)
WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), 'workflows')
LOGS_DIR = 'logs'

class WorkflowInfo:
    def __init__(self, name, workflow_dir):
        self.name = name
        self.workflow_dir = workflow_dir
        self.status = "stopped"
        self.start_time = None
        self.process = None
        self.logs = []
        self.error = None
        self.restart_count = 0
        self.last_restart = None
        self.config = None
        self.log_thread = None
        self.monitor_thread = None
        self.last_error_scan = None

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "error": self.error,
            "restart_count": self.restart_count,
            "last_restart": self.last_restart.isoformat() if self.last_restart else None,
            "last_error_scan": self.last_error_scan,
        }

class WorkflowManager:
    def __init__(self, workflows_dir=WORKFLOWS_DIR, enable_monitoring=True):
        self.workflows_dir = workflows_dir
        self.enable_monitoring = enable_monitoring
        self.workflows = {}  # {workflow_name: WorkflowInfo}
        self.state_file = os.path.join(workflows_dir, '.workflow_state.json')
        self._stop_monitoring = False
        
        # Create necessary directories
        os.makedirs(LOGS_DIR, exist_ok=True)
        os.makedirs(workflows_dir, exist_ok=True)
        
        # Load existing state
        self.load_state()
        self.discover_workflows()

    def get_script_path(self, name):
        """Find the main script for a workflow"""
        for script in [f"{name}_6.py", f"{name}.py", "main.py", "silicon_echo.py"]:
            path = os.path.join(self.workflows_dir, name, script)
            if os.path.exists(path):
                return path
        return None

    def validate_workflow_structure(self, workflow_dir):
        """Validate workflow directory structure"""
        required_dirs = ['message_history', 'posted_messages', 'logs']
        for dir_name in required_dirs:
            if not os.path.exists(os.path.join(workflow_dir, dir_name)):
                os.makedirs(os.path.join(workflow_dir, dir_name))
        return True

    def discover_workflows(self):
        """Scan and register workflows"""
        for name in os.listdir(self.workflows_dir):
            workflow_dir = os.path.join(self.workflows_dir, name)
            if os.path.isdir(workflow_dir):
                if self.validate_workflow_structure(workflow_dir):
                    if name not in self.workflows:
                        self.workflows[name] = WorkflowInfo(name, workflow_dir)
                        logging.info(f"Discovered workflow: {name}")

    def start_workflow(self, workflow_name):
        """Start a workflow"""
        if workflow_name not in self.workflows:
            return False, "Workflow not found"

        workflow = self.workflows[workflow_name]
        if workflow.status == "running":
            # Before returning, check if the process is actually alive
            if workflow.process and workflow.process.poll() is not None:
                # Process has exited, mark as stopped
                workflow.status = "stopped"
                workflow.process = None
            else:
                return True, "Already running"

        # Ensure any previously spawned process is terminated
        if workflow.process and workflow.process.poll() is None:
            try:
                workflow.process.terminate()
                workflow.process.wait(timeout=3)
            except Exception:
                try:
                    workflow.process.kill()
                except Exception:
                    pass
            workflow.process = None
            workflow.status = "stopped"

        script_path = self.get_script_path(workflow_name)
        if not script_path:
            return False, "Script not found"

        try:
            # Set up environment
            env = os.environ.copy()
            # Add project root to PYTHONPATH to allow imports of modules from root
            project_root = os.path.dirname(os.path.abspath(__file__))
            python_path = env.get('PYTHONPATH', '')
            env['PYTHONPATH'] = f"{project_root}{os.pathsep}{python_path}"
            
            env_file = os.path.join(self.workflows_dir, workflow_name, '.env')
            if os.path.exists(env_file):
                with open(env_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if '=' in line:
                                key, value = line.split('=', 1)
                                value = value.strip().strip("'").strip('"')
                                env[key.strip()] = value

            # Start process with environment
            workflow.process = subprocess.Popen(
                ['/Users/userok/opt/anaconda3/envs/twitter_automation/bin/python', script_path],
                cwd=os.path.dirname(script_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env
            )
            workflow.start_time = datetime.now()
            workflow.status = "running"
            workflow.error = None
            workflow.last_error_scan = None
            
            # Start log monitoring
            self._start_log_thread(workflow)
            
            # Start process monitoring
            if self.enable_monitoring:
                self._start_monitor_thread(workflow)
            
            self.save_state()
            return True, "Started successfully"
        except Exception as e:
            workflow.error = str(e)
            return False, str(e)

    def stop_workflow(self, workflow_name):
        """Stop a workflow"""
        if workflow_name not in self.workflows:
            return False, "Workflow not found"

        workflow = self.workflows[workflow_name]
        if workflow.status != "running":
            return True, "Already stopped"

        try:
            if workflow.process and workflow.process.poll() is None:
                workflow.process.terminate()
                try:
                    workflow.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    workflow.process.kill()
            
            workflow.status = "stopped"
            workflow.process = None
            self.save_state()
            return True, "Stopped successfully"
        except Exception as e:
            workflow.error = str(e)
            return False, str(e)

    def get_workflow_status(self, workflow_name):
        """Get workflow status"""
        if workflow_name not in self.workflows:
            return None
        
        workflow = self.workflows[workflow_name]
        return workflow.to_dict()

    def get_workflow_logs(self, workflow_name, lines=50):
        """Get recent logs for a workflow"""
        log_path = os.path.join(LOGS_DIR, f"{workflow_name}.log")
        if not os.path.exists(log_path):
            return []
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.readlines()[-lines:]
        except Exception:
            return []

    def _start_log_thread(self, workflow):
        """Start log monitoring thread"""
        def log_reader():
            log_path = os.path.join(LOGS_DIR, f"{workflow.name}.log")
            with open(log_path, 'a', buffering=1) as f:
                while workflow.process and workflow.process.poll() is None:
                    line = workflow.process.stdout.readline()
                    if not line:
                        break
                    f.write(line.decode(errors='replace'))
        
        workflow.log_thread = threading.Thread(target=log_reader, daemon=True)
        workflow.log_thread.start()

    def _start_monitor_thread(self, workflow):
        """Start process monitoring thread"""
        def monitor():
            while not self._stop_monitoring and workflow.status == "running":
                if workflow.process.poll() is not None:
                    workflow.status = "error"
                    workflow.error = f"Process exited with code {workflow.process.returncode}"
                    workflow.restart_count += 1
                    workflow.last_restart = datetime.now()
                    # Scan for repeated errors in the log
                    log_path = os.path.join(LOGS_DIR, f"{workflow.name}.log")
                    if os.path.exists(log_path):
                        try:
                            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                                lines = f.readlines()[-20:]
                            # Look for repeated error patterns
                            error_counts = {}
                            for line in lines:
                                if 'Missing required Twitter API credentials' in line:
                                    error_counts['Missing required Twitter API credentials'] = error_counts.get('Missing required Twitter API credentials', 0) + 1
                                # Add more error patterns as needed
                            if error_counts:
                                workflow.last_error_scan = f"Repeated errors detected: {error_counts}"
                            else:
                                workflow.last_error_scan = None
                        except Exception as e:
                            workflow.last_error_scan = f"Error scanning log: {e}"
                    # Auto-restart if enabled
                    if self.enable_monitoring:
                        self.start_workflow(workflow.name)
                time.sleep(0.5)  # Faster polling
        
        workflow.monitor_thread = threading.Thread(target=monitor, daemon=True)
        workflow.monitor_thread.start()

    def save_state(self):
        """Save manager state to file"""
        state = {
            name: info.to_dict()
            for name, info in self.workflows.items()
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logging.error(f"Failed to save state: {e}")

    def load_state(self):
        """Load manager state from file"""
        if not os.path.exists(self.state_file):
            return
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            for name, info in state.items():
                workflow_dir = os.path.join(self.workflows_dir, name)
                if os.path.exists(workflow_dir):
                    workflow = WorkflowInfo(name, workflow_dir)
                    workflow.status = info.get('status', 'stopped')
                    workflow.error = info.get('error')
                    workflow.restart_count = info.get('restart_count', 0)
                    
                    if info.get('start_time'):
                        workflow.start_time = datetime.fromisoformat(info['start_time'])
                    if info.get('last_restart'):
                        workflow.last_restart = datetime.fromisoformat(info['last_restart'])
                    
                    self.workflows[name] = workflow
        except Exception as e:
            logging.error(f"Failed to load state: {e}")

    def shutdown(self):
        """Shutdown the manager and all workflows"""
        self._stop_monitoring = True
        for name in list(self.workflows.keys()):
            self.stop_workflow(name)
        self.save_state()

    def get_messages(self, workflow_name, message_type='history'):
        """Get messages for a workflow"""
        if workflow_name not in self.workflows:
            return []

        workflow = self.workflows[workflow_name]
        base_dir = os.path.join(workflow.workflow_dir, 
                              'message_history' if message_type == 'history' else 'posted_messages')
        
        messages = []
        if not os.path.exists(base_dir):
            return messages

        # Get all message directories
        message_dirs = sorted(glob.glob(os.path.join(base_dir, '*')), reverse=True)
        
        for msg_dir in message_dirs[:50]:  # Limit to last 50 messages
            if not os.path.isdir(msg_dir):
                continue

            message = {}
            
            # Try to load JSON file
            json_files = glob.glob(os.path.join(msg_dir, '*.json'))
            if json_files:
                try:
                    with open(json_files[0], 'r', encoding='utf-8') as f:
                        message = json.load(f)
                except Exception as e:
                    logging.error(f"Error loading JSON: {e}")
                    continue
            
            # Load text file if JSON not found
            if not message:
                text_file = os.path.join(msg_dir, 'tweet_text.txt' if message_type == 'posted' else 'original_message.txt')
                if os.path.exists(text_file):
                    try:
                        with open(text_file, 'r', encoding='utf-8') as f:
                            message['text'] = f.read()
                    except Exception as e:
                        logging.error(f"Error loading text: {e}")
                        continue

            # Get media files
            media_files = [f for f in os.listdir(msg_dir) 
                         if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.mp4'))]
            if media_files:
                message['media'] = media_files

            # Add directory name for media URLs
            message['dir'] = os.path.basename(msg_dir)
            
            messages.append(message)

        return messages

# Create global workflow manager instance
workflow_manager = WorkflowManager()

# Modified Flask routes to use WorkflowManager
@app.route('/start', methods=['POST'])
def start_workflow():
    name = request.json['name']
    success, message = workflow_manager.start_workflow(name)
    return jsonify({'status': 'success' if success else 'error', 'message': message})

@app.route('/stop', methods=['POST'])
def stop_workflow():
    name = request.json['name']
    success, message = workflow_manager.stop_workflow(name)
    return jsonify({'status': 'success' if success else 'error', 'message': message})

@app.route('/status', methods=['GET'])
def status():
    name = request.args['name']
    status = workflow_manager.get_workflow_status(name)
    # Add last error scan info if available
    if status and name in workflow_manager.workflows:
        wf = workflow_manager.workflows[name]
        if hasattr(wf, 'last_error_scan') and wf.last_error_scan:
            status['last_error_scan'] = wf.last_error_scan
    return jsonify(status if status else {'status': 'not found'})

@app.route('/list', methods=['GET'])
def list_workflows():
    return jsonify(list(workflow_manager.workflows.keys()))

@app.route('/logs', methods=['GET'])
def logs():
    name = request.args['name']
    lines = int(request.args.get('lines', 40))
    logs = workflow_manager.get_workflow_logs(name, lines)
    return Response(''.join(logs), mimetype='text/plain')

@app.route('/health', methods=['GET'])
def health():
    health = {
        name: info.status
        for name, info in workflow_manager.workflows.items()
    }
    return jsonify({'manager': 'running', 'workflows': health})

@app.route('/workflow/info', methods=['GET'])
def workflow_info():
    """Get detailed information about a workflow"""
    name = request.args['name']
    info = workflow_manager.get_workflow_status(name)
    if info:
        info['logs'] = workflow_manager.get_workflow_logs(name, 10)  # Last 10 lines
    return jsonify(info if info else {'error': 'Workflow not found'})

@app.route('/workflow/discover', methods=['POST'])
def discover_workflows():
    """Manually trigger workflow discovery"""
    workflow_manager.discover_workflows()
    return jsonify({'status': 'success', 'workflows': list(workflow_manager.workflows.keys())})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    workflow_manager.shutdown()
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    return jsonify({'status': 'manager stopped'})

@app.route('/workflow/<name>/messages/<type>')
def get_workflow_messages(name, type):
    """Get messages for a workflow"""
    messages = workflow_manager.get_messages(name, type)
    return jsonify(messages)

if __name__ == '__main__':
    app.run(port=9000, debug=True) 