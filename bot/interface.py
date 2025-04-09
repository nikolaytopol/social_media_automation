# bot/interface.py
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackContext
)

# Define conversation states
(
    MAIN_MENU,
    CONFIG_SOURCES,
    CONFIG_TARGETS,
    CONFIG_FILTER,
    CONFIG_MODIFY,
    MONITOR_HISTORY,
    MARK_ERROR,
    ERROR_COMMENT,
) = range(8)

async def start(update: Update, context: CallbackContext) -> int:
    """Start command: welcome the user and show the main menu."""
    keyboard = [
        [InlineKeyboardButton("Start Workflow", callback_data="start_workflow")],
        [InlineKeyboardButton("Monitoring Workflow", callback_data="monitor_workflow")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to the Reposting SaaS Bot! Please choose an option:", reply_markup=reply_markup
    )
    return MAIN_MENU

def main_menu_handler(update: Update, context: CallbackContext) -> int:
    """Handle main menu button presses."""
    query = update.callback_query
    query.answer()
    choice = query.data

    if choice == "start_workflow":
        # Start configuration: first ask for sources
        query.edit_message_text("Please specify your content sources (e.g., Telegram channel IDs, folders, etc.):")
        return CONFIG_SOURCES
    elif choice == "monitor_workflow":
        # Go to monitoring: show history and statistics
        query.edit_message_text("Monitoring Workflow selected. Use /history to view messages or /stats for daily stats.")
        return MONITOR_HISTORY
    return MAIN_MENU

def config_sources(update: Update, context: CallbackContext) -> int:
    """Store sources and ask for target channels."""
    user_input = update.message.text
    context.user_data['sources'] = user_input.split(",")  # e.g., list of source identifiers
    update.message.reply_text("Sources saved. Now, please provide the target channel(s) (username or chat IDs):")
    return CONFIG_TARGETS

def config_targets(update: Update, context: CallbackContext) -> int:
    """Store target channels and ask for filter prompt."""
    user_input = update.message.text
    context.user_data['targets'] = user_input.split(",")
    update.message.reply_text("Targets saved. Now, provide your filter prompt or type 'default':")
    return CONFIG_FILTER

def config_filter(update: Update, context: CallbackContext) -> int:
    """Store filter prompt and ask for modification prompt."""
    user_input = update.message.text
    context.user_data['filter_prompt'] = user_input if user_input.lower() != 'default' else "Default filter prompt text..."
    update.message.reply_text("Filter prompt saved. Finally, provide your modification prompt (or type 'default'):")
    return CONFIG_MODIFY

def config_modify(update: Update, context: CallbackContext) -> int:
    """Store modification prompt and finish configuration."""
    user_input = update.message.text
    context.user_data['modify_prompt'] = user_input if user_input.lower() != 'default' else "Default modification prompt text..."
    
    # Save the workflow configuration (example: save to a database or in-memory storage)
    workflow = {
        "user_id": update.message.from_user.id,
        "sources": context.user_data.get('sources', []),
        "targets": context.user_data.get('targets', []),
        "filter_prompt": context.user_data.get('filter_prompt', "Default filter prompt text..."),
        "modify_prompt": context.user_data.get('modify_prompt', "Default modification prompt text..."),
    }
    # Example: Save to a database or file (replace this with your actual storage logic)
    save_workflow_to_db(workflow)

    update.message.reply_text("Configuration complete! Your workflow is now set up.")
    return ConversationHandler.END

def history_command(update: Update, context: CallbackContext) -> None:
    """Command to display message history."""
    # Fetch history from your storage (database or files)
    history = "Sample message history (chronological order) with inline buttons to mark errors."
    # Create an inline keyboard for each history message (this is a simplified example)
    keyboard = [[InlineKeyboardButton("Mark as Wrong", callback_data="mark_error_12345")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(history, reply_markup=reply_markup)

def mark_error_callback(update: Update, context: CallbackContext) -> int:
    """Handle the inline button press to mark a message as wrong."""
    query = update.callback_query
    query.answer()
    # Extract message ID from callback data if needed
    context.user_data['error_msg_id'] = query.data.split("_")[-1]
    query.edit_message_text("Please enter your comment explaining why this message was processed incorrectly:")
    return ERROR_COMMENT

def error_comment(update: Update, context: CallbackContext) -> int:
    """Store the error comment."""
    comment = update.message.text
    message_id = context.user_data.get('error_msg_id')
    # Save this comment along with the message ID in your storage for later retraining
    update.message.reply_text(f"Message {message_id} marked as wrong with comment: {comment}")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Operation canceled.")
    return ConversationHandler.END

def main() -> None:
    # Replace 'YOUR_BOT_TOKEN' with your actual token from BotFather
    application = Application.builder().token("7496592695:AAGy430MGUr9iAOeKffk1HBTG39xPkVPcpc").build()

    # Create a conversation handler for configuration
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(main_menu_handler)],
            CONFIG_SOURCES: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_sources)],
            CONFIG_TARGETS: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_targets)],
            CONFIG_FILTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_filter)],
            CONFIG_MODIFY: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_modify)],
            ERROR_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, error_comment)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('history', history_command))
    application.add_handler(CallbackQueryHandler(mark_error_callback, pattern="mark_error_"))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
