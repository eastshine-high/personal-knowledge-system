"""페이지 범위 파서 — "10-15, 21" ↔ [10,11,12,13,14,15,21]."""
from __future__ import annotations


def _parse_page_token(token: str, pages: set[int]) -> None:
    """단일 토큰("10-15" 또는 "7")을 파싱해 pages에 in-place 추가. 범위 오류 시 ValueError."""
    if "-" in token:
        parts = token.split("-", 1)
        start, end = int(parts[0].strip()), int(parts[1].strip())
        if start < 1 or end < 1:
            raise ValueError(f"페이지 번호는 1 이상이어야 합니다: {token}")
        if start > end:
            raise ValueError(f"범위 시작이 끝보다 큽니다: {token}")
        pages.update(range(start, end + 1))
    else:
        page = int(token)
        if page < 1:
            raise ValueError(f"페이지 번호는 1 이상이어야 합니다: {token}")
        pages.add(page)


def parse_pages(pages_str: str) -> list[int]:
    """혼합 페이지 문자열을 정렬·중복제거된 정수 리스트로 변환.

    지원 형식: "5", "10-15", "1-3, 7, 10-12"
    """
    pages: set[int] = set()
    for token in pages_str.split(","):
        token = token.strip()
        if token:
            _parse_page_token(token, pages)
    if not pages:
        raise ValueError("페이지 범위가 비어 있습니다")
    return sorted(pages)


def format_pages(pages: list[int]) -> str:
    """정수 리스트를 사람이 읽기 좋은 범위 문자열로 압축.

    [1,2,3,7,10,11,12] → "p.1-3, 7, 10-12"
    """
    if not pages:
        return ""
    sorted_pages = sorted(set(pages))
    groups: list[tuple[int, int]] = []
    start = end = sorted_pages[0]
    for p in sorted_pages[1:]:
        if p == end + 1:
            end = p
        else:
            groups.append((start, end))
            start = end = p
    groups.append((start, end))

    parts = [str(s) if s == e else f"{s}-{e}" for s, e in groups]
    return "p." + ", ".join(parts)
