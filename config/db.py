from pymongo import MongoClient
from dotenv import load_dotenv
import os
import logging

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
try:
    client = MongoClient(MONGO_URI)
    db = client["social_manager"]
    users = db["users"]
    workflows_col = db["workflows"]  # Add workflows collection
    logger.info("Connected to MongoDB successfully!")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

# Helper functions
def register_user(telegram_id, username):
    if not users.find_one({"telegram_id": telegram_id}):
        users.insert_one({
            "telegram_id": telegram_id,
            "username": username,
            "plan": "free",
            "accounts": {
                "telegram": [],
                "twitter": [],
                "openai": []
            }
        })

def get_accounts(telegram_id):
    """Retrieve accounts for a user."""
    user = users.find_one({"telegram_id": telegram_id})
    return user.get("accounts", {}) if user else {}

def add_account(telegram_id, service, account_data):
    """Add an account for a user."""
    users.update_one(
        {"telegram_id": telegram_id},
        {"$push": {"accounts": {service: account_data}}},
        upsert=True
    )

def remove_account(telegram_id, service, index):
    """Remove an account for a user."""
    user = users.find_one({"telegram_id": telegram_id})
    if user and "accounts" in user:
        accounts = user["accounts"]
        if service in accounts and len(accounts[service]) > index:
            del accounts[service][index]
            users.update_one({"telegram_id": telegram_id}, {"$set": {"accounts": accounts}})

def get_workflows(telegram_id: int) -> list:
    """Retrieve all workflows belonging to a specific user."""
    docs = workflows_col.find({"telegram_id": telegram_id})
    workflows = []
    for doc in docs:
        workflows.append({
            "id": str(doc.get("_id")),
            "name": doc.get("name", "<unnamed>"),
            "status": doc.get("status", "unknown")
        })
    return workflows