# utils/npc_reconciler.py

import json
import os
import re
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_read_json, safe_write_json
from utils.module_context import ModuleContext
from openai import OpenAI
from config import OPENAI_API_KEY, DM_MINI_MODEL
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T088", "utils/npc_reconciler.py", 68)

class NpcReconciler:
    """
    Ensures all NPC names in area files match their canonical names
    from the module context.
    """
    def __init__(self, module_name: str):
        self.path_manager = ModulePathManager(module_name)
        self.context_path = self.path_manager.get_context_path()
        self.context = None
        self.canonical_map = {}
        # --- ADD THIS LINE ---
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def load_context(self):
        """Loads the module context and builds a map of all aliases to their canonical name."""
        if not os.path.exists(self.context_path):
            print(f"ERROR: [NpcReconciler] Context file not found at {self.context_path}")
            return False
        
        self.context = ModuleContext.load(self.context_path)
        
        for npc_data in self.context.npcs.values():
            canonical_name = npc_data['name']
            # Map the canonical name to itself
            self.canonical_map[canonical_name] = canonical_name
            # Map all aliases to the canonical name
            for alias in npc_data.get('aliases', []):
                self.canonical_map[alias] = canonical_name
        
        print(f"DEBUG: [NpcReconciler] Built canonical map with {len(self.canonical_map)} entries.")
        return True

    def get_canonical_name(self, original_name: str) -> str:
        """Finds the canonical name for a given NPC name."""
        # First, try a direct match in our map
        if original_name in self.canonical_map:
            return self.canonical_map[original_name]
        
        # If not found, try matching the base name (without parentheses)
        base_name = re.sub(r'\s*\([^)]*\)\s*', '', original_name).strip()
        if base_name in self.canonical_map:
            return self.canonical_map[base_name]
            
        # If still not found, return the original name as a fallback
        print(f"WARNING: [NpcReconciler] Could not find canonical name for '{original_name}'. Using original.")
        return original_name

    # --- ADD THIS NEW METHOD ---
    def _ai_confirm_merge(self, npc1_name: str, npc2_name: str) -> bool:
        """Uses a cheap AI call to confirm if two NPCs are the same entity."""
        prompt = f"""Are these two fantasy characters likely the same person, just described differently?
- NPC 1: "{npc1_name}"
- NPC 2: "{npc2_name}"

Answer with only the word "true" or "false"."""
        try:
            response = capture_and_fanout("T088", self.client.chat.completions.create, messages=[{"role": "user", "content": prompt}], model=DM_MINI_MODEL,
                max_tokens=1,
                temperature=0.0
            )
            answer = response.choices[0].message.content.lower().strip()
            return answer == "true"
        except Exception as e:
            print(f"WARNING: [NpcReconciler] AI merge confirmation failed: {e}")
            return False # Default to not merging if AI fails

    # --- ADD THIS NEW METHOD ---
    def _find_and_merge_semantic_duplicates(self):
        """Finds potential duplicates and uses AI to confirm and merge them in the context."""
        if not self.context or not self.context.npcs:
            return

        print("DEBUG: [NpcReconciler] Checking for semantic duplicates...")
        npc_list = list(self.context.npcs.values())
        merged_keys = set()
        
        for i in range(len(npc_list)):
            for j in range(i + 1, len(npc_list)):
                npc1 = npc_list[i]
                npc2 = npc_list[j]

                # Skip if either has already been merged
                if npc1['name'] in merged_keys or npc2['name'] in merged_keys:
                    continue

                # Simple check: if one name is a substring of the other (e.g., "Elara" in "Old Elara")
                # This is a good heuristic to find potential matches
                if npc1['name'].lower() in npc2['name'].lower() or npc2['name'].lower() in npc1['name'].lower():
                    if self._ai_confirm_merge(npc1['name'], npc2['name']):
                        # AI confirmed they are the same. Merge npc2 into npc1.
                        print(f"  -> AI confirmed merge: '{npc2['name']}' into '{npc1['name']}'")
                        
                        # Add npc2's original name and aliases to npc1's aliases
                        npc1.setdefault('aliases', []).append(npc2['name'])
                        npc1['aliases'].extend(npc2.get('aliases', []))
                        npc1['aliases'] = sorted(list(set(npc1['aliases']))) # Remove duplicates
                        
                        # Merge appearances
                        for appearance in npc2.get('appears_in', []):
                            if appearance not in npc1['appears_in']:
                                npc1['appears_in'].append(appearance)
                        
                        # Mark npc2 for deletion
                        merged_keys.add(npc2['name'])

        # Now, remove the merged NPCs from the context
        if merged_keys:
            self.context.npcs = {
                key: data for key, data in self.context.npcs.items() if data['name'] not in merged_keys
            }
            print(f"DEBUG: [NpcReconciler] Merged {len(merged_keys)} duplicate NPC entries.")
            # Re-save the context file with the merged data
            self.context.save(self.context_path)

    def reconcile_all_areas(self):
        """Iterates through all area files and reconciles NPC names."""
        if not self.context:
            print("ERROR: [NpcReconciler] Context not loaded. Cannot reconcile.")
            return

        # --- ADD THIS CALL ---
        # First, perform semantic merging on the context object itself
        self._find_and_merge_semantic_duplicates()
        
        # Second, rebuild the canonical map with the newly merged data
        self.load_context() # This reloads the saved context and rebuilds the map

        area_ids = self.path_manager.get_area_ids()
        print(f"DEBUG: [NpcReconciler] Reconciling NPCs for {len(area_ids)} areas...")

        for area_id in area_ids:
            area_path = self.path_manager.get_area_path(area_id)
            area_data = safe_read_json(area_path)
            
            if not area_data or "locations" not in area_data:
                continue

            modified = False
            for location in area_data.get("locations", []):
                reconciled_npcs = []
                for npc_entry in location.get("npcs", []):
                    original_name = npc_entry.get("name")
                    if original_name:
                        canonical_name = self.get_canonical_name(original_name)
                        if original_name != canonical_name:
                            npc_entry["name"] = canonical_name
                            modified = True
                    reconciled_npcs.append(npc_entry)
                location["npcs"] = reconciled_npcs

            if modified:
                safe_write_json(area_data, area_path)
                print(f"  -> Reconciled NPC names in {area_id}.json")

def main():
    """For testing the reconciler directly."""
    module_name = input("Enter the module name to reconcile (e.g., Cult_Test_1): ").strip()
    if not module_name:
        print("Module name is required.")
        return

    reconciler = NpcReconciler(module_name)
    if reconciler.load_context():
        reconciler.reconcile_all_areas()
        print("Reconciliation complete.")

if __name__ == "__main__":
    main()