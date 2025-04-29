import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env file

class Settings:
    PROJECT_NAME: str = "Agentic MFAPI AI"
    VERSION: str = "0.1.0"

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL_NAME: str = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")

    # Add other settings as needed

settings = Settings() 