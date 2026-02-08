# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
AI Client Factory - Multi-Provider AI Client Management
Provides unified interface for OpenAI, OpenRouter, and future providers
"""

from typing import Optional, Dict, Any
from openai import OpenAI
from utils.enhanced_logger import debug, info, warning, error

# Track fallback status to avoid spamming notifications
_fallback_status = {
    'has_triggered': False,
    'primary_provider': None,
    'fallback_provider': None,
    'last_error': None,
    'fallback_count': 0
}


def _get_actual_provider(use_fallback: bool = False) -> tuple[str, bool]:
    """
    Single source of truth for determining which provider to actually use.
    
    This function resolves the split-brain issue where configuration says OpenRouter
    but runtime conditions (missing API key) require OpenAI fallback.
    
    Args:
        use_fallback: Force OpenAI regardless of configuration
        
    Returns:
        Tuple of (provider_name: str, is_openrouter: bool)
        - provider_name: "openrouter" or "openai"
        - is_openrouter: True if OpenRouter can actually be used
    """
    try:
        import config
        from model_config import LLM_PROVIDER, ENABLE_PROVIDER_FALLBACK
        
        # Check if fallback is forced
        if use_fallback or not ENABLE_PROVIDER_FALLBACK:
            return "openai", False
        
        # Check if OpenRouter is configured AND has API key
        if LLM_PROVIDER == "openrouter":
            api_key = getattr(config, 'OPENROUTER_API_KEY', '')
            if api_key:
                return "openrouter", True
            else:
                warning("OPENROUTER_API_KEY not set, falling back to OpenAI", 
                       category="ai_provider")
        
        return "openai", False
        
    except ImportError:
        # Safe fallback if imports fail
        return "openai", False


def create_chat_client(use_fallback: bool = False) -> OpenAI:
    """
    Create chat/LLM client based on configuration.
    
    Args:
        use_fallback: Force fallback to OpenAI (used internally after failures)
        
    Returns:
        OpenAI client configured for the selected provider
        
    Provider Selection Logic:
        1. If use_fallback=True or ENABLE_PROVIDER_FALLBACK=False -> OpenAI
        2. If LLM_PROVIDER="openrouter" and OPENROUTER_API_KEY set -> OpenRouter
        3. Otherwise -> OpenAI (safe default)
    """
    global _fallback_status
    
    # Use single source of truth for provider selection
    provider, is_openrouter = _get_actual_provider(use_fallback)
    
    try:
        import config
        from model_config import (
            OPENROUTER_BASE_URL,
            OPENROUTER_HTTP_REFERER,
            OPENROUTER_APP_TITLE,
        )
    except ImportError as e:
        error(f"Failed to import config: {e}")
        raise
    
    # Create client with appropriate configuration
    if is_openrouter:
        api_key = getattr(config, 'OPENROUTER_API_KEY', '')
        debug("Creating OpenRouter client for chat", category="ai_provider")
        client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": OPENROUTER_HTTP_REFERER,
                "X-Title": OPENROUTER_APP_TITLE
            }
        )
        
        # Track primary provider selection
        _fallback_status['primary_provider'] = 'openrouter'
        _fallback_status['fallback_provider'] = 'openai'
        
    else:
        api_key = getattr(config, 'OPENAI_API_KEY', '')
        debug("Creating OpenAI client for chat", category="ai_provider")
        client = OpenAI(api_key=api_key)
        _fallback_status['primary_provider'] = 'openai'
    
    return client


def get_chat_model_name() -> str:
    """
    Get the appropriate chat model name based on provider configuration.
    
    Returns:
        Model name string for use in API calls
    """
    try:
        import config
        from model_config import LLM_PROVIDER, OPENROUTER_CHAT_MODEL, DM_MAIN_MODEL
        
        provider = getattr(config, 'LLM_PROVIDER', 'openai')
        
        if provider == "openrouter" and getattr(config, 'OPENROUTER_API_KEY', ''):
            return OPENROUTER_CHAT_MODEL
        else:
            return DM_MAIN_MODEL
            
    except ImportError:
        # Safe fallback if imports fail
        return "gpt-4.1-2025-04-14"


def get_model_display_name() -> str:
    """
    Get human-readable model name for UI display.
    
    Returns:
        Display name string (e.g., "Kimi K2.5" or "GPT-4.1")
    """
    model = get_chat_model_name()
    
    # Map model IDs to display names
    display_names = {
        "moonshotai/kimi-k2.5": "Kimi K2.5",
        "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet",
        "google/gemini-2.0-flash-exp": "Gemini 2.0 Flash",
        "openai/gpt-4.1-2025-04-14": "GPT-4.1",
        "gpt-4.1-2025-04-14": "GPT-4.1",
        "gpt-4.1-mini-2025-04-14": "GPT-4.1 Mini"
    }
    
    return display_names.get(model, model)


def handle_provider_error(error: Exception, context: str = "") -> Dict[str, Any]:
    """
    Handle provider errors and determine if fallback should occur.
    
    Args:
        error: The exception that occurred
        context: Additional context about what operation failed
        
    Returns:
        Dict with error details and fallback recommendation
    """
    global _fallback_status
    
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    # Check if this is a retryable error
    retryable_errors = [
        'rate limit', 'timeout', 'connection', '503', '502', '504',
        'overloaded', 'unavailable', 'internal server error', '429'
    ]
    
    should_fallback = any(err in error_str for err in retryable_errors)
    
    result = {
        'error': str(error),
        'error_type': error_type,
        'context': context,
        'should_fallback': should_fallback,
        'fallback_message': None
    }
    
    if should_fallback and not _fallback_status['has_triggered']:
        _fallback_status['has_triggered'] = True
        _fallback_status['last_error'] = str(error)
        _fallback_status['fallback_count'] += 1
        
        # Create user-friendly fallback message
        primary = _fallback_status.get('primary_provider', 'unknown')
        fallback = _fallback_status.get('fallback_provider', 'openai')
        
        if primary != fallback:
            result['fallback_message'] = (
                f"Primary AI provider ({primary}) temporarily unavailable. "
                f"Falling back to {fallback}. Your game will continue normally."
            )
            warning(
                f"Provider fallback triggered: {primary} -> {fallback}. "
                f"Error: {error}",
                category="ai_provider"
            )
    
    return result


def reset_fallback_status():
    """Reset fallback tracking (call at game start)."""
    global _fallback_status
    _fallback_status = {
        'has_triggered': False,
        'primary_provider': None,
        'fallback_provider': None,
        'last_error': None,
        'fallback_count': 0
    }
    debug("Fallback status reset", category="ai_provider")


def get_fallback_notification() -> Optional[str]:
    """
    Get fallback notification message if one should be shown.
    
    Returns:
        Message string to display to user, or None if no notification needed
    """
    global _fallback_status
    
    if (_fallback_status['has_triggered'] and 
        _fallback_status['primary_provider'] != _fallback_status['fallback_provider']):
        return (
            f"[System] AI provider switched from {_fallback_status['primary_provider']} "
            f"to {_fallback_status['fallback_provider']} due to service issue. "
            f"Your game session continues normally."
        )
    
    return None


def get_provider_status() -> Dict[str, Any]:
    """
    Get current provider status for diagnostics.
    
    Returns:
        Dict with provider configuration and fallback status
    """
    global _fallback_status
    
    try:
        import config
        from model_config import LLM_PROVIDER, ENABLE_PROVIDER_FALLBACK
        
        current_provider = getattr(config, 'LLM_PROVIDER', 'openai')
        actual_provider = _fallback_status.get('primary_provider', current_provider)
        
        return {
            'configured_provider': current_provider,
            'active_provider': actual_provider,
            'model': get_chat_model_name(),
            'model_display': get_model_display_name(),
            'fallback_enabled': ENABLE_PROVIDER_FALLBACK,
            'fallback_triggered': _fallback_status['has_triggered'],
            'fallback_count': _fallback_status['fallback_count'],
            'last_error': _fallback_status['last_error']
        }
    except ImportError:
        return {
            'configured_provider': 'unknown',
            'active_provider': 'unknown',
            'model': 'unknown',
            'error': 'Failed to load configuration'
        }


# ============================================================================
# Future Provider Functions (Phase 2+ Stubs)
# ============================================================================

def create_image_client() -> OpenAI:
    """
    Create image generation client (Phase 2).
    Currently returns OpenAI client.
    """
    try:
        import config
        from model_config import IMAGE_PROVIDER
        
        if IMAGE_PROVIDER == "openrouter":
            # Future: Add OpenRouter image support
            warning("OpenRouter image generation not yet implemented, using OpenAI")
        
        return OpenAI(api_key=getattr(config, 'OPENAI_API_KEY', ''))
        
    except ImportError:
        return OpenAI(api_key="")


def create_tts_client() -> OpenAI:
    """
    Create TTS client (Phase 2).
    Currently returns OpenAI client.
    """
    try:
        import config
        from model_config import TTS_PROVIDER
        
        if TTS_PROVIDER == "openrouter":
            # Future: Add OpenRouter TTS support
            warning("OpenRouter TTS not yet implemented, using OpenAI")
        
        return OpenAI(api_key=getattr(config, 'OPENAI_API_KEY', ''))
        
    except ImportError:
        return OpenAI(api_key="")


def create_video_client():
    """
    Create video generation client (Phase 3).
    Returns None for now (no video generation currently implemented).
    """
    # Phase 3: Implement OpenRouter video generation
    # Models: HunyuanVideo, Wan 2.1, Mochi 1, LTXVideo
    return None


# ============================================================================
# PHASE 1B: Full OpenRouter Enablement - 3-Tier Model Configuration
# ============================================================================

def get_model_config(task_id: str, original_openai_model: Optional[str] = None) -> Dict[str, Any]:
    """
    Get complete model configuration for a task using 3-tier fallback system.
    
    TIER 1: Kimi K2.5 with Thinking Toggle (Primary)
      - thinking: enabled for complex tasks (upstream gpt-4.1-full equivalents)
      - thinking: disabled for simple tasks (upstream gpt-4.1-mini equivalents)
    
    TIER 2: Dual Model Strategy (Secondary Fallback)
      - Kimi K2.5 for full tasks, Gemini Flash for mini tasks
    
    TIER 3: OpenAI Upstream (Tertiary Fallback)
      - Uses original OpenAI model constants
      - Automatic fallback when OpenRouter fails
    
    Args:
        task_id: Task identifier (e.g., "dm_main", "combat_main", "summaries")
        original_openai_model: Original OpenAI model constant (for fallback)
        
    Returns:
        Dict containing:
        - model: Model ID string
        - temperature: Temperature setting
        - extra_body: Additional API parameters (for Kimi thinking mode)
        - use_openrouter: Boolean indicating if OpenRouter should be used
        - fallback_strategy: Strategy to use if this tier fails
    
    Usage:
        config = get_model_config("combat_main", COMBAT_MAIN_MODEL)
        response = client.chat.completions.create(
            model=config["model"],
            messages=messages,
            temperature=config["temperature"],
            **config.get("extra_body", {})
        )
    """
    try:
        from model_config import (
            LLM_PROVIDER,
            OPENROUTER_STRATEGY,
            OPENROUTER_CHAT_MODEL,
            OPENROUTER_FULL_MODEL,
            OPENROUTER_MINI_MODEL,
            THINKING_ENABLED_TASKS,
            TASK_OVERRIDES,
            TASK_TEMPERATURES,
        )
    except ImportError:
        # Fallback if imports fail - use OpenAI defaults
        return {
            "model": original_openai_model or "gpt-4.1-2025-04-14",
            "temperature": 0.7,
            "extra_body": {},
            "use_openrouter": False,
            "fallback_strategy": None,
        }
    
    # CRITICAL FIX: Use single source of truth to determine actual provider
    # This prevents the split-brain issue where config says OpenRouter but
    # runtime conditions (missing API key) require OpenAI fallback
    provider, is_openrouter = _get_actual_provider()
    
    if not is_openrouter:
        return {
            "model": original_openai_model or "gpt-4.1-2025-04-14",
            "temperature": TASK_TEMPERATURES.get(task_id, 0.7),
            "extra_body": {},
            "use_openrouter": False,
            "fallback_strategy": None,
        }
    
    # Check for task-specific override (highest priority)
    if task_id in TASK_OVERRIDES:
        override = TASK_OVERRIDES[task_id]
        model = override.get("model", OPENROUTER_CHAT_MODEL)
        thinking = override.get("thinking")
        temp = override.get("temperature", TASK_TEMPERATURES.get(task_id, 0.7))
        
        extra_body = {}
        if thinking:
            extra_body = {"extra_body": {"thinking": {"type": thinking}}}
        
        return {
            "model": model,
            "temperature": temp,
            "extra_body": extra_body,
            "use_openrouter": True,
            "fallback_strategy": "dual_model",
        }
    
    # TIER 1: Kimi with thinking toggle (primary strategy)
    if OPENROUTER_STRATEGY == "kimi_thinking":
        # Determine if this is a complex task (thinking enabled) or simple task (thinking disabled)
        is_complex = task_id in THINKING_ENABLED_TASKS
        thinking_mode = "enabled" if is_complex else "disabled"
        
        # Set temperature based on thinking mode
        # Higher temp (1.0) for thinking mode, lower (0.6) for instant mode
        if task_id in TASK_TEMPERATURES:
            temperature = TASK_TEMPERATURES[task_id]
        else:
            temperature = 1.0 if thinking_mode == "enabled" else 0.6
        
        return {
            "model": OPENROUTER_CHAT_MODEL,
            "temperature": temperature,
            "extra_body": {"thinking": {"type": thinking_mode}},
            "use_openrouter": True,
            "fallback_strategy": "dual_model",
        }
    
    # TIER 2: Dual model strategy
    elif OPENROUTER_STRATEGY == "dual_model":
        is_complex = task_id in THINKING_ENABLED_TASKS
        model = OPENROUTER_FULL_MODEL if is_complex else OPENROUTER_MINI_MODEL
        temperature = TASK_TEMPERATURES.get(task_id, 0.7)
        
        return {
            "model": model,
            "temperature": temperature,
            "extra_body": {},
            "use_openrouter": True,
            "fallback_strategy": "openai",
        }
    
    # TIER 3: Single model strategy (use full model for everything)
    else:
        return {
            "model": OPENROUTER_CHAT_MODEL,
            "temperature": TASK_TEMPERATURES.get(task_id, 0.7),
            "extra_body": {},
            "use_openrouter": True,
            "fallback_strategy": "openai",
        }


def is_thinking_enabled(task_id: str) -> bool:
    """
    Check if thinking mode is enabled for a task.
    
    Args:
        task_id: Task identifier
        
    Returns:
        True if thinking is enabled, False otherwise
    """
    try:
        from model_config import THINKING_ENABLED_TASKS, LLM_PROVIDER, OPENROUTER_STRATEGY
        
        if LLM_PROVIDER != "openrouter" or OPENROUTER_STRATEGY != "kimi_thinking":
            return False
        
        return task_id in THINKING_ENABLED_TASKS
    except ImportError:
        return False


def get_task_complexity(task_id: str) -> str:
    """
    Get the complexity level of a task (full or mini).
    
    Args:
        task_id: Task identifier
        
    Returns:
        "full" for complex tasks, "mini" for simple tasks
    """
    try:
        from model_config import THINKING_ENABLED_TASKS
        return "full" if task_id in THINKING_ENABLED_TASKS else "mini"
    except ImportError:
        return "full"


# Convenience function for simple model selection
def get_model_for_task(task_id: str, original_openai_model: Optional[str] = None) -> str:
    """
    Simple function to get just the model name.
    
    Args:
        task_id: Task identifier
        original_openai_model: Original OpenAI model constant
        
    Returns:
        Model ID string
    """
    config = get_model_config(task_id, original_openai_model)
    return config["model"]


# ============================================================================
