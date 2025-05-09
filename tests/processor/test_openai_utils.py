# test_openai_utils.py
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import OpenAIUtils
from processor.openai_utils import OpenAIUtils

async def test_filter_and_modify():
    # Pass API key directly (replace with your actual API key)
    api_key = "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"
    openai = OpenAIUtils(api_key=api_key)
    
    # Test filtering
    text = "This is a test message with promotional content!"
    filter_prompt = "Is this message promotional? Answer yes or no."
    result = await openai.filter_content(text, filter_prompt)
    print(f"Filter result: {result}")
    
    # Test modification
    mod_prompt = "Convert this message to a more formal tone."
    modified = await openai.modify_content(text, mod_prompt)
    print(f"Modified text: {modified}")

# Run the test
asyncio.run(test_filter_and_modify())