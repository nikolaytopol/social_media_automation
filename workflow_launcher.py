import os
import json
import subprocess
from flask import Flask, render_template_string, redirect, url_for, request, send_file, jsonify
import threading
import time
import shutil
import uuid
import requests
import glob

WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), 'workflows')
LOGS_DIR = 'logs'
REVIEW_APP_PORT_BASE = 6000  # Each workflow gets its own port
MANAGER_URL = "http://localhost:9000"

app = Flask(__name__)

# Track running processes: {workflow_name: (process, log_path)}
running_workflows = {}

STYLE = '''<style>
body { font-family: 'Segoe UI', Arial, sans-serif; background: #f6f8fa; margin: 0; }
.header { position: sticky; top: 0; background: #fff; z-index: 10; padding: 16px 0 8px 0; box-shadow: 0 2px 8px #0001; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px; }
.workflow-table { width: 100%; border-collapse: collapse; margin-bottom: 32px; }
.workflow-table th, .workflow-table td { padding: 12px 16px; text-align: left; }
.workflow-table th { background: #f0f1f3; }
.workflow-table tr { transition: background 0.2s; }
.workflow-table tr:hover { background: #e6f0fa; }
.status-running { color: #2ecc40; font-weight: bold; }
.status-stopped { color: #ff4136; font-weight: bold; }
.btn { padding: 7px 18px; border: none; border-radius: 4px; background: #0074d9; color: #fff; cursor: pointer; font-size: 15px; margin-right: 8px; transition: background 0.2s, box-shadow 0.2s; box-shadow: 0 2px 4px #0001; }
.btn:hover { background: #005fa3; }
.btn-stop { background: #ff4136; }
.btn-stop:hover { background: #c9302c; }
.btn-manage { background: #2ecc40; }
.btn-manage:hover { background: #27ae60; }
.section { margin-bottom: 32px; }
.section-header { font-size: 1.3em; font-weight: 600; margin-bottom: 12px; border-bottom: 2px solid #e0e0e0; padding-bottom: 4px; }
.tweet-columns { display: flex; gap: 32px; flex-wrap: wrap; }
.tweet-col { flex: 1 1 350px; min-width: 320px; background: #f9fafb; border-radius: 10px; padding: 18px; box-shadow: 0 2px 8px #0001; }
.tweet-card { background: #fff; border-radius: 8px; box-shadow: 0 1px 4px #0001; margin-bottom: 18px; padding: 14px 16px; transition: box-shadow 0.2s, background 0.2s; position: relative; }
.tweet-card:hover { box-shadow: 0 4px 16px #0002; background: #f0f8ff; }
.tweet-media { margin-top: 8px; }
.tweet-media img, .tweet-media video { max-width: 100%; max-height: 180px; border-radius: 6px; margin-right: 8px; margin-bottom: 6px; }
.tweet-meta { font-size: 0.95em; color: #888; margin-bottom: 6px; }
.review-status { font-size: 0.95em; color: #b8860b; margin-bottom: 6px; }
.log-window { background: #222; color: #eee; font-family: monospace; font-size: 14px; border-radius: 8px; padding: 14px; height: 260px; overflow-y: auto; margin-bottom: 18px; white-space: pre-line; border: 1px solid #ccc; }
.modal-bg { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100vw; height: 100vh; background: #0007; }
.modal { display: none; position: fixed; z-index: 1001; left: 50%; top: 50%; transform: translate(-50%, -50%); background: #fff; border-radius: 10px; box-shadow: 0 8px 32px #0003; padding: 32px 28px; min-width: 320px; }
.modal h2 { margin-top: 0; }
.modal textarea { width: 100%; min-height: 60px; margin-bottom: 16px; border-radius: 6px; border: 1px solid #ccc; padding: 8px; font-size: 15px; }
.modal .btn { margin-right: 0; }
@media (max-width: 900px) { .tweet-columns { flex-direction: column; gap: 18px; } .tweet-col { min-width: 0; } }
</style>'''

def get_workflow_entries():
    entries = []
    for fname in os.listdir(WORKFLOWS_DIR):
        if os.path.isdir(os.path.join(WORKFLOWS_DIR, fname)):
            config_path = os.path.join(WORKFLOWS_DIR, fname, 'config.json')
            script_path = os.path.join(WORKFLOWS_DIR, fname, f'{fname}.py')
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    entries.append({
                        'name': fname,
                        'type': 'Config',
                        'config': cfg
                    })
            elif os.path.exists(script_path):
                entries.append({
                    'name': fname,
                    'type': 'Script',
                    'file': f'{fname}.py'
                })
    return entries

def get_workflow_status(name):
    return 'Running' if name in running_workflows else 'Stopped'

def get_run_workflows():
    # List all subdirectories in workflows/ as workflows
    return [d for d in os.listdir(WORKFLOWS_DIR) 
            if os.path.isdir(os.path.join(WORKFLOWS_DIR, d))]

def is_workflow_running(name):
    # Check if a workflow is running by looking for a process in running_workflows
    return name in running_workflows

@app.route('/')
def home():
    workflows = get_run_workflows()
    html = STYLE + '<h1 style="text-align:center;">Workflow Launcher</h1>'
    html += '<div class="container"><table class="workflow-table"><tr><th>Name</th><th>Status</th><th>Actions</th></tr>'
    for wf in workflows:
        # Query manager for status
        try:
            r = requests.get(f"{MANAGER_URL}/status", params={'name': wf}, timeout=2)
            status = r.json().get('status', 'Unknown')
        except Exception:
            status = 'Unknown'
        html += f'<tr><td><b>{wf}</b></td>'
        html += f'<td class="status-{status.lower()}">{status}</td>'
        html += '<td>'
        if status == 'stopped':
            html += f'<a class="btn" href="/start/{wf}">Start</a>'
        elif status == 'running':
            html += f'<a class="btn btn-stop" href="/stop/{wf}">Stop</a>'
        html += f'<a class="btn btn-manage" href="/workflow/{wf}/manage">Manage</a></td></tr>'
    html += '</table>'
    html += '<form method="post" action="/shutdown_manager" style="display:inline;"><button class="btn btn-stop" type="submit">Shutdown Manager</button></form>'
    html += '</div>'
    return html

@app.route('/start/<name>')
def start_workflow(name):
    requests.post(f"{MANAGER_URL}/start", json={'name': name})
    return redirect(url_for('home'))

@app.route('/stop/<name>')
def stop_workflow(name):
    requests.post(f"{MANAGER_URL}/stop", json={'name': name})
    return redirect(url_for('home'))

@app.route('/shutdown_manager', methods=['POST'])
def shutdown_manager():
    try:
        requests.post(f"{MANAGER_URL}/shutdown", timeout=2)
    except Exception:
        pass
    return '<h2>Manager has been shut down. Please close this page.</h2>'

@app.route('/start_api/<name>', methods=['POST'])
def start_api(name):
    r = requests.post(f"{MANAGER_URL}/start", json={'name': name})
    return jsonify(r.json())

@app.route('/stop_api/<name>', methods=['POST'])
def stop_api(name):
    r = requests.post(f"{MANAGER_URL}/stop", json={'name': name})
    return jsonify(r.json())

def get_tweet_dirs(base_dir, subdir):
    d = os.path.join(base_dir, subdir)
    if not os.path.exists(d):
        return []
    return [os.path.join(d, x) for x in sorted(os.listdir(d)) if os.path.isdir(os.path.join(d, x))]

def get_tweet_jsons(tweet_dir):
    if not os.path.exists(tweet_dir):
        return []
    return [os.path.join(tweet_dir, f) for f in sorted(os.listdir(tweet_dir)) if f.endswith('.json')]

def get_tweet_data_flexible(base_dir, subdir, posted=True):
    tweet_dirs = get_tweet_dirs(base_dir, subdir)
    tweets = []
    for tdir in tweet_dirs:
        jsons = get_tweet_jsons(tdir)
        tweet = {}
        if jsons:
            for f in jsons:
                try:
                    with open(f, 'r', encoding='utf-8') as jf:
                        data = json.load(jf)
                    data['__json_path'] = f
                    tweet = data
                except Exception:
                    continue
        else:
            # Fallback: look for .txt and media
            if posted:
                txt_file = os.path.join(tdir, 'tweet_text.txt')
            else:
                txt_file = os.path.join(tdir, 'original_message.txt')
            if os.path.exists(txt_file):
                with open(txt_file, 'r', encoding='utf-8') as f:
                    tweet['text'] = f.read()
            media = [f for f in os.listdir(tdir) if f.lower().endswith(('.jpg','.jpeg','.png','.gif','.mp4'))]
            tweet['media'] = media
            tweet['__json_path'] = tdir  # fallback for modal
            tweet['__sort_key'] = os.path.basename(tdir)
        # Try to load all decision files
        decision_files = {
            'filter_model': 'filter_model_details.json',
            'duplicate_checker': 'duplicate_checker_details.json',
            'tweet_generation': 'tweet_generation_details.json'
        }
        for model_type, filename in decision_files.items():
            decision_path = os.path.join(tdir, filename)
            if os.path.exists(decision_path):
                try:
                    with open(decision_path, "r", encoding="utf-8") as f:
                        if 'decisions' not in tweet:
                            tweet['decisions'] = {}
                        tweet['decisions'][model_type] = json.load(f)
                except Exception:
                    continue
        # Ensure __json_path is always present
        if '__json_path' not in tweet:
            tweet['__json_path'] = tdir
        tweets.append(tweet)
    
    # Sort by timestamp descending, fallback to dir/file name descending
    def sort_key(x):
        ts = x.get('timestamp')
        if ts:
            return ts
        return x.get('__sort_key', '')
    return sorted(tweets, key=sort_key, reverse=True)

@app.route('/workflow/<workflow_name>/manage', methods=['GET'])
def manage_workflow(workflow_name):
    workflow_dir = os.path.join(WORKFLOWS_DIR, workflow_name)
    
    # Update directory names to match your workflow structure
    posted_dirs = list(reversed(get_tweet_dirs(workflow_dir, 'posted_messages')))
    received_dirs = list(reversed(get_tweet_dirs(workflow_dir, 'message_history')))

    # Show latest log from workflow's own logs folder
    log_dir = os.path.join(workflow_dir, 'logs')
    log_files = glob.glob(os.path.join(log_dir, '*.log'))
    log_file = max(log_files, key=os.path.getmtime) if log_files else None
    log_content = ''
    if log_file and os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            log_content = f.read()[-8000:]
    log_html = f'''
    <div class="log-window" id="log-window">Loading logs...</div>
    <script>
    function fetchLogs() {{
        fetch('/workflow/{workflow_name}/latest_log').then(r => r.text()).then(txt => {{
            document.getElementById('log-window').innerText = txt;
        }});
    }}
    fetchLogs();
    setInterval(fetchLogs, 5000);
    </script>
    '''

    # Main two columns: show each message as a card with media, text, and file links
    tweets_html = (
        '<div style="text-align:right;margin-bottom:8px;">'
        '<button class="btn" id="refresh-tweets-btn" type="button">Refresh</button>'
        '</div>'
        '<div id="tweets-columns-container">'
        + render_tweet_columns(posted_dirs, received_dirs, workflow_name) +
        '</div>'
        '<script>'
        'document.getElementById("refresh-tweets-btn").onclick = function() {'
        '    fetch("/workflow/{workflow_name}/tweet_columns").then(r => r.text()).then(html => {'
        '        document.getElementById("tweets-columns-container").innerHTML = html;'
        '    });'
        '};'
        '</script>'
    )

    # Start/Stop controls
    status = 'Running' if is_workflow_running(workflow_name) else 'Stopped'
    controls_html = '<div class="section-header">Workflow Controls</div>'
    controls_html += f'<span id="workflow-status" class="status-{("running" if status == "Running" else "stopped")}">{status}</span>'
    controls_html += f'<div style="color:#888;font-size:0.95em;">[Debug] Status value: <span id="debug-status-value">{status}</span></div>'
    # Render both buttons, hide one with CSS
    start_display = '' if status.lower() in ['stopped'] else 'display:none;'
    stop_display = '' if status.lower() in ['running', 'error'] else 'display:none;'
    controls_html += f'<button class="btn" id="start-btn" style="{start_display}">Start</button>'
    controls_html += f'<button class="btn btn-stop" id="stop-btn" style="{stop_display}">Stop</button>'
    controls_html += f'<a class="btn" href="/">Back to Launcher</a>'

    # Modal and script (unchanged)
    modal_html = '''<div class="modal-bg" id="modal-bg"></div>
    <div class="modal" id="modal">
        <h2>Mark as Incorrect</h2>
        <form id="incorrect-form">
            <input type="hidden" name="json_path" id="modal-json-path">
            <input type="hidden" name="tweet_type" id="modal-tweet-type">
            <textarea name="comment" id="modal-comment" placeholder="Describe why this is incorrect (optional)"></textarea>
            <button type="submit" class="btn btn-stop">Submit</button>
            <button type="button" class="btn" onclick="closeModal()">Cancel</button>
        </form>
    </div>
    <script>
    function openModal(jsonPath, tweetType) {
        document.getElementById('modal-bg').style.display = 'block';
        document.getElementById('modal').style.display = 'block';
        document.getElementById('modal-json-path').value = jsonPath;
        document.getElementById('modal-tweet-type').value = tweetType;
    }
    function closeModal() {
        document.getElementById('modal-bg').style.display = 'none';
        document.getElementById('modal').style.display = 'none';
    }
    document.getElementById('incorrect-form').onsubmit = function(e) {
        e.preventDefault();
        fetch('/mark_incorrect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                json_path: document.getElementById('modal-json-path').value,
                tweet_type: document.getElementById('modal-tweet-type').value,
                comment: document.getElementById('modal-comment').value
            })
        }).then(r => r.json()).then(data => {
            closeModal();
            if (data.success) {
                alert('Marked as incorrect!');
                window.location.reload();
            } else {
                alert('Error: ' + data.error);
            }
        });
    };
    </script>'''

    # Add AJAX for Start/Stop and live status polling
    extra_js = f'''
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        var startBtn = document.getElementById('start-btn');
        var stopBtn = document.getElementById('stop-btn');
        function updateStatus() {{
            fetch('{MANAGER_URL}/status?name={workflow_name}')
                .then(r => r.json())
                .then(data => {{
                    var status = data.status || 'Unknown';
                    var statusSpan = document.getElementById('workflow-status');
                    var debugStatus = document.getElementById('debug-status-value');
                    if (statusSpan) {{
                        statusSpan.textContent = status.charAt(0).toUpperCase() + status.slice(1);
                        statusSpan.className = 'status-' + status.toLowerCase();
                    }}
                    if (debugStatus) {{
                        debugStatus.textContent = status;
                    }}
                    // Show/hide Start/Stop buttons based on status
                    if (startBtn && stopBtn) {{
                        if (['running','error'].includes(status.toLowerCase())) {{
                            startBtn.style.display = 'none';
                            stopBtn.style.display = '';
                        }} else if (['stopped'].includes(status.toLowerCase())) {{
                            startBtn.style.display = '';
                            stopBtn.style.display = 'none';
                        }} else {{
                            startBtn.style.display = '';
                            stopBtn.style.display = '';
                        }}
                    }}
                }});
        }}
        if (startBtn) {{
            startBtn.onclick = function(e) {{
                e.preventDefault();
                fetch('/start_api/{workflow_name}', {{method: 'POST'}})
                    .then(r => r.json())
                    .then(data => {{
                        if (data.status === 'success') {{
                            updateStatus();
                        }} else {{
                            alert('Error: ' + data.message);
                        }}
                    }});
            }};
        }}
        if (stopBtn) {{
            stopBtn.onclick = function(e) {{
                e.preventDefault();
                fetch('/stop_api/{workflow_name}', {{method: 'POST'}})
                    .then(r => r.json())
                    .then(data => {{
                        if (data.status === 'success') {{
                            updateStatus();
                        }} else {{
                            alert('Error: ' + data.message);
                        }}
                    }});
            }};
        }}
        // Poll status every 5 seconds
        setInterval(updateStatus, 5000);
        updateStatus();
    }});
    </script>
    '''

    return STYLE + f'<h1 style="text-align:center;">Manage Workflow: {workflow_name}</h1>' + controls_html + log_html + tweets_html + modal_html + extra_js

@app.route('/media/<workflow>/<subdir>/<dir>/<filename>')
def media(workflow, subdir, dir, filename):
    """
    Handle media file requests for workflow directories.
    Supports files in message_history and posted_messages folders.
    """
    # First try the direct expected path
    file_path = os.path.join(WORKFLOWS_DIR, workflow, subdir, dir, filename)
    
    if os.path.exists(file_path):
        return send_file(file_path)
        
    # Try searching in just the message directory
    alt_path = os.path.join(WORKFLOWS_DIR, workflow, subdir, filename)
    if os.path.exists(alt_path):
        return send_file(alt_path)
    
    # Try searching within all message directories in the subdir
    message_dir = os.path.join(WORKFLOWS_DIR, workflow, subdir)
    if os.path.exists(message_dir):
        for root, _, files in os.walk(message_dir):
            if filename in files:
                return send_file(os.path.join(root, filename))
    
    # Create static folder for placeholder if it doesn't exist
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    os.makedirs(static_dir, exist_ok=True)
    
    # If placeholder exists, use it
    placeholder_path = os.path.join(static_dir, 'placeholder.jpg')
    if not os.path.exists(placeholder_path):
        # Create a simple placeholder image (1x1 pixel)
        try:
            with open(placeholder_path, 'wb') as f:
                # Minimal valid JPG file (1x1 pixel)
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xdb\x00C\x01\t\t\t\x0c\x0b\x0c\x18\r\r\x182!\x1c!22222222222222222222222222222222222222222222222222\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc4\x00\x1f\x01\x00\x03\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x11\x00\x02\x01\x02\x04\x04\x03\x04\x07\x05\x04\x04\x00\x01\x02w\x00\x01\x02\x03\x11\x04\x05!1\x06\x12AQ\x07aq\x13"2\x81\x08\x14B\x91\xa1\xb1\xc1\t#3R\xf0\x15br\xd1\n\x16$4\xe1%\xf1\x17\x18\x19\x1a&\'()*56789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\xfe\xfe(\xa2\x8a\x00\xff\xd9')
        except Exception:
            # If can't create placeholder, return a simple error message
            return "Image not found", 404
    
    return send_file(placeholder_path)

@app.route('/mark_incorrect', methods=['POST'])
def mark_incorrect():
    data = request.json
    json_path = data['json_path']
    comment = data.get('comment', '')
    tweet_type = data.get('tweet_type', '')
    
    # Use tweet_type directly since old directories are removed
    actual_tweet_type = tweet_type
    workflow_name = json_path.split('/workflows/')[1].split('/')[0]
    workflow_dir = os.path.join(WORKFLOWS_DIR, workflow_name)

    # If the path is a directory, look for a .json file inside
    if os.path.isdir(json_path):
        json_files = [f for f in os.listdir(json_path) if f.endswith('.json')]
        if json_files:
            json_path = os.path.join(json_path, json_files[0])  # Use the first JSON file found
        else:
            # No JSON file: create one from directory contents
            tweet = {}
            # Use correct directory names for text files
            txt_file = os.path.join(json_path, 'tweet_text.txt' if actual_tweet_type == 'posted_messages' else 'original_message.txt')
            if os.path.exists(txt_file):
                with open(txt_file, 'r', encoding='utf-8') as f:
                    tweet['text'] = f.read()
            # Get media
            media = [f for f in os.listdir(json_path) if f.lower().endswith(('.jpg','.jpeg','.png','.gif','.mp4'))]
            tweet['media'] = media
            # Add review info
            tweet['review'] = {
                'status': 'incorrect',
                'reason': comment
            }
            retraining_dir = os.path.join(workflow_dir, 'retraining')
            os.makedirs(retraining_dir, exist_ok=True)
            new_json_path = os.path.join(retraining_dir, f"{os.path.basename(json_path)}_{uuid.uuid4().hex[:8]}.json")
            with open(new_json_path, 'w', encoding='utf-8') as f:
                json.dump(tweet, f, ensure_ascii=False, indent=2)
            return jsonify({'success': True})

    # If we get here, json_path is a file
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            tweet = json.load(f)
        # Update review field
        if 'review' not in tweet:
            tweet['review'] = {}
        tweet['review']['status'] = 'incorrect'
        tweet['review']['reason'] = comment
        
        model_type = 'filter_model' if actual_tweet_type == 'message_history' else 'tweet_generation'
        retraining_dir = os.path.join(workflow_dir, 'retraining', model_type)
        os.makedirs(retraining_dir, exist_ok=True)
        
        new_path = os.path.join(retraining_dir, os.path.basename(json_path))
        with open(new_path, 'w', encoding='utf-8') as f:
            json.dump(tweet, f, ensure_ascii=False, indent=2)
        # Optionally, remove or mark the original file
        os.remove(json_path)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in mark_incorrect: {e}")
        return jsonify({'success': False, 'error': str(e)})

def init_workflow(workflow_name, config=None, script_path=None):
    """Initialize a new workflow directory structure."""
    workflow_dir = os.path.join(WORKFLOWS_DIR, workflow_name)
    os.makedirs(workflow_dir, exist_ok=True)

    # Create required subdirectories with updated names
    for subdir in ['message_history', 'posted_messages', 'logs', 'retraining']:
        os.makedirs(os.path.join(workflow_dir, subdir), exist_ok=True)

    # Create empty .env file
    open(os.path.join(workflow_dir, '.env'), 'a').close()

    # Either config.json or .py file
    if config:
        with open(os.path.join(workflow_dir, 'config.json'), 'w') as f:
            json.dump(config, f, indent=2)
    elif script_path:
        shutil.copy(script_path, os.path.join(workflow_dir, os.path.basename(script_path)))
    else:
        raise ValueError("Must provide either config or script_path")

    print(f"Initialized workflow directory: {workflow_dir}")

# Add helper to render tweet columns as HTML (for AJAX refresh)
def render_tweet_columns(posted_dirs, received_dirs, workflow_name):
    tweets_html = '<div class="tweet-columns">'
    # Posted Tweets
    tweets_html += '<div class="tweet-col"><div class="section-header">Posted Tweets</div>'
    if posted_dirs:
        for tdir in posted_dirs:
            files = os.listdir(tdir)
            media = [f for f in files if f.lower().endswith((".jpg",".jpeg",".png",".gif",".mp4"))]
            texts = [f for f in files if f.lower().endswith((".txt"))]
            others = [f for f in files if f not in media + texts]
            tweets_html += f'<div class="tweet-card">'
            txt_file = os.path.join(tdir, 'tweet_text.txt')
            if os.path.exists(txt_file):
                with open(txt_file, 'r', encoding='utf-8') as f:
                    tweets_html += f'<b>Text:</b> <pre style="word-break:break-word;white-space:pre-wrap;">{f.read()}</pre>'
            if media:
                tweets_html += '<b>Media:</b><br>'
                for m in media:
                    if m.lower().endswith((".jpg",".jpeg",".png",".gif")):
                        tweets_html += f'<img src="/media/{workflow_name}/posted_messages/{os.path.basename(tdir)}/{m}" style="max-width:120px;max-height:90px;margin:2px;vertical-align:middle;" onerror="this.style.display=\'none\';"> '
                    elif m.lower().endswith('.mp4'):
                        tweets_html += f'<video style="max-width:120px;max-height:90px;margin:2px;vertical-align:middle;" controls><source src="/media/{workflow_name}/posted_messages/{os.path.basename(tdir)}/{m}"></video> '
            if others:
                tweets_html += '<br><b>Other files:</b><ul style="margin:0 0 0 16px;padding:0;">'
                for o in others:
                    tweets_html += f'<li><a href="/media/{workflow_name}/posted_messages/{os.path.basename(tdir)}/{o}" target="_blank">{o}</a></li>'
                tweets_html += '</ul>'
            tweets_html += f'<button class="btn btn-stop" onclick="openModal(\'{tdir}\', \'posted_messages\')">Mark as Incorrect</button>'
            tweets_html += '</div>'
    else:
        tweets_html += '<i>No posted tweets found.</i>'
    tweets_html += '</div>'
    # Received Tweets
    tweets_html += '<div class="tweet-col"><div class="section-header">Received Tweets</div>'
    if received_dirs:
        for tdir in received_dirs:
            files = os.listdir(tdir)
            media = [f for f in files if f.lower().endswith((".jpg",".jpeg",".png",".gif",".mp4"))]
            texts = [f for f in files if f.lower().endswith((".txt"))]
            others = [f for f in files if f not in media + texts]
            tweets_html += f'<div class="tweet-card">'
            txt_file = os.path.join(tdir, 'original_message.txt')
            if os.path.exists(txt_file):
                with open(txt_file, 'r', encoding='utf-8') as f:
                    tweets_html += f'<b>Text:</b> <pre style="word-break:break-word;white-space:pre-wrap;">{f.read()}</pre>'
            if media:
                tweets_html += '<b>Media:</b><br>'
                for m in media:
                    if m.lower().endswith((".jpg",".jpeg",".png",".gif")):
                        tweets_html += f'<img src="/media/{workflow_name}/message_history/{os.path.basename(tdir)}/{m}" style="max-width:120px;max-height:90px;margin:2px;vertical-align:middle;" onerror="this.style.display=\'none\';"> '
                    elif m.lower().endswith('.mp4'):
                        tweets_html += f'<video style="max-width:120px;max-height:90px;margin:2px;vertical-align:middle;" controls><source src="/media/{workflow_name}/message_history/{os.path.basename(tdir)}/{m}"></video> '
            if others:
                tweets_html += '<br><b>Other files:</b><ul style="margin:0 0 0 16px;padding:0;">'
                for o in others:
                    tweets_html += f'<li><a href="/media/{workflow_name}/message_history/{os.path.basename(tdir)}/{o}" target="_blank">{o}</a></li>'
                tweets_html += '</ul>'
            tweets_html += f'<button class="btn btn-stop" onclick="openModal(\'{tdir}\', \'message_history\')">Mark as Incorrect</button>'
            tweets_html += '</div>'
    else:
        tweets_html += '<i>No received tweets found.</i>'
    tweets_html += '</div></div>'
    return tweets_html

# Add Flask routes for AJAX endpoints
@app.route('/workflow/<workflow_name>/latest_log')
def latest_log(workflow_name):
    workflow_dir = os.path.join(WORKFLOWS_DIR, workflow_name)
    log_dir = os.path.join(workflow_dir, 'logs')
    log_files = glob.glob(os.path.join(log_dir, '*.log'))
    log_file = max(log_files, key=os.path.getmtime) if log_files else None
    if log_file and os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()[-8000:]
    return 'No logs found.'

@app.route('/workflow/<workflow_name>/tweet_columns')
def tweet_columns(workflow_name):
    workflow_dir = os.path.join(WORKFLOWS_DIR, workflow_name)
    posted_dirs = list(reversed(get_tweet_dirs(workflow_dir, 'posted_messages')))
    received_dirs = list(reversed(get_tweet_dirs(workflow_dir, 'message_history')))
    return render_tweet_columns(posted_dirs, received_dirs, workflow_name)

if __name__ == '__main__':
    app.run(debug=True, port=7000) 