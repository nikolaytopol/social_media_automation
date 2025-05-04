# bot/interface.py
# This adds support for our workflow types to the existing interface_beta3.py

# Add these imports
from processor.workflow_manager import WorkflowManager
from datetime import datetime

# Initialize the workflow manager
workflow_manager = WorkflowManager()

# Add these functions to your bot interface

async def select_workflow_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Let user select what type of workflow to create."""
    keyboard = [
        [InlineKeyboardButton("Live Reposting", callback_data="workflow_type_live")],
        [InlineKeyboardButton("History Reposting", callback_data="workflow_type_history")],
    ]
    await update.message.reply_text(
        "Please select the type of workflow to create:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_workflow_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle workflow type selection."""
    query = update.callback_query
    await query.answer()
    
    workflow_type = query.data.replace("workflow_type_", "")
    uid = query.from_user.id
    
    # Store the selected type in user state
    user_workflow_state.setdefault(uid, {})["type"] = workflow_type
    
    # For history repost, ask for start date
    if workflow_type == "history":
        await query.edit_message_text(
            "You've selected to repost historical content.\n\n"
            "Please enter the start date in YYYY-MM-DD format:"
        )
        context.user_data["await_start_date"] = True
    else:
        # For live repost, go to source selection
        await query.edit_message_text(
            "You've selected to repost live content.\n\n"
            "Please enter the source channels (comma-separated):"
        )
        context.user_data["await_sources"] = True

async def start_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle start date input for history reposting workflow."""
    if not context.user_data.pop("await_start_date", False):
        return
        
    uid = update.effective_user.id
    date_text = update.message.text
    
    try:
        # Validate date format
        start_date = datetime.strptime(date_text, "%Y-%m-%d")
        user_workflow_state[uid]["start_date"] = date_text
        
        await update.message.reply_text(
            f"Start date set to: {date_text}\n\n"
            "Now please enter the source channels (comma-separated):"
        )
        context.user_data["await_sources"] = True
    except ValueError:
        await update.message.reply_text(
            "Invalid date format. Please use YYYY-MM-DD format:"
        )
        context.user_data["await_start_date"] = True

async def source_channels_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle source channels input."""
    if not context.user_data.pop("await_sources", False):
        return
        
    uid = update.effective_user.id
    channels_text = update.message.text
    
    # Parse channels
    channels = [ch.strip() for ch in channels_text.split(",")]
    
    # Store in user state
    user_workflow_state[uid]["sources"] = [
        {"type": "telegram", "name": ch} for ch in channels
    ]
    
    await update.message.reply_text(
        f"Source channels set: {', '.join(channels)}\n\n"
        "Now please enter the target channel:"
    )
    context.user_data["await_target"] = True

async def target_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle target channel input."""
    if not context.user_data.pop("await_target", False):
        return
        
    uid = update.effective_user.id
    target = update.message.text.strip()
    
    # Store in user state
    user_workflow_state[uid]["destinations"] = [
        {"type": "telegram", "name": target}
    ]
    
    # Continue to filter prompt
    await workflow_handler(update, context)

async def create_and_start_workflow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create and start a workflow based on the user's configuration."""
    query = update.callback_query
    await query.answer()
    
    uid = query.from_user.id
    state = user_workflow_state.get(uid, {})
    
    # Create workflow config
    workflow_config = {
        "user_id": uid,
        "type": state.get("type", "live"),
        "sources": state.get("sources", []),
        "destinations": state.get("destinations", []),
        "filter_prompt": state.get("filter", ""),
        "mod_prompt": state.get("mod_prompt", ""),
        "duplicate_check": state.get("duplicate", False),
        "status": "stopped"
    }
    
    # Add start date for history workflows
    if state.get("type") == "history" and "start_date" in state:
        workflow_config["start_date"] = state["start_date"]
    
    # Create the workflow
    workflow_id = workflow_manager.create_workflow(workflow_config)
    
    # Start the workflow
    success = workflow_manager.start_workflow(workflow_id)
    
    if success:
        await query.edit_message_text(
            f"✅ Workflow created and started!\n\n"
            f"ID: {workflow_id}\n"
            f"Type: {workflow_config['type']}\n"
            f"Sources: {', '.join(src['name'] for src in workflow_config['sources'])}\n"
            f"Destinations: {', '.join(dest['name'] for dest in workflow_config['destinations'])}"
        )
    else:
        await query.edit_message_text(
            f"❌ Failed to start workflow. Please check logs."
        )

# Add these handlers to your main() function in bot/interface.py

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # Add existing handlers...
    
    # Add new workflow type handlers
    app.add_handler(CommandHandler("new_workflow", select_workflow_type))
    app.add_handler(CallbackQueryHandler(handle_workflow_type_selection, 
                                         pattern="^workflow_type_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                  start_date_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                  source_channels_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                  target_channel_handler))
    app.add_handler(CallbackQueryHandler(create_and_start_workflow, 
                                         pattern="^create_start_workflow$"))
                                         
    # Add handlers for workflow actions
    app.add_handler(CallbackQueryHandler(handle_workflow_action, 
                                         pattern="^workflow_action_"))
                                         
    app.run_polling()