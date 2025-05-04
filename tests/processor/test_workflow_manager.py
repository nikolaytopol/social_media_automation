# test_workflow_manager.py
import asyncio
import time
import os

import sys

from dotenv import load_dotenv

# Load environment variables BEFORE importing modules that use them
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.env")))

# Verify environment variables
if not os.getenv('TELEGRAM_API_ID') or not os.getenv('TELEGRAM_API_HASH'):
    print("ERROR: Telegram credentials missing in .env file")
    print("Make sure TELEGRAM_API_ID and TELEGRAM_API_HASH are defined")
    sys.exit(1)

# Add the project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from processor.workflow_manager import WorkflowManager

# Create a test workflow configuration
test_config = {
    "user_id": 12345,
    "type": "live",
    "sources": [
        {"type": "telegram", "name": "@tradeduckydemo"}
    ],
    "destinations": [
        {"type": "telegram", "name": "@angelsclothesshop"}
    ],
    "filter_prompt": "Consider almost all messages suitable for reposting. Only filter out messages that contain explicit content, illegal activities, or spam. Answer yes for most messages, including short or simple ones.",
    "mod_prompt": "Rewrite this message to be more professional.",
    "duplicate_check": False,
    }

# For OpenAI
test_config["ai_provider"] = {"name": "openai", "model": "gpt-4o-2024-11-20"}

# For DeepSeek
test_config["ai_provider"] = {"name": "deepseek", "model": "deepseek-chat"}

# For history workflow, add start date
if test_config["type"] == "history":
    test_config["start_date"] = "2025-04-01"

# Initialize manager
manager = WorkflowManager()

# Create workflow
workflow_id = manager.create_workflow(test_config)
print(f"Created workflow with ID: {workflow_id}")

# Start workflow
success = manager.start_workflow(workflow_id)
print(f"Started workflow: {success}")

# Let it run for 60 seconds
print("Workflow running for 60 seconds...")
time.sleep(60)

# Stop workflow
success = manager.stop_workflow(workflow_id)
print(f"Stopped workflow: {success}")

# List all workflows
workflows = manager.list_workflows()
print(f"All workflows: {workflows}")