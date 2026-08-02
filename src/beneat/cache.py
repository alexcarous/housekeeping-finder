"""Reference data caching with a TTL.

BeNeat's province/district/service lists are static and rarely change, so we
cache them on disk and re-fetch after a configurable TTL (default 30 days).
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from beneat.config import settings


@dataclass(frozen=True)
class CacheData:
    """In-memory representation of cached reference data."""

    provinces: list[dict[str, object]]
    districts: dict[int, list[dict[str, object]]] = field(default_factory=dict)
    services: list[dict[str, object]] = field(default_factory=list)
    cached_at: float = field(default=0.0)


def ensure_cache_dir() -> Path:
    """Create the cache directory if it doesn't exist."""
    path = Path(settings.cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_path() -> Path:
    """Absolute path to the reference-data cache file."""
    return Path(settings.cache_dir) / "reference.json"


def is_fresh(path: Path, ttl_days: int | None = None) -> bool:
    """Return True if the cache file exists and is newer than the TTL."""
    if not path.exists():
        return False
    ttl = ttl_days if ttl_days is not None else settings.cache_ttl_days
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds < ttl * 24 * 60 * 60


def load(path: Path | None = None) -> CacheData | None:
    """Load cached reference data from disk, or None if absent/invalid."""
    target = path if path is not None else cache_path()
    if not target.exists():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        districts = {int(k): v for k, v in raw.get("districts", {}).items()}
        return CacheData(
            provinces=raw.get("provinces", []),
            districts=districts,
            services=raw.get("services", []),
            cached_at=raw.get("cached_at", 0.0),
        )
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return None


def save(data: CacheData, path: Path | None = None) -> None:
    """Atomically write cached reference data to disk."""
    target = path if path is not None else cache_path()
    ensure_cache_dir()
    payload = {
        "provinces": data.provinces,
        "districts": data.districts,
        "services": data.services,
        "cached_at": data.cached_at,
    }
    fd, tmp_name = tempfile.mkstemp(
        dir=settings.cache_dir, prefix="reference-", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        tmp_path.replace(target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def clear(path: Path | None = None) -> None:
    """Remove the cache file if present."""
    target = path if path is not None else cache_path()
    target.unlink(missing_ok=True)
