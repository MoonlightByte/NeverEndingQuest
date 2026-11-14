# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""What a module build is built on, taken once when it starts (#2018).

A build reads the provider, the story-first arm, the names of characters in
other modules and, on Local/Custom, the endpoint's URL and model through the
readers below. Inside a build they return the values taken at its start, so
a setting changed while the build runs applies to the next build; outside a
build they return the live value, as before. A credential stays paired with
the endpoint it was configured for: the Local/Custom key is taken with its
URL and model, held in memory only.

Not frozen, on purpose: the build's own output folder (read live by
get_party_members), the game files the stitcher and publication read
(world_registry.json, party_tracker.json), the OpenAI and Gemini keys (their
endpoints never change), and the learned Local/Custom rate (only a waiting
deadline). The DM_* profiles are fixed tables, selected by the frozen
provider.
"""

import glob
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BuildInputs:
    provider: str
    story_first: bool
    party_names: tuple
    local_base_url: str = None
    local_model: str = None
    # In memory only: never in a repr, log, record or message.
    local_api_key: str = field(default=None, repr=False)


_current = ContextVar("neq_build_inputs", default=None)


def other_module_character_names():
    """Player and NPC names in every module's characters folder (live)."""
    character_names = []
    try:
        for char_file in glob.glob("modules/*/characters/*.json"):
            try:
                with open(char_file, 'r') as f:
                    char_data = json.load(f)
                    char_role = char_data.get('character_role', '')
                    if char_role in ['player', 'npc']:
                        name = char_data.get('name', '').strip()
                        if name and name not in character_names:
                            character_names.append(name)
            except Exception:
                continue
    except Exception:
        pass
    return character_names


def _live_story_first():
    from core.generators.story_first.settings import story_first_enabled

    return story_first_enabled()


def take_build_inputs():
    import model_config

    provider = model_config.get_provider()
    base_url = model = api_key = None
    if provider == "lmstudio":
        endpoint = model_config.get_local_endpoint()
        base_url, model = endpoint.get("base_url"), endpoint.get("model")
        api_key = endpoint.get("api_key")
    return BuildInputs(
        provider=provider,
        story_first=_live_story_first(),
        party_names=tuple(other_module_character_names()),
        local_base_url=base_url,
        local_model=model,
        local_api_key=api_key,
    )


@contextmanager
def build_inputs(preset=None):
    """Take the inputs at a build's start; a nested build keeps the outer ones.
    ``preset``: inputs already taken (#2021: by the turn that starts a job)."""
    current = _current.get()
    if current is not None:
        yield current
        return
    token = _current.set(preset if preset is not None else take_build_inputs())
    try:
        yield _current.get()
    finally:
        _current.reset(token)


def current_build_inputs():
    return _current.get()


def build_provider():
    inputs = _current.get()
    if inputs is not None:
        return inputs.provider
    import model_config

    return model_config.get_provider()


def build_story_first():
    inputs = _current.get()
    return inputs.story_first if inputs is not None else _live_story_first()


def build_party_names():
    inputs = _current.get()
    if inputs is not None:
        return list(inputs.party_names)
    return other_module_character_names()


def request_local_endpoint():
    """The Local/Custom endpoint for one request: live, or inside a build that
    started on Local/Custom the URL, model and key it started with."""
    inputs = _current.get()
    if inputs is not None and inputs.provider == "lmstudio":
        return {"base_url": inputs.local_base_url, "api_key": inputs.local_api_key,
                "model": inputs.local_model}
    import model_config

    return model_config.get_local_endpoint()
