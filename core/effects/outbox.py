# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Pure stable-ID helpers for effect notification delivery."""

import hashlib
import re


MARKER_PREFIX = "EFFECT-NOTICE"
_MARKER_RE = re.compile(r"\[EFFECT-NOTICE:([^\]]+)\]")


def notification_id(owner, effect_id, reason):
    material = "%s|%s|%s" % (str(owner), str(effect_id), str(reason))
    return "FXN-%s" % hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def delivered_ids(history):
    delivered = set()
    for message in history or []:
        content = message.get("content", "") if isinstance(message, dict) else ""
        for match in _MARKER_RE.finditer(str(content)):
            delivered.update(item for item in match.group(1).split(",") if item)
    return delivered


def build_message(records):
    records = [record for record in records or [] if isinstance(record, dict)]
    ids = [str(record.get("notificationId")) for record in records if record.get("notificationId")]
    descriptions = [str(record.get("text")) for record in records if record.get("text")]
    if not ids or not descriptions:
        return None
    return {
        "role": "system",
        "content": (
            "[%s:%s] These effects ended automatically: %s "
            "Narrate the change naturally when it is relevant; do not apply or reverse it again."
            % (MARKER_PREFIX, ",".join(ids), "; ".join(descriptions))
        ),
    }
