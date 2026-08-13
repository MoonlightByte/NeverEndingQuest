# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Bounded, classify-only verification of natural-language currency offers."""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

import config
import model_config
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.enhanced_logger import warning


register_callsite("T104", "core/ai/currency_offer_verifier.py", 108)

_CLASSIFICATIONS = frozenset({"explicit_offer", "not_explicit", "uncertain"})
_DENOMINATIONS = frozenset({"gold", "silver", "copper"})
_SYSTEM_PROMPT = """You are a narrow intent classifier for a role-playing game.
Read only the player's message and the supplied current coin balances.
Decide whether the player COMMITTED to offering one explicit numeric amount of
gold, silver, or copper as payment/gift/exchange in this turn. Natural player
wording is unrestricted: infer ordinary paraphrases, but do not treat questions,
hypotheticals, tentative thoughts, vague prices, or multiple ambiguous amounts
as an explicit offer. Do not decide whether a sale succeeds and do not invent or
modify game state.

Also classify whether the candidate actions mechanically complete the claimed
transaction.  A newly purchased asset must be granted by updateCharacterInfo;
storageInteraction alone only moves an already-owned asset and NEVER counts as
the acquisition.  A storage-service fee is complete when payment and movement
of the already-owned asset are both encoded.  A refusal or counteroffer is not
a completed purchase.  This is observation only; never repair or propose
actions.

Return JSON only with exactly:
{"classification":"explicit_offer|not_explicit|uncertain",
 "amount":positive_integer_or_null,
 "denomination":"gold|silver|copper"_or_null,
 "completed_purchase":true_or_false}

Use explicit_offer only when one committed amount and denomination are clear.
Use not_explicit when the player clearly made no such committed numeric offer.
Use uncertain for genuine ambiguity. Balances are context only; report the
player's stated amount even when it exceeds the balance."""


def _provider_config() -> Dict[str, Any]:
    provider = model_config.MODEL_PROVIDER
    if provider == "openai":
        return config.CURRENCY_OFFER_T104_GPT54MINI_NONE
    if provider == "gemini":
        return config.CURRENCY_OFFER_T104_GEMINI_FLASHLITE_LOW
    if provider == "lmstudio":
        return config.CURRENCY_OFFER_T104_LMSTUDIO
    return config.CURRENCY_OFFER_T104_LEGACY


def _uncertain(reason: str) -> Dict[str, Any]:
    return {
        "classification": "uncertain",
        "amount": None,
        "denomination": None,
        "completed_purchase": True,
        "reason": reason,
    }


def _normalize_contract(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "classification",
        "amount",
        "denomination",
        "completed_purchase",
    }:
        return _uncertain("invalid response shape")
    classification = value.get("classification")
    amount = value.get("amount")
    denomination = value.get("denomination")
    completed_purchase = value.get("completed_purchase")
    if classification not in _CLASSIFICATIONS:
        return _uncertain("invalid classification")
    if not isinstance(completed_purchase, bool):
        return _uncertain("invalid completed-purchase fact")
    if classification == "explicit_offer":
        if (
            isinstance(amount, bool)
            or not isinstance(amount, int)
            or amount <= 0
            or denomination not in _DENOMINATIONS
        ):
            return _uncertain("invalid explicit offer facts")
    elif amount is not None or denomination is not None:
        return _uncertain("non-offer result included offer facts")
    return {
        "classification": classification,
        "amount": amount,
        "denomination": denomination,
        "completed_purchase": completed_purchase,
    }


def classify_currency_offer(
    player_input: str,
    currency: Mapping[str, Any],
    candidate_actions: Any,
) -> Dict[str, Any]:
    """Make at most one mini-model call and return a fail-closed fact record."""
    packet = {
        "player_input": str(player_input or ""),
        "current_currency": {
            denomination: currency.get(denomination, 0)
            for denomination in sorted(_DENOMINATIONS)
        },
        "candidate_actions": candidate_actions if isinstance(candidate_actions, list) else [],
    }
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(packet, ensure_ascii=False, sort_keys=True),
        },
    ]
    try:
        provider_config = _provider_config()
        response = capture_and_fanout(
            "T104",
            api_client.create_completion,
            _request_provider=model_config.MODEL_PROVIDER,
            messages=messages,
            model=provider_config["model"],
            temperature=0.1,
            **{
                key: value
                for key, value in provider_config.items()
                if key != "model"
            },
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            return _uncertain("empty classifier response")
        return _normalize_contract(json.loads(content))
    except Exception as exc:
        warning(
            f"T104 currency-offer verification failed closed: {exc}",
            category="character_updates",
        )
        return _uncertain("classifier unavailable")
