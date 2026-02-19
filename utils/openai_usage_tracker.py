#!/usr/bin/env python3
"""
OpenAI Usage Tracker - Compatibility shim for provider-agnostic LLM Usage Tracker

This module provides backward-compatible imports while delegating to the
provider-agnostic utils.llm_usage_tracker implementation.

DEPRECATION NOTE: New code should import from utils.llm_usage_tracker directly.
This module is maintained for compatibility with existing imports.
"""

# Import the generic tracker implementation
from utils.llm_usage_tracker import (
    LLMUsageTracker as OpenAIUsageTracker,
    get_global_tracker,
    track_response,
    get_usage_stats,
    track_image_cost,
    get_dalle3_cost_usd
)

# Re-export for backward compatibility
__all__ = ['OpenAIUsageTracker', 'get_global_tracker', 'track_response', 'get_usage_stats', 'track_image_cost', 'get_dalle3_cost_usd']
