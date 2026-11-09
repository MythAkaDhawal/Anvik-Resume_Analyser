"""Unit tests for text cleaning and normalization (UT-CLEAN-01..05)."""

from __future__ import annotations

from resume_analyzer.parsing.text_cleaner import clean_text


def test_ut_clean_01_control_character_stripping():
    """UT-CLEAN-01: Control characters and zero-width spaces are removed while newlines/tabs are kept."""
    raw = "Hello\x00World\u200b!\x08 Line 1\tTab\nLine 2\x0cEnd"
    cleaned = clean_text(raw)
    assert "\x00" not in cleaned
    assert "\u200b" not in cleaned
    assert "\x08" not in cleaned
    assert "\x0c" not in cleaned
    assert "Hello" in cleaned
    assert "Line 1\tTab" in cleaned or "Line 1 Tab" in cleaned
    assert "Line 2" in cleaned
    assert "End" in cleaned


def test_ut_clean_02_hyphenated_line_rejoining():
    """UT-CLEAN-02: Hyphenated words across line breaks rejoin when following char is lowercase."""
    raw = "Designed scalable micro-\nservices for cloud infra.\nNon-\nBreaking word."
    cleaned = clean_text(raw)
    assert "microservices" in cleaned
    # Non-\nBreaking has uppercase B, so not rejoined as a single word
    assert "Non-" in cleaned


def test_ut_clean_03_unicode_nfkc_normalization():
    """UT-CLEAN-03: Ligatures and full-width unicode characters are normalized via NFKC."""
    raw = "The ﬁnal oﬃce ﬂow in ２０２４."
    cleaned = clean_text(raw)
    assert "final" in cleaned
    assert "office" in cleaned
    assert "flow" in cleaned
    assert "2024" in cleaned


def test_ut_clean_04_bullet_point_normalization():
    """UT-CLEAN-04: Diverse bullet glyphs are normalized to standard '- ' format."""
    raw = "• Item one\n● Item two\n▪ Item three\n■ Item four\n◦ Item five\n‣ Item six\n· Item seven"
    cleaned = clean_text(raw)
    for line in cleaned.split("\n"):
        assert line.startswith("- ")


def test_ut_clean_05_idempotence():
    """UT-CLEAN-05: Clean text function is strictly idempotent."""
    samples = [
        "Simple clean text.",
        "• Multiple\n● Bullets\n\n\n\nAnd micro-\nservices with ﬁ ligatures.",
        "   Leading and trailing whitespace   \n\r\n\tText with \x00 controls.  ",
        "",
    ]
    for s in samples:
        once = clean_text(s)
        twice = clean_text(once)
        assert once == twice
