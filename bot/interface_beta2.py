# bot/interface_beta.py

import os
import json
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import BadRequest
from config.db import (
    register_user,
    get_accounts,
    add_account,
    remove_account,
    get_workflows,
)
from keyboards import (
    account_list_keyboard,
    service_selection_keyboard,
    workflow_list_keyboard,
)

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Callback data constants
CB_START = "cb_start"
CB_START_WF = "cb_start_wf"
CB_MANAGE_WF = "cb_manage_wf"
CB_MANAGE_ACCT = "cb_manage_acct"
CB_ADD_ACCOUNT = "cb_add_account"
CB_SAVE_ACCOUNT = "cb_save_account"
# Workflow callbacks
CB_WF_FILTER = "cb_wf_filter"
CB_WF_TOGGLE_DUP = "cb_wf_toggle_dup"
CB_WF_PROCESS_NOW = "cb_wf_process_now"
# Reposting method callbacks
CB_REPOST_IMMEDIATE = "cb_repost_immediate"
CB_REPOST_HISTORY = "cb_repost_history"
CB_REPOST_HISTORY_QUEUE = "cb_repost_history_queue"
CB_REPOST_QUEUE = "cb_repost_queue"
# Additional Callback Data Constants
CB_MODIFY_PHOTOS_TEXT = "cb_modify_photos_text"
CB_MODIFY_TEXT_ONLY = "cb_modify_text_only"
CB_SET_MOD_PROMPT = "cb_set_mod_prompt"
CB_SET_OUTPUT_FOLDER = "cb_set_output_folder"
CB_SELECT_REPOST_TARGET = "cb_select_repost_target"
CB_REPOST_TO_TELEGRAM = "cb_repost_to_telegram"
CB_REPOST_TO_TWITTER = "cb_repost_to_twitter"

# In-memory workflow state per user
user_workflow_state = {}

logging.basicConfig(level=logging.INFO)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start: register user and show entry button."""
    user = update.effective_user
    register_user(user.id, user.username)
    keyboard = [[InlineKeyboardButton("Start", callback_data=CB_START)]]
    await update.message.reply_text(
        "Welcome to the Reposting Bot! Tap Start to continue:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show main menu options: workflow, workflows, accounts."""
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Start Workflow", callback_data=CB_START_WF)],
        [InlineKeyboardButton("Manage Workflows", callback_data=CB_MANAGE_WF)],
        [InlineKeyboardButton("Manage Accounts", callback_data=CB_MANAGE_ACCT)],
    ]
    await query.edit_message_text(
        "Please choose an action:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Workflow Setup Handlers ---
async def workflow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display current workflow settings and config buttons."""
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    state = user_workflow_state.setdefault(uid, {"filter": "", "duplicate": False})

    filter_text = state['filter'] if state['filter'] else "<no filter set>"
    dup_text = "Enabled" if state['duplicate'] else "Disabled"

    keyboard = [
        [InlineKeyboardButton("Set Filter Prompt", callback_data=CB_WF_FILTER)],
        [InlineKeyboardButton(f"Duplicate Check: {dup_text}", callback_data=CB_WF_TOGGLE_DUP)],
        [InlineKeyboardButton("Choose Reposting Method", callback_data=CB_WF_PROCESS_NOW)],
    ]
    await query.edit_message_text(
        f"Workflow Setup:\n"
        f"• Filter Prompt: {filter_text}\n"
        f"• Duplicate Check: {dup_text}\n\n"
        f"Use the buttons below to configure your workflow:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def workflow_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the workflow menu to the user."""
    uid = update.effective_user.id
    state = user_workflow_state.setdefault(uid, {"filter": "", "duplicate": False})

    filter_text = state['filter'] if state['filter'] else "<no filter set>"
    dup_text = "Enabled" if state['duplicate'] else "Disabled"

    keyboard = [
        [InlineKeyboardButton("Set Filter Prompt", callback_data=CB_WF_FILTER)],
        [InlineKeyboardButton(f"Duplicate Check: {dup_text}", callback_data=CB_WF_TOGGLE_DUP)],
        [InlineKeyboardButton("Choose Reposting Method", callback_data=CB_WF_PROCESS_NOW)],
    ]
    await update.message.reply_text(
        f"Workflow Setup:\n"
        f"• Filter Prompt: {filter_text}\n"
        f"• Duplicate Check: {dup_text}\n\n"
        f"Use the buttons below to configure your workflow:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def wf_set_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user to enter a filter string."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please type your filter prompt:")
    context.user_data['await_filter'] = True

async def filter_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input for filter prompt and return workflow menu."""
    # Only process if we are expecting filter input
    if not context.user_data.pop('await_filter', False):
        return
    uid = update.effective_user.id
    # Save the filter prompt
    text = update.message.text
    user_workflow_state.setdefault(uid, {"filter": "", "duplicate": False})
    user_workflow_state[uid]['filter'] = text
    # Acknowledge
    await update.message.reply_text(f"Filter prompt saved: {text}")
    # Redirect to workflow menu
    await workflow_menu(update, context)

async def wf_toggle_duplicate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle duplicate-check flag and return to workflow menu."""
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    state = user_workflow_state[uid]
    state['duplicate'] = not state['duplicate']
    status = "enabled" if state['duplicate'] else "disabled"
    await query.edit_message_text(f"Duplicate check {status}.")
    # Redirect back to workflow menu
    await workflow_handler(update, context)

# --- Reposting Method Menu ---
async def wf_process_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show reposting method selection with explanations."""
    query = update.callback_query
    await query.answer()
    text = (
        "Choose reposting method:\n\n"
        "• Repost Immediately: publish content as soon as detected.\n"
        "• Repost History: repost all past content at once without queueing.\n"
        "• Repost History with Queue: schedule historical reposts sequentially.\n"
        "• Repost with Queue: queue live content reposts for controlled delivery."
    )
    keyboard = [
        [InlineKeyboardButton("Repost Immediately", callback_data=CB_REPOST_IMMEDIATE)],
        [InlineKeyboardButton("Repost History", callback_data=CB_REPOST_HISTORY)],
        [InlineKeyboardButton("Repost History with Queue", callback_data=CB_REPOST_HISTORY_QUEUE)],
        [InlineKeyboardButton("Repost with Queue", callback_data=CB_REPOST_QUEUE)],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# --- Tweet Modification Method Menu ---
async def tweet_modification_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show tweet modification method options."""
    query = update.callback_query
    await query.answer()

    text = (
        "Choose how to modify tweets:\n\n"
        "• Process Photos and Text: Modify both photos and text in tweets.\n"
        "• Process Text Only: Modify only the text in tweets."
    )
    keyboard = [
        [InlineKeyboardButton("Process Photos and Text", callback_data=CB_SET_MOD_PROMPT)],
        [InlineKeyboardButton("Process Text Only", callback_data=CB_SET_MOD_PROMPT)],
    ]

    # Check if the current message content and reply markup are already the same
    current_message = query.message
    logging.info(f"Current message text: {current_message.text}")
    logging.info(f"New message text: {text}")
    logging.info(f"Current reply markup: {current_message.reply_markup}")
    logging.info(f"New reply markup: {InlineKeyboardMarkup(keyboard)}")

    # Edit the message only if the content or reply markup has changed
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise

async def handle_mod_method_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user selection of modification method and prompt for custom input."""
    query = update.callback_query
    await query.answer()

    # Save the selected method
    uid = query.from_user.id
    method = "photos_text" if query.data == CB_MODIFY_PHOTOS_TEXT else "text_only"
    user_workflow_state.setdefault(uid, {})['mod_method'] = method

    # Prompt for the modification prompt
    await query.edit_message_text("Great! Please type your **modification prompt** now:")
    context.user_data['await_mod_prompt'] = True

async def handle_tweet_modification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle selection of tweet modification method and ask for modification prompt."""
    query = update.callback_query
    logging.info("Handling tweet modification...")
    await query.answer()
    method = "Photos and Text" if query.data == CB_MODIFY_PHOTOS_TEXT else "Text Only"
    logging.info(f"Selected method: {method}")

    uid = query.from_user.id
    user_workflow_state.setdefault(uid, {"mod_method": "", "mod_prompt": "", "repost_target": ""})
    user_workflow_state[uid]["mod_method"] = method

    try:
        await query.edit_message_text(f"Selected modification method: {method}\n\nPlease type your modification prompt:")
        context.user_data['await_mod_prompt'] = True
    except telegram.error.BadRequest as e:
        logging.error(f"Failed to edit message: {e}")

# --- Set Modification Prompt ---
async def set_modification_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user to enter a modification prompt."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please type your modification prompt:")
    context.user_data['await_mod_prompt'] = True

async def modification_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input for modification prompt and proceed to reposting target selection."""
    # Only process if we are expecting the input
    if not context.user_data.pop('await_mod_prompt', False):
        return

    uid = update.effective_user.id
    text = update.message.text
    user_workflow_state.setdefault(uid, {})['mod_prompt'] = text

    await update.message.reply_text(f"✅ Saved modification prompt:\n{text}")

    # Proceed to reposting target selection
    await select_reposting_target(update, context)

# --- Select Reposting Target ---
async def select_reposting_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask the user to select a reposting target."""
    keyboard = [
        [InlineKeyboardButton("→ Telegram", callback_data=CB_REPOST_TO_TELEGRAM)],
        [InlineKeyboardButton("→ Twitter", callback_data=CB_REPOST_TO_TWITTER)],
    ]
    await update.message.reply_text(
        "Finally, choose which account to repost to:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_reposting_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle selection of reposting target and confirm the workflow."""
    query = update.callback_query
    await query.answer()
    target = "Telegram" if query.data == CB_REPOST_TO_TELEGRAM else "Twitter"
    uid = query.from_user.id
    user_workflow_state.setdefault(uid, {"mod_method": "", "mod_prompt": "", "repost_target": ""})
    user_workflow_state[uid]['repost_target'] = target
    await query.edit_message_text(f"Reposting target selected: {target}\n\nYour workflow is now complete!")

# --- Set Output Folder ---
async def set_output_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user to specify an output folder."""
    await update.message.reply_text("Please specify the output folder:")
    context.user_data['await_output_folder'] = True

async def output_folder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input for output folder and return to main menu."""
    if not context.user_data.pop('await_output_folder', False):
        return
    uid = update.effective_user.id
    folder = update.message.text
    user_workflow_state.setdefault(uid, {"mod_prompt": "", "output_folder": ""})
    user_workflow_state[uid]['output_folder'] = folder
    await update.message.reply_text(f"Output folder saved: {folder}")
    # Redirect to main menu
    await workflow_menu(update, context)

# --- Placeholder handlers for repost actions ---
async def repost_immediate_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle immediate reposting."""
    query = update.callback_query
    await query.answer()
    await tweet_modification_menu(update, context)

async def repost_history_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reposting history."""
    query = update.callback_query
    await query.answer()
    await tweet_modification_menu(update, context)

async def repost_history_queue_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reposting history with queue."""
    query = update.callback_query
    await query.answer()
    await tweet_modification_menu(update, context)

async def repost_queue_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reposting live content with queue."""
    query = update.callback_query
    await query.answer()
    await tweet_modification_menu(update, context)

# --- Manage Workflows Handler ---
async def manage_workflows_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    workflows = get_workflows(query.from_user.id)
    keyboard = workflow_list_keyboard(workflows)
    await query.edit_message_text(
        "Your Workflows:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Manage Accounts Handler ---
async def manage_accounts_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    accounts = get_accounts(query.from_user.id)
    keyboard = account_list_keyboard(accounts)
    await query.edit_message_text(
        "Here are your accounts:",
        reply_markup=keyboard
    )

async def add_account_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = service_selection_keyboard()
    await query.edit_message_text(
        "Choose a service to add an account:",
        reply_markup=keyboard
    )

async def save_account_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    service = query.data
    creds = {"placeholder": True}
    add_account(query.from_user.id, service, creds)
    await query.edit_message_text(f"Added {service} account.")

async def remove_account_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    service, idx = query.data.split("|")
    remove_account(query.from_user.id, service, int(idx))
    await query.edit_message_text(f"Removed {service} account #{int(idx)+1}.")

# --- Main Setup ---
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # Core commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(start_button_handler, pattern=f"^{CB_START}$"))

    # Workflow setup
    app.add_handler(CallbackQueryHandler(workflow_handler, pattern=f"^{CB_START_WF}$"))
    app.add_handler(CallbackQueryHandler(wf_set_filter, pattern=f"^{CB_WF_FILTER}$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filter_prompt_handler))
    app.add_handler(CallbackQueryHandler(wf_toggle_duplicate, pattern=f"^{CB_WF_TOGGLE_DUP}$"))
    app.add_handler(CallbackQueryHandler(wf_process_now, pattern=f"^{CB_WF_PROCESS_NOW}$"))

    # Reposting actions
    app.add_handler(        CallbackQueryHandler(repost_immediate_cb,                              pattern=f"^{CB_REPOST_IMMEDIATE}$"))
    app.add_handler(CallbackQueryHandler(repost_history_cb, pattern=f"^{CB_REPOST_HISTORY}$"))
    app.add_handler(CallbackQueryHandler(repost_history_queue_cb, pattern=f"^{CB_REPOST_HISTORY_QUEUE}$"))
    app.add_handler(CallbackQueryHandler(repost_queue_cb, pattern=f"^{CB_REPOST_QUEUE}$"))

    # Manage workflows
    app.add_handler(CallbackQueryHandler(manage_workflows_cb, pattern=f"^{CB_MANAGE_WF}$"))

    # Manage accounts
    app.add_handler(CallbackQueryHandler(manage_accounts_cb, pattern=f"^{CB_MANAGE_ACCT}$"))
    app.add_handler(CallbackQueryHandler(add_account_cb, pattern=f"^{CB_ADD_ACCOUNT}$"))
    app.add_handler(CallbackQueryHandler(save_account_cb, pattern="^(telegram|twitter|openai)$"))
    app.add_handler(CallbackQueryHandler(remove_account_cb, pattern=r"^(telegram|twitter|openai)\|\d+$"))

    # Tweet modification
    app.add_handler(CallbackQueryHandler(tweet_modification_menu, pattern=f"^{CB_MODIFY_PHOTOS_TEXT}$|^{CB_MODIFY_TEXT_ONLY}$"))
    app.add_handler(CallbackQueryHandler(handle_mod_method_selection,   pattern=f"^{CB_MODIFY_PHOTOS_TEXT}$|^{CB_MODIFY_TEXT_ONLY}$"))
    app.add_handler(CallbackQueryHandler(set_modification_prompt, pattern=f"^{CB_SET_MOD_PROMPT}$")    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, modification_prompt_handler))

    # Reposting target
    app.add_handler(CallbackQueryHandler(select_reposting_target, pattern=f"^{CB_SELECT_REPOST_TARGET}$")    )
    app.add_handler(CallbackQueryHandler(handle_reposting_target, pattern=f"^{CB_REPOST_TO_TELEGRAM}$|^{CB_REPOST_TO_TWITTER}$")    )

    app.run_polling()

if __name__ == "__main__":
    main()
