# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# STORAGE_PROCESSOR.PY - AGENTIC AI STORAGE OPERATION PROCESSOR
# ============================================================================
# 
# ARCHITECTURE ROLE: Natural Language Storage Processing Layer
# 
# This module implements an agentic AI system that processes natural language
# storage descriptions and converts them into validated JSON operations.
# Similar to the updateCharacterInfo workflow, it uses the full model (not mini)
# for accurate interpretation of player intent.
# 
# KEY RESPONSIBILITIES:
# - Parse natural language storage descriptions
# - Convert descriptions to structured JSON operations
# - Validate operations against storage action schema
# - Provide intelligent error handling and suggestions
# - Maintain context awareness of current game state
# 
# AGENTIC FEATURES:
# - Uses full OpenAI model for accurate interpretation
# - Context-aware processing with game state information
# - Flexible handling of various storage descriptions
# - Intelligent mapping of descriptions to locations
# - Error recovery and suggestion generation
# ============================================================================

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T049", "core/managers/storage_processor.py", 286)
import config
from core.ai import api_client
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.module_path_manager import ModulePathManager
import jsonschema
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("storage_processor")

class StorageProcessor:
    """Processes natural language storage descriptions using AI"""
    
    def __init__(self):
        """Initialize storage processor"""
        # No raw OpenAI client: all API calls route through api_client.create_completion()
        # per the multi-provider migration. A direct OpenAI(api_key=...) here crashed at
        # construction for Gemini/LM Studio users with no OPENAI_API_KEY (it was never used).
        self.model = config.DM_MAIN_MODEL  # Use full model, not mini
        self.schema_file = "schemas/storage_action_schema.json"
        # Get current module from party tracker for consistent path resolution
        try:
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            self.path_manager = ModulePathManager(current_module)
        except:
            self.path_manager = ModulePathManager()  # Fallback to reading from file
        
    def _get_storage_schema(self) -> Dict[str, Any]:
        """Load storage action schema"""
        if os.path.exists(self.schema_file):
            return safe_json_load(self.schema_file)
        return {}
        
    def _get_game_context(self, character_name: str) -> Dict[str, Any]:
        """Get current game context for processing"""
        context = {
            "character": None,
            "party": None,
            "location": None,
            "existing_storage": []
        }
        
        try:
            # Get character data
            character_file = self.path_manager.get_character_path(character_name)
            if os.path.exists(character_file):
                context["character"] = safe_json_load(character_file)
                
            # Get party data
            if os.path.exists("party_tracker.json"):
                context["party"] = safe_json_load("party_tracker.json")
                
            # Get current location info
            if context["party"]:
                world_conditions = context["party"].get("worldConditions", {})
                context["location"] = {
                    "id": world_conditions.get("currentLocationId", "UNKNOWN"),
                    "name": world_conditions.get("currentLocation", "Unknown Location"),
                    "area_id": world_conditions.get("currentAreaId", "UNKNOWN"),
                    "area_name": world_conditions.get("currentArea", "Unknown Area")
                }
                
            # Get existing storage at current location
            if os.path.exists("player_storage.json"):
                storage_data = safe_json_load("player_storage.json")
                current_location_id = context["location"]["id"] if context["location"] else "UNKNOWN"
                context["existing_storage"] = [
                    storage for storage in storage_data.get("playerStorage", [])
                    if storage.get("locationId") == current_location_id
                ]
                
        except Exception as e:
            print(f"[WARNING] Could not load full game context: {e}")
            
        return context
        
    def _create_processing_prompt(self, description: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Create AI prompt for processing storage description"""
        
        schema = self._get_storage_schema()
        
        # Format character inventory for context - Only include items with quantity > 0
        character_inventory = []
        if context.get("character") and context["character"].get("equipment"):
            available_items = [item for item in context["character"]["equipment"] if item.get("quantity", 1) > 0]
            for item in available_items:  # Include ALL items, no limit
                character_inventory.append({
                    "name": item.get("item_name", "Unknown"),
                    "quantity": item.get("quantity", 1),
                    "type": item.get("item_type", "miscellaneous")
                })
                
        # Format existing storage for context
        existing_storage_info = []
        for storage in context.get("existing_storage", []):
            existing_storage_info.append({
                "id": storage["id"],
                "name": storage["deviceName"],
                "type": storage["deviceType"],
                "contents_count": len(storage.get("contents", []))
            })
            
        system_prompt = f"""You are a storage operations specialist for a 5th Edition RPG system. Your task is to convert natural language storage descriptions into valid JSON operations that match the provided schema.

CONTEXT INFORMATION:
Character: {context.get('character', {}).get('name', 'Unknown')}
Current Location: {context.get('location', {}).get('name', 'Unknown Location')} (ID: {context.get('location', {}).get('id', 'UNKNOWN')})
Current Area: {context.get('location', {}).get('area_name', 'Unknown Area')} (ID: {context.get('location', {}).get('area_id', 'UNKNOWN')})

CHARACTER INVENTORY (all items):
{json.dumps(character_inventory, indent=2)}

EXISTING STORAGE AT LOCATION:
{json.dumps(existing_storage_info, indent=2)}

STORAGE ACTION SCHEMA:
{json.dumps(schema, indent=2)}

INSTRUCTIONS:
1. Analyze the natural language description carefully
2. Determine the appropriate storage action (create_storage, store_item, retrieve_item, view_storage)
3. Extract all relevant information (character, items, quantities, storage types, etc.)
4. If creating new storage, infer appropriate storage type and name
5. If referencing existing storage, use the storage_id from the context
6. Ensure all required fields are present according to the schema
7. Use the current location information provided in context
8. Validate item names against the character's inventory for store operations
9. For multiple items, use the "items" array format instead of single item_name/quantity
10. NEVER return action "error" - always use a valid action type from the enum

OUTPUT REQUIREMENTS:
- Return ONLY valid JSON that matches the storage action schema
- Include all required fields for the detected action type
- Use EXACT item names from character inventory (never modify or assume item names)
- Extract the specific item name mentioned in the player's request
- Use the exact quantity requested, or 1 if not specified
- Reference existing storage IDs when applicable
- If the request is unclear, default to store_item action with the specific item mentioned

EXAMPLE OUTPUTS:

For "I store my rope in a chest here":
{{
  "action": "store_item",
  "character": "Norn",
  "storage_type": "chest",
  "storage_name": "Storage Chest",
  "location_description": "current location",
  "item_name": "Hemp Rope (50 feet)",
  "quantity": 1
}}

For "I store my torch and dagger in the chest":
{{
  "action": "store_item",
  "character": "Norn",
  "storage_type": "chest",
  "storage_name": "Equipment Chest",
  "location_description": "current location", 
  "items": [
    {{"item_name": "Torch", "quantity": 1}},
    {{"item_name": "Dagger", "quantity": 1}}
  ]
}}

For "I get my torch from the chest we made":
{{
  "action": "retrieve_item",
  "character": "Norn", 
  "storage_id": "storage_12345678",
  "item_name": "Torch",
  "quantity": 1
}}

For "What's in our storage here?":
{{
  "action": "view_storage",
  "character": "Norn",
  "location_id": "A15"
}}"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Convert this storage description to a valid JSON operation:\n\n\"{description}\""}
        ]
        
    def _validate_operation(self, operation: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate storage operation against schema"""
        try:
            schema = self._get_storage_schema()
            if schema:
                jsonschema.validate(operation, schema)
            return True, ""
        except jsonschema.ValidationError as e:
            return False, f"Schema validation error: {e.message}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
            
    def _post_process_operation(self, operation: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process operation to add missing information"""
        
        # Ensure character is set
        if not operation.get("character"):
            operation["character"] = context.get("character", {}).get("name", "Unknown")
            
        # Handle location information
        if operation.get("action") in ["create_storage", "store_item"]:
            if not operation.get("location_id") and context.get("location"):
                operation["location_id"] = context["location"]["id"]
                
        # Handle existing storage references
        if operation.get("action") in ["retrieve_item", "view_storage", "store_item"]:
            if not operation.get("storage_id") and context.get("existing_storage"):
                # Try to match storage by type or name
                storage_type = operation.get("storage_type", "").lower()
                for storage in context["existing_storage"]:
                    if storage_type in storage.get("deviceType", "").lower():
                        operation["storage_id"] = storage["id"]
                        break
                        
                # If still no match, use first available storage
                if not operation.get("storage_id") and context["existing_storage"]:
                    operation["storage_id"] = context["existing_storage"][0]["id"]
                    
        # Handle combined create/store operations (only if no existing storage found)
        if operation.get("action") == "store_item" and not operation.get("storage_id"):
            # This will trigger storage creation in storage_manager
            if not operation.get("storage_type"):
                operation["storage_type"] = "chest"  # Default storage type
                
        return operation
        
    def process_storage_description(self, description: str, character_name: str) -> Dict[str, Any]:
        """Process natural language storage description into validated operation with retry logic"""
        
        max_attempts = 3
        original_description = description
        
        for attempt in range(max_attempts):
            try:
                debug(f"AI_CALL: Storage processing attempt {attempt + 1} of {max_attempts}", category="storage_operations")
                
                # Get game context
                context = self._get_game_context(character_name)
                
                # Create AI prompt
                messages = self._create_processing_prompt(description, context)

                # T049: storage-action extraction (mini-tier JSON extraction).
                # Route through the provider-aware router so MODEL_PROVIDER toggle
                # actually drives which provider/model handles the call.
                # HIGH-12 (#127): deferred import (read per call) so set_provider()
                # changes propagate live -- never import MODEL_PROVIDER at module level.
                from model_config import MODEL_PROVIDER
                if MODEL_PROVIDER == "openai":
                    sp_cfg = config.STORAGE_PROCESSOR_T049_GPT5MINI
                elif MODEL_PROVIDER == "gemini":
                    sp_cfg = config.STORAGE_PROCESSOR_T049_GEMINI_FLASHLITE_MINIMAL
                elif MODEL_PROVIDER == "lmstudio":
                    sp_cfg = config.STORAGE_PROCESSOR_T049_LMSTUDIO
                else:  # legacy
                    sp_cfg = config.STORAGE_PROCESSOR_T049_LEGACY

                # T049: fail loud (gemini-only) if the schema failed to load at import.
                # Without response_schema, gemini-flash-lite emits narration instead of
                # a storage operation and the action silently fails after retries.
                if MODEL_PROVIDER == "gemini" and sp_cfg.get("response_schema") is None:
                    raise RuntimeError(
                        "T049 storage action aborted: Gemini response_schema is None "
                        "(schemas/storage_action_schema.json failed to load at import). "
                        "Restore the schema file or switch MODEL_PROVIDER off gemini."
                    )

                # Call AI model
                response = capture_and_fanout("T049", api_client.create_completion,
                    messages=messages,
                    model=sp_cfg["model"],
                    temperature=0.1,    # callsite owns temperature
                    **{k: v for k, v in sp_cfg.items() if k != "model"})
                
                # Parse AI response
                ai_response = response.choices[0].message.content.strip()
                
                # Try to parse JSON from response
                try:
                    # Handle cases where AI might wrap JSON in markdown
                    if "```json" in ai_response:
                        ai_response = ai_response.split("```json")[1].split("```")[0].strip()
                    elif "```" in ai_response:
                        ai_response = ai_response.split("```")[1].strip()
                        
                    operation = json.loads(ai_response)
                    
                except json.JSONDecodeError as e:
                    if attempt == max_attempts - 1:  # Last attempt
                        return {
                            "success": False,
                            "error": f"AI response was not valid JSON after {max_attempts} attempts: {e}",
                            "raw_response": ai_response
                        }
                    continue  # Retry on JSON parse error
                    
                # Post-process operation
                operation = self._post_process_operation(operation, context)
                
                # Validate operation
                is_valid, validation_error = self._validate_operation(operation)
                
                if not is_valid:
                    warning(f"VALIDATION: Failed on attempt {attempt + 1}: {validation_error}", category="storage_operations")
                    
                    if attempt == max_attempts - 1:  # Last attempt
                        return {
                            "success": False,
                            "error": f"Generated operation failed validation after {max_attempts} attempts: {validation_error}",
                            "operation": operation
                        }
                    
                    # Prepare retry with error feedback
                    if "Character does not have" in validation_error:
                        # Extract the problematic item name from the error
                        error_parts = validation_error.split("Character does not have ")
                        if len(error_parts) > 1:
                            missing_item = error_parts[1].strip()
                            description = f"{original_description}\n\nPREVIOUS ATTEMPT FAILED: The item '{missing_item}' was not found in the character's inventory. Please check the CHARACTER INVENTORY list above and use the EXACT item name that matches what the player described. Try to match '{missing_item}' to the closest item in the inventory list."
                    else:
                        description = f"{original_description}\n\nPREVIOUS ATTEMPT FAILED: {validation_error}. Please try again using exact item names from the CHARACTER INVENTORY list."
                    
                    continue  # Retry with feedback
                    
                # Success!
                info(f"SUCCESS: Storage processing succeeded on attempt {attempt + 1}", category="storage_operations")
                return {
                    "success": True,
                    "operation": operation,
                    "description": original_description,
                    "processed_at": datetime.now().isoformat()
                }
                
            except Exception as e:
                error(f"FAILURE: Storage processing exception on attempt {attempt + 1}", exception=e, category="storage_operations")
                if attempt == max_attempts - 1:  # Last attempt
                    return {
                        "success": False,
                        "error": f"Failed to process storage description after {max_attempts} attempts: {str(e)}",
                        "description": original_description
                    }
                continue  # Retry on exception
        
        # Should never reach here, but just in case
        return {
            "success": False,
            "error": f"Storage processing failed after {max_attempts} attempts",
            "description": original_description
        }
            
    def suggest_storage_actions(self, character_name: str) -> List[str]:
        """Suggest possible storage actions based on current context"""
        
        try:
            context = self._get_game_context(character_name)
            suggestions = []
            
            # Suggest based on character inventory
            if context.get("character") and context["character"].get("equipment"):
                high_quantity_items = [
                    item for item in context["character"]["equipment"]
                    if item.get("quantity", 1) > 5
                ]
                
                if high_quantity_items:
                    item_name = high_quantity_items[0].get("item_name", "items")
                    suggestions.append(f"Store excess {item_name} in a chest")
                    
            # Suggest based on existing storage
            if context.get("existing_storage"):
                storage_name = context["existing_storage"][0].get("deviceName", "storage")
                suggestions.append(f"Retrieve items from {storage_name}")
                suggestions.append(f"Check what's in {storage_name}")
            else:
                suggestions.append("Create a chest to store valuable items")
                
            # Location-specific suggestions
            location_name = context.get("location", {}).get("name", "").lower()
            if "tavern" in location_name or "inn" in location_name:
                suggestions.append("Create a lockbox for secure storage")
            elif "home" in location_name or "base" in location_name:
                suggestions.append("Create a barrel for bulk storage")
                
            return suggestions[:3]  # Return top 3 suggestions
            
        except Exception as e:
            print(f"[WARNING] Could not generate storage suggestions: {e}")
            return [
                "Store items in a chest",
                "Retrieve items from storage", 
                "Check storage contents"
            ]

# Convenience functions for external use
def process_storage_request(description: str, character_name: str) -> Dict[str, Any]:
    """Process a storage request from natural language description"""
    processor = StorageProcessor()
    return processor.process_storage_description(description, character_name)

def get_storage_suggestions(character_name: str) -> List[str]:
    """Get storage action suggestions for a character"""
    processor = StorageProcessor()
    return processor.suggest_storage_actions(character_name)