# processor/workflow_registry.py

import os
import importlib.util
import inspect
import logging

logger = logging.getLogger('WorkflowRegistry')

class WorkflowRegistry:
    def __init__(self):
        """Initialize the workflow registry."""
        self.preset_workflows = {}
        self.preset_dir = os.path.join(os.path.dirname(__file__), 'preset_workflows')
        
        # Ensure the preset directory exists
        if not os.path.exists(self.preset_dir):
            os.makedirs(self.preset_dir)
            
    def discover_workflows(self):
        """Scan the preset_workflows directory and register available workflow classes."""
        logger.info(f"Discovering workflows in {self.preset_dir}")
        
        for filename in os.listdir(self.preset_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                try:
                    module_path = os.path.join(self.preset_dir, filename)
                    module_name = filename[:-3]  # Remove .py extension
                    
                    # Load the module
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for a workflow class
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and hasattr(obj, 'workflow_type') and hasattr(obj, 'workflow_info'):
                            # Register the workflow class
                            workflow_id = obj.workflow_info.get('id', module_name)
                            self.preset_workflows[workflow_id] = {
                                'class': obj,
                                'info': obj.workflow_info
                            }
                            logger.info(f"Registered preset workflow: {workflow_id}")
                except Exception as e:
                    logger.error(f"Error loading workflow from {filename}: {e}")
                    
        return self.preset_workflows
        
    def get_preset_workflows(self):
        """Get the list of available preset workflows."""
        if not self.preset_workflows:
            self.discover_workflows()
        return self.preset_workflows
        
    def get_workflow_class(self, workflow_id):
        """Get a workflow class by ID."""
        workflows = self.get_preset_workflows()
        if workflow_id in workflows:
            return workflows[workflow_id]['class']
        return None
        
    def get_workflow_info(self, workflow_id):
        """Get workflow metadata by ID."""
        workflows = self.get_preset_workflows()
        if workflow_id in workflows:
            return workflows[workflow_id]['info']
        return None