"""
OpenAI Client Factory
Provides centralized client creation with LM Studio support
"""

from openai import OpenAI
import config


def get_openai_client():
    """
    Create and return an OpenAI client configured for the active provider.

    Returns:
        OpenAI: Configured OpenAI client

    Behavior:
        - If MODEL_PROVIDER == "lmstudio": Connects to localhost:1234 (local LM Studio)
        - Otherwise: Connects to OpenAI API (requires config.OPENAI_API_KEY)

    Usage:
        from utils.openai_client import get_openai_client
        client = get_openai_client()
        response = client.chat.completions.create(...)
    """
    from model_config import MODEL_PROVIDER

    if MODEL_PROVIDER == "lmstudio":
        # Connect to local LM Studio server
        # No API key needed for local server
        return OpenAI(
            base_url="http://localhost:1234/v1",
            api_key="not-needed"
        )
    else:
        # Connect to OpenAI API (default)
        # Requires valid API key in config.py
        return OpenAI(api_key=config.OPENAI_API_KEY)


def is_using_lm_studio():
    """
    Check if the game is configured to use LM Studio.

    Returns:
        bool: True if MODEL_PROVIDER is "lmstudio", False otherwise

    Usage:
        from utils.openai_client import is_using_lm_studio
        if is_using_lm_studio():
            print("Running with local LM Studio")
    """
    from model_config import MODEL_PROVIDER
    return MODEL_PROVIDER == "lmstudio"
