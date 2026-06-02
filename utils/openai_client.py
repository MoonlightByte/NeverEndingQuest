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
        # Local / OpenAI-compatible server (LM Studio, Ollama, vLLM, OpenRouter,
        # remote host). Endpoint is read live from user_settings.json so a web-UI
        # change applies on the next request with no restart. Defaults preserve
        # the original LM Studio localhost:1234 behavior. (Issue #120)
        import model_config
        ep = model_config.get_local_endpoint()
        return OpenAI(
            base_url=ep["base_url"],
            api_key=ep["api_key"] or "not-needed"
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
