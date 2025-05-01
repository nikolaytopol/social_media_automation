# bot/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def build_history_keyboard(message_id):
    keyboard = [[InlineKeyboardButton("Mark as Wrong", callback_data=f"mark_error_{message_id}")]]
    return InlineKeyboardMarkup(keyboard)

def account_list_keyboard(accounts):
    """Build a keyboard to list accounts with options to remove them."""
    keyboard = []
    for idx, (service, account) in enumerate(accounts.items()):
        keyboard.append([
            InlineKeyboardButton(
                f"{service}: {account['username']}",
                callback_data=f"remove_account|{service}|{idx}"
            )
        ])
    keyboard.append([InlineKeyboardButton("Add Account", callback_data="add_account")])
    return InlineKeyboardMarkup(keyboard)

def service_selection_keyboard():
    """Build a keyboard to select a service for adding an account."""
    keyboard = [
        [InlineKeyboardButton("Telegram", callback_data="telegram")],
        [InlineKeyboardButton("Twitter", callback_data="twitter")],
    ]
    return InlineKeyboardMarkup(keyboard)

def workflow_list_keyboard(workflows: list) -> InlineKeyboardMarkup:
    """Create an inline keyboard listing all workflows with status labels."""
    buttons = []
    for wf in workflows:
        label = f"{wf['name']} [{wf['status']}]"
        # callback_data could be used to trigger detailed workflow management
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"manage_wf|{wf['id']}")
        ])
    return InlineKeyboardMarkup(buttons)