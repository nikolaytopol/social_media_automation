# test_deepseek_utils.py
import asyncio
import sys
import os
# Add the project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
# Import DeepSeekUtils
from processor.deepseek_utils import DeepSeekUtils

async def test_filter_and_modify():
    # Pass API key directly (replace with your actual API key)
    api_key = 'sk-7429ad07ef2d441b95403e42068202cb'  # Replace with your DeepSeek API key
    deepseek = DeepSeekUtils(api_key=api_key)
    
    # Test filtering
    text = "This is a test message with promotional content!"
    filter_prompt = "Is this message promotional? Answer yes or no."
    result = await deepseek.filter_content(text, filter_prompt)
    print(f"Filter result: {result}") 
    
    # Test modification
    mod_prompt = "Convert this message to a more formal tone."
    modified = await deepseek.modify_content(text, mod_prompt)
    print(f"Modified text: {modified}")

# Run the test
if __name__ == "__main__":
    asyncio.run(test_filter_and_modify())