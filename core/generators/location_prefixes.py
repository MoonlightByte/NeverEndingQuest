"""Location ID prefixes: the one encoding every generator and the stitcher use (#646).

A location ID is a prefix of one to three capital letters and two digits
(schemas/loca_schema.json: ``^[A-Z]{1,3}[0-9]{2}$``). Index 0..25 is A..Z,
26..701 is AA..ZZ and 702..18277 is AAA..ZZZ; the first 702 are the prefixes
every existing module already uses.
"""
from typing import Optional

PREFIX_COUNT = 26 + 26 * 26 + 26 * 26 * 26  # 18278: every 1-3 letter prefix


def location_prefix(index: int) -> str:
    """The prefix for a 0-based index; ValueError outside 0..PREFIX_COUNT-1."""
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < PREFIX_COUNT:
        raise ValueError("location prefix index %r is outside 0..%d" % (index, PREFIX_COUNT - 1))
    letters = ""
    n = index + 1
    while n:
        n, r = divmod(n - 1, 26)
        letters = chr(65 + r) + letters
    return letters


def location_prefix_index(prefix: str) -> Optional[int]:
    """The index of a 1-3 capital-letter prefix (the inverse of location_prefix), else None."""
    if not isinstance(prefix, str) or not 1 <= len(prefix) <= 3 or not all("A" <= c <= "Z" for c in prefix):
        return None
    n = 0
    for c in prefix:
        n = n * 26 + (ord(c) - 64)
    return n - 1
