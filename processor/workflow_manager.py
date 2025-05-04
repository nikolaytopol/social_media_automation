# processor/workflow_manager.py
import threading
import time
import asyncio
from pymongo import MongoClient
from bson.objectid import ObjectId
from processor.workflows.live_repost_workflow import LiveRepostWorkflow
from processor.workflows.history_repost_workflow import HistoryRepostWorkflow
from processor.workflow_registry import WorkflowRegistry
from datetime import datetime

class WorkflowManager:
    def __init__(self, mongo_uri="mongodb://127.0.0.1:27017/", db_name="social_manager"):
        """Initialize the workflow manager."""
        self.client = MongoClient(mongo_uri)
        self.db_name = db_name  # Add this line
        self.db = self.client[db_name]
        self.collection = self.db["workflows"]
        self.workflows = {}  # Store active workflow instances
        self.threads = {}  # Store workflow threads
        self.registry = WorkflowRegistry()
        self.registry.discover_workflows()
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
    
    def get_preset_workflows(self):
        """Get available preset workflows."""
        presets = []
        for workflow_id, workflow in self.registry.get_preset_workflows().items():
            info = workflow['info']
            presets.append({
                "id": workflow_id,
                "name": info.get("name", workflow_id),
                "description": info.get("description", ""),
                "type": info.get("workflow_type", "live"),
                "author": info.get("author", "Unknown"),
                "version": info.get("version", "1.0"),
                "required_fields": info.get("required_fields", []),
                "optional_fields": info.get("optional_fields", [])
            })
        return presets
    
    def create_from_preset(self, preset_id, config):
        """Create a workflow from a preset."""
        workflow_class = self.registry.get_workflow_class(preset_id)
        if not workflow_class:
            return None, f"Preset '{preset_id}' not found"
        
        # Create workflow configuration
        workflow_config = {
            "user_id": config.get("user_id", 1),
            "type": workflow_class.workflow_type,
            "sources": [],
            "destinations": [],
            "is_preset": True,
            "preset_id": preset_id
        }
        
        # Process source channels
        if "source_channels" in config:
            workflow_config["sources"] = [
                {"type": "telegram", "name": src.strip()}
                for src in config["source_channels"].split(",")
                if src.strip()
            ]
            
        # Process target channels
        if "target_channels" in config:
            workflow_config["destinations"] = [
                {"type": "telegram", "name": target.strip()}
                for target in config["target_channels"].split(",")
                if target.strip()
            ]
            
        # Copy other config fields
        for field in ["filter_prompt", "mod_prompt", "duplicate_check", "preserve_files", "start_date", "ai_provider"]:
            if field in config:
                workflow_config[field] = config[field]
        
        # Create workflow in database
        workflow_id = self.create_workflow(workflow_config)
        return workflow_id, "Workflow created successfully"
    
    def start_workflow(self, workflow_id):
        """Start a workflow by ID."""
        workflow = self.db.workflows.find_one({"_id": ObjectId(workflow_id)})
        if not workflow:
            return False
            
        if workflow.get("status") == "running":
            return True  # Already running
            
        try:
            # Check if this is a preset workflow
            if workflow.get("is_preset") and workflow.get("preset_id"):
                preset_id = workflow.get("preset_id")
                workflow_class = self.registry.get_workflow_class(preset_id)
                if workflow_class:
                    workflow_instance = workflow_class(workflow)
                else:
                    # Fall back to standard workflow types if preset not found
                    if workflow["type"] == "live":
                        from processor.workflows.live_repost_workflow import LiveRepostWorkflow
                        workflow_instance = LiveRepostWorkflow(workflow)
                    else:
                        return False
            else:
                # Not a preset, use standard workflow types
                if workflow["type"] == "live":
                    from processor.workflows.live_repost_workflow import LiveRepostWorkflow
                    workflow_instance = LiveRepostWorkflow(workflow)
                else:
                    return False
                    
            # Start the workflow
            asyncio.create_task(workflow_instance.start())
            self.active_workflows[str(workflow["_id"])] = workflow_instance
            self.db.workflows.update_one({"_id": workflow["_id"]}, {"$set": {"status": "running"}})
            return True
            
        except Exception as e:
            print(f"Error starting workflow: {e}")
            import traceback
            print(traceback.format_exc())
            return False
    
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

    def log_message(self, workflow_id, message_data):
        """
        Log a processed message for a workflow.
        
        Args:
            workflow_id (str): The workflow ID
            message_data (dict): Data about the processed message
        """
        # Ensure we have a collection for workflow messages
        if not hasattr(self, 'message_collection'):
            self.message_collection = self.db['workflow_messages']
            
            # Create indexes if needed
            self.message_collection.create_index([('workflow_id', 1), ('timestamp', -1)])
            self.message_collection.create_index('message_key', unique=True)
        
        # Add timestamp and workflow_id
        message_data['timestamp'] = datetime.now()
        message_data['workflow_id'] = workflow_id
        
        # Insert the message, with upsert in case of duplicates
        try:
            self.message_collection.update_one(
                {'message_key': message_data.get('message_key')}, 
                {'$set': message_data},
                upsert=True
            )
        except Exception as e:
            print(f"Error logging message: {e}")
