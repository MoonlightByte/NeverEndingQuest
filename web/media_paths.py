"""Resolve a /media/<type>/<filename> request to one real file, or None.

Stdlib only so it can be unit tested without the web app. The filename comes
from the URL: it must stay inside the media directory it was asked for, so
absolute paths, parent references, backslashes and NUL bytes are refused
before any filesystem lookup. Lookup order is unchanged from the original
route: the current module, every other module, then the static fallback.
"""
import os
import posixpath
import re

MEDIA_TYPES = ("monsters", "npcs", "environment")
# The name generated scene images are saved under (#1755); anything else in the
# images folder (image_metadata.json) is never served.
GENERATED_IMAGE_NAME = re.compile(r"img_[A-Za-z0-9_.-]+\.png")


def _safe_relative(filename):
    """Normalized relative path, or None if it could escape its directory."""
    if not filename or "\x00" in filename or "\\" in filename:
        return None
    if filename.startswith("/"):
        return None
    if any(part == ".." for part in filename.split("/")):
        return None
    normalized = posixpath.normpath(filename)
    if normalized in (".", "") or normalized.startswith("../") \
            or normalized == ".." or "/../" in normalized:
        return None
    parts = normalized.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    return os.path.join(*parts)


def _safe_component(name):
    return bool(name) and name not in (".", "..") and "/" not in name \
        and "\\" not in name and "\x00" not in name


# #1998: why a client name was refused, by the kind of name.
NAME_REFUSALS = {
    "pack_name": "That pack name is not allowed.",
    "monster_id": "That monster id is not allowed.",
    "npc_id": "That NPC id is not allowed.",
    "module_name": "That module name is not allowed.",
    "asset_id": "That asset id is not allowed.",
    "character_name": "That character name is not allowed.",
    "style": "That style is not allowed.",
    "filename": "That file name is not allowed.",
}

# #1998: names Windows gives to devices, whatever follows the first dot.
_WINDOWS_DEVICES = frozenset(
    ["CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"]
    + ["COM%s" % d for d in "123456789\u00b9\u00b2\u00b3"]
    + ["LPT%s" % d for d in "123456789\u00b9\u00b2\u00b3"])


def safe_name(value):
    """#1998: True for one folder or file name that stays where it is joined,
    on Linux and on Windows: a non-empty str, not '.' or '..', with no slash,
    backslash, colon or control character, not ending in a dot or a space,
    and not a Windows device name (CON, NUL, COM1, LPT1, ... before the first
    dot, in any case)."""
    if not isinstance(value, str) or not _safe_component(value):
        return False
    if ":" in value or any(ord(c) < 0x20 for c in value):
        return False
    if value.endswith((".", " ")):
        return False
    if value.partition(".")[0].rstrip(" ").upper() in _WINDOWS_DEVICES:
        return False
    return True


def refused_name(dict_items=(), **values):
    """#1998: {success, error, reason} for the first client value that could
    leave its folder, else None. Keys are the kinds in NAME_REFUSALS.

    None (not sent) is skipped, so a missing value keeps its existing
    handling. A str must pass safe_name. A list is checked item by item: a str
    item must pass safe_name; a dict item is accepted only for the kinds in
    dict_items (the routes that read item['id']), and then its 'id' must be a
    str that passes safe_name. Anything else (a number, a dict, a list inside
    a list) is refused. A style is checked as the folder it names, temp_<style>."""
    for reason, value in values.items():
        if value is None:
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if isinstance(item, dict) and reason in dict_items and isinstance(value, list):
                item = item.get("id")
            if not isinstance(item, str):
                return {"success": False, "error": NAME_REFUSALS[reason], "reason": reason}
            if reason == "style":
                item = "temp_" + item
            if not safe_name(item):
                return {"success": False, "error": NAME_REFUSALS[reason], "reason": reason}
    return None


def dir_within(directory, name):
    """#1998: directory/name when name is one safe component, else None.
    Lexical on purpose: a folder inside directory that links to another disk
    keeps working (resolve_file_within keeps its real-path check)."""
    if not safe_name(name):
        return None
    path = os.path.join(directory, name)
    if not os.path.abspath(path).startswith(os.path.abspath(directory) + os.sep):
        return None
    return path


def _inside(base, candidate):
    base = os.path.abspath(base)
    candidate = os.path.realpath(candidate)
    return candidate == base or candidate.startswith(base + os.sep)


def resolve_file_within(directory, filename):
    """Resolve untrusted media names without following links outside the root.

    Keep the configured root lexical: resolving it first would bless a symlink
    that replaced the entire media directory with an unrelated directory.
    """
    relative = _safe_relative(filename)
    if relative is None:
        return None
    candidate = os.path.realpath(os.path.join(directory, relative))
    if not _inside(directory, candidate) or not os.path.isfile(candidate):
        return None
    return candidate


def resolve_media_path(media_type, filename, current_module, modules_dir,
                       static_media_dir):
    if media_type not in MEDIA_TYPES:
        return None
    relative = _safe_relative(filename)
    if relative is None:
        return None

    candidates = []
    if current_module and _safe_component(current_module):
        candidates.append((
            os.path.join(modules_dir, current_module, "media", media_type),
            "module:" + current_module))
    if os.path.isdir(modules_dir):
        for name in sorted(os.listdir(modules_dir)):
            if name == current_module or not _safe_component(name):
                continue
            if os.path.isdir(os.path.join(modules_dir, name)):
                candidates.append((
                    os.path.join(modules_dir, name, "media", media_type),
                    "module:" + name))
    candidates.append((os.path.join(static_media_dir, media_type), "static"))

    for base, _source in candidates:
        path = resolve_file_within(base, filename)
        if path is not None:
            return path
    if media_type == "npcs":
        # A named villain the module authors as a monster (Bandit Captain
        # Gorvek) keeps his portrait under media/monsters, but he is listed
        # among a place's people, so the screen asks for an NPC portrait.
        return resolve_media_path("monsters", filename, current_module,
                                  modules_dir, static_media_dir)
    return None


def resolve_generated_image(module, filename, modules_dir):
    """A saved scene image in modules/<module>/images, or None (#1755).

    The module is the one the image was saved under, named in the URL, so
    there is no lookup across modules or into static media.
    """
    if not _safe_component(module) or not os.path.isdir(os.path.join(modules_dir, module)):
        return None
    if not _safe_component(filename) or not GENERATED_IMAGE_NAME.fullmatch(filename):
        return None
    return resolve_file_within(os.path.join(modules_dir, module, "images"), filename)
