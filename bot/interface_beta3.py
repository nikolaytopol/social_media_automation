# bot/interface_beta.py
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import os
import logging
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import BadRequest
from processor.workflow_manager import workflow_manager

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
CB_START              = "cb_start"
CB_START_WF           = "cb_start_wf"
CB_MANAGE_WF          = "cb_manage_wf"
CB_MANAGE_ACCT        = "cb_manage_acct"
CB_ADD_ACCOUNT        = "cb_add_account"  

CB_WF_FILTER          = "cb_wf_filter"
CB_WF_TOGGLE_DUP      = "cb_wf_toggle_dup"
CB_WF_PROCESS_NOW     = "cb_wf_process_now"

CB_REPOST_IMMEDIATE       = "cb_repost_immediate"
CB_REPOST_HISTORY         = "cb_repost_history"
CB_REPOST_HISTORY_QUEUE   = "cb_repost_history_queue"
CB_REPOST_QUEUE           = "cb_repost_queue"

CB_MODIFY_PHOTOS_TEXT  = "cb_modify_photos_text"
CB_MODIFY_TEXT_ONLY    = "cb_modify_text_only"

CB_REPOST_TO_TELEGRAM  = "cb_repost_to_telegram"
CB_REPOST_TO_TWITTER   = "cb_repost_to_twitter"

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
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def start_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show main menu options: Start Workflow, Manage Workflows, Manage Accounts."""
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Start Workflow", callback_data=CB_START_WF)],
        [InlineKeyboardButton("Manage Workflows", callback_data=CB_MANAGE_WF)],
        [InlineKeyboardButton("Manage Accounts", callback_data=CB_MANAGE_ACCT)],
    ]
    await query.edit_message_text(
        "Please choose an action:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# --- Workflow Setup Handlers ------------------------------------------------

async def workflow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display current workflow settings and config buttons."""
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    state = user_workflow_state.setdefault(uid, {"filter": "", "duplicate": False})

    filter_text = state["filter"] or "<no filter set>"
    dup_text = "Enabled" if state["duplicate"] else "Disabled"

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
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def wf_set_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please type your filter prompt:")
    context.user_data["await_filter"] = True


async def filter_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.pop("await_filter", False):
        return
    uid = update.effective_user.id
    text = update.message.text
    user_workflow_state.setdefault(uid, {})["filter"] = text
    await update.message.reply_text(f"✅ Filter prompt saved:\n{text}")
    # Go back to workflow menu
    await workflow_handler(update, context)


async def wf_toggle_duplicate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    state = user_workflow_state[uid]
    state["duplicate"] = not state["duplicate"]
    status = "enabled" if state["duplicate"] else "disabled"
    await query.edit_message_text(f"Duplicate check {status}.")
    # Back to workflow menu
    await workflow_handler(update, context)


async def wf_process_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = (
        "Choose reposting method:\n\n"
        "• Repost Immediately\n"
        "• Repost History\n"
        "• Repost History with Queue\n"
        "• Repost with Queue"
    )
    keyboard = [
        [InlineKeyboardButton("Repost Immediately",       callback_data=CB_REPOST_IMMEDIATE)],
        [InlineKeyboardButton("Repost History",           callback_data=CB_REPOST_HISTORY)],
        [InlineKeyboardButton("Repost Hist w/ Queue",     callback_data=CB_REPOST_HISTORY_QUEUE)],
        [InlineKeyboardButton("Repost Live w/ Queue",     callback_data=CB_REPOST_QUEUE)],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# --- Tweet Modification Method Menu -----------------------------------------

async def tweet_modification_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show tweet modification method options."""
    query = update.callback_query
    await query.answer()

    text = (
        "Choose how to modify tweets:\n\n"
        "• Process Photos + Text\n"
        "• Process Text Only"
    )
    keyboard = [
        [InlineKeyboardButton("Photos + Text", callback_data=CB_MODIFY_PHOTOS_TEXT)],
        [InlineKeyboardButton("Text Only",      callback_data=CB_MODIFY_TEXT_ONLY)],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise


async def handle_mod_method_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle selection of modification method and prompt for prompt text."""
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    method = "photos_text" if query.data == CB_MODIFY_PHOTOS_TEXT else "text_only"
    user_workflow_state.setdefault(uid, {})["mod_method"] = method

    logging.info(f"User {uid} selected modification method: {method}")
    await query.edit_message_text("Great! Please type your modification prompt now:")
    context.user_data["await_mod_prompt"] = True


async def modification_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save the prompt text, then offer account selection."""
    logging.info("Handling modification prompt...")
    if not context.user_data.pop("await_mod_prompt", False):
        logging.warning("Received unexpected text input. Ignoring.")
        return

    uid = update.effective_user.id
    text = update.message.text
    user_workflow_state.setdefault(uid, {})["mod_prompt"] = text

    logging.info(f"User {uid} entered modification prompt: {text}")
    await update.message.reply_text(f"✅ Modification prompt saved:\n{text}")

    # Now show account-selection
    keyboard = [
        [InlineKeyboardButton("→ Telegram", callback_data=CB_REPOST_TO_TELEGRAM)],
        [InlineKeyboardButton("→ Twitter", callback_data=CB_REPOST_TO_TWITTER)],
    ]
    await update.message.reply_text(
        "Finally, choose which account to repost to:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_reposting_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Finalize repost target, create and start workflow."""
    query = update.callback_query
    await query.answer()

    target = (
        "Telegram"
        if query.data == CB_REPOST_TO_TELEGRAM
        else "Twitter"
    )
    uid = query.from_user.id
    state = user_workflow_state.setdefault(uid, {})
    state["repost_target"] = target

    # Extract workflow settings from session
    sources = ["some_source_placeholder"]  # TODO: Replace with real source selection later
    filter_prompt = state.get("filter", "")
    repost_method = "immediate"  # Simplify for now
    destinations = [target.lower()]
    duplicate_check = state.get("duplicate", False)
    mod_prompt = state.get("mod_prompt", "")

    # Create workflow
    workflow = workflow_manager.create_workflow(
        user_id=uid,
        sources=sources,
        filter_prompt=filter_prompt,
        repost_method=repost_method,
        destinations=destinations,
        duplicate_check=duplicate_check,
        mod_prompt=mod_prompt,
    )

    # (Optional) Start it immediately
    workflow_manager.start_workflow(workflow._id)

    await query.edit_message_text(
        f"✅ Repost target: {target}\n\n"
        f"Workflow created and started!\n\n"
        f"Workflow ID: {workflow._id}"
    )


# --- Manage Workflows & Accounts -------------------------------------------

async def manage_workflows_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    workflows = get_workflows(query.from_user.id)
    keyboard = workflow_list_keyboard(workflows)
    await query.edit_message_text(
        "Your Workflows:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def manage_accounts_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    accounts = get_accounts(query.from_user.id)
    keyboard = account_list_keyboard(accounts)
    await query.edit_message_text("Here are your accounts:", reply_markup=keyboard)


async def add_account_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = service_selection_keyboard()
    await query.edit_message_text(
        "Choose a service to add an account:", reply_markup=keyboard
    )


async def save_account_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    service = query.data
    add_account(query.from_user.id, service, {"placeholder": True})
    await query.edit_message_text(f"Added {service} account.")


async def remove_account_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    service, idx = query.data.split("|")
    remove_account(query.from_user.id, service, int(idx))
    await query.edit_message_text(f"Removed {service} account #{int(idx)+1}.")


# --- Bot Initialization -----------------------------------------------------

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # Core
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(start_button_handler, pattern=f"^{CB_START}$"))

    # Workflow setup
    app.add_handler(CallbackQueryHandler(workflow_handler, pattern=f"^{CB_START_WF}$"))
    app.add_handler(CallbackQueryHandler(wf_set_filter, pattern=f"^{CB_WF_FILTER}$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filter_prompt_handler))
    app.add_handler(CallbackQueryHandler(wf_toggle_duplicate, pattern=f"^{CB_WF_TOGGLE_DUP}$"))
    app.add_handler(CallbackQueryHandler(wf_process_now, pattern=f"^{CB_WF_PROCESS_NOW}$"))

    # Reposting actions → modification menu
    app.add_handler(CallbackQueryHandler(tweet_modification_menu,
        pattern=(
            f"^{CB_REPOST_IMMEDIATE}$|"
            f"^{CB_REPOST_HISTORY}$|"
            f"^{CB_REPOST_HISTORY_QUEUE}$|"
            f"^{CB_REPOST_QUEUE}$"
        )
    ))
    # Handle their choice of Photos+Text vs Text Only
    app.add_handler(CallbackQueryHandler(handle_mod_method_selection,
        pattern=f"^{CB_MODIFY_PHOTOS_TEXT}$|^{CB_MODIFY_TEXT_ONLY}$"
    ))
    # Their typed prompt
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, modification_prompt_handler))
    # Final repost target
    app.add_handler(CallbackQueryHandler(handle_reposting_target,
        pattern=f"^{CB_REPOST_TO_TELEGRAM}$|^{CB_REPOST_TO_TWITTER}$"
    ))

# Manage workflows & accounts
    app.add_handler(CallbackQueryHandler(manage_workflows_cb, pattern=f"^{CB_MANAGE_WF}$"))
    app.add_handler(CallbackQueryHandler(manage_accounts_cb,  pattern=f"^{CB_MANAGE_ACCT}$"))
    app.add_handler(CallbackQueryHandler(add_account_cb,      pattern=f"^{CB_ADD_ACCOUNT}$"))
    app.add_handler(CallbackQueryHandler(save_account_cb,     pattern="^(telegram|twitter|openai)$"))
    app.add_handler(CallbackQueryHandler(remove_account_cb,   pattern=r"^(telegram|twitter|openai)\|\d+$"))
    app.run_polling()

if __name__ == "__main__":
    main()
