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


def test_normalizer_and_fuzzy_cache_hits_and_clearing() -> None:
    """UT-CACHE-03 / UT-CACHE-04: Verify normalizer and fuzzy similarity LRU caching and cache clearing."""
    from resume_analyzer.skills.normalizer import (
        clear_normalizer_caches,
        fuzzy_similarity,
        normalize_skill,
    )

    clear_normalizer_caches()

    # Normalizer cache test
    norm1 = normalize_skill("Python (advanced)")
    norm2 = normalize_skill("Python (advanced)")
    assert norm1 == norm2 == "python"
    assert normalize_skill.cache_info().hits >= 1

    # Fuzzy similarity cache test
    sim1 = fuzzy_similarity("python", "python")
    sim2 = fuzzy_similarity("python", "python")
    assert sim1 == sim2 == 100.0
    assert fuzzy_similarity.cache_info().hits >= 1

    # Clear caches
    clear_normalizer_caches()
    assert normalize_skill.cache_info().hits == 0
    assert fuzzy_similarity.cache_info().hits == 0


def test_skill_index_and_taxonomy_caching() -> None:
    """UT-CACHE-05: Verify SkillIndex and Taxonomy caching and reuse across AnalysisService."""
    from resume_analyzer.services.analysis_service import (
        DEFAULT_TAXONOMY_PATH,
        AnalysisService,
    )
    from resume_analyzer.skills.skill_index import get_skill_index
    from resume_analyzer.skills.taxonomy import (
        clear_taxonomy_cache,
    )

    clear_taxonomy_cache()
    get_skill_index.cache_clear()

    idx1 = get_skill_index(DEFAULT_TAXONOMY_PATH)
    idx2 = get_skill_index(DEFAULT_TAXONOMY_PATH)
    assert idx1 is idx2
    assert get_skill_index.cache_info().hits >= 1

    svc1 = AnalysisService()
    svc2 = AnalysisService()
    assert svc1.skill_index is svc2.skill_index
    assert get_skill_index.cache_info().hits >= 2
