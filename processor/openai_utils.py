# processor/openai_utils.py
import os
import openai
import logging

class OpenAIUtils:
    def __init__(self, api_key=None):
        """Initialize OpenAI utilities."""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            logging.warning("No OpenAI API key found! Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        else:
            openai.api_key = self.api_key
    
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
            full_prompt = f"{filter_prompt}\n\nContent: {text}"
            
            response = openai.chat.completions.create(
                model="gpt-4o-2024-11-20",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a content filter that evaluates if content should be reposted."
                    },
                    {"role": "user", "content": full_prompt}
                ],
                max_tokens=10,
                temperature=0
            )
            
            result = response.choices[0].message.content.strip().lower()
            return "yes" in result
        except Exception as e:
            print(f"[OpenAIUtils] Error during filtering: {e}")
            return False
    
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
            
            response = openai.chat.completions.create(
                model="gpt-4o-2024-11-20",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a content editor that transforms text according to instructions."
                    },
                    {"role": "user", "content": full_prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[OpenAIUtils] Error during content modification: {e}")
            return text  # Return original text if an error occurs