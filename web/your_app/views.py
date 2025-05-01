# web/your_app/views.py

from flask import Blueprint, render_template, redirect, url_for, request
from processor.workflow_manager import workflow_manager
from config.db import db

webapp = Blueprint('webapp', __name__)

@webapp.route('/workflows/')
def list_workflows():
    """Display all workflows."""
    workflows = workflow_manager.list_workflows()
    return render_template('workflows.html', workflows=workflows)

@webapp.route('/workflows/start/<workflow_id>')
def start_workflow(workflow_id):
    """Start a specific workflow."""
    workflow_manager.start_workflow(workflow_id)
    return redirect(url_for('webapp.list_workflows'))

@webapp.route('/workflows/new', methods=["GET", "POST"])
def create_workflow():
    """Create a new workflow."""
    if request.method == "POST":
        channels = request.form.get("channels")
        interval = int(request.form.get("interval"))
        mode = request.form.get("mode")
        threshold = int(request.form.get("threshold", 50))

        # Save workflow to database
        workflow = {
            "channels": channels.split(","),
            "interval": interval,
            "mode": mode,
            "threshold": threshold,
        }
        db.workflows.insert_one(workflow)
        return redirect(url_for("webapp.list_workflows"))

    return render_template("new_workflow.html")

@webapp.route('/')
def dashboard():
    """Dashboard landing page."""
    return render_template('dashboard.html')

@webapp.route('/start-workflow/')
def start_workflow_form():
    """Placeholder page for starting a workflow."""
    return "<h2>Start Workflow Page (Coming Soon)</h2>"

@webapp.route('/accounts/')
def manage_accounts():
    """Placeholder page for managing accounts."""
    return "<h2>Manage Accounts Page (Coming Soon)</h2>"
