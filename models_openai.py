# OpenAI Model Functions with Configurable Parameters and Decision Storage

import asyncio
import openai
import logging
import json
import os
import datetime
import re
from typing import Dict, Any, List
import uuid
import traceback

# Get logger instance
logger = logging.getLogger("telegram_twitter_bot")

def save_model_decision(
    step: str,
    input_data: dict,
    model: str,
    parameters: dict,
    output: str,
    explanation: str,
    directory_prefix: str
):
    """
    Save model decision information as JSON to a specified directory.
    Args:
        step: Name of the function (tweet_generation, filter_model, etc.)
        input_data: Input data sent to the model
        model: Name of the model used
        parameters: Parameters used for the model call
        output: Main output from the model
        explanation: Explanation from the model
        directory_prefix: Full directory path to save the file
    """
    import uuid
    import datetime
    import os
    import json
    uid = str(uuid.uuid4())
    now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    record = {
        "id": uid,
        "created_at": now_iso,
        "step": step,
        "input": input_data,
        "model": model,
        "parameters": parameters,
        "output": output,
        "explanation": explanation,
        "user_feedback": {
            "is_correct": None,
            "corrected_value": None,
            "comment": None,
            "corrected_at": None
        }
    }
    os.makedirs(directory_prefix, exist_ok=True)
    out_path = os.path.join(directory_prefix, f"{step}_details.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return out_path


def update_model_review(json_path: str, status: str, reason: str = "", reviewed_by: str = ""): 
    """
    Update the review field of a model decision JSON file.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['review'] = {
        'status': status,
        'reason': reason,
        'reviewed_by': reviewed_by,
        'reviewed_at': datetime.datetime.now().isoformat()
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def tweet_generation(
    content: str,
    prompt_text: str,
    model: str = "gpt-4o-2024-11-20",
    system_content: str = "You are a Twitter blogger creating concise, engaging tweets. Be cool and not overly excited.",
    temperature: float = 0.7,
    top_p: float = 1.0,
    max_tokens: int = 900,
    presence_penalty: float = 0.0,
    frequency_penalty: float = 0.0,
    timeout: int = 60,
    save_decision: bool = True,
    directory_prefix: str = None
) -> str:
    """
    Generate tweet content using OpenAI.
    
    Args:
        content: The input content to generate tweet from
        prompt_text: The prompt template to use
        model: OpenAI model to use
        system_content: System message for the model
        temperature: Controls randomness (0.0 = deterministic, 1.0 = very random)
        top_p: Nucleus sampling parameter
        max_tokens: Maximum tokens to generate
        presence_penalty: Penalize new topics (-2.0 to 2.0)
        frequency_penalty: Penalize repetition (-2.0 to 2.0)
        timeout: API call timeout in seconds
        save_decision: Whether to save the model decision
        directory_prefix: Prefix for saved decision file
    
    Returns:
        Generated tweet text or fallback message on error
    """
    logger.info("Generating tweet content using OpenAI")
    # Replace placeholders in the prompt with the provided content
    if "{content}" not in prompt_text:
        raise ValueError("The prompt_text must contain the '{content}' placeholder.")
    # Ensure explanation separator instructions are present in the prompt
    if "<<<EXPLANATION_START>>>" not in prompt_text or "<<<EXPLANATION_END>>>" not in prompt_text:
        prompt_text = (
            prompt_text.strip() +
            "\n\nAfter your main output, add a new line with '<<<EXPLANATION_START>>>' and then provide a short explanation. End the explanation with '<<<EXPLANATION_END>>>'.\n"
            "Format:\n<main_output>\n<<<EXPLANATION_START>>>\n<explanation>\n<<<EXPLANATION_END>>>\n"
        )
    formatted_prompt = prompt_text.format(content=content)
    
    try:
        response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: openai.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": formatted_prompt}
                    ],
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty
                )
            ),
            timeout=timeout
        )
        full_text = response.choices[0].message.content.strip()
        logger.info(f"Generated tweet content: {full_text}")
        
        # Initialize tweet_text with the full response as fallback
        tweet_text = full_text
        explanation_text = ""
        
        if '<<<EXPLANATION_START>>>' in full_text and '<<<EXPLANATION_END>>>' in full_text:
            tweet_text = full_text.split('<<<EXPLANATION_START>>>')[0].strip()
            explanation_text = full_text.split('<<<EXPLANATION_START>>>')[1].split('<<<EXPLANATION_END>>>')[0].strip()
        
        # Save decision in the same format as other decisions
        if save_decision and directory_prefix:
            # Create the decision file path
            decision_file = os.path.join(directory_prefix, "tweet_generation_details.json")
            
            # Prepare the decision data
            decision_data = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "step": "tweet_generation",
                "input": {
                    "content": content,
                    "prompt": formatted_prompt,
                    "system_content": system_content
                },
                "model": model,
                "parameters": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty
                },
                "output": tweet_text,
                "explanation": explanation_text
            }
            
            # Save the decision file
            os.makedirs(os.path.dirname(decision_file), exist_ok=True)
            with open(decision_file, "w", encoding="utf-8") as f:
                json.dump(decision_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Tweet generation decision saved to {decision_file}")
        
        return tweet_text
    except asyncio.TimeoutError:
        logger.error(f"OpenAI API call for tweet generation timed out after {timeout} seconds")
        fallback = "Check out this update from the crypto world! #crypto #news"
        
        if save_decision and directory_prefix:
            decision_file = os.path.join(directory_prefix, "tweet_generation_details.json")
            decision_data = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "step": "tweet_generation",
                "input": {
                    "content": content,
                    "prompt": formatted_prompt,
                    "system_content": system_content
                },
                "model": model,
                "parameters": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty
                },
                "output": fallback,
                "explanation": "Timeout error"
            }
            
            os.makedirs(os.path.dirname(decision_file), exist_ok=True)
            with open(decision_file, "w", encoding="utf-8") as f:
                json.dump(decision_data, f, ensure_ascii=False, indent=2)
            
        return fallback
        
    except Exception as e:
        logger.error(f"Error generating tweet with OpenAI: {e}")
        fallback = "Check out this update from the crypto world! #crypto #news"
        error_msg = f"Error: {str(e)}"
        
        if save_decision and directory_prefix:
            decision_file = os.path.join(directory_prefix, "tweet_generation_details.json")
            decision_data = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "step": "tweet_generation",
                "input": {
                    "content": content,
                    "prompt": formatted_prompt,
                    "system_content": system_content
                },
                "model": model,
                "parameters": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty
                },
                "output": f"ERROR: {error_msg} - {fallback}",
                "explanation": error_msg
            }
            
            os.makedirs(os.path.dirname(decision_file), exist_ok=True)
            with open(decision_file, "w", encoding="utf-8") as f:
                json.dump(decision_data, f, ensure_ascii=False, indent=2)
            
        return fallback


async def filter_model(
    tweet_text: str,
    prompt_text: str,
    model: str = "gpt-4o-2024-11-20",
    system_content: str = "You are a filter system for identifying content not suitable for posting. First answer with 'Yes' or 'No', then provide a brief explanation after '<<<EXPLANATION>>>'.",
    temperature: float = 0.0,
    top_p: float = 1.0,
    max_tokens: int = 150,  # Increased to allow for explanation
    presence_penalty: float = 0.0,
    frequency_penalty: float = 0.0,
    timeout: int = 30,
    save_decision: bool = True,
    directory_prefix: str = None
) -> str:
    """
    Filter tweet content for promotional content.
    
    Args:
        tweet_text: The tweet text to filter
        prompt_text: The prompt template to use
        model: OpenAI model to use
        system_content: System message for the model
        temperature: Controls randomness (0.0 = deterministic)
        top_p: Nucleus sampling parameter
        max_tokens: Maximum tokens to generate
        presence_penalty: Penalize new topics
        frequency_penalty: Penalize repetition
        timeout: API call timeout in seconds
        save_decision: Whether to save the model decision
        directory_prefix: Prefix for saved decision file
    
    Returns "yes" or "no" and includes explanation in logs.
    """
    logger.info("Filtering tweet for promotional content")
    
    # Create a safe prompt format that includes both the original prompt and explanation request
    safe_prompt = (
        f"{prompt_text}\n\n"  # First include the original prompt with all its rules
        "=====\n"  # Add a separator
        "Analyze the content above according to the given rules.\n"
        "First respond with ONLY 'Yes' or 'No', then on a new line after '<<<EXPLANATION>>>' "
        "provide a brief explanation of your decision.\n\n"
        "Format your response exactly like this:\n"
        "Yes/No\n"
        "<<<EXPLANATION>>>\n"
        "Your explanation here"
    )
    
    try:
        response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: openai.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": safe_prompt}
                    ],
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty
                )
            ),
            timeout=timeout
        )
        
        full_response = response.choices[0].message.content.strip()
        logger.debug(f"Raw filter response: {full_response}")
        
        # Split response into decision and explanation
        parts = full_response.split('<<<EXPLANATION>>>')
        decision = parts[0].strip().lower()
        explanation = parts[1].strip() if len(parts) > 1 else "No explanation provided"
        
        # Log the full response but return just the decision
        logger.info(f"Filter decision: {decision}")
        logger.info(f"Filter explanation: {explanation}")
        
        # Save decision if requested
        if save_decision:
            save_model_decision(
                step="filter_model",
                input_data={
                    "tweet_text": tweet_text,
                    "prompt": safe_prompt,
                    "system_content": system_content
                },
                model=model,
                parameters={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty
                },
                output=decision,
                explanation=explanation,
                directory_prefix=directory_prefix
            )
        
        # Ensure we return only 'yes' or 'no'
        return 'yes' if decision.lower().startswith('y') else 'no'
        
    except asyncio.TimeoutError:
        logger.error(f"OpenAI API call for content filtering timed out after {timeout} seconds")
        
        if save_decision:
            save_model_decision(
                step="filter_model",
                input_data={
                    "tweet_text": tweet_text,
                    "prompt": safe_prompt,
                    "system_content": system_content
                },
                model=model,
                parameters={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty
                },
                output="TIMEOUT_ERROR: yes (default)",
                explanation="TIMEOUT_ERROR: yes (default)",
                directory_prefix=directory_prefix
            )
        
        return "yes"  # Default to filtering out on error
    except Exception as e:
        logger.error(f"Error filtering tweet with OpenAI: {e}")
        
        if save_decision:
            save_model_decision(
                step="filter_model",
                input_data={
                    "tweet_text": tweet_text,
                    "prompt": safe_prompt,
                    "system_content": system_content
                },
                model=model,
                parameters={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty
                },
                output=f"ERROR: {str(e)} - yes (default)",
                explanation=f"ERROR: {str(e)}",
                directory_prefix=directory_prefix
            )
        
        return "yes"  # Default to filtering out on error


async def duplicate_checker(
    current_message: str,
    current_media_info: List[Dict[str, Any]],
    recent_entries: List[Dict[str, Any]],
    prompt_text: str,
    model: str = "gpt-4o-2024-11-20",
    system_content: str = "You are an assistant that compares messages for duplication.",
    temperature: float = 0.0,
    top_p: float = 1.0,
    max_tokens: int = 1000,
    presence_penalty: float = 0.0,
    frequency_penalty: float = 0.0,
    timeout: int = 60,
    save_decision: bool = True,
    directory_prefix: str = None
) -> bool:
    """
    Check if current message is a duplicate of recent messages.
    
    Args:
        current_message: The current message text
        current_media_info: Information about current message media
        recent_entries: List of recent message entries to compare against
        prompt_text: The prompt template to use
        model: OpenAI model to use
        system_content: System message for the model
        temperature: Controls randomness (0.0 = deterministic)
        top_p: Nucleus sampling parameter
        max_tokens: Maximum tokens to generate
        presence_penalty: Penalize new topics
        frequency_penalty: Penalize repetition
        timeout: API call timeout in seconds
        save_decision: Whether to save the model decision
        directory_prefix: Prefix for saved decision file
    
    Returns:
        True if duplicate, False otherwise
    """
    logger.info("Checking for duplicate tweets using OpenAI")
    
    current_media_str = format_media_info(current_media_info)
    
    # Format the prompt with all the data
    prompt_data = {
        "current_message": current_message,
        "current_media": current_media_str,
        "recent_entries": recent_entries
    }
    
    # If prompt_text expects specific formatting, construct it here
    formatted_prompt = prompt_text.format(**prompt_data)
    
    try:
        response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: openai.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": formatted_prompt}
                    ],
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty
                )
            ),
            timeout=timeout
        )
        answer = response.choices[0].message.content.strip().lower()
        logger.info(f"OpenAI duplicate check result: {answer[:100]}...")
        
        is_duplicate = "yes" in answer
        
        # Save decision if requested
        if save_decision:
            save_model_decision(
                step="duplicate_checker",
                input_data={
                    "current_message": current_message,
                    "current_media_info": current_media_info,
                    "recent_entries_count": len(recent_entries),
                    "prompt": formatted_prompt[:500] + "..." if len(formatted_prompt) > 500 else formatted_prompt,
                    "system_content": system_content
                },
                model=model,
                parameters={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty
                },
                output=answer,
                explanation=answer,
                directory_prefix=directory_prefix
            )
        
        if is_duplicate:
            logger.warning("Message identified as duplicate by OpenAI")
            
        return is_duplicate
        
    except asyncio.TimeoutError:
        logger.error(f"OpenAI API call for duplicate check timed out after {timeout} seconds")
        
        if save_decision:
            save_model_decision(
                step="duplicate_checker",
                input_data={
                    "current_message": current_message,
                    "current_media_info": current_media_info,
                    "recent_entries_count": len(recent_entries)
                },
                model=model,
                parameters={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty
                },
                output="TIMEOUT_ERROR: False (default)",
                explanation="TIMEOUT_ERROR: False (default)",
                directory_prefix=directory_prefix
            )
        
        return False  # Default to not duplicate on error
    except Exception as e:
        logger.error(f"Error comparing messages using OpenAI: {e}")
        
        if save_decision:
            save_model_decision(
                step="duplicate_checker",
                input_data={
                    "current_message": current_message,
                    "current_media_info": current_media_info,
                    "recent_entries_count": len(recent_entries)
                },
                model=model,
                parameters={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty
                },
                output=f"ERROR: {str(e)} - False (default)",
                explanation=f"ERROR: {str(e)}",
                directory_prefix=directory_prefix
            )
        
        return False  # Default to not duplicate on error


async def analyze_image_with_openai(
    image_path: str,
    prompt_text: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    top_p: float = 1.0,
    max_tokens: int = 500,
    presence_penalty: float = 0.0,
    frequency_penalty: float = 0.0,
    timeout: int = 30,
    save_decision: bool = True,
    directory_prefix: str = None
) -> str:
    """
    Analyze an image using OpenAI Vision model.
    
    Args:
        image_path: Path to the image file
        prompt_text: The prompt for image analysis
        model: OpenAI model to use (must support vision)
        temperature: Controls randomness
        top_p: Nucleus sampling parameter
        max_tokens: Maximum tokens to generate
        presence_penalty: Penalize new topics
        frequency_penalty: Penalize repetition
        timeout: API call timeout in seconds
        save_decision: Whether to save the model decision
        directory_prefix: Prefix for saved decision file
    
    Returns:
        Analysis text or error message
    """
    try:
        base64_image = encode_image(image_path)
        
        response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: openai.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                            ]
                        }
                    ],
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty
                )
            ),
            timeout=timeout
        )
        
        analysis = response.choices[0].message.content.strip()
        
        # # Check for Cyrillic characters and add prefix if needed
        # if re.search(r'[\u0400-\u04FF]', analysis) and not analysis.startswith("RUSSIAN:"):
        #     analysis = "RUSSIAN: " + analysis
            
        logger.info(f"Image analysis completed successfully for {os.path.basename(image_path)}")
        
        # Save decision if requested
        if save_decision:
            save_model_decision(
                step="analyze_image",
                input_data={
                    "image_path": image_path,
                    "prompt": prompt_text,
                    "image_size": os.path.getsize(image_path) if os.path.exists(image_path) else "unknown"
                },
                model=model,
                parameters={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty
                },
                output=analysis,
                explanation=analysis,
                directory_prefix=directory_prefix
            )
        
        return analysis
        
    except asyncio.TimeoutError:
        logger.error(f"OpenAI API call timed out for image {image_path}")
        error_msg = "Error analyzing image: API timeout"
        
        if save_decision:
            save_model_decision(
                step="analyze_image",
                input_data={
                    "image_path": image_path,
                    "prompt": prompt_text
                },
                model=model,
                parameters={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens
                },
                output=f"TIMEOUT_ERROR: {error_msg}",
                explanation=error_msg,
                directory_prefix=directory_prefix
            )
        
        return error_msg
    except Exception as e:
        logger.error(f"Error analyzing image {image_path}: {e}")
        error_msg = f"Error analyzing image: {e}"
        
        if save_decision:
            save_model_decision(
                step="analyze_image",
                input_data={
                    "image_path": image_path,
                    "prompt": prompt_text
                },
                model=model,
                parameters={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens
                },
                output=f"ERROR: {error_msg}",
                explanation=error_msg,
                directory_prefix=directory_prefix
            )
        
        return error_msg


# Helper functions
def format_media_info(media_info):
    """
    Given a list of media file info dictionaries, returns a string summarizing the details.
    """
    if not media_info:
        return "No media files."
    
    formatted_items = []
    for item in media_info:
        formatted_items.append(
            f"(Extension: {item['file_extension']}, Size: {item['file_size']} bytes)"
        )
    return ", ".join(formatted_items)


def encode_image(image_path):
    """Encode image to base64"""
    import base64
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
    
async def analyze_image(image_path):
    """Analyze an image with error handling and proper response extraction"""
    try:
        base64_image = encode_image(image_path)
        
        # Set a timeout for the OpenAI API call
        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Analyze this image in two parts:\n\n1. Image Description: Provide a detailed description of the image content that could be used in a post.\n\n2. Posting Assessment: Determine if the image is suitable for reposting by checking for:\n- Brand logos or watermarks\n- Copyright information\n- Channel/source identifiers\n- Russian/Cyrillic text or characters\n- Any other elements that would make it inappropriate for reposting\n\nFormat your response as:\nDESCRIPTION:\n[Your detailed image description]\n\nPOSTING ASSESSMENT:\n[Yes/No] - [Brief explanation of why it can/cannot be posted]\n"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                                ]
                            }
                        ]
                    )
                ),
                timeout=30  # Adjust timeout as needed
            )
    
            # Extract the analysis from the response
            analysis = response.choices[0].message.content.strip()
            logger.info(f"Image analysis completed successfully for {os.path.basename(image_path)}")
            return analysis
            
        except asyncio.TimeoutError:
            logger.error(f"OpenAI API call timed out for image {image_path}")
            return f"Error analyzing image: API timeout"
        except Exception as e:
            logger.error(f"Error with OpenAI API call for image {image_path}: {e}")
            return f"Error analyzing image: {e}"
        
    except Exception as e:
        logger.error(f"Error preparing image {image_path} for analysis: {e}")
        logger.error(traceback.format_exc())
        return f"Error analyzing image: {e}"


if __name__ == "__main__":
    import asyncio
    import sys
    
    # Set OpenAI API key if not already set
    if not openai.api_key:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY environment variable not set")
            sys.exit(1)
        openai.api_key = api_key
    
    # Basic logging setup for testing
    logging.basicConfig(level=logging.INFO)
    
    async def run_tests():
        print("\n===== OpenAI Model Functions Tester =====")
        print("1. Test tweet_generation")
        print("2. Test filter_model")
        print("3. Test duplicate_checker")
        print("4. Test analyze_image_with_openai")
        print("q. Quit")
        
        choice = input("\nEnter your choice (1-4, q): ")
        
        if choice == '1':
            content = input("Enter text to generate a tweet from: ")
            prompt = ("Rewrite the following content to make it suitable for a Twitter post:\n\n"
                     "{content}\n\nEnsure it sounds authentic and engaging, adding relevant emojis.")
            
            result = await tweet_generation(content=content, prompt_text=prompt)
            print("\nGENERATED TWEET:")
            print(result)
            
        elif choice == '2':
            text = input("Enter text to check for filtering: ")
            prompt = ("Is the following tweet promotional content?\n"
                     "If the tweet is promotional, respond with 'Yes'. "
                     "Otherwise, respond with 'No'.\n\nTweet: {tweet_text}")
            
            result = await filter_model(tweet_text=text, prompt_text=prompt)
            print("\nFILTER RESULT:")
            print(f"Should filter: {result}")
            
        elif choice == '3':
            text = input("Enter message to check for duplication: ")
            media_ext = input("Enter media extension (e.g., .jpg, .png) or leave empty: ")
            
            current_media_info = []
            if media_ext:
                size = input("Enter media size in bytes (default: 100000): ") or "100000"
                current_media_info = [{"file_extension": media_ext, "file_size": int(size)}]
            
            # Example recent entries
            recent_entries = [
                {"text": "Bitcoin showing strong resistance at $65,000", 
                 "media_info": [{"file_extension": ".jpg", "file_size": 120000}]},
                {"text": "Ethereum's bullish pattern continues with strong volume", 
                 "media_info": [{"file_extension": ".png", "file_size": 85000}]}
            ]
            
            prompt = ("Determine if the new message is a duplicate of any previous messages.\n"
                     "Answer only Yes or No.\n\n"
                     "New message: {current_message}\n"
                     "New message media: {current_media}\n\n"
                     "Previous messages:\n"
                     "1. Bitcoin showing strong resistance at $65,000\n"
                     "2. Ethereum's bullish pattern continues with strong volume")
            
            result = await duplicate_checker(
                current_message=text,
                current_media_info=current_media_info,
                recent_entries=recent_entries,
                prompt_text=prompt
            )
            print("\nDUPLICATE CHECK RESULT:")
            print(f"Is duplicate: {result}")
            
        elif choice == '4':
            image_path = input("Enter full path to image file: ")
            if not os.path.exists(image_path):
                print(f"Error: Image file not found at {image_path}")
                return
                
            prompt = "Analyze this image for information that can be used in a tweet that describes this image."
            
            result = await analyze_image_with_openai(image_path=image_path, prompt_text=prompt)
            print("\nIMAGE ANALYSIS RESULT:")
            print(result)
            
        elif choice.lower() == 'q':
            print("Exiting tester.")
            return
            
        else:
            print("Invalid choice!")
        
        # Ask if user wants to continue testing
        if input("\nRun another test? (y/n): ").lower() == 'y':
            await run_tests()
    
    # Run the tests
    asyncio.run(run_tests())