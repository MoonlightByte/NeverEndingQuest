"""Bound portrait parsing/decoding independently of gameplay request concurrency."""
from functools import wraps
import threading

from flask import jsonify, request
from PIL import Image
from werkzeug.exceptions import RequestEntityTooLarge

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 16 * 1024 * 1024
_decoder = threading.BoundedSemaphore(1)


def bounded_portrait_upload(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        # Set the streaming parser limit before touching request.files/form.
        request.max_content_length = min(request.max_content_length or MAX_UPLOAD_BYTES, MAX_UPLOAD_BYTES)
        if (request.content_length or 0) > request.max_content_length:
            return jsonify(success=False, message='Portrait must be smaller than 10 MB'), 413
        if not _decoder.acquire(blocking=False):
            response = jsonify(success=False, message='Another portrait is processing. Please try again shortly.')
            response.headers['Retry-After'] = '2'
            return response, 429
        try:
            return view(*args, **kwargs)
        except RequestEntityTooLarge:
            return jsonify(success=False, message='Portrait must be smaller than 10 MB'), 413
        finally:
            _decoder.release()
    return guarded


def decode_portrait(stream):
    with Image.open(stream) as image:
        width, height = image.size
        if image.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise ValueError('Unsupported portrait format')
        if min(width, height) < 1 or max(width, height) > 16384 or width * height > MAX_PIXELS:
            raise ValueError('Portrait dimensions exceed the limit')
        image.verify()
    stream.seek(0)
    with Image.open(stream) as image:
        return image.convert('RGB')
