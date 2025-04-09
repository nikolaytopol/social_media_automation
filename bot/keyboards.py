# bot/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def build_history_keyboard(message_id):
    keyboard = [[InlineKeyboardButton("Mark as Wrong", callback_data=f"mark_error_{message_id}")]]
    return InlineKeyboardMarkup(keyboard)
