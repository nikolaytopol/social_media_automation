# processor/workflow_manager.py

import threading
import time
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask import Flask, request, redirect, url_for, render_template

# MongoDB settings
MONGO_URI = "mongodb://127.0.0.1:27017/"
DB_NAME = "social_manager"
COLLECTION_NAME = "workflows"

class Workflow:
    def __init__(self, user_id, sources, filter_prompt, repost_method, destinations, duplicate_check, mod_prompt, status='stopped', _id=None):
        self.user_id = user_id
        self.sources = sources
        self.filter_prompt = filter_prompt
        self.repost_method = repost_method
        self.destinations = destinations
        self.duplicate_check = duplicate_check
        self.mod_prompt = mod_prompt
        self.status = status
        self._id = _id  # MongoDB ID
        self.thread = None  # Thread object placeholder

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "sources": self.sources,
            "filter_prompt": self.filter_prompt,
            "repost_method": self.repost_method,
            "destinations": self.destinations,
            "duplicate_check": self.duplicate_check,
            "mod_prompt": self.mod_prompt,
            "status": self.status,
        }

class WorkflowManager:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.collection = self.db[COLLECTION_NAME]
        self.workflows = {}
        self._load_existing_workflows()

    def _load_existing_workflows(self):
        """Load workflows from MongoDB on startup."""
        for doc in self.collection.find():
            workflow = Workflow(**doc, _id=str(doc["_id"]))
            self.workflows[str(doc["_id"])] = workflow

    def create_workflow(self, user_id, sources, interval, mode, threshold, status="stopped"):
        """Create a new workflow and save it to the database."""
        workflow = Workflow(
            user_id=user_id,
            sources=sources,
            interval=interval,
            mode=mode,
            threshold=threshold,
            status=status,
        )
        result = self.collection.insert_one(workflow.to_dict())
        workflow._id = str(result.inserted_id)
        self.workflows[workflow._id] = workflow
        return workflow

    def _simulate_reposting(self, workflow_id):
        """Simulate background reposting."""
        workflow = self.workflows.get(workflow_id)
        while workflow and workflow.status == "running":
            print(f"🔄 [Workflow {workflow_id}] Reposting simulation...")
            time.sleep(5)  # Simulate reposting every 5 seconds

    def start_workflow(self, workflow_id):
        """Start a specific workflow."""
        workflow = self.workflows.get(workflow_id)
        if workflow and workflow.status != "running":
            workflow.status = "running"
            self.collection.update_one({"_id": ObjectId(workflow_id)}, {"$set": {"status": "running"}})

            # Initialize QueueManager
            queue_manager = QueueManager(
                interval_seconds=workflow.interval,
                mode=workflow.mode,
                ai_grade_callback=score_text if workflow.mode == "ai_grade" else None,
                threshold=workflow.threshold,
            )

            # Simulate adding tasks to the queue
            for source in workflow.sources:
                queue_manager.add_to_queue(
                    text=f"Message from {source}",
                    media_paths=[],
                    post_callback=self._simulate_posting,  # Replace with actual posting logic
                )

            # Start the queue manager
            queue_manager.start_worker()
            workflow.thread = queue_manager.thread  # Save thread reference
            print(f"✅ [Workflow {workflow_id}] Started.")

    def stop_workflow(self, workflow_id):
        workflow = self.workflows.get(workflow_id)
        if workflow and workflow.status == "running":
            workflow.status = "stopped"
            self.collection.update_one({"_id": ObjectId(workflow_id)}, {"$set": {"status": "stopped"}})
            print(f"⛔ [Workflow {workflow_id}] Stopped.")

    def list_workflows(self):
        """Return all workflows as a list of dicts."""
        return [vars(wf) for wf in self.workflows.values()]

# Singleton instance
workflow_manager = WorkflowManager()

# Flask app setup
webapp = Flask(__name__)

@webapp.route('/workflows/new', methods=["GET", "POST"])
def create_workflow():
    """Create a new workflow."""
    if request.method == "POST":
        # Collect form data
        channels = request.form.get("channels")
        interval = int(request.form.get("interval"))
        mode = request.form.get("mode")
        threshold = int(request.form.get("threshold", 50))

        # Save workflow to database
        workflow = {
            "user_id": 1,  # Replace with actual user ID from session
            "sources": channels.split(","),
            "interval": interval,
            "mode": mode,
            "threshold": threshold,
            "status": "stopped",  # Default status
        }
        workflow_id = workflow_manager.create_workflow(**workflow)._id

        # Optionally start the workflow immediately
        workflow_manager.start_workflow(workflow_id)

        return redirect(url_for("webapp.list_workflows"))

    return render_template("new_workflow.html")

