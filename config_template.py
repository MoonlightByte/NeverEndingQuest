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

# WARNING: Replace with your actual OpenAI API key and move to environment variables in production
OPENAI_API_KEY = "your_openai_api_key_here"

# OpenRouter API Key (optional - enables Kimi K2.5 and other models via OpenRouter)
# Get your key at: https://openrouter.ai/keys
OPENROUTER_API_KEY = ""

# --- Module folder structure ---
MODULES_DIR = "modules"
DEFAULT_MODULE = "The_Thornwood_Watch"

# --- Live Exchange Rate Configuration (Optional) ---
# TABLETOP MODE: Real-time USD to target currency conversion for Debug tab cost estimates
# Rate is fetched ONCE at game session start (no periodic refresh)
# 
# Supported currency codes: 3-letter ISO codes (e.g., NZD, AUD, CAD, EUR, GBP, JPY)
# Common examples:
#   "NZD" = New Zealand Dollar (default)
#   "AUD" = Australian Dollar
#   "CAD" = Canadian Dollar  
#   "EUR" = Euro
#   "GBP" = British Pound
#   "JPY" = Japanese Yen
# 
# Get free API key at: https://www.exchangerate-api.com/
# URL format: https://v6.exchangerate-api.com/v6/YOUR_KEY/latest/USD
# 
# Fallback behavior:
# - If EXCHANGE_RATE_API_URL is empty/disabled -> uses static USD_TO_NZD_RATE
# - If target currency code is invalid/missing from API -> falls back to USD (rate 1.0)
# - If API fails -> falls back to static rate for NZD, or USD (1.0) for other currencies
EXCHANGE_RATE_API_URL = ""  # Leave empty to use static fallback rate
EXCHANGE_RATE_TARGET_CURRENCY = "NZD"  # 3-letter code: NZD, AUD, CAD, EUR, GBP, JPY, etc.
EXCHANGE_RATE_TIMEOUT_SECONDS = 5  # Max wait for API response at startup
ENABLE_LIVE_EXCHANGE_RATE = False  # Disabled by default for safety

# Note: All model configurations are now imported from model_config.py above

# --- Web Interface Configuration ---
WEB_PORT = 8357                                         # Port for the web interface (changed from 5000 for security)
DEBUG_STATUS_SYNC = False                               # Enable/disable noisy status synchronization debug logs

# --- END OF FILE config_template.py ---
