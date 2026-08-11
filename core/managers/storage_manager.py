# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Storage Manager
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# STORAGE_MANAGER.PY - PLAYER STORAGE SYSTEM WITH ATOMIC FILE PROTECTION
# ============================================================================
# 
# ARCHITECTURE ROLE: Player Storage Management Layer
# 
# This module implements a safe, atomic player storage system that allows
# players to create and manage storage containers at specific locations.
# All operations use backup/restore patterns to ensure data integrity.
# 
# KEY RESPONSIBILITIES:
# - Manage player-created storage containers
# - Execute atomic inventory transfers between characters and storage
# - Provide backup/restore functionality for all file operations
# - Validate all operations against schemas
# - Maintain storage persistence across sessions and modules
# 
# SAFETY FEATURES:
# - Atomic file operations with automatic rollback
# - Character file backup before inventory modifications
# - Storage file backup before any changes
# - Schema validation for all data structures
# - Full operation rollback on any failure
# 
# STORAGE DESIGN:
# - Central player_storage.json repository
# - Location-tied storage containers
# - Player-initiated storage creation only
# - Party-accessible storage by default
# ============================================================================

import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import jsonschema
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_read_json, safe_write_json
from core.validation.character_validator import AICharacterValidator
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name(__name__)

class StorageManager:
    """Manages player storage with atomic file protection"""
    
    def __init__(self):
        """Initialize storage manager"""
        debug("INITIALIZATION: Starting StorageManager", category="storage_operations")
        self.storage_file = "player_storage.json"
        self.schema_file = "schemas/storage_action_schema.json"
        # Get current module from party tracker for consistent path resolution
        try:
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            self.path_manager = ModulePathManager(current_module)
            debug(f"INITIALIZATION: Module path manager initialized for module: {current_module}", category="storage_operations")
        except Exception as e:
            warning(f"INITIALIZATION: Could not load party tracker, using default", category="storage_operations")
            self.path_manager = ModulePathManager()  # Fallback to reading from file
        self.character_validator = AICharacterValidator()
        
    def _ensure_storage_file_exists(self):
        """Report existence; creation is owned by the transaction adapter."""
        return os.path.exists(self.storage_file)
            
    def _create_backup(self, file_path: str) -> str:
        """Create a timestamped backup of a file"""
        if not os.path.exists(file_path):
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = f"{file_path}.backup_{timestamp}"
        shutil.copy2(file_path, backup_path)
        return backup_path
        
    def _restore_backup(self, original_path: str, backup_path: str):
        """Restore a file from backup"""
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, original_path)
            os.remove(backup_path)
            
    def _cleanup_backup(self, backup_path: str):
        """Remove backup file after successful operation"""
        if backup_path and os.path.exists(backup_path):
            os.remove(backup_path)
            
    def _validate_storage_operation(self, operation: Dict[str, Any]) -> bool:
        """Validate storage operation against schema"""
        try:
            if os.path.exists(self.schema_file):
                schema = safe_json_load(self.schema_file)
                jsonschema.validate(operation, schema)
            return True
        except (jsonschema.ValidationError, Exception) as e:
            error(f"VALIDATION: Storage operation validation failed", exception=e, category="storage_operations")
            return False
            
    def _find_item_in_character(self, character_data: Dict[str, Any], item_name: str, quantity: int) -> Tuple[bool, int, Dict[str, Any]]:
        """Find and validate item in character inventory"""
        equipment = character_data.get("equipment", [])
        
        for item in equipment:
            if item.get("item_name") == item_name:
                available_quantity = item.get("quantity", 1)
                if available_quantity >= quantity:
                    return True, available_quantity, item
                else:
                    return False, available_quantity, item
                    
        return False, 0, None
        
    def _remove_item_from_character(self, character_data: Dict[str, Any], item_name: str, quantity: int) -> bool:
        """Remove item from character inventory"""
        equipment = character_data.get("equipment", [])
        
        for i, item in enumerate(equipment):
            if item.get("item_name") == item_name:
                current_quantity = item.get("quantity", 1)
                if current_quantity >= quantity:
                    if current_quantity == quantity:
                        # Remove item completely
                        equipment.pop(i)
                    else:
                        # Reduce quantity
                        item["quantity"] = current_quantity - quantity
                    return True
                    
        return False
        
    def _add_item_to_character(self, character_data: Dict[str, Any], item_data: Dict[str, Any], quantity: int):
        """Add item to character inventory"""
        equipment = character_data.get("equipment", [])
        
        # Check if item already exists in inventory
        for item in equipment:
            if item.get("item_name") == item_data["item_name"]:
                item["quantity"] = item.get("quantity", 1) + quantity
                return
                
        # Add new item to inventory
        new_item = item_data.copy()
        new_item["quantity"] = quantity
        equipment.append(new_item)
        
    def _find_storage_at_location(self, location_id: str) -> List[Dict[str, Any]]:
        """Find all storage containers at a specific location"""
        storage_data = safe_read_json(self.storage_file)
        if not storage_data:
            return []
        return [
            storage for storage in storage_data.get("playerStorage", [])
            if storage.get("locationId") == location_id
        ]
        
    def _get_location_info(self, location_description: str) -> Tuple[str, str, str, str]:
        """Get location information from description"""
        # This is a simplified implementation
        # In practice, this would use AI or lookup tables to map descriptions to IDs
        
        # For now, get current location from party tracker
        try:
            party_data = safe_json_load("party_tracker.json")
            current_location_id = party_data.get("worldConditions", {}).get("currentLocationId", "UNKNOWN")
            current_location_name = party_data.get("worldConditions", {}).get("currentLocation", "Unknown Location")
            current_area_id = party_data.get("worldConditions", {}).get("currentAreaId", "UNKNOWN")
            current_area_name = party_data.get("worldConditions", {}).get("currentArea", "Unknown Area")
            
            return current_location_id, current_location_name, current_area_id, current_area_name
        except:
            return "UNKNOWN", "Unknown Location", "UNKNOWN", "Unknown Area"
            
    def create_storage(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new storage container"""
        from core.managers.storage_transaction import execute_item_storage_operation

        return execute_item_storage_operation(operation)

        # Legacy implementation retained below for source-history reference;
        # every callable entry now returns through the coordinator above.
        debug(f"STATE_CHANGE: Creating storage for character '{operation.get('character')}'", category="storage_operations")
        
        if not self._validate_storage_operation(operation):
            return {"success": False, "error": "Invalid storage operation"}
            
        storage_backup = None
        
        try:
            # Create backup of storage file
            storage_backup = self._create_backup(self.storage_file)
            if storage_backup:
                debug(f"FILE_OP: Created backup: {storage_backup}", category="file_operations")
            
            # Load current storage data
            storage_data = safe_read_json(self.storage_file)
            if not storage_data:
                storage_data = {"playerStorage": []}
            
            # Get location information
            location_id, location_name, area_id, area_name = self._get_location_info(
                operation.get("location_description", "")
            )
            
            # Generate unique storage ID
            storage_id = f"storage_{uuid.uuid4().hex[:8]}"
            
            # Create storage entry
            new_storage = {
                "id": storage_id,
                "deviceType": operation["storage_type"],
                "deviceName": operation.get("storage_name", f"{operation['storage_type'].title()} at {location_name}"),
                "locationId": location_id,
                "locationName": location_name,
                "areaId": area_id,
                "areaName": area_name,
                "contents": [],
                "createdBy": operation["character"],
                "createdDate": datetime.now().isoformat(),
                "accessibility": "party",
                "lastAccessed": datetime.now().isoformat(),
                "accessLog": [
                    {
                        "character": operation["character"],
                        "action": "create",
                        "timestamp": datetime.now().isoformat()
                    }
                ]
            }
            
            # Add to storage data
            storage_data["playerStorage"].append(new_storage)
            storage_data["lastUpdated"] = datetime.now().isoformat()
            
            # Save updated storage data
            if not safe_write_json(self.storage_file, storage_data):
                raise Exception("Failed to save storage data")
            
            # Clean up backup
            self._cleanup_backup(storage_backup)
            
            info(f"SUCCESS: Created {operation['storage_type']} '{new_storage['deviceName']}' with ID {storage_id}", category="storage_operations")
            
            return {
                "success": True,
                "storage_id": storage_id,
                "message": f"Created {operation['storage_type']} at {location_name}"
            }
            
        except Exception as e:
            # Restore backup on failure
            if storage_backup:
                self._restore_backup(self.storage_file, storage_backup)
                warning(f"FAILURE: Storage creation failed, restored backup", category="storage_operations")
                
            error(f"FAILURE: Failed to create storage - {str(e)}", category="storage_operations")
            return {"success": False, "error": f"Failed to create storage: {str(e)}"}
            
    def store_item(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Store an item in a storage container"""
        from core.managers.storage_transaction import execute_item_storage_operation

        return execute_item_storage_operation(operation)

        # Legacy implementation retained below for source-history reference;
        # every callable entry now returns through the coordinator above.
        item_desc = operation.get("item_name", "multiple items") if "item_name" in operation else "multiple items"
        debug(f"STATE_CHANGE: Character '{operation.get('character')}' storing {item_desc}", category="storage_operations")
        
        if not self._validate_storage_operation(operation):
            return {"success": False, "error": "Invalid storage operation"}
            
        character_backup = None
        storage_backup = None
        
        try:
            # Get character file path
            character_file = self.path_manager.get_character_path(operation["character"])
            debug(f"FILE_OP: Loading character from {character_file}", category="file_operations")
            
            # Create backups
            character_backup = self._create_backup(character_file)
            storage_backup = self._create_backup(self.storage_file)
            
            # Load character data
            character_data = safe_read_json(character_file)
            if not character_data:
                raise Exception(f"Could not load character data for {operation['character']}")
            
            # Handle both single item and multi-item operations
            items_to_store = []
            if "items" in operation:
                # Multi-item operation
                for item_info in operation["items"]:
                    has_item, available_quantity, item_data = self._find_item_in_character(
                        character_data, item_info["item_name"], item_info["quantity"]
                    )
                    if not has_item:
                        raise Exception(f"Character does not have {item_info['item_name']}")
                    if available_quantity < item_info["quantity"]:
                        raise Exception(f"Character only has {available_quantity} {item_info['item_name']}, requested {item_info['quantity']}")
                    items_to_store.append((item_info["item_name"], item_info["quantity"], item_data))
            else:
                # Single item operation
                has_item, available_quantity, item_data = self._find_item_in_character(
                    character_data, operation["item_name"], operation["quantity"]
                )
                if not has_item:
                    raise Exception(f"Character does not have {operation['item_name']}")
                if available_quantity < operation["quantity"]:
                    raise Exception(f"Character only has {available_quantity} {operation['item_name']}, requested {operation['quantity']}")
                items_to_store.append((operation["item_name"], operation["quantity"], item_data))
                
            # Get or create storage
            storage_id = operation.get("storage_id")
            if not storage_id:
                # Create new storage first
                create_operation = {
                    "action": "create_storage",
                    "character": operation["character"],
                    "storage_type": operation.get("storage_type", "chest"),
                    "storage_name": operation.get("storage_name"),
                    "location_description": operation.get("location_description", "")
                }
                create_result = self.create_storage(create_operation)
                if not create_result["success"]:
                    raise Exception(f"Failed to create storage: {create_result['error']}")
                storage_id = create_result["storage_id"]
                
            # Load storage data
            storage_data = safe_read_json(self.storage_file)
            if not storage_data:
                storage_data = {"playerStorage": []}
            
            # Find the storage container
            storage_container = None
            for storage in storage_data["playerStorage"]:
                if storage["id"] == storage_id:
                    storage_container = storage
                    break
                    
            if not storage_container:
                raise Exception(f"Storage container {storage_id} not found")
                
            # Process all items for storage
            storage_contents = storage_container["contents"]
            stored_item_names = []
            
            for item_name, quantity, item_data in items_to_store:
                # Remove item from character
                if not self._remove_item_from_character(character_data, item_name, quantity):
                    raise Exception(f"Failed to remove {item_name} from character")
                
                # Add item to storage
                # Check if item already exists in storage
                item_found = False
                for stored_item in storage_contents:
                    if stored_item["item_name"] == item_name:
                        stored_item["quantity"] = stored_item.get("quantity", 1) + quantity
                        item_found = True
                        break
                        
                if not item_found:
                    # Add new item to storage - preserve ALL metadata from character equipment
                    stored_item = item_data.copy()  # Copy complete item object
                    stored_item["quantity"] = quantity  # Override quantity
                    # Set equipped to False when storing (items in storage are not equipped)
                    stored_item["equipped"] = False
                    storage_contents.append(stored_item)
                
                stored_item_names.append(f"{quantity} {item_name}")
                
            # Update access log
            storage_container["lastAccessed"] = datetime.now().isoformat()
            if "items" in operation:
                # Multi-item log entry
                storage_container["accessLog"].append({
                    "character": operation["character"],
                    "action": "store_items",
                    "items": [{"item": name, "quantity": qty} for name, qty, _ in items_to_store],
                    "timestamp": datetime.now().isoformat()
                })
            else:
                # Single item log entry
                storage_container["accessLog"].append({
                    "character": operation["character"],
                    "action": "store_item",
                    "item": operation["item_name"],
                    "quantity": operation["quantity"],
                    "timestamp": datetime.now().isoformat()
                })
            
            # Save updated character data
            if not safe_write_json(character_file, character_data):
                raise Exception("Failed to save character data")
            
            # Validate and save character data with AI validation
            validated_character_data, validation_success = self.character_validator.validate_character_file_safe(character_file)
            if not validation_success:
                raise Exception("Character validation failed after store operation")
            
            # Save updated storage data
            if not safe_write_json(self.storage_file, storage_data):
                raise Exception("Failed to save storage data")
            
            # Clean up backups
            self._cleanup_backup(character_backup)
            self._cleanup_backup(storage_backup)
            
            # Create success message
            if "items" in operation:
                message = f"Stored {', '.join(stored_item_names)} in {storage_container['deviceName']}"
            else:
                message = f"Stored {operation['quantity']} {operation['item_name']} in {storage_container['deviceName']}"
            
            info(f"SUCCESS: {message}", category="storage_operations")
            
            return {
                "success": True,
                "message": message
            }
            
        except Exception as e:
            # Restore backups on failure
            if character_backup:
                self._restore_backup(character_file, character_backup)
            if storage_backup:
                self._restore_backup(self.storage_file, storage_backup)
            
            error(f"FAILURE: Failed to store item - {str(e)}", category="storage_operations")    
            return {"success": False, "error": f"Failed to store item: {str(e)}"}
            
    def retrieve_item(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve an item from a storage container"""
        from core.managers.storage_transaction import execute_item_storage_operation

        return execute_item_storage_operation(operation)

        # Legacy implementation retained below for source-history reference;
        # every callable entry now returns through the coordinator above.
        item_desc = operation.get("item_name", "multiple items") if "item_name" in operation else "multiple items"
        debug(f"STATE_CHANGE: Character '{operation.get('character')}' retrieving {item_desc}", category="storage_operations")
        
        if not self._validate_storage_operation(operation):
            return {"success": False, "error": "Invalid storage operation"}
            
        character_backup = None
        storage_backup = None
        
        try:
            # Get character file path
            character_file = self.path_manager.get_character_path(operation["character"])
            
            # Create backups
            character_backup = self._create_backup(character_file)
            storage_backup = self._create_backup(self.storage_file)
            
            # Load data
            character_data = safe_read_json(character_file)
            if not character_data:
                raise Exception(f"Could not load character data for {operation['character']}")
            storage_data = safe_read_json(self.storage_file)
            if not storage_data:
                storage_data = {"playerStorage": []}
            
            # Find storage container
            storage_container = None
            for storage in storage_data["playerStorage"]:
                if storage["id"] == operation["storage_id"]:
                    storage_container = storage
                    break
                    
            if not storage_container:
                raise Exception(f"Storage container {operation['storage_id']} not found")
                
            # Handle both single item and multi-item operations
            items_to_retrieve = []
            if "items" in operation:
                # Multi-item operation
                for item_info in operation["items"]:
                    # Find item in storage and validate availability
                    stored_item = None
                    for item in storage_container["contents"]:
                        if item["item_name"] == item_info["item_name"]:
                            stored_item = item
                            break
                            
                    if not stored_item:
                        raise Exception(f"{item_info['item_name']} not found in storage")
                        
                    available_quantity = stored_item.get("quantity", 1)
                    if available_quantity < item_info["quantity"]:
                        raise Exception(f"Storage only has {available_quantity} {item_info['item_name']}, requested {item_info['quantity']}")
                        
                    items_to_retrieve.append((item_info["item_name"], item_info["quantity"], stored_item))
            else:
                # Single item operation
                stored_item = None
                for item in storage_container["contents"]:
                    if item["item_name"] == operation["item_name"]:
                        stored_item = item
                        break
                        
                if not stored_item:
                    raise Exception(f"{operation['item_name']} not found in storage")
                    
                available_quantity = stored_item.get("quantity", 1)
                if available_quantity < operation["quantity"]:
                    raise Exception(f"Storage only has {available_quantity} {operation['item_name']}, requested {operation['quantity']}")
                    
                items_to_retrieve.append((operation["item_name"], operation["quantity"], stored_item))
            
            # Process all items for retrieval
            retrieved_item_names = []
            
            for item_name, quantity, stored_item in items_to_retrieve:
                # Remove item from storage
                available_quantity = stored_item.get("quantity", 1)
                if available_quantity == quantity:
                    storage_container["contents"].remove(stored_item)
                else:
                    stored_item["quantity"] = available_quantity - quantity
                    
                # Add item to character
                self._add_item_to_character(character_data, stored_item, quantity)
                
                retrieved_item_names.append(f"{quantity} {item_name}")
            
            # Update access log
            storage_container["lastAccessed"] = datetime.now().isoformat()
            if "items" in operation:
                # Multi-item log entry
                storage_container["accessLog"].append({
                    "character": operation["character"],
                    "action": "retrieve_items",
                    "items": [{"item": name, "quantity": qty} for name, qty, _ in items_to_retrieve],
                    "timestamp": datetime.now().isoformat()
                })
            else:
                # Single item log entry
                storage_container["accessLog"].append({
                    "character": operation["character"],
                    "action": "retrieve_item",
                    "item": operation["item_name"],
                    "quantity": operation["quantity"],
                    "timestamp": datetime.now().isoformat()
                })
            
            # Save updated character data
            if not safe_write_json(character_file, character_data):
                raise Exception("Failed to save character data")
            
            # Validate and save character data with AI validation
            validated_character_data, validation_success = self.character_validator.validate_character_file_safe(character_file)
            if not validation_success:
                raise Exception("Character validation failed after retrieve operation")
            
            # Save updated storage data
            if not safe_write_json(self.storage_file, storage_data):
                raise Exception("Failed to save storage data")
            
            # Clean up backups
            self._cleanup_backup(character_backup)
            self._cleanup_backup(storage_backup)
            
            # Generate success message
            if "items" in operation:
                message = f"Retrieved {', '.join(retrieved_item_names)} from {storage_container['deviceName']}"
            else:
                message = f"Retrieved {operation['quantity']} {operation['item_name']} from {storage_container['deviceName']}"
            
            info(f"SUCCESS: {message}", category="storage_operations")
            
            return {
                "success": True,
                "message": message
            }
            
        except Exception as e:
            # Restore backups on failure
            if character_backup:
                self._restore_backup(character_file, character_backup)
            if storage_backup:
                self._restore_backup(self.storage_file, storage_backup)
            
            error(f"FAILURE: Failed to retrieve item - {str(e)}", category="storage_operations")
            return {"success": False, "error": f"Failed to retrieve item: {str(e)}"}
            
    def view_storage(self, location_id: str = None) -> Dict[str, Any]:
        """View storage containers at a location"""
        try:
            storage_data = safe_read_json(self.storage_file)
            if not storage_data:
                storage_data = {"playerStorage": []}
            
            if location_id:
                # Get storage at specific location
                location_storage = self._find_storage_at_location(location_id)
            else:
                # Get all storage
                location_storage = storage_data.get("playerStorage", [])
                
            storage_info = []
            for storage in location_storage:
                storage_info.append({
                    "id": storage["id"],
                    "name": storage["deviceName"],
                    "type": storage["deviceType"],
                    "location": storage["locationName"],
                    "contents": storage["contents"],
                    "currency": storage.get(
                        "currency", {"gold": 0, "silver": 0, "copper": 0}
                    ),
                    "ammunition": storage.get("ammunition", []),
                    "created_by": storage["createdBy"],
                    "last_accessed": storage["lastAccessed"]
                })
                
            return {
                "success": True,
                "storage": storage_info,
                "count": len(storage_info)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to view storage: {str(e)}"}
            
    def get_storage_at_location(self, location_id: str) -> List[Dict[str, Any]]:
        """Get all storage containers at a specific location"""
        try:
            return self._find_storage_at_location(location_id)
        except:
            return []

# Convenience functions for external use
def get_storage_manager() -> StorageManager:
    """Get storage manager instance"""
    return StorageManager()

def execute_storage_operation(operation: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a storage operation"""
    action = operation.get("action")

    if action in {
        "create_storage",
        "store_item",
        "retrieve_item",
        "store_currency",
        "retrieve_currency",
        "store_ammunition",
        "retrieve_ammunition",
    }:
        # T049/T053 preparation and both participant images are completed
        # before the shared coordinator acquires character -> storage leases.
        # This also makes create+first-store one transaction instead of a
        # nested storage commit followed by a character commit.
        from core.managers.storage_transaction import (
            execute_item_storage_operation,
        )

        return execute_item_storage_operation(operation)
    elif action == "view_storage":
        manager = get_storage_manager()
        location_id = operation.get("location_id")
        return manager.view_storage(location_id)
    else:
        return {"success": False, "error": f"Unknown storage action: {action}"}
