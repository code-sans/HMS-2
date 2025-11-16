import json
import logging
from typing import Any, Optional

from flask import current_app

import redis

logger = logging.getLogger(__name__)


def _init_client():
    """Initialize a Redis client using Flask app config or environment defaults.

    This uses lazy initialization via reading `current_app.config` so it must be
    called within an application context or after the app has been created.
    """
    try:
        cfg = current_app.config
    except RuntimeError:
        # not in app context, fallback to defaults
        host = "127.0.0.1"
        port = 6379
        db = 0
    else:
        host = cfg.get("REDIS_HOST", "127.0.0.1")
        port = cfg.get("REDIS_PORT", 6379)
        db = cfg.get("REDIS_DB", 0)

    try:
        client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        # quick ping to validate connection (non-fatal)
        client.ping()
        return client
    except Exception as e:
        logger.warning("Redis client init failed: %s", e)
        return None


_CLIENT = None


def _client() -> Optional[redis.Redis]:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = _init_client()
    return _CLIENT


def get_cache(key: str) -> Optional[Any]:
    """Return the Python object stored at `key` or None if missing/error.

    Stored values are JSON-encoded strings. This returns the decoded object.
    """
    client = _client()
    if not client:
        return None
    try:
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.debug("get_cache error for key %s: %s", key, e)
        return None


def set_cache(key: str, value: Any, expiration: int) -> bool:
    """Serialize `value` to JSON and set it with explicit expiration (seconds).

    Returns True on success, False otherwise.
    """
    client = _client()
    if not client:
        return False
    try:
        raw = json.dumps(value)
        client.set(key, raw, ex=int(expiration))
        return True
    except Exception as e:
        logger.debug("set_cache error for key %s: %s", key, e)
        return False


def delete_cache(key: str) -> bool:
    """Delete a single key. Returns True if deleted or not present, False on error."""
    client = _client()
    if not client:
        return False
    try:
        client.delete(key)
        return True
    except Exception as e:
        logger.debug("delete_cache error for key %s: %s", key, e)
        return False


def invalidate_pattern(pattern: str) -> int:
    """Invalidate (delete) all keys matching the glob-style `pattern`.

    Uses `scan_iter` to avoid blocking Redis on large keyspaces.
    Returns the number of keys deleted.
    """
    client = _client()
    if not client:
        return 0
    deleted = 0
    try:
        for k in client.scan_iter(match=pattern):
            try:
                client.delete(k)
                deleted += 1
            except Exception:
                logger.debug("Failed to delete cache key during pattern invalidate: %s", k)
        return deleted
    except Exception as e:
        logger.debug("invalidate_pattern error for %s: %s", pattern, e)
        return deleted


# Optional decorator for caching view responses. It's simple and intended for
# read-only GET endpoints. It builds a key from `key_prefix` and request args.
def cache_response(key_prefix: str, expire: int):
    from functools import wraps
    from flask import request, jsonify

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Build stable key from prefix + path + sorted query string
            qs = "&".join(sorted([f"{k}={v}" for k, v in request.args.items()]))
            key = f"{key_prefix}:{request.path}:{qs}" if qs else f"{key_prefix}:{request.path}"

            cached = get_cache(key)
            if cached is not None:
                # return cached JSON object
                return jsonify(cached)

            resp = fn(*args, **kwargs)
            # If view returned (data, status), handle both
            data = None
            status = None
            try:
                # If it's a flask.Response, don't attempt to cache
                from flask import Response

                if isinstance(resp, Response):
                    return resp
                if isinstance(resp, tuple):
                    data, status = resp
                else:
                    data = resp
                # assume data is dict-like
                body = data.get_json() if hasattr(data, "get_json") else data
                # cache only successful GET results
                if isinstance(body, (dict, list)):
                    set_cache(key, body, expire)
            except Exception:
                # caching best-effort
                pass

            return resp

        return wrapper

    return decorator
