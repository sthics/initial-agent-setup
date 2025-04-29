# app/core/llm_client.py

from openai import OpenAI, OpenAIError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize the OpenAI client
client = None
if settings.OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info(f"OpenAI client initialized successfully for model: {settings.OPENAI_MODEL_NAME}")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        client = None # Ensure client is None if init fails
else:
    logger.warning("OPENAI_API_KEY not found in environment variables. LLM features will be disabled.")

def get_llm_response(prompt: str, max_tokens: int = 150) -> str | None:
    """Gets a completion from the configured OpenAI model."""
    if not client:
        logger.error("OpenAI client is not initialized. Cannot get LLM response.")
        # Depending on strictness, could raise an exception instead
        return "Error: LLM client not configured."

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are Arth, a helpful financial assistant specialized in Indian mutual funds."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7, # Creativity vs Factualness
        )
        # Access the response content correctly
        content = response.choices[0].message.content
        if content:
             return content.strip()
        else:
             logger.warning("Received empty content from LLM.")
             return None

    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        return f"Error communicating with LLM: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during LLM call: {e}")
        return "An unexpected error occurred while processing the request."

# --- Mock LLM for testing/development without API key ---

USE_MOCK_LLM = client is None # Use mock if client failed to initialize

def get_mock_llm_response(prompt: str, max_tokens: int = 150) -> str:
     """Returns a predefined mock response for testing purposes."""
     logger.warning(f"Using MOCK LLM response for prompt: {prompt[:50]}...")
     if "search" in prompt.lower() or "find" in prompt.lower():
         return "Mock response: Found funds A, B, C."
     elif "compare" in prompt.lower():
         return "Mock response: Fund X is better than Fund Y based on mock data."
     elif "summarize" in prompt.lower() or "details" in prompt.lower():
          return "Mock response: This fund has shown consistent mock growth."
     else:
         return "Mock LLM response: Unable to determine action from prompt."

# You can switch between real and mock LLM easily if needed
def get_current_llm_response(prompt: str, max_tokens: int = 150) -> str | None:
     if USE_MOCK_LLM:
         return get_mock_llm_response(prompt, max_tokens)
     else:
         return get_llm_response(prompt, max_tokens) 