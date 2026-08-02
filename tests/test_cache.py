import json
import time

import pytest

from beneat import cache
from beneat.config import settings


@pytest.fixture()
def cache_dir(tmp_path: pytest.TempPathFactory) -> None:
    original = settings.cache_dir
    settings.cache_dir = tmp_path  # type: ignore[assignment]
    yield
    settings.cache_dir = original


def test_is_fresh_missing_file(tmp_path: pytest.TempPathFactory) -> None:
    assert not cache.is_fresh(tmp_path / "nope.json")


def test_is_fresh_within_ttl(tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "ref.json"
    path.write_text("{}", encoding="utf-8")
    assert cache.is_fresh(path, ttl_days=30)


def test_is_fresh_expired(tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "ref.json"
    path.write_text("{}", encoding="utf-8")
    old = time.time() - (60 * 24 * 60 * 60)
    import os

    os.utime(path, (old, old))
    assert not cache.is_fresh(path, ttl_days=30)


def test_save_load_roundtrip(tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "ref.json"
    data = cache.CacheData(
        provinces=[{"id": 1, "name": "Bangkok"}],
        districts={1: [{"id": 9, "name_th": "เขตพระโขนง"}]},
        services=[{"id": 1}],
        cached_at=123.0,
    )
    cache.save(data, path)
    loaded = cache.load(path)
    assert loaded is not None
    assert loaded.provinces == data.provinces
    assert loaded.districts[1] == data.districts[1]
    assert loaded.services == data.services
    assert loaded.cached_at == 123.0


def test_load_corrupt_returns_none(tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "ref.json"
    path.write_text("not json", encoding="utf-8")
    assert cache.load(path) is None


def test_save_is_atomic(tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "ref.json"
    cache.save(cache.CacheData(provinces=[], cached_at=0.0), path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "provinces" in raw
    assert "cached_at" in raw


def test_clear_removes_file(tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "ref.json"
    path.write_text("{}", encoding="utf-8")
    cache.clear(path)
    assert not path.exists()
