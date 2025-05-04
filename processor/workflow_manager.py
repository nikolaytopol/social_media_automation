# processor/workflow_manager.py
import threading
import time
import asyncio
from pymongo import MongoClient
from bson.objectid import ObjectId
from processor.workflows.live_repost_workflow import LiveRepostWorkflow
from processor.workflows.history_repost_workflow import HistoryRepostWorkflow

class WorkflowManager:
    def __init__(self, mongo_uri="mongodb://127.0.0.1:27017/", db_name="social_manager"):
        """Initialize the workflow manager."""
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db["workflows"]
        self.workflows = {}  # Store active workflow instances
        self.threads = {}  # Store workflow threads
        self._load_existing_workflows()
    
    def _load_existing_workflows(self):
        """Load workflows from the database."""
        for doc in self.collection.find():
            self.workflows[str(doc["_id"])] = doc
    
    def create_workflow(self, config):
        """
        Create a new workflow and save it to the database.
        
        Args:
            config (dict): Workflow configuration.
            
        Returns:
            str: The ID of the created workflow.
        """
        # Ensure config has required fields
        config.setdefault("status", "stopped")
        
        # Insert to database
        result = self.collection.insert_one(config)
        workflow_id = str(result.inserted_id)
        
        # Add to memory cache
        config["_id"] = workflow_id
        self.workflows[workflow_id] = config
        
        return workflow_id
    
    def start_workflow(self, workflow_id):
        """
        Start a workflow by its ID.
        
        Args:
            workflow_id (str): The ID of the workflow to start.
            
        Returns:
            bool: True if successfully started, False otherwise.
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            print(f"[WorkflowManager] Workflow {workflow_id} not found.")
            return False
            
        if workflow.get("status") == "running":
            print(f"[WorkflowManager] Workflow {workflow_id} is already running.")
            return True
            
        # Determine workflow type
        workflow_type = workflow.get("type", "live")  # Default to live
        
        # Create appropriate workflow instance
        if workflow_type == "live":
            workflow_instance = LiveRepostWorkflow(workflow)
        elif workflow_type == "history":
            workflow_instance = HistoryRepostWorkflow(workflow)
        else:
            print(f"[WorkflowManager] Unknown workflow type: {workflow_type}")
            return False
            
        # Update status in database
        self.collection.update_one(
            {"_id": ObjectId(workflow_id)}, 
            {"$set": {"status": "running"}}
        )
        
        # Update status in memory
        workflow["status"] = "running"
        
        # Start in a separate thread
        def run_workflow():
            asyncio.run(workflow_instance.start())
            
        thread = threading.Thread(target=run_workflow)
        thread.daemon = True
        thread.start()
        
        # Store thread and instance
        self.threads[workflow_id] = {
            "thread": thread,
            "instance": workflow_instance
        }
        
        print(f"[WorkflowManager] Started workflow {workflow_id}")
        return True
    
    def stop_workflow(self, workflow_id):
        """
        Stop a running workflow.
        
        Args:
            workflow_id (str): The ID of the workflow to stop.
            
        Returns:
            bool: True if successfully stopped, False otherwise.
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            print(f"[WorkflowManager] Workflow {workflow_id} not found.")
            return False
            
        if workflow.get("status") != "running":
            print(f"[WorkflowManager] Workflow {workflow_id} is not running.")
            return True
            
        # Get thread and instance
        thread_info = self.threads.get(workflow_id)
        if not thread_info:
            print(f"[WorkflowManager] Thread for workflow {workflow_id} not found.")
            return False
            
        # Stop the workflow
        asyncio.run(thread_info["instance"].stop())
        
        # Update status in database
        self.collection.update_one(
            {"_id": ObjectId(workflow_id)}, 
            {"$set": {"status": "stopped"}}
        )
        
        # Update status in memory
        workflow["status"] = "stopped"
        
        # Remove thread info
        del self.threads[workflow_id]
        
        print(f"[WorkflowManager] Stopped workflow {workflow_id}")
        return True
    
    def get_workflow(self, workflow_id):
        """Get a workflow by its ID."""
        return self.workflows.get(workflow_id)
    
    def list_workflows(self):
        """List all workflows."""
        return list(self.workflows.values())
    
    def update_workflow(self, workflow_id, updates):
        """Update a workflow's configuration."""
        if workflow_id not in self.workflows:
            print(f"[WorkflowManager] Workflow {workflow_id} not found.")
            return False
            
        # Update in database
        self.collection.update_one(
            {"_id": ObjectId(workflow_id)},
            {"$set": updates}
        )
        
        # Update in memory
        self.workflows[workflow_id].update(updates)
        
        return True
    
    def delete_workflow(self, workflow_id):
        """Delete a workflow."""
        if workflow_id not in self.workflows:
            print(f"[WorkflowManager] Workflow {workflow_id} not found.")
            return False
            
        # Stop if running
        if self.workflows[workflow_id].get("status") == "running":
            self.stop_workflow(workflow_id)
            
        # Delete from database
        self.collection.delete_one({"_id": ObjectId(workflow_id)})
        
        # Delete from memory
        del self.workflows[workflow_id]
        
        return True
