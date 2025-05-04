# web/your_app/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
import asyncio
from processor.workflow_manager import WorkflowManager

webapp = Blueprint('webapp', __name__)
workflow_manager = WorkflowManager()

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
        
        # Create the workflow
        workflow_id = workflow_manager.create_workflow(workflow_config)
        flash(f"Workflow created successfully", "success")
        
        return redirect(url_for("webapp.list_workflows"))
    
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
    workflows = workflow_manager.list_workflows()
    return render_template('start_workflow_form.html', workflows=workflows)

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

@webapp.route('/accounts/')
def manage_accounts():
    """Manage social media accounts."""
    # This would be where you'd show accounts, add new ones, etc.
    return render_template('accounts.html')