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