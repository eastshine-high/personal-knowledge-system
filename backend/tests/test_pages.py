"""T1 — parse_pages / format_pages 단위 테스트."""
import pytest
from app.pages import format_pages, parse_pages


# --- parse_pages ---

def test_single_page():
    assert parse_pages("5") == [5]


def test_range():
    assert parse_pages("10-15") == [10, 11, 12, 13, 14, 15]


def test_mixed():
    assert parse_pages("1-3, 7, 10-12") == [1, 2, 3, 7, 10, 11, 12]


def test_dedup_and_sort():
    assert parse_pages("5, 3, 5, 1-3") == [1, 2, 3, 5]


def test_reverse_range_raises():
    with pytest.raises(ValueError):
        parse_pages("10-5")


def test_zero_page_raises():
    with pytest.raises(ValueError):
        parse_pages("0")


def test_negative_page_raises():
    with pytest.raises(ValueError):
        parse_pages("-1")


def test_empty_raises():
    with pytest.raises(ValueError):
        parse_pages("  ")


# --- format_pages ---

def test_format_single():
    assert format_pages([5]) == "p.5"


def test_format_range():
    assert format_pages([10, 11, 12, 13, 14, 15]) == "p.10-15"


def test_format_mixed():
    assert format_pages([1, 2, 3, 7, 10, 11, 12]) == "p.1-3, 7, 10-12"


def test_format_roundtrip():
    pages = [1, 2, 3, 7, 10, 11, 12]
    assert parse_pages("1-3, 7, 10-12") == pages
