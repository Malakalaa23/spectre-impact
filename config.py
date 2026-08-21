import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_env(key, default=None):
    """Get an environment variable or raise an error if missing."""
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Missing environment variable: {key}")
    return value

def get_openai_api_key():
    """Get the OpenAI API key."""
    return get_env("OPENAI_API_KEY")

# 👇 THIS is the function we need for Google Gemini
def get_google_api_key():
    """Get the Google Gemini API key."""
    return get_env("GOOGLE_API_KEY")

def get_github_token():
    """Get the GitHub token."""
    return get_env("GITHUB_TOKEN")

def get_database_url():
    """Get the database URL."""
    return get_env("DATABASE_URL", "sqlite:///history.db")