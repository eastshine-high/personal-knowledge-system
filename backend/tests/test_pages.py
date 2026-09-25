"""pages 유틸리티 BDD 명세."""
import pytest
from app.pages import format_pages, parse_pages


class DescribeParsePages:
    """parse_pages 의 파싱 동작 명세."""

    def test_single_page_number(self):
        assert parse_pages("5") == [5]

    def test_hyphen_range_is_expanded(self):
        assert parse_pages("10-15") == [10, 11, 12, 13, 14, 15]

    def test_mixed_singles_and_ranges(self):
        assert parse_pages("1-3, 7, 10-12") == [1, 2, 3, 7, 10, 11, 12]

    def test_duplicates_are_removed_and_result_is_sorted(self):
        assert parse_pages("5, 3, 5, 1-3") == [1, 2, 3, 5]

    def test_reversed_range_raises(self):
        with pytest.raises(ValueError):
            parse_pages("10-5")

    def test_zero_page_raises(self):
        with pytest.raises(ValueError):
            parse_pages("0")

    def test_negative_page_raises(self):
        with pytest.raises(ValueError):
            parse_pages("-1")

    def test_blank_input_raises(self):
        with pytest.raises(ValueError):
            parse_pages("  ")


class DescribeFormatPages:
    """format_pages 의 표시 포맷 명세."""

    def test_single_page_is_formatted_with_p_prefix(self):
        assert format_pages([5]) == "p.5"

    def test_contiguous_range_is_compressed(self):
        assert format_pages([10, 11, 12, 13, 14, 15]) == "p.10-15"

    def test_mixed_singles_and_ranges(self):
        assert format_pages([1, 2, 3, 7, 10, 11, 12]) == "p.1-3, 7, 10-12"

    def test_parse_and_format_are_inverse_operations(self):
        pages = [1, 2, 3, 7, 10, 11, 12]
        assert parse_pages("1-3, 7, 10-12") == pages
