# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Versioned SRD reference loading and exact/alias lookup.

The reference index is guidance data for provider context. It deliberately does
not execute spell rules. Keeping lookup deterministic means an explicit rule
name adds no provider call and an old saved-sheet name can still resolve after
an SRD rename.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


DEFAULT_SPELL_REPOSITORY = (
    Path(__file__).resolve().parents[2] / "data" / "spell_repository.json"
)
DEFAULT_COMMON_RULE_REPOSITORY = (
    Path(__file__).resolve().parents[2] / "data" / "srd_common_rules.json"
)


class SRDReferenceError(ValueError):
    """The production SRD reference data is internally inconsistent."""


def normalize_rule_name(value):
    """Return one punctuation- and Unicode-stable lookup key."""
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKD", value).replace("’", "'")
    value = "".join(
        character for character in value if not unicodedata.combining(character)
    )
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower())
    return value.strip("_")


class SRDReferenceIndex:
    """Validated, immutable-by-convention lookup over SRD guidance entries."""

    def __init__(self, repository):
        if not isinstance(repository, dict):
            raise SRDReferenceError("SRD repository must be a JSON object")
        metadata = repository.get("_metadata")
        if not isinstance(metadata, dict):
            raise SRDReferenceError("SRD repository requires _metadata")
        entry_kind = metadata.get("entry_kind", "spell")
        if entry_kind not in ("spell", "rule"):
            raise SRDReferenceError(
                "SRD repository has unsupported entry kind %r" % entry_kind
            )

        entries = {}
        names = {}
        aliases_by_key = {}
        kinds_by_key = {}
        for key, raw_entry in repository.items():
            if str(key).startswith("_"):
                continue
            if not isinstance(raw_entry, dict):
                raise SRDReferenceError("SRD entry %r must be an object" % key)
            entry = dict(raw_entry)
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip():
                raise SRDReferenceError("SRD entry %r requires a name" % key)
            canonical_key = normalize_rule_name(name)
            if canonical_key != key:
                raise SRDReferenceError(
                    "SRD key %r does not match normalized name %r"
                    % (key, canonical_key)
                )
            if entry.get("source") != "SRD 5.2.1" or entry.get("version") != "5.2.1":
                raise SRDReferenceError(
                    "SRD entry %r has an unsupported source/version" % key
                )
            item_kind = entry.get("kind", entry_kind)
            if item_kind != entry_kind:
                raise SRDReferenceError(
                    "SRD entry %r kind %r does not match repository kind %r"
                    % (key, item_kind, entry_kind)
                )
            guidance = entry.get("compactGuidance")
            if not isinstance(guidance, str) or not guidance.strip():
                raise SRDReferenceError("SRD entry %r requires compactGuidance" % key)
            aliases = entry.get("aliases", [])
            if not isinstance(aliases, list) or not all(
                isinstance(alias, str) and alias.strip() for alias in aliases
            ):
                raise SRDReferenceError("SRD entry %r has invalid aliases" % key)

            entries[key] = entry
            aliases_by_key[key] = tuple(aliases)
            kinds_by_key[key] = item_kind
            for candidate in (name, *aliases):
                lookup_key = normalize_rule_name(candidate)
                existing = names.get(lookup_key)
                if existing is not None and existing != key:
                    raise SRDReferenceError(
                        "SRD alias collision %r between %r and %r"
                        % (candidate, existing, key)
                    )
                names[lookup_key] = key

        count_field = "total_entries" if "total_entries" in metadata else "total_spells"
        declared_total = metadata.get(count_field)
        if declared_total != len(entries):
            raise SRDReferenceError(
                "SRD metadata declares %r entries but contains %d"
                % (declared_total, len(entries))
            )
        self.metadata = dict(metadata)
        self.entry_kind = entry_kind
        self.entries = entries
        self._names = names
        self._aliases_by_key = aliases_by_key
        self._kinds_by_key = kinds_by_key

    @classmethod
    def from_path(cls, path=DEFAULT_SPELL_REPOSITORY):
        with Path(path).open("r", encoding="utf-8") as handle:
            return cls(json.load(handle))

    def resolve_key(self, value):
        """Resolve a current name, historical name, punctuation variant, or key."""
        return self._names.get(normalize_rule_name(value))

    def resolve(self, value):
        key = self.resolve_key(value)
        return self.entries.get(key) if key else None

    def reference(self, value):
        """Return the stable ID plus the production entry for provider context."""
        key = self.resolve_key(value)
        if not key:
            return None
        return {
            "id": "%s:%s" % (self._kinds_by_key[key], key),
            "kind": self._kinds_by_key[key],
            "key": key,
            "entry": self.entries[key],
        }

    def compatibility_spell_map(self):
        """Expose canonical and legacy keys for old character-sheet tooltips."""
        result = {"_metadata": dict(self.metadata)}
        result.update(self.entries)
        for canonical_key, aliases in self._aliases_by_key.items():
            for alias in aliases:
                result.setdefault(
                    normalize_rule_name(alias), self.entries[canonical_key]
                )
        return result

    def lookup_terms(self):
        """Yield canonical lookup key, display term, and alias status."""
        for canonical_key, entry in self.entries.items():
            yield canonical_key, entry["name"], False
            for alias in self._aliases_by_key[canonical_key]:
                yield canonical_key, alias, True

    def reference_terms(self):
        """Yield kind-aware canonical and alias terms for contextual matching."""
        for canonical_key, term, is_alias in self.lookup_terms():
            yield (
                self._kinds_by_key[canonical_key],
                canonical_key,
                term,
                is_alias,
            )


_COMMON_OR_SHORT_RULE_NAMES = frozenset(
    ("aid", "confusion", "help", "light", "shield", "slow")
)
_EXPLICIT_RULE_VERBS = frozenset(
    (
        "cast",
        "casts",
        "casting",
        "cst",
        "invoke",
        "invokes",
        "invoking",
        "channel",
        "channels",
    )
)
_COMMON_RULE_SINGLE_TEXT_BLOCKLIST = frozenset(
    ("cover", "prone", "darkness", "light", "falling", "object", "objects")
)
_DEFAULT_RULE_INDEX = object()


def tokenize_rule_text(value):
    """Return the canonical token stream used by every SRD matcher."""
    normalized = unicodedata.normalize("NFKD", str(value or "")).replace("’", "'")
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return tuple(re.findall(r"[a-z0-9]+", normalized.lower()))


_tokens = tokenize_rule_text


def _phrase_spans(haystack, needle):
    if not needle or len(needle) > len(haystack):
        return ()
    return tuple(
        (index, index + len(needle))
        for index in range(len(haystack) - len(needle) + 1)
        if haystack[index : index + len(needle)] == needle
    )


def _explicit_short_rule_use(tokens, start, end):
    before = tokens[max(0, start - 3) : start]
    after = tokens[end : min(len(tokens), end + 2)]
    return bool(set(before) & _EXPLICIT_RULE_VERBS) or "spell" in after


def fuzzy_rule_candidate_allowed(text, term, kind, span):
    """Apply the exact matcher's conservative guards to one fuzzy candidate.

    ``span`` is the token range in ``text`` that approximately matched
    ``term``.  Fuzzy lookup is optional provider guidance, so ambiguity must
    fail closed and it must never be looser than exact contextual lookup.
    """
    text_tokens = _tokens(text)
    term_tokens = _tokens(term)
    if not term_tokens or not isinstance(span, (tuple, list)) or len(span) != 2:
        return False
    start, end = span
    if type(start) is not int or type(end) is not int:
        return False
    if start < 0 or end <= start or end > len(text_tokens):
        return False
    key = normalize_rule_name(term)
    if kind == "spell":
        guarded = key in _COMMON_OR_SHORT_RULE_NAMES or (
            len(term_tokens) == 1 and len(term_tokens[0]) <= 8
        )
        if (
            len(term_tokens) == 1
            and len(term_tokens[0]) <= 5
            and (
                key in _COMMON_OR_SHORT_RULE_NAMES
                or term_tokens[0] in _COMMON_RULE_SINGLE_TEXT_BLOCKLIST
            )
        ):
            return False
        if guarded and not _explicit_short_rule_use(text_tokens, start, end):
            return False
    elif (
        len(term_tokens) == 1
        and term_tokens[0] in _COMMON_RULE_SINGLE_TEXT_BLOCKLIST
    ):
        return False
    return True


def _sheet_spell_names(sheet):
    spells = ((sheet or {}).get("spellcasting") or {}).get("spells") or {}
    if not isinstance(spells, dict):
        return ()
    result = []
    for values in spells.values():
        if isinstance(values, list):
            result.extend(str(value).strip() for value in values if value)
    return tuple(result)


def _spell_slot_hints(sheet, spell_level):
    if spell_level <= 0:
        return ()
    slots = ((sheet or {}).get("spellcasting") or {}).get("spellSlots") or {}
    if not isinstance(slots, dict):
        return ()
    hints = []
    for name, value in slots.items():
        match = re.fullmatch(r"level\s*_?\s*([1-9])", str(name), re.IGNORECASE)
        if not match or int(match.group(1)) < spell_level:
            continue
        if isinstance(value, dict):
            current = value.get("current")
            maximum = value.get("max")
        else:
            current = value
            maximum = None
        if (
            isinstance(maximum, int)
            and maximum <= 0
            and int(match.group(1)) != spell_level
        ):
            continue
        hints.append(
            {
                "kind": "spellSlot",
                "name": str(name),
                "current": current if isinstance(current, int) else None,
                "max": maximum if isinstance(maximum, int) else None,
            }
        )
    return tuple(hints)


class SRDContextMatcher:
    """Select a tiny set of exact SRD references for one actor/action context."""

    def __init__(
        self,
        index=None,
        rule_index=_DEFAULT_RULE_INDEX,
    ):
        self.index = index or load_srd_reference_index()
        if rule_index is _DEFAULT_RULE_INDEX:
            try:
                rule_index = load_srd_common_rule_index()
            except (OSError, ValueError, json.JSONDecodeError):
                # Common guidance is optional enrichment. A missing or damaged
                # file must not disable valid spell guidance or gameplay.
                rule_index = None
        self.rule_index = rule_index
        indexes = [self.index]
        if self.rule_index is not None:
            indexes.append(self.rule_index)
        self._reference_indexes = tuple(indexes)
        self._terms = tuple(
            (reference_index, kind, key, term, is_alias, _tokens(term))
            for reference_index in self._reference_indexes
            for kind, key, term, is_alias in reference_index.reference_terms()
        )

    def select(self, text, actor_sheet=None, structured_names=None):
        """Return ranked exact/alias matches without calling a provider."""
        text_tokens = _tokens(text)
        known_names = _sheet_spell_names(actor_sheet)
        known_by_key = {}
        for sheet_name in known_names:
            key = self.index.resolve_key(sheet_name)
            if key:
                known_by_key.setdefault(key, sheet_name)

        selected = {}
        spans_by_key = {}
        for reference_index, kind, key, term, is_alias, term_tokens in self._terms:
            for start, end in _phrase_spans(text_tokens, term_tokens):
                if kind == "spell":
                    canonical_short = key in _COMMON_OR_SHORT_RULE_NAMES or (
                        len(term_tokens) == 1 and len(term_tokens[0]) <= 8
                    )
                    if canonical_short and not _explicit_short_rule_use(
                        text_tokens, start, end
                    ):
                        continue
                    score = 300 if key in known_by_key else 200
                    if _explicit_short_rule_use(text_tokens, start, end):
                        score += 100
                else:
                    if (
                        len(term_tokens) == 1
                        and term_tokens[0] in _COMMON_RULE_SINGLE_TEXT_BLOCKLIST
                    ):
                        continue
                    score = 220
                if is_alias:
                    score -= 5
                rule_id = "%s:%s" % (kind, key)
                candidate = {
                    "key": key,
                    "ruleId": rule_id,
                    "kind": kind,
                    "entry": reference_index.entries[key],
                    "matchedTerm": term,
                    "matchSource": "text",
                    "score": score,
                    "span": (start, end),
                }
                existing = selected.get(rule_id)
                if existing is None or (score, end - start) > (
                    existing["score"],
                    existing["span"][1] - existing["span"][0],
                ):
                    selected[rule_id] = candidate
                    spans_by_key[rule_id] = (start, end)

        if isinstance(structured_names, str):
            structured_values = (structured_names,)
        else:
            structured_values = structured_names or ()
        for value in structured_values:
            resolved = []
            for reference_index in self._reference_indexes:
                key = reference_index.resolve_key(value)
                if key:
                    resolved.append(
                        (
                            reference_index,
                            reference_index._kinds_by_key[key],
                            key,
                        )
                    )
            if len(resolved) > 1:
                listed_spell = [
                    item
                    for item in resolved
                    if item[1] == "spell" and item[2] in known_by_key
                ]
                if len(listed_spell) == 1:
                    resolved = listed_spell
            # Cross-family ambiguity fails closed rather than injecting a
            # seemingly authoritative guess.
            if len(resolved) != 1:
                continue
            reference_index, kind, key = resolved[0]
            rule_id = "%s:%s" % (kind, key)
            selected[rule_id] = {
                "key": key,
                "ruleId": rule_id,
                "kind": kind,
                "entry": reference_index.entries[key],
                "matchedTerm": str(value),
                "matchSource": "structured",
                "score": 500,
                "span": None,
            }

        # Prefer the longest exact phrase when names overlap, such as Shield
        # and Shield of Faith. Explicit structured fields remain authoritative.
        suppressed = set()
        for rule_id, candidate in tuple(selected.items()):
            span = candidate.get("span")
            if span is None:
                continue
            for other_rule_id, other in tuple(selected.items()):
                if other_rule_id == rule_id or other.get("span") is None:
                    continue
                other_span = other["span"]
                if other_span == span and other["kind"] != candidate["kind"]:
                    # Some terms name both a spell and a general rule, such as
                    # Darkvision. An explicit cast/spell phrase selects the
                    # spell. A bare mention selects the rule instead of
                    # teaching spell mechanics for an ordinary sense.
                    explicit_spell = _explicit_short_rule_use(
                        text_tokens, span[0], span[1]
                    )
                    if candidate["kind"] == ("rule" if explicit_spell else "spell"):
                        suppressed.add(rule_id)
                        break
                if (
                    other_span[0] <= span[0]
                    and other_span[1] >= span[1]
                    and other_span[1] - other_span[0] > span[1] - span[0]
                ):
                    suppressed.add(rule_id)
                    break

        for rule_id in suppressed:
            selected.pop(rule_id, None)

        ranked = sorted(
            selected.values(),
            key=lambda item: (-item["score"], item["ruleId"]),
        )
        for match in ranked:
            key = match["key"]
            entry = match["entry"]
            if match["kind"] != "spell":
                match["actorAvailability"] = "not_applicable"
                match["sheetSpellName"] = None
                match["resourceHints"] = ()
                continue
            if not isinstance(actor_sheet, dict):
                match["actorAvailability"] = "unknown"
            else:
                match["actorAvailability"] = (
                    "listed" if key in known_by_key else "not_listed"
                )
            match["sheetSpellName"] = known_by_key.get(key)
            match["resourceHints"] = _spell_slot_hints(
                actor_sheet, int(entry.get("level", 0) or 0)
            )
        return ranked

    def render(self, matches):
        """Render every selected whole reference."""
        if not matches:
            return ""
        header = "[SRD CONTEXT — SRD 5.2.1 guidance for this turn]"
        footer = (
            "Use a reference only for the named rule being resolved. "
            "Do not invent actor availability or resource names."
        )
        blocks = []
        for match in matches:
            entry = match["entry"]
            lines = [
                "[%s] %s" % (match["ruleId"], entry["name"]),
            ]
            if match["kind"] == "spell":
                if match.get("sheetSpellName"):
                    availability = (
                        'listed on the actor sheet as "%s"'
                        % match["sheetSpellName"]
                    )
                elif match.get("actorAvailability") == "not_listed":
                    availability = "not listed on the actor spell list"
                else:
                    availability = (
                        "actor sheet unavailable; verify availability from current state"
                    )
                lines.append("Actor availability: %s." % availability)
                hints = match.get("resourceHints") or ()
                if hints:
                    rendered_hints = []
                    for hint in hints:
                        values = ""
                        if hint.get("current") is not None:
                            values = " current=%s" % hint["current"]
                        if hint.get("max") is not None:
                            values += " max=%s" % hint["max"]
                        rendered_hints.append(
                            "kind=%s name=%s%s"
                            % (hint["kind"], hint["name"], values)
                        )
                    lines.append(
                        "Exact available sheet resource keys: %s."
                        % "; ".join(rendered_hints)
                    )
            lines.append("Guidance: %s" % entry["compactGuidance"])
            block = "\n".join(lines)
            blocks.append(block)
        if not blocks:
            return ""
        return "%s\n%s\n%s" % (header, "\n\n".join(blocks), footer)

    def context_for(self, text, actor_sheet=None, structured_names=None):
        matches = self.select(text, actor_sheet, structured_names)
        return {"matches": matches, "context": self.render(matches)}

    def legal_spell_index(self, actors):
        """Return the complete metadata-only index for automatic actor choices."""
        result = []
        seen = set()
        actor_rows = [
            (str(actor_name), sheet, _sheet_spell_names(sheet))
            for actor_name, sheet in (actors or ())
        ]
        longest = max((len(names) for _name, _sheet, names in actor_rows), default=0)
        # Round-robin prevents the first caster from consuming the entire cap
        # when one automatic initiative window contains several actors.
        for position in range(longest):
            for actor_name, sheet, spell_names in actor_rows:
                if position >= len(spell_names):
                    continue
                listed_name = spell_names[position]
                key = self.index.resolve_key(listed_name)
                marker = (actor_name, key)
                if not key or marker in seen:
                    continue
                seen.add(marker)
                entry = self.index.entries[key]
                item = {
                    "actor": actor_name,
                    "ruleId": "spell:%s" % key,
                    "listedName": listed_name,
                    "name": entry["name"],
                    "level": entry["level"],
                    "castingTime": entry["casting_time"],
                    "range": entry["range"],
                    "duration": entry["duration"],
                    "concentration": entry["concentration"],
                    # Automatic actors need the represented mechanics, not just a
                    # list of spell names. Otherwise a weak model still has to
                    # guess saves, damage, targeting, and restrictions.
                    "guidance": entry["compactGuidance"],
                    "resourceHints": list(
                        _spell_slot_hints(sheet, int(entry.get("level", 0) or 0))
                    ),
                }
                result.append(item)
        return result


def compact_rule_reference(match, actor=None):
    """Serialize one matcher result for a provider-facing context payload."""
    result = {
        "ruleId": match["ruleId"],
        "kind": match["kind"],
        "name": match["entry"]["name"],
        "actorAvailability": match.get("actorAvailability", "not_applicable"),
        "sheetSpellName": match.get("sheetSpellName"),
        "resourceHints": list(match.get("resourceHints") or ()),
        "guidance": match["entry"]["compactGuidance"],
    }
    if actor is not None:
        result["actor"] = actor
    return result


def corrective_rule_references(
    batch,
    actor_id,
    encounter,
    characters,
    index=None,
):
    """Return exact SRD guidance named by one rejected structured intent.

    This is deliberately deterministic and conservative. It inspects only
    schema fields that are supposed to contain rule/resource names; free-form
    narration and validation error prose can never cause a guessed match.
    """
    if not isinstance(batch, dict):
        return []
    intents = batch.get("intents")
    if not isinstance(intents, list):
        return []
    candidates = [
        intent
        for intent in intents
        if isinstance(intent, dict)
        and (actor_id is None or intent.get("actorId") == actor_id)
    ]
    if actor_id is None and len(candidates) != 1:
        return []
    if not candidates:
        return []
    intent = candidates[0]

    structured_names = []
    for key in ("ability", "spell", "feature", "item", "action"):
        value = intent.get(key)
        if isinstance(value, str) and value.strip():
            structured_names.append(value.strip())
    for resource in intent.get("resources", []) or []:
        if isinstance(resource, dict) and isinstance(resource.get("name"), str):
            structured_names.append(resource["name"].strip())
    for effect_op in intent.get("effects", []) or []:
        if not isinstance(effect_op, dict):
            continue
        value = effect_op.get("name")
        if isinstance(value, str) and value.strip():
            structured_names.append(value.strip())
        effect = effect_op.get("effect")
        if isinstance(effect, dict) and isinstance(effect.get("name"), str):
            structured_names.append(effect["name"].strip())

    actor = next(
        (
            creature
            for creature in (encounter or {}).get("creatures", [])
            if isinstance(creature, dict)
            and creature.get("combatantId") == intent.get("actorId")
        ),
        None,
    )
    actor_name = actor.get("name") if isinstance(actor, dict) else None
    actor_sheet = (characters or {}).get(actor_name) if actor_name else None
    matcher = SRDContextMatcher(index=index)
    matches = matcher.select(
        "",
        actor_sheet=actor_sheet,
        structured_names=structured_names,
    )
    return [compact_rule_reference(match, actor=actor_name) for match in matches]


@lru_cache(maxsize=4)
def _load_index_cached(path_string):
    return SRDReferenceIndex.from_path(Path(path_string))


@lru_cache(maxsize=4)
def _load_common_index_cached(path_string):
    return SRDReferenceIndex.from_path(Path(path_string))


def load_srd_reference_index(path=DEFAULT_SPELL_REPOSITORY):
    """Load and cache a validated reference index for the current process."""
    return _load_index_cached(str(Path(path).resolve()))


def load_srd_common_rule_index(path=DEFAULT_COMMON_RULE_REPOSITORY):
    """Load and cache the optional common-rule guidance index."""
    return _load_common_index_cached(str(Path(path).resolve()))


def clear_srd_reference_cache():
    """Explicit invalidation hook for development and controlled reloads."""
    _load_index_cached.cache_clear()
    _load_common_index_cached.cache_clear()
