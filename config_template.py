# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# CONFIG_TEMPLATE.PY - SYSTEM CONFIGURATION TEMPLATE
# ============================================================================
# 
# ARCHITECTURE ROLE: Configuration Management - Central System Settings Template
# 
# This template provides the structure for config.py including API keys, model
# selections, file paths, and operational parameters. It implements our
# "Configurable AI Strategy" by allowing model selection per use case.
# 
# KEY RESPONSIBILITIES:
# - API key and authentication management template
# - AI model configuration for different use cases
# - File system path configuration
# - System operational parameters
# - Environment-specific settings
# 
# CONFIGURATION CATEGORIES:
# - AI Models: Different models for DM, combat, validation, generation
# - File Paths: Module directories and schema locations
# - API Settings: Keys, timeouts, and retry parameters
# - System Parameters: Debug modes, logging levels, validation settings
# 
# SECURITY CONSIDERATIONS:
# - API keys should be moved to environment variables in production
# - Sensitive configuration should not be committed to version control
# - Copy this template to config.py and add your actual API key
# 
# ARCHITECTURAL INTEGRATION:
# - Used by all modules requiring AI model access
# - Provides centralized model selection strategy
# - Enables easy switching between different AI configurations
# - Supports our multi-model AI architecture
# 
# This module enables our flexible, multi-model AI strategy while
# maintaining centralized configuration management.
# ============================================================================

# Import model configuration settings
from model_config import *

# --- API Keys ---
# WARNING: Replace with your actual API keys and move to environment variables in production
#
# OPENAI_API_KEY (Required): Used for Legacy (GPT-4.1) and OpenAI (GPT-5.x) providers
# Get your key at: https://platform.openai.com/api-keys
OPENAI_API_KEY = "your_openai_api_key_here"

# GEMINI_API_KEY (Optional): Used for Gemini 3.1 provider
# Only needed if you want to use Gemini as an alternative AI provider
# Get your key at: https://aistudio.google.com/apikey
GEMINI_API_KEY = "your_gemini_api_key_here"

# Local / OpenAI-compatible endpoint (optional): set it from the web UI instead --
# Settings -> AI Provider -> Local / Custom Server. Non-secret endpoint choices
# are stored in user_settings.json; credentials use the OS credential store.
# Defaults to http://localhost:1234/v1 when unset.

# --- Module folder structure ---
MODULES_DIR = "modules"
DEFAULT_MODULE = "The_Thornwood_Watch"

# Developer-only story-first module generator. Keep False for the unchanged
# production/legacy module builder. The gold path currently supports approved
# OpenAI/Gemini cloud configurations; LM Studio support is a later phase.
USE_STORY_FIRST_GENERATOR = False

# Note: All model configurations are now imported from model_config.py above

# --- Web Interface Configuration ---
WEB_PORT = 8357                                         # Port for the web interface (changed from 5000 for security)


# Apply web-set API keys from the OS credential store (overrides the values
# above). No-op when no key has been saved via the web UI.
try:
    import model_config as _mc
    _mc.apply_persisted_openai_key()
    _mc.apply_persisted_gemini_key()
except Exception:
    pass

# --- END OF FILE config_template.py ---
