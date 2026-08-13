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

import copy
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T049", "core/managers/storage_processor.py", 313)
import config
from core.ai import api_client
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.module_path_manager import ModulePathManager
import jsonschema
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("storage_processor")

MAX_STORAGE_CONTEXT_ROWS = 128
MAX_STORAGE_CONTEXT_BYTES = 32 * 1024


def _bounded_accessible_storage_context(
    storage_data: Dict[str, Any],
    current_location_id: str,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Return complete local container contents or fail closed on bounds."""
    containers = storage_data.get("playerStorage", [])
    if not isinstance(containers, list):
        return [], "player storage is malformed"
    selected = []
    row_count = 0
    for container in containers:
        if not isinstance(container, dict):
            return [], "player storage contains a malformed container"
        if container.get("locationId") != current_location_id:
            continue
        contents = container.get("contents", [])
        if not isinstance(contents, list) or not all(
            isinstance(item, dict) for item in contents
        ):
            return [], "a local storage container has malformed contents"
        currency = container.get("currency", {})
        if not isinstance(currency, dict) or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in currency.values()
        ):
            return [], "a local storage container has malformed currency"
        ammunition = container.get("ammunition", [])
        if not isinstance(ammunition, list) or not all(
            isinstance(row, dict) for row in ammunition
        ):
            return [], "a local storage container has malformed ammunition"
        projected = {
            "id": container.get("id"),
            "deviceName": container.get("deviceName"),
            "deviceType": container.get("deviceType"),
            "locationId": container.get("locationId"),
            "contents": copy.deepcopy(contents),
            "currency": {
                denomination: currency.get(denomination, 0)
                for denomination in ("gold", "silver", "copper")
            },
            "ammunition": copy.deepcopy(ammunition),
        }
        projected_rows = (
            1
            + len(contents)
            + len(ammunition)
            + sum(
                bool(currency.get(name, 0))
                for name in ("gold", "silver", "copper")
            )
        )
        candidate = selected + [projected]
        candidate_bytes = len(
            json.dumps(
                candidate,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )
        if (
            row_count + projected_rows > MAX_STORAGE_CONTEXT_ROWS
            or candidate_bytes > MAX_STORAGE_CONTEXT_BYTES
        ):
            return [], (
                "local storage contents exceed the safe model context bound; "
                "the game will not guess which container or item was intended"
            )
        row_count += projected_rows
        selected.append(projected)
    return selected, None


def build_accessible_storage_snapshot(
    party_tracker_path="party_tracker.json",
    storage_path="player_storage.json",
) -> Dict[str, Any]:
    """Build exact, read-only storage facts for the current location."""
    party = safe_json_load(party_tracker_path)
    if not isinstance(party, dict):
        return {"available": False, "containers": []}
    location_id = (party.get("worldConditions") or {}).get(
        "currentLocationId"
    )
    if not isinstance(location_id, str) or not location_id.strip():
        return {"available": False, "containers": []}
    if not os.path.exists(storage_path):
        return {
            "available": True,
            "currentLocationId": location_id,
            "containers": [],
        }
    storage = safe_json_load(storage_path)
    if not isinstance(storage, dict):
        return {"available": False, "containers": []}
    containers, context_error = _bounded_accessible_storage_context(
        storage,
        location_id,
    )
    if context_error:
        return {"available": False, "containers": []}
    return {
        "available": True,
        "currentLocationId": location_id,
        "containers": containers,
    }

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

    def _bounded_storage_context(
        self,
        storage_data: Dict[str, Any],
        current_location_id: str,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Return complete local container contents or fail closed on bounds."""
        return _bounded_accessible_storage_context(
            storage_data,
            current_location_id,
        )
        
    def _get_game_context(self, character_name: str) -> Dict[str, Any]:
        """Get current game context for processing"""
        context = {
            "character": None,
            "party": None,
            "location": None,
            "existing_storage": [],
            "storage_context_error": None,
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
                if not isinstance(storage_data, dict):
                    context["storage_context_error"] = "player storage is unavailable"
                else:
                    (
                        context["existing_storage"],
                        context["storage_context_error"],
                    ) = self._bounded_storage_context(
                        storage_data,
                        current_location_id,
                    )
                
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
        character_currency = copy.deepcopy(
            context.get("character", {}).get("currency") or {}
        )
        character_ammunition = copy.deepcopy(
            context.get("character", {}).get("ammunition") or []
        )
                
        # Format existing storage for context
        existing_storage_info = []
        for storage in context.get("existing_storage", []):
            existing_storage_info.append({
                "id": storage["id"],
                "name": storage["deviceName"],
                "type": storage["deviceType"],
                "location_id": storage["locationId"],
                "contents": copy.deepcopy(storage.get("contents", [])),
                "currency": copy.deepcopy(storage.get("currency", {})),
                "ammunition": copy.deepcopy(storage.get("ammunition", [])),
            })
            
        system_prompt = f"""You are a storage operations specialist for a 5th Edition RPG system. Your task is to convert natural language storage descriptions into valid JSON operations that match the provided schema.

CONTEXT INFORMATION:
Character: {context.get('character', {}).get('name', 'Unknown')}
Current Location: {context.get('location', {}).get('name', 'Unknown Location')} (ID: {context.get('location', {}).get('id', 'UNKNOWN')})
Current Area: {context.get('location', {}).get('area_name', 'Unknown Area')} (ID: {context.get('location', {}).get('area_id', 'UNKNOWN')})

CHARACTER INVENTORY (all items):
{json.dumps(character_inventory, indent=2)}

CHARACTER CURRENCY (exact denominations):
{json.dumps(character_currency, indent=2)}

CHARACTER AMMUNITION (use exact names):
{json.dumps(character_ammunition, indent=2)}

EXISTING STORAGE AT LOCATION:
{json.dumps(existing_storage_info, indent=2)}

STORAGE ACTION SCHEMA:
{json.dumps(schema, indent=2)}

INSTRUCTIONS:
1. Analyze the natural language description carefully
2. Export the player's COMPLETE storage intent in one JSON response
3. A single resource family may use one operation; mixed item/currency/ammunition intent MUST use an "operations" array containing every requested operation
4. If creating new storage, infer appropriate storage type and name
5. If referencing existing storage, use the storage_id from the context
6. Ensure all required fields are present according to the schema
7. Use the current location information provided in context
8. Validate item names against the character's inventory for store operations
9. For multiple items, use the "items" array format instead of single item_name/quantity
10. NEVER return action "error" - always use a valid action type from the enum
11. Currency uses store_currency/retrieve_currency with denomination and quantity; never represent coins as items
12. Ammunition uses store_ammunition/retrieve_ammunition with ammunition_name and quantity; never represent ammunition as an item
13. Every operation in one operations array must use the same character and storage container
14. Never omit part of a mixed request; the game commits the complete operations array atomically or commits none of it

OUTPUT REQUIREMENTS:
- Return ONLY valid JSON that matches the storage action schema
- Include all required fields for the detected action type
- For item actions, use EXACT item names from character inventory (never modify or assume item names)
- For ammunition actions, use the EXACT ammunition name from character or storage context
- For currency actions, use exactly gold, silver, or copper and never convert denominations
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

For "I store 5 gold in the chest":
{{
  "action": "store_currency",
  "character": "Norn",
  "storage_id": "storage_12345678",
  "denomination": "gold",
  "quantity": 5
}}

For "I retrieve 10 arrows from the chest":
{{
  "action": "retrieve_ammunition",
  "character": "Norn",
  "storage_id": "storage_12345678",
  "ammunition_name": "Arrows",
  "quantity": 10
}}

For "I put a torch, 2 gold, 3 silver, and 5 arrows in the chest":
{{
  "operations": [
    {{"action": "store_item", "character": "Norn", "storage_id": "storage_12345678", "item_name": "Torch", "quantity": 1}},
    {{"action": "store_currency", "character": "Norn", "storage_id": "storage_12345678", "denomination": "gold", "quantity": 2}},
    {{"action": "store_currency", "character": "Norn", "storage_id": "storage_12345678", "denomination": "silver", "quantity": 3}},
    {{"action": "store_ammunition", "character": "Norn", "storage_id": "storage_12345678", "ammunition_name": "Arrows", "quantity": 5}}
  ]
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

        if isinstance(operation.get("operations"), list):
            if not operation["operations"]:
                raise ValueError("the storage operation set is empty")
            processed = []
            for item in operation["operations"]:
                if not isinstance(item, dict):
                    raise ValueError("a storage operation is malformed")
                if item.get("action") == "view_storage":
                    raise ValueError(
                        "view_storage cannot be mixed with storage mutations"
                    )
                processed.append(self._post_process_operation(item, context))
            storage_ids = {
                item.get("storage_id")
                for item in processed
                if item.get("storage_id")
            }
            if len(storage_ids) > 1:
                raise ValueError(
                    "one storage request cannot target multiple containers"
                )
            return {"operations": processed}

        # The call-site character is authoritative; the model cannot redirect
        # a storage mutation to a different sheet.
        authoritative_character = context.get("character", {}).get("name")
        if not authoritative_character:
            raise ValueError("the requested character inventory is unavailable")
        operation["character"] = authoritative_character
            
        # Handle location information
        if operation.get("action") in [
            "create_storage",
            "store_item",
            "store_currency",
            "store_ammunition",
        ]:
            if not operation.get("location_id") and context.get("location"):
                operation["location_id"] = context["location"]["id"]
                
        # Handle existing storage references
        if operation.get("action") in [
            "retrieve_item",
            "retrieve_currency",
            "retrieve_ammunition",
            "view_storage",
            "store_item",
            "store_currency",
            "store_ammunition",
        ]:
            existing = context.get("existing_storage") or []
            existing_ids = {storage.get("id") for storage in existing}
            if operation.get("storage_id"):
                if operation["storage_id"] not in existing_ids:
                    raise ValueError("the selected storage container is not at this location")
            elif existing:
                requested_type = str(operation.get("storage_type") or "").strip().casefold()
                requested_name = str(operation.get("storage_name") or "").strip().casefold()
                matches = [
                    storage
                    for storage in existing
                    if (
                        requested_name
                        and str(storage.get("deviceName") or "").strip().casefold()
                        == requested_name
                    )
                    or (
                        requested_type
                        and str(storage.get("deviceType") or "").strip().casefold()
                        == requested_type
                    )
                ]
                if len(matches) == 1:
                    operation["storage_id"] = matches[0]["id"]
                elif len(matches) > 1 or len(existing) > 1:
                    raise ValueError(
                        "more than one storage container could match; use one exact "
                        "container id/name from the supplied contents"
                    )
                elif len(existing) == 1 and not requested_name and not requested_type:
                    operation["storage_id"] = existing[0]["id"]
                elif operation.get("action") not in {
                    "store_item",
                    "store_currency",
                    "store_ammunition",
                }:
                    raise ValueError("no exact local storage container was selected")
                    
        # Handle combined create/store operations (only if no existing storage found)
        if operation.get("action") in {
            "store_item",
            "store_currency",
            "store_ammunition",
        } and not operation.get("storage_id"):
            # This will trigger storage creation in storage_manager
            if not operation.get("storage_type"):
                operation["storage_type"] = "chest"  # Default storage type
                
        return operation
        
    def process_storage_description(
        self,
        description: str,
        character_name: str,
        required_deltas=(),
    ) -> Dict[str, Any]:
        """Process natural language storage description into validated operation with retry logic"""
        
        max_attempts = 3
        original_description = description
        
        for attempt in range(max_attempts):
            try:
                debug(f"AI_CALL: Storage processing attempt {attempt + 1} of {max_attempts}", category="storage_operations")
                
                # Get game context
                context = self._get_game_context(character_name)
                if context.get("storage_context_error"):
                    return {
                        "success": False,
                        "error": context["storage_context_error"],
                        "failure_code": "storage_context_ambiguous",
                    }
                
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
                    sp_cfg = config.STORAGE_PROCESSOR_T049_GEMINI_FLASHLITE_LOW
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
                    _request_provider=MODEL_PROVIDER,
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
                    if not isinstance(operation, dict):
                        raise ValueError("storage response must be a JSON object")
                    
                except (json.JSONDecodeError, ValueError) as e:
                    if attempt == max_attempts - 1:  # Last attempt
                        return {
                            "success": False,
                            "error": f"AI response was not valid JSON after {max_attempts} attempts: {e}",
                            "raw_response": ai_response
                        }
                    continue  # Retry on JSON parse error
                    
                # Post-process operation
                try:
                    operation = self._post_process_operation(operation, context)
                except ValueError as post_process_error:
                    if attempt == max_attempts - 1:
                        return {
                            "success": False,
                            "error": str(post_process_error),
                            "operation": operation,
                        }
                    description = (
                        f"{original_description}\n\nPREVIOUS ATTEMPT FAILED: "
                        f"{post_process_error}. Select one exact container from "
                        "EXISTING STORAGE AT LOCATION."
                    )
                    continue
                
                # Validate operation
                is_valid, validation_error = self._validate_operation(operation)
                if is_valid and required_deltas:
                    from core.managers.storage_transaction import (
                        _storage_operation_coverage_error,
                    )

                    validation_error = _storage_operation_coverage_error(
                        operation,
                        required_deltas,
                    )
                    is_valid = validation_error is None
                
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
                            description = (
                                f"{original_description}\n\nPREVIOUS ATTEMPT FAILED: "
                                f"{validation_error}. Please try again using the exact "
                                "item or ammunition name and exact coin denomination "
                                "shown in the supplied context."
                            )
                    
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
def process_storage_request(
    description: str,
    character_name: str,
    required_deltas=(),
) -> Dict[str, Any]:
    """Process a storage request from natural language description"""
    processor = StorageProcessor()
    return processor.process_storage_description(
        description,
        character_name,
        required_deltas=required_deltas,
    )

def get_storage_suggestions(character_name: str) -> List[str]:
    """Get storage action suggestions for a character"""
    processor = StorageProcessor()
    return processor.suggest_storage_actions(character_name)
