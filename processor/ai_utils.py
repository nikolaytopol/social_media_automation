import random
import logging
from config.settings import OPENAI_API_KEY
import openai

# Initialize OpenAI API if the key is provided
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

async def score_text(text: str) -> int:
    """
    Score a given text using AI (OpenAI or dummy scorer).
    Returns a score between 0 and 100.
    """
    try:
        if OPENAI_API_KEY:
            # Use OpenAI API to score the text
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=f"Rate the following text on a scale of 0 to 100 for quality:\n\n{text}",
                max_tokens=5,
                temperature=0.5,
            )
            score = int(response.choices[0].text.strip())
            logging.info(f"AI Score for text: {score}")
            return max(0, min(score, 100))  # Ensure score is between 0 and 100
        else:
            # Dummy scorer (random score for testing)
            score = random.randint(0, 100)
            logging.info(f"Dummy Score for text: {score}")
            return score
    except Exception as e:
        logging.error(f"Error scoring text: {e}")
        return 0  # Default to 0 if there's an error