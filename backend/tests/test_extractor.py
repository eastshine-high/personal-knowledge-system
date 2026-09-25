"""ModalLayoutExtractor BDD 명세 — 엔드포인트 호출은 mock(결정적, GPU 불필요).

렌더·크롭은 임시 PDF로 실제 수행하고, PaddleOCR-VL 호출(_call_endpoint)만 대체한다.
"""
from __future__ import annotations

import pymupdf
import pytest

from app import config
from app.extractor import BlockType, StubLayoutExtractor, normalize_label
from app.extractors import (
    ExtractionError,
    FixtureLayoutExtractor,
    ModalLayoutExtractor,
    get_extractor,
)
from app.extractors.modal_extractor import ModalExtractorConfig


# ---------------------------------------------------------------------------
# 공용 fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def tiny_pdf(tmp_path):
    doc = pymupdf.open()
    doc.new_page(width=300, height=300)
    p = tmp_path / "tiny.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


@pytest.fixture
def highlighted_pdf(tmp_path):
    """텍스트 레이어 + 형광 표시 1개가 있는 PDF."""
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((10, 50), "Important concept here", fontsize=12)
    annot = page.add_highlight_annot(pymupdf.Rect(8, 38, 200, 62))
    annot.update()
    p = tmp_path / "highlighted.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


@pytest.fixture
def no_text_highlighted_pdf(tmp_path):
    """텍스트 레이어 없는 PDF + 형광 표시 — OCR 폴백 테스트용."""
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    annot = page.add_highlight_annot(pymupdf.Rect(8, 38, 200, 62))
    annot.update()
    p = tmp_path / "no_text.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def _raw(blocks, w=833, h=833):
    return {
        "predict_seconds": 0.0,
        "meta": {"width": w, "height": h, "labels": sorted({b["label"] for b in blocks})},
        "blocks": blocks,
        "markdown": "",
    }


def _make_ext(raw, tmp_path):
    """GPU 호출을 대체한 ModalLayoutExtractor."""
    ext = ModalLayoutExtractor(ModalExtractorConfig(
        endpoint_url="http://fake", api_token="tok",
        render_dpi=200, timeout_s=5, crop_dir=str(tmp_path / "crops"), warmup=False,
    ))
    ext._call_endpoint = lambda img_bytes: raw
    return ext


def _no_retry_ext():
    return ModalLayoutExtractor(ModalExtractorConfig(
        endpoint_url="http://fake", api_token="tok", max_retries=0, retry_backoff_s=0,
    ))


class _FakeResp:
    def __init__(self, status_code, payload=None, text="boom"):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
    def json(self): return self._payload


def _settings(backend):
    return config.Settings(
        extract_backend=backend, modal_endpoint_url="http://fake", modal_api_token="tok",
        render_dpi=200, request_timeout_s=5, crop_dir="/tmp/crops", max_retries=2,
        retry_backoff_s=0, warmup=False, fixtures_dir="/tmp/fixtures",
        llm_backend="mock", llm_model="claude-sonnet-4-6",
    )


# ---------------------------------------------------------------------------
# Describe: 라벨 정규화
# ---------------------------------------------------------------------------

class DescribeLabelNormalization:
    """normalize_label 의 동작 명세."""

    def test_maps_all_known_raw_labels_to_canonical_types(self):
        assert normalize_label("image") == "figure"
        assert normalize_label("figure_title") == "figure_caption"
        assert normalize_label("display_formula") == "formula"
        assert normalize_label("formula") == "formula"
        assert normalize_label("algorithm") == "code"
        assert normalize_label("code") == "code"
        assert normalize_label("number") == "number"
        assert normalize_label("text") == "text"

    def test_unknown_label_falls_back_to_other(self):
        assert normalize_label("무엇이든모르는라벨") == "other"


# ---------------------------------------------------------------------------
# Describe: 정상 추출
# ---------------------------------------------------------------------------

class DescribeExtraction:
    """ModalLayoutExtractor 정상 추출 경로의 동작 명세."""

    def test_normalizes_labels_and_preserves_nullable_reading_order(self, tiny_pdf, tmp_path):
        # Given a raw response with mixed labels and some null reading orders
        raw = _raw([
            {"order": None, "id": 0, "label": "header",         "bbox": [0, 0, 100, 20], "content": "H"},
            {"order": 1,    "id": 1, "label": "text",           "bbox": [0, 30, 800, 60], "content": "본문1"},
            {"order": None, "id": 2, "label": "image",          "bbox": [50, 80, 400, 400], "content": ""},
            {"order": None, "id": 3, "label": "figure_title",   "bbox": [60, 410, 300, 440], "content": "그림 캡션"},
            {"order": 2,    "id": 4, "label": "display_formula","bbox": [50, 460, 400, 500], "content": "$$x$$"},
            {"order": None, "id": 5, "label": "number",         "bbox": [790, 800, 820, 830], "content": "1"},
        ])

        # When extracted
        res = _make_ext(raw, tmp_path).extract(tiny_pdf, (1, 1))
        pe = res.pages[0]

        # Then labels are normalized and reading_order is preserved (including None)
        assert pe.page == 1 and pe.render_dpi == 200 and pe.width_px == 833
        assert [b.type for b in pe.blocks] == ["header", "text", "figure", "figure_caption", "formula", "number"]
        assert [b.reading_order for b in pe.blocks] == [None, 1, None, None, 2, None]
        assert pe.blocks[1].text == "본문1"
        assert pe.blocks[4].text == "$$x$$"

    def test_figure_block_gets_a_crop_file(self, tiny_pdf, tmp_path):
        # Given a raw response with a figure block
        raw = _raw([
            {"order": 1,    "id": 0, "label": "text",  "bbox": [0, 0, 800, 30], "content": "t"},
            {"order": None, "id": 1, "label": "image", "bbox": [50, 50, 400, 300], "content": ""},
        ])

        # When extracted
        res = _make_ext(raw, tmp_path).extract(tiny_pdf, (1, 1))
        figs = [b for b in res.pages[0].blocks if b.type == "figure"]

        # Then the figure has an image_ref pointing to a real PNG file
        assert len(figs) == 1
        from pathlib import Path
        assert figs[0].image_ref is not None
        assert Path(figs[0].image_ref).is_file()
        assert pymupdf.Pixmap(figs[0].image_ref).width > 0
        assert all(b.image_ref is None for b in res.pages[0].blocks if b.type != "figure")

    def test_page_with_no_figures_creates_no_crop_directory(self, tiny_pdf, tmp_path):
        # Given a raw response with only text blocks
        raw = _raw([
            {"order": 1, "id": 0, "label": "text", "bbox": [0, 0, 800, 30], "content": "t1"},
            {"order": 2, "id": 1, "label": "text", "bbox": [0, 40, 800, 70], "content": "t2"},
        ])

        # When extracted
        res = _make_ext(raw, tmp_path).extract(tiny_pdf, (1, 1))

        # Then no image_refs exist and the crops directory is not created
        assert all(b.image_ref is None for b in res.pages[0].blocks)
        from pathlib import Path
        assert not (tmp_path / "crops").exists()

    def test_empty_blocks_response_is_handled(self, tiny_pdf, tmp_path):
        # Given a raw response with no blocks at all
        res = _make_ext(_raw([]), tmp_path).extract(tiny_pdf, (1, 1))
        assert res.pages[0].blocks == []

        # And a response with only a figure (no text) also works
        raw = _raw([{"order": None, "id": 0, "label": "image", "bbox": [10, 10, 200, 200], "content": ""}])
        res2 = _make_ext(raw, tmp_path).extract(tiny_pdf, (1, 1))
        assert [b.type for b in res2.pages[0].blocks] == ["figure"]

    def test_invalid_page_range_raises(self, tiny_pdf, tmp_path):
        ext = _make_ext(_raw([]), tmp_path)
        with pytest.raises(ValueError): ext.extract(tiny_pdf, (0, 2))   # page 0 invalid
        with pytest.raises(ValueError): ext.extract(tiny_pdf, (5, 3))   # reversed range

    def test_missing_endpoint_url_raises_on_construction(self):
        with pytest.raises(ValueError):
            ModalLayoutExtractor(ModalExtractorConfig(endpoint_url="", api_token="tok"))


# ---------------------------------------------------------------------------
# Describe: 에러 처리 + 재시도
# ---------------------------------------------------------------------------

class DescribeErrorHandlingAndRetry:
    """엔드포인트 오류·재시도 동작 명세."""

    def test_non_200_response_raises_extraction_error(self, monkeypatch):
        # Given the endpoint returns 500
        from app.extractors import modal_extractor
        monkeypatch.setattr(modal_extractor.httpx, "post", lambda *a, **k: _FakeResp(500))

        # Then ExtractionError is raised
        with pytest.raises(ExtractionError):
            _no_retry_ext()._call_endpoint(b"img")

    def test_network_error_raises_extraction_error(self, monkeypatch):
        # Given a network failure
        from app.extractors import modal_extractor
        monkeypatch.setattr(modal_extractor.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(modal_extractor.httpx.ConnectError("no route")))

        # Then ExtractionError is raised
        with pytest.raises(ExtractionError):
            _no_retry_ext()._call_endpoint(b"img")

    def test_transient_500_is_retried_and_succeeds_on_second_attempt(self, monkeypatch):
        # Given the first call returns 500 (transient) and the second returns 200
        from app.extractors import modal_extractor
        calls = {"n": 0}
        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1: return _FakeResp(500, text="Server lost track")
            return _FakeResp(200, payload={"meta": {}, "blocks": []})
        monkeypatch.setattr(modal_extractor.httpx, "post", flaky)
        ext = ModalLayoutExtractor(ModalExtractorConfig(endpoint_url="http://fake", api_token="tok", max_retries=2, retry_backoff_s=0))

        # When _call_endpoint is invoked
        result = ext._call_endpoint(b"img")

        # Then it succeeds after 1 retry
        assert result == {"meta": {}, "blocks": []}
        assert calls["n"] == 2

    def test_retries_exhausted_raises_after_max_attempts(self, monkeypatch):
        # Given the endpoint always returns 500
        from app.extractors import modal_extractor
        calls = {"n": 0}
        def always_500(*a, **k):
            calls["n"] += 1
            return _FakeResp(500)
        monkeypatch.setattr(modal_extractor.httpx, "post", always_500)
        ext = ModalLayoutExtractor(ModalExtractorConfig(endpoint_url="http://fake", api_token="tok", max_retries=2, retry_backoff_s=0))

        # Then ExtractionError is raised and all attempts are used
        with pytest.raises(ExtractionError):
            ext._call_endpoint(b"img")
        assert calls["n"] == 3  # 최초 1 + 재시도 2

    def test_4xx_error_is_not_retried(self, monkeypatch):
        # Given the endpoint returns 401 (permanent error)
        from app.extractors import modal_extractor
        calls = {"n": 0}
        def unauthorized(*a, **k):
            calls["n"] += 1
            return _FakeResp(401, text="unauthorized")
        monkeypatch.setattr(modal_extractor.httpx, "post", unauthorized)
        ext = ModalLayoutExtractor(ModalExtractorConfig(endpoint_url="http://fake", api_token="tok", max_retries=2, retry_backoff_s=0))

        # Then it raises immediately without retrying
        with pytest.raises(ExtractionError):
            ext._call_endpoint(b"img")
        assert calls["n"] == 1  # 재시도 없음

    def test_state_is_intact_after_failure_allowing_retry(self, tiny_pdf, tmp_path):
        # Given an extractor that fails on the first call
        ext = ModalLayoutExtractor(ModalExtractorConfig(
            endpoint_url="http://fake", api_token="tok",
            render_dpi=200, crop_dir=str(tmp_path / "c"), max_retries=0, retry_backoff_s=0, warmup=False,
        ))
        ext._call_endpoint = lambda _img: (_ for _ in ()).throw(ExtractionError("boom"))
        with pytest.raises(ExtractionError):
            ext.extract(tiny_pdf, (1, 1))

        # When the same instance is reused with a working endpoint
        ext._call_endpoint = lambda _img: _raw([{"order": 1, "id": 0, "label": "text", "bbox": [0, 0, 10, 10], "content": "ok"}])
        res = ext.extract(tiny_pdf, (1, 1))

        # Then it succeeds (state was not corrupted)
        assert res.pages[0].blocks[0].text == "ok"


# ---------------------------------------------------------------------------
# Describe: 워밍업 핑
# ---------------------------------------------------------------------------

class DescribeWarmup:
    """워밍업 /health 핑 동작 명세."""

    def test_pings_health_endpoint_before_first_extract(self, tiny_pdf, tmp_path, monkeypatch):
        # Given warmup=True and a healthy endpoint
        from app.extractors import modal_extractor
        calls = {"health": 0}
        def fake_get(url, **k):
            calls["health"] += 1
            assert url.endswith("/health")
            return _FakeResp(200)
        monkeypatch.setattr(modal_extractor.httpx, "get", fake_get)
        ext = ModalLayoutExtractor(ModalExtractorConfig(
            endpoint_url="http://fake", api_token="tok",
            render_dpi=200, crop_dir=str(tmp_path / "c"), warmup=True, retry_backoff_s=0,
        ))
        ext._call_endpoint = lambda _img: _raw([])

        # When extract is called
        ext.extract(tiny_pdf, (1, 1))

        # Then health was pinged exactly once (warm container → immediate 200)
        assert calls["health"] == 1

    def test_warmup_disabled_skips_health_ping(self, tiny_pdf, tmp_path, monkeypatch):
        # Given warmup=False
        from app.extractors import modal_extractor
        monkeypatch.setattr(modal_extractor.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("warmup=False인데 /health 호출됨")))

        # Then health is never pinged
        _make_ext(_raw([]), tmp_path).extract(tiny_pdf, (1, 1))


# ---------------------------------------------------------------------------
# Describe: 팩토리
# ---------------------------------------------------------------------------

class DescribeExtractorFactory:
    """get_extractor 팩토리 선택 동작 명세."""

    def test_selects_correct_implementation_per_backend_setting(self):
        assert isinstance(get_extractor(_settings("stub")), StubLayoutExtractor)
        assert isinstance(get_extractor(_settings("modal")), ModalLayoutExtractor)
        assert isinstance(get_extractor(_settings("fixture")), FixtureLayoutExtractor)
        with pytest.raises(NotImplementedError): get_extractor(_settings("local"))
        with pytest.raises(ValueError): get_extractor(_settings("nonsense"))


# ---------------------------------------------------------------------------
# Describe: FixtureLayoutExtractor
# ---------------------------------------------------------------------------

def _write_fixture(fixtures_dir, page_no, blocks, w=833, h=833):
    import json
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / f"page{page_no}.json").write_text(
        json.dumps(_raw(blocks, w, h), ensure_ascii=False), encoding="utf-8"
    )


class DescribeFixtureExtractor:
    """FixtureLayoutExtractor(오프라인 재생) 동작 명세."""

    def test_replays_offline_fixture_with_full_normalization_and_crops(self, tiny_pdf, tmp_path):
        # Given a fixture file with mixed block types
        fixtures = tmp_path / "fixtures"
        _write_fixture(fixtures, 1, [
            {"order": 1,    "id": 0, "label": "text",      "bbox": [0, 0, 800, 30], "content": "본문"},
            {"order": None, "id": 1, "label": "image",     "bbox": [50, 50, 400, 300], "content": ""},
            {"order": 2,    "id": 2, "label": "algorithm", "bbox": [0, 320, 800, 360], "content": "def f(): ..."},
        ])
        ext = FixtureLayoutExtractor(str(fixtures), render_dpi=200, crop_dir=str(tmp_path / "crops"))

        # When extracted
        res = ext.extract(tiny_pdf, (1, 1))

        # Then types are normalized (algorithm→code, image→figure) and figure has a crop file
        assert [b.type for b in res.pages[0].blocks] == ["text", "figure", "code"]
        fig = [b for b in res.pages[0].blocks if b.type == "figure"][0]
        from pathlib import Path
        assert fig.image_ref is not None and Path(fig.image_ref).is_file()

    def test_missing_fixture_file_raises(self, tiny_pdf, tmp_path):
        # Given a fixtures directory with no page1.json
        ext = FixtureLayoutExtractor(str(tmp_path / "fixtures"), crop_dir=str(tmp_path / "crops"))

        # Then ExtractionError is raised
        with pytest.raises(ExtractionError):
            ext.extract(tiny_pdf, (1, 1))


# ---------------------------------------------------------------------------
# Describe: 형광 표시(highlight) 추출
# ---------------------------------------------------------------------------

class DescribeHighlightExtraction:
    """GoodNotes 형광 표시 → highlights 추출 동작 명세."""

    def test_extracts_highlighted_text_from_annotation_layer(self, highlighted_pdf, tmp_path):
        # Given a PDF with a highlight annotation over a text layer
        ext = _make_ext(_raw([]), tmp_path)

        # When extracted
        res = ext.extract(highlighted_pdf, (1, 1))

        # Then the highlighted text is captured
        assert len(res.pages[0].highlights) == 1
        assert "Important" in res.pages[0].highlights[0]

    def test_no_annotation_yields_empty_highlights(self, tiny_pdf, tmp_path):
        # Given a PDF with no annotations
        ext = _make_ext(_raw([]), tmp_path)

        # When extracted
        res = ext.extract(tiny_pdf, (1, 1))

        # Then highlights is an empty list
        assert res.pages[0].highlights == []

    def test_falls_back_to_ocr_blocks_when_text_layer_is_absent(self, no_text_highlighted_pdf, tmp_path):
        # Given a PDF with a highlight but no text layer, and OCR blocks covering the annotation rect
        sx = 200 / 72  # render_dpi / pdf_point
        raw = _raw([{
            "order": 1, "id": 0, "label": "text",
            "bbox": [round(8 * sx), round(38 * sx), round(200 * sx), round(62 * sx)],
            "content": "OCR 폴백 텍스트",
        }])
        ext = _make_ext(raw, tmp_path)

        # When extracted
        res = ext.extract(no_text_highlighted_pdf, (1, 1))

        # Then the OCR text from the overlapping block is used as the highlight
        assert res.pages[0].highlights == ["OCR 폴백 텍스트"]
