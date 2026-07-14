# utils/npc_reconciler.py

import copy
import json
import os
import re
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_read_json, safe_write_json
from utils.module_context import ModuleContext
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T088", "utils/npc_reconciler.py", 101)


def build_npc_merge_confirmation_prompt(npc1_name: str, npc2_name: str) -> str:
    """Build T088's conservative, fail-closed identity decision prompt."""
    return f"""Decide whether these two fantasy NPC name labels refer to the same established person.

Answer true ONLY when the labels share a distinctive personal name and the difference is a compatible title, honorific, surname, epithet, or role. A short personal name and its clearly expanded form may match.

Answer false when either of these is true:
- Both labels are generic or anonymous descriptions without a shared proper name.
- Their age or identity descriptors conflict, such as "Old" versus "Young".
- They name different people or the evidence is ambiguous.

There is no context beyond the two labels. Do not invent an identity connection. When uncertain, answer false.

- NPC 1: "{npc1_name}"
- NPC 2: "{npc2_name}"

Respond with exactly one JSON object: {{"answer": true}} or {{"answer": false}}."""


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

    def load_context(self):
        """Loads the module context and builds a map of all aliases to their canonical name."""
        if not os.path.exists(self.context_path):
            print(f"ERROR: [NpcReconciler] Context file not found at {self.context_path}")
            return False
        
        self.context = ModuleContext.load(self.context_path)
        self._rebuild_canonical_map()

        print(f"DEBUG: [NpcReconciler] Built canonical map with {len(self.canonical_map)} entries.")
        return True

    def _rebuild_canonical_map(self):
        """Rebuild aliases from the current context without retaining stale entries."""
        self.canonical_map = {}
        if not self.context:
            return

        for npc_data in self.context.npcs.values():
            canonical_name = npc_data['name']
            # Map the canonical name to itself
            self.canonical_map[canonical_name] = canonical_name
            # Map all aliases to the canonical name
            for alias in npc_data.get('aliases', []):
                self.canonical_map[alias] = canonical_name

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

    def _ai_confirm_merge(self, npc1_name: str, npc2_name: str) -> bool:
        """Uses a cheap AI call to confirm if two NPCs are the same entity."""
        prompt = build_npc_merge_confirmation_prompt(npc1_name, npc2_name)
        try:
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                mini_cfg = config.MINI_UTIL_GPT54MINI_NONE
            elif MODEL_PROVIDER == "gemini":
                mini_cfg = config.MINI_UTIL_GEMINI_FLASH_LOW
            elif MODEL_PROVIDER == "lmstudio":
                mini_cfg = config.MINI_UTIL_LMSTUDIO
            else:  # legacy
                mini_cfg = config.MINI_UTIL_LEGACY

            response = capture_and_fanout("T088", api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=[{"role": "user", "content": prompt}],
                model=mini_cfg["model"],
                temperature=0.0,
                response_format=None,
                **{k: v for k, v in mini_cfg.items() if k != "model"})
            result = json.loads(response.choices[0].message.content)
            if (
                not isinstance(result, dict)
                or set(result) != {"answer"}
                or type(result["answer"]) is not bool
            ):
                raise ValueError(
                    "T088 response must be exactly a JSON object containing a boolean answer"
                )
            return result["answer"]
        except Exception as e:
            print(f"WARNING: [NpcReconciler] AI merge confirmation failed: {e}")
            return False

    @staticmethod
    def _rewrite_name_list(names, identity_map):
        """Replace merged identities in a name list and preserve stable order."""
        rewritten = []
        for name in names:
            replacement = identity_map.get(name, name)
            if replacement not in rewritten:
                rewritten.append(replacement)
        return rewritten

    def _rewrite_context_identity_references(self, identity_map):
        """Rewrite structured context references for identities merged by T088."""
        for area in self.context.areas.values():
            if isinstance(area.get("npcs"), list):
                area["npcs"] = self._rewrite_name_list(
                    area["npcs"], identity_map
                )

        for location in self.context.locations.values():
            if isinstance(location.get("npcs"), list):
                location["npcs"] = self._rewrite_name_list(
                    location["npcs"], identity_map
                )

        rewritten_references = {}
        for reference_key, sources in self.context.references.items():
            rewritten_key = reference_key
            if reference_key.startswith("npc:"):
                npc_name = reference_key[len("npc:"):]
                rewritten_key = f"npc:{identity_map.get(npc_name, npc_name)}"
            rewritten_references.setdefault(rewritten_key, set()).update(sources)
        self.context.references = rewritten_references

    def _find_and_merge_semantic_duplicates(self):
        """Merge confirmed duplicates in memory and return their identity map."""
        if not self.context or not self.context.npcs:
            return {}

        print("DEBUG: [NpcReconciler] Checking for semantic duplicates...")
        npc_list = list(self.context.npcs.values())
        merged_keys = set()
        identity_map = {}
        
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
                        npc2_aliases = npc2.get('aliases', [])
                        npc1.setdefault('aliases', []).append(npc2['name'])
                        npc1['aliases'].extend(npc2_aliases)
                        npc1['aliases'] = sorted(list(set(npc1['aliases']))) # Remove duplicates
                        
                        # Merge appearances
                        npc1.setdefault('appears_in', [])
                        for appearance in npc2.get('appears_in', []):
                            if appearance not in npc1['appears_in']:
                                npc1['appears_in'].append(appearance)
                        
                        # Mark npc2 for deletion
                        merged_keys.add(npc2['name'])
                        identity_map[npc2['name']] = npc1['name']
                        for alias in npc1['aliases']:
                            identity_map[alias] = npc1['name']
                        for alias in npc2_aliases:
                            identity_map[alias] = npc1['name']

        # Now, remove the merged NPCs from the context
        if merged_keys:
            self.context.npcs = {
                key: data for key, data in self.context.npcs.items() if data['name'] not in merged_keys
            }
            self._rewrite_context_identity_references(identity_map)
            print(f"DEBUG: [NpcReconciler] Merged {len(merged_keys)} duplicate NPC entries.")
        return identity_map

    def _stage_area_reconciliation(self, area_data):
        """Return a reconciled copy and whether it differs from its source."""
        staged_area = copy.deepcopy(area_data)
        modified = False

        for location in staged_area.get("locations", []):
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

        return staged_area, modified

    def _rollback_attempted_writes(self, snapshots, attempted_paths):
        """Best-effort restoration of every file touched by this transaction."""
        rollback_ok = True
        for path in reversed(attempted_paths):
            try:
                restored = safe_write_json(path, snapshots[path])
            except Exception as exc:
                restored = False
                print(f"ERROR: [NpcReconciler] Rollback raised for {path}: {exc}")
            if not restored:
                rollback_ok = False
                print(f"ERROR: [NpcReconciler] Failed to roll back {path}")
        return rollback_ok

    def reconcile_all_areas(self):
        """Reconcile context and area identities as one rollback-capable unit."""
        if not self.context:
            print("ERROR: [NpcReconciler] Context not loaded. Cannot reconcile.")
            return False

        original_context = copy.deepcopy(self.context)
        context_snapshot = safe_read_json(self.context_path)
        if context_snapshot is None:
            print("ERROR: [NpcReconciler] Cannot snapshot context for reconciliation.")
            return False

        snapshots = {}
        staged_writes = {}

        try:
            # Build every prospective change in memory before the first write.
            identity_map = self._find_and_merge_semantic_duplicates()
            self._rebuild_canonical_map()

            if identity_map:
                snapshots[self.context_path] = context_snapshot
                staged_writes[self.context_path] = self.context.to_dict()

            area_ids = self.path_manager.get_area_ids()
            print(f"DEBUG: [NpcReconciler] Reconciling NPCs for {len(area_ids)} areas...")

            for area_id in area_ids:
                area_path = self.path_manager.get_area_path(area_id)
                area_data = safe_read_json(area_path)

                if not area_data or "locations" not in area_data:
                    continue

                staged_area, modified = self._stage_area_reconciliation(area_data)
                if modified:
                    snapshots[area_path] = copy.deepcopy(area_data)
                    staged_writes[area_path] = staged_area
        except Exception as exc:
            self.context = original_context
            self._rebuild_canonical_map()
            print(f"ERROR: [NpcReconciler] Failed to stage reconciliation: {exc}")
            return False

        attempted_paths = []
        for path, payload in staged_writes.items():
            attempted_paths.append(path)
            try:
                written = safe_write_json(path, payload)
            except Exception as exc:
                written = False
                print(f"ERROR: [NpcReconciler] Write raised for {path}: {exc}")

            if not written:
                print(f"ERROR: [NpcReconciler] Transaction write failed for {path}")
                self._rollback_attempted_writes(snapshots, attempted_paths)
                self.context = original_context
                self._rebuild_canonical_map()
                return False

            if path != self.context_path:
                print(f"  -> Reconciled NPC names in {os.path.basename(path)}")

        return True

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