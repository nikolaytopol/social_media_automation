import subprocess
import atexit
import os
import signal
import time
import sys

PID_FILE = ".processes.pid"
processes = []

def cleanup():
    """
    Function to be called on script exit.
    Terminates all child processes started by this script.
    """
    print("Shutting down child processes...")
    for p in processes:
        try:
            if p.poll() is None:  # Check if the process is still running
                print(f"Terminating process {p.pid}...")
                p.terminate()
                p.wait(timeout=5)
        except ProcessLookupError:
            # Process might have already been terminated
            pass
        except subprocess.TimeoutExpired:
            print(f"Process {p.pid} did not terminate gracefully, killing.")
            p.kill()
    
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    print("Cleanup complete.")

def kill_previous_processes():
    """
    Reads PIDs from the PID_FILE and terminates those processes
    if they are still running.
    """
    if not os.path.exists(PID_FILE):
        return
        
    print("Found existing PID file, attempting to kill previous processes...")
    with open(PID_FILE, 'r') as f:
        pids = [int(pid) for pid in f.read().splitlines() if pid.strip()]

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to process {pid}")
        except ProcessLookupError:
            print(f"Process {pid} not found, likely already stopped.")
        except Exception as e:
            print(f"Error killing process {pid}: {e}")
    
    # Give processes a moment to die
    time.sleep(2)
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)

# Register the cleanup function to be called on exit
atexit.register(cleanup)

# Kill any processes from a previous run
kill_previous_processes()

# --- Start the applications ---

# Use sys.executable to ensure subprocesses use the same python interpreter
python_executable = sys.executable

# Start Workflow Manager
manager_process = subprocess.Popen([python_executable, 'workflow_manager.py'])
processes.append(manager_process)
print(f"Started Workflow Manager with PID: {manager_process.pid}")

# Wait a moment for the manager to initialize before starting the launcher
time.sleep(2)

# Start Workflow Launcher
launcher_process = subprocess.Popen([python_executable, 'workflow_launcher.py'])
processes.append(launcher_process)
print(f"Started Workflow Launcher with PID: {launcher_process.pid}")

# --- Save PIDs and wait ---

# Save the PIDs of the new processes
with open(PID_FILE, 'w') as f:
    for p in processes:
        f.write(f"{p.pid}\n")

print("\nApplications are running. Press Ctrl+C to stop.")
try:
    # Wait for the launcher process to exit. 
    # Since it's a web server, it will run until interrupted.
    launcher_process.wait()
except KeyboardInterrupt:
    print("\nCtrl+C received, initiating shutdown...") 