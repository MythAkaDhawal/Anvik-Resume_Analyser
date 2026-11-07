"""Unit tests for caching behavior (UT-CACHE-*)."""

from __future__ import annotations

from resume_analyzer.config.settings import (
    clear_settings_cache,
    get_settings,
)


def test_get_settings_cache_hits_and_clearing() -> None:
    """UT-CACHE-01 / UT-CACHE-02: Verify get_settings LRU cache works and clear_settings_cache resets."""
    clear_settings_cache()

    info_start = get_settings.cache_info()
    assert info_start.hits == 0

    s1 = get_settings()
    s2 = get_settings()

    assert s1 is s2
    info_after = get_settings.cache_info()
    assert info_after.hits >= 1

    clear_settings_cache()
    info_cleared = get_settings.cache_info()
    assert info_cleared.hits == 0
    assert info_cleared.misses == 0

