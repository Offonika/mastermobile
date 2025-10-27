"""Lightweight state store implementations for ephemeral data."""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Protocol, cast

import redis
from redis import Redis

__all__ = [
    "KeyValueStore",
    "InMemoryStore",
    "RedisStore",
    "build_store",
]


class KeyValueStore(Protocol):
    """Protocol describing the store operations used by the services."""

    def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        """Persist the value under the provided key."""

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Return a previously stored value."""

    def pop(self, key: str, default: Any | None = None) -> Any | None:
        """Remove and return a stored value if present."""

    def delete(self, key: str) -> bool:
        """Remove the value associated with the key."""

    def clear(self) -> None:
        """Remove all values maintained by the store."""

    def increment(
        self,
        key: str,
        amount: int = 1,
        *,
        ttl: int | None = None,
    ) -> int:
        """Increment a numeric counter and return its new value."""


class InMemoryStore:
    """Thread-safe dictionary with optional TTL support."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[Any, float | None]] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        expires_at = self._expiry_from_ttl(ttl)
        with self._lock:
            self._data[key] = (value, expires_at)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return default
            value, expires_at = item
            if expires_at is not None and expires_at <= time.monotonic():
                self._data.pop(key, None)
                return default
            return value

    def pop(self, key: str, default: Any | None = None) -> Any | None:
        with self._lock:
            item = self._data.pop(key, None)
            if item is None:
                return default
            value, expires_at = item
            if expires_at is not None and expires_at <= time.monotonic():
                return default
            return value

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._data.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def increment(
        self,
        key: str,
        amount: int = 1,
        *,
        ttl: int | None = None,
    ) -> int:
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive when provided")

        with self._lock:
            item = self._data.get(key)
            if item is None:
                expires_at = self._expiry_from_ttl(ttl)
                new_value = amount
            else:
                value, expires_at = item
                if expires_at is not None and expires_at <= time.monotonic():
                    expires_at = self._expiry_from_ttl(ttl)
                    new_value = amount
                else:
                    try:
                        current = int(value)
                    except (TypeError, ValueError):
                        current = 0
                    new_value = current + amount
            self._data[key] = (new_value, expires_at)
            return new_value

    def _expiry_from_ttl(self, ttl: int | None) -> float | None:
        if ttl is None:
            return None
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        return time.monotonic() + ttl


class RedisStore:
    """Redis-backed key/value store with namespacing."""

    def __init__(self, redis_client: Redis, *, namespace: str) -> None:
        if not namespace:
            msg = "RedisStore requires a non-empty namespace"
            raise ValueError(msg)
        self._redis = redis_client
        self._namespace = namespace

    def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        payload = json.dumps(value)
        name = self._format_key(key)
        if ttl is not None:
            if ttl <= 0:
                raise ValueError("ttl must be positive when provided")
            self._redis.set(name, payload, ex=ttl)
        else:
            self._redis.set(name, payload)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        name = self._format_key(key)
        payload = self._redis.get(name)
        if payload is None:
            return default
        try:
            payload_str = cast(str | bytes | bytearray, payload)
            return json.loads(payload_str)
        except (TypeError, json.JSONDecodeError):
            return default

    def pop(self, key: str, default: Any | None = None) -> Any | None:
        name = self._format_key(key)
        try:
            payload = self._redis.getdel(name)
        except AttributeError:  # pragma: no cover - fallback for old Redis versions
            pipe = self._redis.pipeline()
            pipe.get(name)
            pipe.delete(name)
            payload, _ = pipe.execute()
        if payload is None:
            return default
        try:
            payload_str = cast(str | bytes | bytearray, payload)
            return json.loads(payload_str)
        except (TypeError, json.JSONDecodeError):
            return default

    def delete(self, key: str) -> bool:
        name = self._format_key(key)
        removed = self._redis.delete(name)
        return bool(removed)

    def clear(self) -> None:
        pattern = f"{self._namespace}:*"
        keys = list(self._redis.scan_iter(match=pattern))
        if keys:
            self._redis.delete(*keys)

    def increment(
        self,
        key: str,
        amount: int = 1,
        *,
        ttl: int | None = None,
    ) -> int:
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive when provided")

        name = self._format_key(key)
        pipe = self._redis.pipeline()
        pipe.incrby(name, amount)
        ttl_result_index: int | None = None
        if ttl is not None:
            ttl_result_index = len(pipe.command_stack)
            pipe.ttl(name)
        results = pipe.execute()
        new_value = int(results[0])
        if ttl_result_index is not None and ttl is not None:
            ttl_result = results[ttl_result_index]
            try:
                current_ttl = int(ttl_result)
            except (TypeError, ValueError):
                current_ttl = -2
            if current_ttl == -1:
                self._redis.expire(name, ttl)
        return new_value

    def _format_key(self, key: str) -> str:
        return f"{self._namespace}:{key}"


def build_store(
    namespace: str,
    *,
    redis_url: str | None = None,
    redis_client: Redis | None = None,
) -> KeyValueStore:
    """Return an appropriate store implementation for the namespace."""

    if redis_client is not None:
        return RedisStore(redis_client, namespace=namespace)

    redis_url = redis_url or os.getenv("REDIS_URL")
    if redis_url:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        return RedisStore(client, namespace=namespace)

    return InMemoryStore()
