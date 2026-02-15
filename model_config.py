# Model Configuration Settings
# This file contains all AI model configurations and can be safely committed to git

# --- Main Game Logic Models (used in main.py) ---
DM_MAIN_MODEL = "gpt-4.1-2025-04-14"
DM_SUMMARIZATION_MODEL = "gpt-4.1-mini-2025-04-14"
DM_VALIDATION_MODEL = "gpt-4.1-2025-04-14"

# --- Action Prediction Model (used in action_predictor.py) ---
ACTION_PREDICTION_MODEL = "gpt-4.1-2025-04-14"  # Use full model for accurate action prediction

# --- Combat Simulation Models (used in combat_manager.py) ---
COMBAT_MAIN_MODEL = "gpt-4.1-2025-04-14"
# COMBAT_SCHEMA_UPDATER_MODEL - This was defined but not directly used.
# If needed for update_player_info, update_npc_info, update_encounter called from combat_sim,
# those modules will use their own specific models defined below.
COMBAT_DIALOGUE_SUMMARY_MODEL = "gpt-4.1-mini-2025-04-14"

# --- Utility and Builder Models ---
NPC_BUILDER_MODEL = "gpt-4.1-2025-04-14"                # Used in npc_builder.py
ADVENTURE_SUMMARY_MODEL = "gpt-4.1-mini-2025-04-14"
CHARACTER_VALIDATOR_MODEL = "gpt-4.1-2025-04-14"    # Used in adv_summary.py
PLOT_UPDATE_MODEL = "gpt-4.1-mini-2025-04-14"          # Used in plot_update.py
PLAYER_INFO_UPDATE_MODEL = "gpt-4.1-mini-2025-04-14"   # Used in update_player_info.py
NPC_INFO_UPDATE_MODEL = "gpt-4.1-mini-2025-04-14"      # Used in update_npc_info.py
MONSTER_BUILDER_MODEL = "gpt-4.1-2025-04-14"
ENCOUNTER_UPDATE_MODEL = "gpt-4.1-mini-2025-04-14"
LEVEL_UP_MODEL = "gpt-4.1-2025-04-14"                  # Used in level_up.py

# --- Transition Validation Model ---
TRANSITION_VALIDATOR_MODEL = "gpt-4.1-mini-2025-04-14"  # Used in transition_validator.py
TRANSITION_VALIDATOR_TEMPERATURE = 0.3                   # Low temp for analytical reasoning

# --- Token Optimization Models ---
DM_MINI_MODEL = "gpt-4.1-mini-2025-04-14"              # Used for simple conversations and plot-only updates
DM_FULL_MODEL = "gpt-4.1-2025-04-14"                   # Used for complex actions requiring JSON operations

# --- Model Routing Settings ---
ENABLE_INTELLIGENT_ROUTING = True                        # Enable/disable action-based model routing
MAX_VALIDATION_RETRIES = 1                              # Retry with full model after this many validation failures

# --- GPT-5 Model Configuration ---
GPT5_MINI_MODEL = "gpt-5-mini-2025-08-07"              # GPT-5 mini model for testing
GPT5_FULL_MODEL = "gpt-5-2025-08-07"                   # GPT-5 full model (kept for compatibility, not used)
USE_GPT5_MODELS = False                                 # Toggle for GPT-5 models (default: GPT-4.1)
GPT5_USE_HIGH_REASONING_ON_RETRY = True                # Use high reasoning effort after first failure (instead of model switch)

# --- Combat System Settings ---
USE_COMPRESSED_COMBAT = True                            # Toggle for compressed combat AND validation prompts (False = original prompts)
COMBAT_API_TIMEOUT_SECONDS = 120                        # Per-call timeout for combat LLM calls (prevents indefinite hangs)
COMBAT_CONNECT_TIMEOUT_SECONDS = 10                     # TCP connection timeout for combat LLM calls

# --- Streaming UX Settings ---
# TABLETOP MODE: Reversion defaults - keep stable block narration UX.
ENABLE_CHAT_STREAMING = False                          # Reversion default: keep canonical block narration path
ENABLE_BROWSER_TTS_STREAM_SYNC = False                 # Reversion default: disable sentence-level stream TTS
STREAM_SUPERSEDED_VISIBLE = False                      # Hide superseded draft attempts by default for cleaner UX

# --- TTS Text Sync Settings ---
# TABLETOP MODE: Browser word-boundary sync for progressive text reveal (OFF by default).
# When enabled, narration text reveals word-by-word synchronized with Browser TTS speech.
ENABLE_BROWSER_WORD_SYNC = False                       # Browser TTS word-boundary synchronized text reveal
# Future: Non-browser TTS timing estimation (Phase 2 - scaffold only, not active)
ENABLE_TTS_ESTIMATED_TIMING = False                    # Estimated timing sync for OpenAI TTS (future Phase 2)

# --- Conversation Compression Settings ---
# Enable/disable compression types before API calls
COMPRESSION_ENABLED = True                              # Master switch for all compression
COMPRESS_LOCATION_ENCOUNTERS = True                     # Compress location encounter data using dynamic compressor
COMPRESS_LOCATION_SUMMARIES = True                      # Compress location summaries (now implemented)

# --- Compression Model Configuration ---
# Models used for compressing conversation history and location data
NARRATIVE_COMPRESSION_MODEL = "gpt-4.1-mini-2025-04-14"  # For general narrative compression
LOCATION_COMPRESSION_MODEL = "gpt-4.1-2025-04-14"        # For location encounter compression
COMPRESSION_MAX_WORKERS = 4                              # Number of parallel workers for compression

# --- Text-to-Speech Configuration ---
TTS_MODEL = "tts-1"                                       # OpenAI TTS model (tts-1 or tts-1-hd for higher quality)
TTS_VOICE = "fable"                                       # Voice: alloy, echo, fable, onyx, nova, shimmer (fable is good for narration)
TTS_SPEED = 1.0                                           # Speed: 0.25 to 4.0 (1.0 is normal)

# ============================================================================
# OPENROUTER CONFIGURATION - Multi-Provider AI Support
# ============================================================================

# --- Provider Selection ---
# Set to "openrouter" to use OpenRouter, "openai" for direct OpenAI API
LLM_PROVIDER = "openai"  # Options: "openai", "openrouter"

# --- OpenRouter Settings ---
# Get your API key at: https://openrouter.ai/keys
OPENROUTER_API_KEY = ""  # Set in config.py (not model_config.py)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HTTP_REFERER = "https://github.com/zeug/NeverEndingQuest"  # For OpenRouter rankings
OPENROUTER_APP_TITLE = "NeverEndingQuest AI DM"

# --- Pre-configured Models ---
# Recommended: Kimi K2.5 for DM (excellent reasoning, 1M context)
OPENROUTER_CHAT_MODEL = "moonshotai/kimi-k2.5"

# Alternative models (uncomment to use):
# OPENROUTER_CHAT_MODEL = "anthropic/claude-3.5-sonnet"  # If you prefer Claude
# OPENROUTER_CHAT_MODEL = "google/gemini-2.0-flash-exp"  # Fastest option
# OPENROUTER_CHAT_MODEL = "openai/gpt-4.1-2025-04-14"    # Use OpenAI via OpenRouter

# --- Future Provider Slots (Phase 2+ Prep) ---
IMAGE_PROVIDER = "openai"  # Options: "openai", "openrouter", "stability"
TTS_PROVIDER = "openai"    # Options: "openai", "openrouter", "elevenlabs"
VIDEO_PROVIDER = "none"    # Options: "none", "openrouter" (Phase 3)

# --- Fallback Configuration ---
ENABLE_PROVIDER_FALLBACK = True  # Auto-fallback to OpenAI if OpenRouter fails
FALLBACK_NOTIFICATION = True     # Show system message in GUI when fallback occurs
MAX_FALLBACK_ATTEMPTS = 3        # Retry OpenRouter before falling back

# ============================================================================
# PHASE 1B: FULL OPENROUTER ENABLEMENT - 3-TIER MODEL SYSTEM
# ============================================================================
#
# TIER 1: Kimi K2.5 with Thinking Toggle (PRIMARY - Recommended)
#   - Uses one model with adjustable reasoning depth
#   - thinking: enabled = Complex tasks (matches upstream gpt-4.1-full)
#   - thinking: disabled = Simple tasks (matches upstream gpt-4.1-mini)
#   - Best balance of cost, quality, and simplicity
#
# TIER 2: Dual Model Strategy (SECONDARY - Fallback)
#   - Uses separate models for complex vs simple tasks
#   - Kimi K2.5 for full tasks, Gemini Flash for mini tasks
#   - Use if Kimi thinking toggle has issues
#
# TIER 3: OpenAI Upstream (TERTIARY - Compatibility)
#   - Uses original OpenAI model constants
#   - Automatic fallback when OpenRouter fails
#   - 100% upstream compatibility maintained
#
# To switch strategies, just change OPENROUTER_STRATEGY below
# ============================================================================

# --- Strategy Selection ---
# "kimi_thinking" = One model with thinking toggle (recommended, default)
# "dual_model" = Separate models for full/mini tasks (fallback option)
# "single_model" = One model for everything (not recommended)
OPENROUTER_STRATEGY = "kimi_thinking"

# --- Base Models ---
OPENROUTER_FULL_MODEL = "moonshotai/kimi-k2.5"  # For complex reasoning tasks
OPENROUTER_MINI_MODEL = "google/gemini-2.0-flash-exp"  # For simple tasks (dual_model only)

# Alternative mini models (uncomment to use):
# OPENROUTER_MINI_MODEL = "qwen/qwen-2.5-7b-instruct"  # Cheapest option
# OPENROUTER_MINI_MODEL = "meta-llama/llama-3.3-70b-instruct"  # Balanced quality/cost

# --- Task Mapping (Based on Upstream Model Assignments) ---
# Tasks using GPT-4.1-full upstream → thinking: enabled
# Tasks using GPT-4.1-mini upstream → thinking: disabled
# 
# This mapping preserves upstream's tested model assignments

THINKING_ENABLED_TASKS = [
    # Complex reasoning tasks (upstream used gpt-4.1-full)
    "dm_main",              # Main DM responses
    "dm_validation",        # Response validation
    "combat_main",          # Combat simulation
    "action_prediction",    # Action prediction
    "character_validator",  # Character validation
    "npc_builder",          # NPC generation
    "monster_builder",      # Monster generation
    "level_up",             # Level up processing
    "dm_full",              # Complex actions with JSON
    "location_compression", # Location data compression
]

# All other tasks default to thinking: disabled (upstream used gpt-4.1-mini)
# Including: summaries, updates, compression, transitions, builders (mini tasks)

# --- Task-Specific Overrides (Optional) ---
# Force specific configuration for individual tasks
# Format: "task_id": {"thinking": "enabled|disabled", "model": "model_id"}
# Uncomment lines below to override defaults:
TASK_OVERRIDES = {
    # Example overrides:
    # "combat_main": {"thinking": "disabled"},  # Try faster combat
    # "summaries": {"thinking": "enabled"},     # Try better summaries
    # "validation": {"model": "anthropic/claude-3.5-sonnet"},  # Use Claude for validation
}

# --- Future Model Registry (For Easy Testing) ---
# Add new models here as they become available, then reference in overrides
AVAILABLE_MODELS = {
    "kimi_k2.5": "moonshotai/kimi-k2.5",
    "gemini_flash": "google/gemini-2.0-flash-exp",
    "gemini_pro": "google/gemini-2.0-pro-exp",
    "claude_sonnet": "anthropic/claude-3.5-sonnet",
    "claude_haiku": "anthropic/claude-3.5-haiku",
    "llama_70b": "meta-llama/llama-3.3-70b-instruct",
    "qwen_7b": "qwen/qwen-2.5-7b-instruct",
    "qwen_32b": "qwen/qwen-2.5-32b-instruct",
    # Add future Chinese models here as they come online!
}

# --- Temperature Settings by Task Type ---
# These match upstream temperature preferences
TASK_TEMPERATURES = {
    "dm_main": 0.7,
    "dm_validation": 0.1,  # Low temp for validation
    "combat_main": 0.7,
    "action_prediction": 0.7,
    "validation": 0.3,     # Low temp for analytical tasks
    "summaries": 0.8,
    "updates": 0.7,
    "compression": 0.3,
    "builders": 0.7,
    "default": 0.7,
}

# --- Migration Path Notes ---
# Current: Kimi K2.5 with thinking toggle (smart cost/quality balance)
# Future Phase 2: When cheap models mature, move tasks to dual_model
# Future Phase 3: When one model is "good enough", use single_model
# 
# To migrate: Just change OPENROUTER_STRATEGY and restart server
# No code changes needed - all routing happens in ai_client_factory.py

# ============================================================================
