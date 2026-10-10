"""Resolve a /media/<type>/<filename> request to one real file, or None.

Stdlib only so it can be unit tested without the web app. The filename comes
from the URL: it must stay inside the media directory it was asked for, so
absolute paths, parent references, backslashes and NUL bytes are refused
before any filesystem lookup. Lookup order is unchanged from the original
route: the current module, every other module, then the static fallback.
"""
import os
import posixpath

MEDIA_TYPES = ("monsters", "npcs", "environment")


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
    return None
