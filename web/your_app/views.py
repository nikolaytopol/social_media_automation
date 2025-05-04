# web/your_app/views.py
import os
import sys

# Add the project root directory to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import asyncio
from processor.workflow_manager import WorkflowManager
from bson.objectid import ObjectId
from datetime import datetime

webapp = Blueprint('webapp', __name__)
workflow_manager = WorkflowManager()

def validate_workflow_config(config):
    """Validate workflow configuration before creation."""
    errors = []
    
    # Check sources
    if not config.get("sources") or len(config["sources"]) == 0:
        errors.append("At least one source channel is required")
    
    # Check destinations
    if not config.get("destinations") or len(config["destinations"]) == 0:
        errors.append("At least one destination channel is required")
    
    # Check for valid Telegram channels
    for source in config.get("sources", []):
        if not source["name"].startswith("@") and not source["name"].isdigit():
            errors.append(f"Invalid source format: {source['name']}. Use @channelname or channel ID")
    
    for dest in config.get("destinations", []):
        if not dest["name"].startswith("@") and not dest["name"].isdigit():
            errors.append(f"Invalid destination format: {dest['name']}. Use @channelname or channel ID")
    
    return errors

@webapp.route('/')
def dashboard():
    """Dashboard with workflow stats and controls."""
    active_count = sum(1 for wf in workflow_manager.list_workflows() if wf.get("status") == "running")
    total_count = len(workflow_manager.list_workflows())
    return render_template('dashboard.html', active_count=active_count, total_count=total_count)

@webapp.route('/workflows/')
def list_workflows():
    """List all workflows."""
    workflows = workflow_manager.list_workflows()
    return render_template('workflows.html', workflows=workflows)

@webapp.route('/workflows/new', methods=["GET", "POST"])
def create_workflow():
    """Create a new workflow."""
    if request.method == "POST":
        try:
            # Extract form data
            workflow_type = request.form.get("type", "live")
            sources = [{"type": "telegram", "name": src.strip()} 
                      for src in request.form.get("sources", "").split(",") if src.strip()]
            destinations = [{"type": "telegram", "name": dst.strip()} 
                           for dst in request.form.get("destination", "").split(",") if dst.strip()]
            
            # Create workflow config
            workflow_config = {
                "user_id": 1,  # In production, use actual user ID
                "type": workflow_type,
                "sources": sources,
                "destinations": destinations,
                "filter_prompt": request.form.get("filter_prompt", ""),
                "mod_prompt": request.form.get("mod_prompt", ""),
                "duplicate_check": request.form.get("duplicate_check") == "on",
                "preserve_files": request.form.get("preserve_files") == "on",
                "ai_provider": {
                    "name": request.form.get("ai_provider", "openai"),
                    "model": request.form.get("ai_model", "gpt-4o-2024-11-20")
                }
            }
            
            # Add start date for history workflows
            if workflow_type == "history":
                workflow_config["start_date"] = request.form.get("start_date", "")
            
            # Validate configuration
            errors = validate_workflow_config(workflow_config)
            if errors:
                for error in errors:
                    flash(error, "error")
                return render_template("new_workflow.html")
            
            # Create the workflow
            workflow_id = workflow_manager.create_workflow(workflow_config)
            
            # Start immediately if requested
            if request.form.get("start_immediately") == "on":
                success = workflow_manager.start_workflow(workflow_id)
                if success:
                    flash("Workflow created and started successfully", "success")
                else:
                    flash("Workflow created but failed to start. Check your Telegram credentials.", "warning")
            else:
                flash("Workflow created successfully", "success")
            
            return redirect(url_for("webapp.list_workflows"))
            
        except Exception as e:
            flash(f"Error creating workflow: {str(e)}", "error")
            import traceback
            print(traceback.format_exc())
    
    return render_template("new_workflow.html")

@webapp.route('/workflows/start/<workflow_id>')
def start_workflow(workflow_id):
    """Start a specific workflow."""
    try:
        success = workflow_manager.start_workflow(workflow_id)
        if success:
            flash("Workflow started successfully", "success")
        else:
            flash("Failed to start workflow", "error")
    except Exception as e:
        flash(f"Error starting workflow: {str(e)}", "error")
    return redirect(url_for('webapp.list_workflows'))

@webapp.route('/workflows/start', methods=['GET'])
def start_workflow_form():
    """Display form to start a new workflow."""
    try:
        workflows = workflow_manager.list_workflows()
        
        # Check if there are any stopped workflows available to start
        has_available = any(wf.get('status') == 'stopped' for wf in workflows)
        if not has_available:
            flash("No workflows available to start. Create a new workflow first.", "info")
            
        return render_template('start_workflow_form.html', workflows=workflows)
    except Exception as e:
        flash(f"Error retrieving workflows: {str(e)}", "error")
        return redirect(url_for('webapp.dashboard'))

@webapp.route('/workflows/stop/<workflow_id>')
def stop_workflow(workflow_id):
    """Stop a specific workflow."""
    try:
        success = workflow_manager.stop_workflow(workflow_id)
        if success:
            flash("Workflow stopped successfully", "success")
        else:
            flash("Failed to stop workflow", "error")
    except Exception as e:
        flash(f"Error stopping workflow: {str(e)}", "error")
    return redirect(url_for('webapp.list_workflows'))

@webapp.route('/workflows/delete/<workflow_id>')
def delete_workflow(workflow_id):
    """Delete a specific workflow."""
    try:
        success = workflow_manager.delete_workflow(workflow_id)
        if success:
            flash("Workflow deleted successfully", "success")
        else:
            flash("Failed to delete workflow", "error")
    except Exception as e:
        flash(f"Error deleting workflow: {str(e)}", "error")
    return redirect(url_for('webapp.list_workflows'))

@webapp.route('/workflows/edit/<workflow_id>', methods=["GET", "POST"])
def edit_workflow(workflow_id):
    """Edit an existing workflow."""
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        flash("Workflow not found", "error")
        return redirect(url_for('webapp.list_workflows'))
    
    if request.method == "POST":
        # Only allow updating certain fields when workflow is stopped
        if workflow.get("status") == "running":
            flash("Stop the workflow before editing", "error")
            return redirect(url_for('webapp.list_workflows'))
            
        # Extract form data and update the workflow
        updates = {
            "filter_prompt": request.form.get("filter_prompt", ""),
            "mod_prompt": request.form.get("mod_prompt", ""),
            "duplicate_check": request.form.get("duplicate_check") == "on",
            "preserve_files": request.form.get("preserve_files") == "on",
            "ai_provider": {
                "name": request.form.get("ai_provider", "openai"),
                "model": request.form.get("ai_model", "gpt-4o-2024-11-20")
            }
        }
        
        # Update the workflow
        workflow_manager.update_workflow(workflow_id, updates)
        flash("Workflow updated successfully", "success")
        return redirect(url_for('webapp.list_workflows'))
    
    return render_template("edit_workflow.html", workflow=workflow)

@webapp.route('/workflows/presets')
def list_workflow_presets():
    """Temporary placeholder for workflow presets."""
    flash("Preset workflows feature coming soon!", "info")
    return redirect(url_for('webapp.dashboard'))

@webapp.route('/accounts/')
def manage_accounts():
    """Temporary placeholder for account management."""
    flash("Account management feature coming soon!", "info")
    return redirect(url_for('webapp.dashboard'))

@webapp.route('/workflows/messages/<workflow_id>')
def workflow_messages(workflow_id):
    """View messages processed by a specific workflow."""
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        flash("Workflow not found", "error")
        return redirect(url_for('webapp.list_workflows'))
    
    # Get messages from the database - FIXED CODE HERE
    db = workflow_manager.db  # Use .db instead of .client[workflow_manager.db_name]
    messages = list(db.workflow_messages.find({"workflow_id": workflow_id}).sort("timestamp", -1).limit(100))
    
    return render_template('workflow_messages.html', workflow=workflow, messages=messages)

@webapp.route('/api/workflows/messages/<workflow_id>')
def api_workflow_messages(workflow_id):
    """API endpoint to get the latest messages for a workflow."""
    last_id = request.args.get('last_id')
    
    # Fixed code here
    db = workflow_manager.db  # Use .db instead of .client[workflow_manager.db_name]
    query = {"workflow_id": workflow_id}
    if last_id:
        query["_id"] = {"$gt": ObjectId(last_id)}
    
    messages = list(db.workflow_messages.find(query).sort("timestamp", -1).limit(20))
    
    # Convert to serializable format
    result = []
    for msg in messages:
        msg["_id"] = str(msg["_id"])
        msg["timestamp"] = msg["timestamp"].isoformat() if isinstance(msg["timestamp"], datetime) else msg["timestamp"]
        result.append(msg)
    
    return jsonify(messages=result)

# Add at the end of views.py for testing purposes only
if __name__ == "__main__":
    print("This file should not be run directly. Run run.py instead.")
    print(f"Python path: {sys.path}")
    # For testing purposes only:
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(webapp)
    app.run(debug=True)