# processor/deepseek_utils.py
import os
import requests
import json
import logging

class DeepSeekUtils:
    def __init__(self, api_key=None):
        """Initialize DeepSeek utilities."""
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            logging.warning("No DeepSeek API key found! Set DEEPSEEK_API_KEY environment variable or pass api_key parameter.")
        self.base_url = "https://api.deepseek.com/v1/chat/completions"  # This is an example URL, replace with actual API endpoint
        
    async def filter_content(self, text, filter_prompt):
        """
        Check if content passes a filter based on the given prompt.
        
        Args:
            text (str): The content to check.
            filter_prompt (str): The filter criteria.
            
        Returns:
            bool: True if content passes the filter, False otherwise.
        """
        try:
            # Print debugging info
            print(f"[DeepSeek] Filtering message: {text[:50]}...")
            
            # Make sure the prompt is clear about returning yes/no
            system_prompt = (
                "You are a content filter assistant. Given a piece of content, determine if it should be reposted. "
                "Answer ONLY with 'yes' if the content should be reposted, or 'no' if it should be filtered out. "
                "Do not include any explanation or other text in your response."
            )
            
            user_prompt = f"{filter_prompt}\n\nContent to evaluate: {text}"
            
            # Make the API call to DeepSeek
            # Replace this with your actual DeepSeek API call


            
            result = "yes"  # Temporarily hardcode to yes for testing
            print(f"[DeepSeek] Filter result: {result}")
            
            # Return True (pass) if the result contains "yes"
            return "yes" in result.lower()
            
        except Exception as e:
            print(f"[DeepSeek] Error during filtering: {e}")
            # Default to TRUE on error - let content through when in doubt
            return True
    
    async def modify_content(self, text, mod_prompt):
        """
        Modify content based on the given prompt.
        Args:
            text (str): The content to modify.
            mod_prompt (str): Instructions for modification.
        Returns:
            str: The modified content.
        """
        try:
            full_prompt = f"{mod_prompt}\n\nOriginal content: {text}"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": "deepseek-chat",  # Replace with actual model name
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a content editor that transforms text according to instructions."
                    },
                    {"role": "user", "content": full_prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                data=json.dumps(payload)
            )
            
            response.raise_for_status()  # Raise an exception for 4XX/5XX responses
            
            result_json = response.json()
            return result_json["choices"][0]["message"]["content"].strip()
        
        except Exception as e:
            print(f"[DeepSeekUtils] Error during content modification: {e}")
            return text  # Return original text if an error occurs