"""Request-local DM delivery guidance, after compression and review context."""
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def narration_delivery_prompt():
    return (Path(__file__).resolve().parents[1] / "prompts" /
            "narration_delivery.txt").read_text(encoding="utf-8").strip()


def with_narration_delivery(messages):
    """Keep the complete conversation intact; never persist this request overlay."""
    prompt = narration_delivery_prompt()
    result = list(messages)
    if not result or result[-1] != {"role": "system", "content": prompt}:
        result.append({"role": "system", "content": prompt})
    return result
