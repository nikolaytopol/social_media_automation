# bot/handlers.py
from config.db import get_accounts, add_account, remove_account
from keyboards import account_list_keyboard, service_selection_keyboard
import json

def start_handler(update, context):
    update.message.reply_text("Welcome! Please enter the channels to monitor (e.g., @channel1, @channel2):")
    # Continue conversation...
    
def configure_handler(update, context):
    # Handle configuration conversation (store channels, filter prompt, target channel, etc.)
    update.message.reply_text("Configuration saved!")
    
def history_handler(update, context):
    # Retrieve and display history from the database or data folder
    update.message.reply_text("Displaying message history...")
    
def mark_error_handler(update, context):
    # Start inline error marking (ask user to comment on the error)
    update.message.reply_text("Please reply with your error comment for this message.")

def list_accounts(update, context):
    """List saved accounts for the current user."""
    user_id = update.effective_user.id
    # For simplicity, we're using context.user_data; in a production system, replace this with a DB query.
    accounts = context.user_data.get('accounts', [])
    if accounts:
        text = "Your saved accounts:\n" + "\n".join(f"- {acct}" for acct in accounts)
    else:
        text = "You have no saved accounts. Use /addaccount to add one."
    update.message.reply_text(text)

def add_account(update, context):
    """Prompt user to add a new account."""
    update.message.reply_text("Please enter the account details to add:")
    return 1  # Next state in a conversation handler

def save_account(update, context):
    """Save the account details provided by the user."""
    new_account = update.message.text
    # Retrieve current accounts from context.user_data or initialize an empty list.
    accounts = context.user_data.get('accounts', [])
    accounts.append(new_account)
    context.user_data['accounts'] = accounts
    update.message.reply_text(f"Account '{new_account}' has been added!")
    return ConversationHandler.END

async def manage_accounts_entry(update, context) -> int:
    """Entry point for managing accounts."""
    query = update.callback_query
    await query.answer()
    accounts = get_accounts(query.from_user.id)
    await query.edit_message_text(
        "Here are your current accounts:",
        reply_markup=account_list_keyboard(accounts)
    )
    return MANAGE_ACCOUNTS

async def choose_service_to_add(update, context) -> int:
    """Prompt user to choose a service to add."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Which service do you want to add?",
        reply_markup=service_selection_keyboard()
    )
    return ADD_ACCOUNT_SERVICE

async def add_account_service(update, context) -> int:
    """Handle service selection for adding an account."""
    query = update.callback_query
    await query.answer()
    service = query.data  # e.g., "telegram" or "twitter"
    context.user_data['new_service'] = service
    await query.edit_message_text(f"Now send me the credentials for {service} as JSON.")
    return ADD_ACCOUNT_CREDENTIALS

async def add_account_credentials(update, context) -> int:
    """Save account credentials provided by the user."""
    creds = json.loads(update.message.text)
    add_account(update.message.from_user.id, context.user_data['new_service'], creds)
    await update.message.reply_text("Account added!")
    return ConversationHandler.END

async def remove_account_choice(update, context) -> int:
    """Handle account removal."""
    query = update.callback_query
    await query.answer()
    service, idx = query.data.split("|")  # callback_data="twitter|1"
    remove_account(query.from_user.id, service, int(idx))
    await query.edit_message_text("Removed. Back to main menu.")
    return ConversationHandler.END
