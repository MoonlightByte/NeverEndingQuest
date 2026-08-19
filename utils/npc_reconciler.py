# utils/npc_reconciler.py

import copy
import hashlib
import json
import os
import re
import shutil
import stat
from uuid import uuid4
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_read_json
from utils.module_context import ModuleContext
from utils.path_transaction_lock import (
    path_transaction_lock,
    path_transaction_lock_owned,
)
from utils.module_refresh_lock import (
    module_refresh_lock,
    module_refresh_lock_owned,
)
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T088", "utils/npc_reconciler.py", 184)


_T088_TRANSACTION_VERSION = 1
_T088_SOURCE_RETRY_LIMIT = 3


class _T088SourceDriftError(RuntimeError):
    """T088's exact module inputs changed while its model call was in flight."""


def _stable_path_identity(metadata):
    return (
        int(metadata.st_dev),
        int(metadata.st_ino),
        stat.S_IFMT(metadata.st_mode),
    )


def _capture_contained_json(module_dir, path):
    canonical_module = os.path.abspath(os.path.normpath(os.fspath(module_dir)))
    canonical_path = os.path.abspath(os.path.normpath(os.fspath(path)))
    module_metadata = os.lstat(canonical_module)
    if stat.S_ISLNK(module_metadata.st_mode) or not stat.S_ISDIR(
        module_metadata.st_mode
    ):
        raise _T088SourceDriftError("Module target is not an ordinary directory")
    module_real = os.path.realpath(canonical_module)
    module_identity = _stable_path_identity(module_metadata)
    target_real = os.path.realpath(canonical_path)
    try:
        contained = os.path.commonpath([module_real, target_real]) == module_real
    except ValueError:
        contained = False
    if not contained:
        raise _T088SourceDriftError("T088 input is outside its module directory")

    flags = os.O_RDONLY
    # Issue #134 class: O_BINARY keeps Windows CRT text mode from collapsing
    # CRLF and truncating at 0x1A, so the T088 snapshot is the file's PHYSICAL
    # bytes (matching every other byte-exact reader). POSIX: attr absent -> no-op.
    flags |= getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(canonical_path, flags)
    try:
        file_metadata = os.fstat(descriptor)
        if not stat.S_ISREG(file_metadata.st_mode):
            raise _T088SourceDriftError("T088 input is not a regular file")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    file_identity = _stable_path_identity(file_metadata)
    if (
        _stable_path_identity(os.lstat(canonical_module)) != module_identity
        or os.path.realpath(canonical_module) != module_real
        or _stable_path_identity(os.lstat(canonical_path)) != file_identity
        or os.path.realpath(canonical_path) != target_real
    ):
        raise _T088SourceDriftError("T088 input changed during snapshot")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise _T088SourceDriftError("T088 input is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise _T088SourceDriftError("T088 input is not a JSON object")
    return {
        "path": canonical_path,
        "real": target_real,
        "identity": file_identity,
        "digest": hashlib.sha256(raw).hexdigest(),
        "payload": payload,
        "module_path": canonical_module,
        "module_real": module_real,
        "module_identity": module_identity,
    }


def _durable_copy(source, destination):
    """Atomically preserve a byte-for-byte backup without writer sentinels."""
    canonical_source = os.path.abspath(os.path.normpath(os.fspath(source)))
    canonical_destination = os.path.abspath(
        os.path.normpath(os.fspath(destination))
    )
    parent = os.path.dirname(canonical_destination)
    temp_path = (
        f"{canonical_destination}.{os.getpid()}.{uuid4().hex}.tmp"
    )
    try:
        with open(canonical_source, "rb") as source_handle, open(
            temp_path, "wb"
        ) as destination_handle:
            shutil.copyfileobj(source_handle, destination_handle)
            destination_handle.flush()
            os.fsync(destination_handle.fileno())
        shutil.copystat(canonical_source, temp_path)
        with open(temp_path, "rb") as destination_handle:
            os.fsync(destination_handle.fileno())
        os.replace(temp_path, canonical_destination)
        _fsync_parent(parent)
    finally:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass


def _durable_write_json(path, payload, *, create_backup=False):
    """Atomically persist JSON and its directory without sentinel locks."""
    canonical = os.path.abspath(os.path.normpath(os.fspath(path)))
    parent = os.path.dirname(canonical)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if create_backup and os.path.exists(canonical):
        _durable_copy(canonical, f"{canonical}.bak")
    temp_path = f"{canonical}.{os.getpid()}.{uuid4().hex}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, canonical)
        _fsync_parent(parent)
    finally:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass


def _durable_remove(path):
    """Remove a transaction marker durably when the platform supports it."""
    canonical = os.path.abspath(os.path.normpath(os.fspath(path)))
    try:
        os.remove(canonical)
    except FileNotFoundError:
        return
    _fsync_parent(os.path.dirname(canonical))


def _fsync_parent(parent):
    if not parent or not hasattr(os, "O_DIRECTORY"):
        return
    try:
        directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        # Windows and some filesystems do not permit directory fsync.
        pass


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

    def _install_context_snapshot(self, payload):
        """Install the exact already-captured context without reopening it.

        Loading the context and then independently hashing the path leaves a
        race where those two operations can observe different documents.  T088
        stages exclusively from the bytes represented by its source digest.
        """
        if not isinstance(payload, dict):
            raise _T088SourceDriftError("T088 context snapshot is not an object")
        context = ModuleContext()
        context.module_name = payload.get("module_name", "")
        context.module_id = payload.get("module_id", "")
        context.areas = copy.deepcopy(payload.get("areas", {}))
        context.npcs = copy.deepcopy(payload.get("npcs", {}))
        context.locations = copy.deepcopy(payload.get("locations", {}))
        context.plot_scopes = copy.deepcopy(payload.get("plot_scopes", {}))
        references = payload.get("references", {})
        if not isinstance(references, dict):
            raise _T088SourceDriftError("T088 context references are invalid")
        context.references = {
            key: set(copy.deepcopy(values))
            for key, values in references.items()
        }
        context.validation_issues = copy.deepcopy(
            payload.get("validation_issues", [])
        )
        self.context = context
        self._rebuild_canonical_map()
        print(
            "DEBUG: [NpcReconciler] Built canonical map with "
            f"{len(self.canonical_map)} entries."
        )

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

    def _capture_reconciliation_inputs(self):
        """Capture the complete T088 source set under module refresh."""
        canonical_context = os.path.abspath(
            os.path.normpath(os.fspath(self.context_path))
        )
        module_dir = os.path.dirname(canonical_context)
        context_source = _capture_contained_json(module_dir, canonical_context)
        area_ids = tuple(self.path_manager.get_area_ids())
        areas = []
        seen_paths = set()
        for area_id in area_ids:
            area_path = os.path.abspath(
                os.path.normpath(self.path_manager.get_area_path(area_id))
            )
            identity = os.path.normcase(area_path)
            if identity in seen_paths:
                raise _T088SourceDriftError(
                    "T088 area discovery returned a duplicate target"
                )
            seen_paths.add(identity)
            areas.append(
                (area_id, _capture_contained_json(module_dir, area_path))
            )
        return {
            "module_path": context_source["module_path"],
            "module_real": context_source["module_real"],
            "module_identity": context_source["module_identity"],
            "context": context_source,
            "area_ids": area_ids,
            "areas": tuple(areas),
        }

    @staticmethod
    def _source_file_matches(expected):
        try:
            current = _capture_contained_json(
                expected["module_path"], expected["path"]
            )
        except (OSError, _T088SourceDriftError):
            return False
        return all(
            current[field] == expected[field]
            for field in (
                "path",
                "real",
                "identity",
                "digest",
                "module_path",
                "module_real",
                "module_identity",
            )
        )

    def _reconciliation_inputs_match(self, snapshot):
        try:
            current_area_ids = tuple(self.path_manager.get_area_ids())
            current_paths = tuple(
                os.path.abspath(
                    os.path.normpath(self.path_manager.get_area_path(area_id))
                )
                for area_id in current_area_ids
            )
        except Exception:
            return False
        expected_paths = tuple(
            source["path"] for _area_id, source in snapshot["areas"]
        )
        if (
            current_area_ids != snapshot["area_ids"]
            or current_paths != expected_paths
        ):
            return False
        return self._source_file_matches(snapshot["context"]) and all(
            self._source_file_matches(source)
            for _area_id, source in snapshot["areas"]
        )

    def _stage_reconciliation_from_snapshot(self, snapshot):
        """Run semantic decisions in memory against one immutable snapshot."""
        original_context = copy.deepcopy(self.context)
        snapshots = {}
        staged_writes = {}
        try:
            identity_map = self._find_and_merge_semantic_duplicates()
            self._rebuild_canonical_map()

            context_path = snapshot["context"]["path"]
            if identity_map:
                snapshots[context_path] = copy.deepcopy(
                    snapshot["context"]["payload"]
                )
                staged_writes[context_path] = self.context.to_dict()

            print(
                "DEBUG: [NpcReconciler] Reconciling NPCs for "
                f"{len(snapshot['areas'])} areas..."
            )
            for _area_id, source in snapshot["areas"]:
                area_data = copy.deepcopy(source["payload"])
                if "locations" not in area_data:
                    continue
                staged_area, modified = self._stage_area_reconciliation(area_data)
                if modified:
                    snapshots[source["path"]] = copy.deepcopy(source["payload"])
                    staged_writes[source["path"]] = staged_area
        except Exception:
            self.context = original_context
            self._rebuild_canonical_map()
            raise
        return original_context, snapshots, staged_writes

    def _transaction_path(self):
        canonical_context = os.path.abspath(os.path.normpath(self.context_path))
        return f"{canonical_context}.t088.pending"

    @staticmethod
    def _snapshot_matches(path, existed, payload):
        current_exists = os.path.exists(path)
        if current_exists != existed:
            return False
        if not existed:
            return True
        current = safe_read_json(path)
        return isinstance(current, dict) and current == payload

    def _validate_transaction_record(self, record):
        if not isinstance(record, dict):
            raise OSError("T088 recovery marker must be a JSON object")
        if record.get("version") != _T088_TRANSACTION_VERSION:
            raise OSError("Unsupported T088 recovery marker version")
        if record.get("status") not in {"staged", "rollback_required"}:
            raise OSError("Invalid T088 recovery marker status")
        if not isinstance(record.get("transaction_id"), str) or not record[
            "transaction_id"
        ]:
            raise OSError("T088 recovery marker has no transaction id")

        expected_context = os.path.abspath(os.path.normpath(self.context_path))
        expected_context_identity = os.path.normcase(expected_context)
        recorded_context = record.get("context_path")
        if (
            not isinstance(recorded_context, str)
            or os.path.abspath(os.path.normpath(recorded_context))
            != recorded_context
            or os.path.normcase(recorded_context) != expected_context_identity
        ):
            raise OSError("T088 recovery marker targets another module context")

        targets = record.get("targets")
        if not isinstance(targets, list) or not targets:
            raise OSError("T088 recovery marker has no transaction targets")

        allowed_targets = {expected_context_identity}
        for area_id in self.path_manager.get_area_ids():
            area_path = os.path.abspath(
                os.path.normpath(self.path_manager.get_area_path(area_id))
            )
            allowed_targets.add(os.path.normcase(area_path))

        seen = set()
        for target in targets:
            if not isinstance(target, dict):
                raise OSError("T088 recovery target must be an object")
            path = target.get("path")
            if not isinstance(path, str) or not os.path.isabs(path):
                raise OSError("T088 recovery target path must be absolute")
            canonical = os.path.abspath(os.path.normpath(path))
            identity = os.path.normcase(canonical)
            if canonical != path or identity in seen:
                raise OSError("T088 recovery target path is invalid or duplicated")
            if identity not in allowed_targets:
                raise OSError("T088 recovery target is not a context or area file")
            if not isinstance(target.get("existed"), bool):
                raise OSError("T088 recovery target has no existence snapshot")
            if target["existed"] and not isinstance(target.get("before"), dict):
                raise OSError("T088 recovery target has an invalid before snapshot")
            if not isinstance(target.get("after"), dict):
                raise OSError("T088 recovery target has an invalid after snapshot")
            seen.add(identity)
        return targets

    def _load_transaction_record(self):
        transaction_path = self._transaction_path()
        if not os.path.exists(transaction_path):
            return None
        try:
            with open(transaction_path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise OSError(
                f"Could not read T088 recovery marker {transaction_path}"
            ) from exc
        self._validate_transaction_record(record)
        return record

    @staticmethod
    def _write_transaction_target(path, payload):
        _durable_write_json(path, payload, create_backup=True)

    @classmethod
    def _restore_transaction_target(cls, target, use_after):
        path = target["path"]
        existed = True if use_after else target["existed"]
        payload = target["after"] if use_after else target.get("before")
        if existed:
            cls._write_transaction_target(path, payload)
        else:
            _durable_remove(path)

    def _recover_pending_transaction(self):
        """Roll a durable T088 marker forward or back without clobbering drift."""
        record = self._load_transaction_record()
        if record is None:
            return None
        targets = record["targets"]
        use_after = record["status"] == "staged"

        # Validate the complete recovery set before the first recovery write.
        # A third state means an unrelated writer changed the file, and neither
        # roll-forward nor rollback is safe to apply automatically.
        for target in targets:
            matches_before = self._snapshot_matches(
                target["path"],
                target["existed"],
                target.get("before"),
            )
            matches_after = self._snapshot_matches(
                target["path"],
                True,
                target["after"],
            )
            if not (matches_before or matches_after):
                raise OSError(
                    "T088 recovery stopped because a transaction target "
                    f"changed independently: {target['path']}"
                )

        for target in targets:
            expected_exists = True if use_after else target["existed"]
            expected_payload = (
                target["after"] if use_after else target.get("before")
            )
            if not self._snapshot_matches(
                target["path"], expected_exists, expected_payload
            ):
                self._restore_transaction_target(target, use_after)

        for target in targets:
            expected_exists = True if use_after else target["existed"]
            expected_payload = (
                target["after"] if use_after else target.get("before")
            )
            if not self._snapshot_matches(
                target["path"], expected_exists, expected_payload
            ):
                raise OSError(
                    f"T088 recovery verification failed for {target['path']}"
                )

        _durable_remove(self._transaction_path())
        return "rolled_forward" if use_after else "rolled_back"

    def _build_transaction_record(self, snapshots, staged_writes):
        targets = []
        for path, payload in staged_writes.items():
            canonical = os.path.abspath(os.path.normpath(path))
            before = snapshots[path]
            targets.append(
                {
                    "path": canonical,
                    "existed": True,
                    "before": copy.deepcopy(before),
                    "after": copy.deepcopy(payload),
                }
            )
        record = {
            "version": _T088_TRANSACTION_VERSION,
            "transaction_id": uuid4().hex,
            "status": "staged",
            "context_path": os.path.abspath(os.path.normpath(self.context_path)),
            "targets": targets,
        }
        self._validate_transaction_record(record)
        return record

    def reconcile_all_areas(self):
        """Optimistically reconcile one exact module snapshot.

        Standalone calls release module refresh and the context target lock
        during provider waits, then reacquire strictly refresh -> context and
        revalidate bytes, containment, and directory/file identities. A caller
        that already owns refresh (managed build) retains its outer fence.
        """
        # Do not create a phantom module directory merely to place a lock file.
        # The context is required for both normal work and pending recovery.
        if not os.path.isfile(self.context_path):
            print(
                "ERROR: [NpcReconciler] Context file not found at "
                f"{self.context_path}"
            )
            return False
        if (
            path_transaction_lock_owned(self.context_path)
            and not module_refresh_lock_owned()
        ):
            print(
                "ERROR: [NpcReconciler] Refusing target -> refresh lock inversion"
            )
            return False
        try:
            for source_attempt in range(_T088_SOURCE_RETRY_LIMIT):
                with module_refresh_lock() as snapshot_acquired:
                    if not snapshot_acquired:
                        print(
                            "ERROR: [NpcReconciler] Module refresh is busy; "
                            "T088 made no changes."
                        )
                        return False
                    with path_transaction_lock(self.context_path):
                        recovery = self._recover_pending_transaction()
                        if recovery:
                            print(
                                "INFO: [NpcReconciler] Recovered interrupted "
                                f"T088 transaction ({recovery})."
                            )
                        source_snapshot = self._capture_reconciliation_inputs()
                        self._install_context_snapshot(
                            source_snapshot["context"]["payload"]
                        )

                try:
                    (
                        original_context,
                        snapshots,
                        staged_writes,
                    ) = self._stage_reconciliation_from_snapshot(source_snapshot)
                except Exception as exc:
                    print(
                        "ERROR: [NpcReconciler] Failed to stage "
                        f"reconciliation: {exc}"
                    )
                    return False

                with module_refresh_lock() as commit_acquired:
                    if not commit_acquired:
                        self.context = original_context
                        self._rebuild_canonical_map()
                        print(
                            "ERROR: [NpcReconciler] Module refresh became busy; "
                            "T088 made no changes."
                        )
                        return False
                    with path_transaction_lock(self.context_path):
                        if not self._reconciliation_inputs_match(source_snapshot):
                            self.context = original_context
                            self._rebuild_canonical_map()
                            print(
                                "WARNING: [NpcReconciler] T088 source changed "
                                "during model work; discarding stale result."
                            )
                            continue
                        return self._commit_staged_reconciliation(
                            original_context,
                            snapshots,
                            staged_writes,
                        )
            print(
                "ERROR: [NpcReconciler] T088 source remained unstable; "
                "last committed state was retained."
            )
            return False
        except Exception as exc:
            print(f"ERROR: [NpcReconciler] Reconciliation lock failed: {exc}")
            return False

    def _commit_staged_reconciliation(
        self,
        original_context,
        snapshots,
        staged_writes,
    ):
        """Commit one freshly revalidated T088 candidate under both locks."""
        if not staged_writes:
            return True

        record = None
        try:
            record = self._build_transaction_record(snapshots, staged_writes)

            # Refuse to stage from stale snapshots. Recovery uses this same
            # before/after restriction to avoid overwriting unrelated work.
            for target in record["targets"]:
                if not self._snapshot_matches(
                    target["path"], target["existed"], target["before"]
                ):
                    raise OSError(
                        "T088 transaction target changed while reconciliation "
                        f"was staged: {target['path']}"
                    )

            _durable_write_json(self._transaction_path(), record)

            for target in record["targets"]:
                self._write_transaction_target(target["path"], target["after"])
                if os.path.normcase(target["path"]) != os.path.normcase(
                    os.path.abspath(os.path.normpath(self.context_path))
                ):
                    print(
                        "  -> Reconciled NPC names in "
                        f"{os.path.basename(target['path'])}"
                    )

            for target in record["targets"]:
                if not self._snapshot_matches(
                    target["path"], True, target["after"]
                ):
                    raise OSError(
                        f"T088 commit verification failed for {target['path']}"
                    )
            _durable_remove(self._transaction_path())
        except Exception as exc:
            print(f"ERROR: [NpcReconciler] Transaction commit failed: {exc}")
            if record is not None and os.path.exists(self._transaction_path()):
                try:
                    record["status"] = "rollback_required"
                    _durable_write_json(self._transaction_path(), record)
                    self._recover_pending_transaction()
                except Exception as rollback_exc:
                    print(
                        "ERROR: [NpcReconciler] Durable rollback failed; "
                        f"recovery marker retained: {rollback_exc}"
                    )
            self.context = original_context
            self._rebuild_canonical_map()
            return False

        return True

    def _reconcile_all_areas_unlocked(self):
        """Compatibility path for a caller already owning refresh + context."""
        if not module_refresh_lock_owned() or not path_transaction_lock_owned(
            self.context_path
        ):
            print(
                "ERROR: [NpcReconciler] Unlocked T088 helper lacks ownership"
            )
            return False
        source_snapshot = self._capture_reconciliation_inputs()
        self._install_context_snapshot(source_snapshot["context"]["payload"])
        original_context, snapshots, staged_writes = (
            self._stage_reconciliation_from_snapshot(source_snapshot)
        )
        if not self._reconciliation_inputs_match(source_snapshot):
            self.context = original_context
            self._rebuild_canonical_map()
            return False
        return self._commit_staged_reconciliation(
            original_context,
            snapshots,
            staged_writes,
        )

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
