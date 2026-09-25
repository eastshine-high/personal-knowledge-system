"""ModalLayoutExtractor 단위 테스트 — 엔드포인트 호출은 mock(결정적, GPU 불필요).

렌더/크롭은 임시 PDF로 실제 수행하고, PaddleOCR-VL 호출(_call_endpoint)만 대체한다.
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


# --- fixtures / helpers ---------------------------------------------------

@pytest.fixture
def tiny_pdf(tmp_path):
    doc = pymupdf.open()
    doc.new_page(width=300, height=300)  # 300pt @200dpi ≈ 833px
    p = tmp_path / "tiny.pdf"
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
    ext = ModalLayoutExtractor(ModalExtractorConfig(
        endpoint_url="http://fake", api_token="tok", render_dpi=200, timeout_s=5,
        crop_dir=str(tmp_path / "crops"), warmup=False,
    ))
    ext._call_endpoint = lambda img_bytes: raw  # GPU 호출 대체
    return ext


# --- 라벨 정규화 (단위) ---------------------------------------------------

def test_normalize_label_mappings():
    assert normalize_label("image") == "figure"
    assert normalize_label("figure_title") == "figure_caption"
    assert normalize_label("display_formula") == "formula"
    assert normalize_label("formula") == "formula"
    assert normalize_label("algorithm") == "code"
    assert normalize_label("code") == "code"
    assert normalize_label("number") == "number"
    assert normalize_label("text") == "text"
    assert normalize_label("무엇이든모르는라벨") == "other"


# --- 테스트 케이스 1/5: 정상 추출 + 라벨 정규화 + reading_order nullable ---

def test_extract_normalizes_blocks(tiny_pdf, tmp_path):
    raw = _raw([
        {"order": None, "id": 0, "label": "header", "bbox": [0, 0, 100, 20], "content": "H"},
        {"order": 1, "id": 1, "label": "text", "bbox": [0, 30, 800, 60], "content": "본문1"},
        {"order": None, "id": 2, "label": "image", "bbox": [50, 80, 400, 400], "content": ""},
        {"order": None, "id": 3, "label": "figure_title", "bbox": [60, 410, 300, 440], "content": "그림 캡션"},
        {"order": 2, "id": 4, "label": "display_formula", "bbox": [50, 460, 400, 500], "content": "$$x$$"},
        {"order": None, "id": 5, "label": "number", "bbox": [790, 800, 820, 830], "content": "1"},
    ])
    res = _make_ext(raw, tmp_path).extract(tiny_pdf, (1, 1))

    assert res.pages and len(res.pages) == 1
    pe = res.pages[0]
    assert pe.page == 1 and pe.render_dpi == 200 and pe.width_px == 833

    types = [b.type for b in pe.blocks]
    assert types == ["header", "text", "figure", "figure_caption", "formula", "number"]
    orders = [b.reading_order for b in pe.blocks]
    assert orders == [None, 1, None, None, 2, None]
    # 텍스트 보존
    assert pe.blocks[1].text == "본문1"
    assert pe.blocks[4].text == "$$x$$"


# --- 테스트 케이스: figure 크롭 경로 생성 ---------------------------------

def test_figure_block_gets_crop_file(tiny_pdf, tmp_path):
    raw = _raw([
        {"order": 1, "id": 0, "label": "text", "bbox": [0, 0, 800, 30], "content": "t"},
        {"order": None, "id": 1, "label": "image", "bbox": [50, 50, 400, 300], "content": ""},
    ])
    res = _make_ext(raw, tmp_path).extract(tiny_pdf, (1, 1))
    figs = [b for b in res.pages[0].blocks if b.type == "figure"]
    assert len(figs) == 1
    ref = figs[0].image_ref
    assert ref is not None
    from pathlib import Path
    assert Path(ref).is_file()
    # 유효한 이미지인지 (열려야 함)
    assert pymupdf.Pixmap(ref).width > 0
    # 비-figure는 image_ref 없음
    assert all(b.image_ref is None for b in res.pages[0].blocks if b.type != "figure")


# --- 테스트 케이스 3: figure 없는 페이지 ----------------------------------

def test_no_figure_no_crops(tiny_pdf, tmp_path):
    raw = _raw([
        {"order": 1, "id": 0, "label": "text", "bbox": [0, 0, 800, 30], "content": "t1"},
        {"order": 2, "id": 1, "label": "text", "bbox": [0, 40, 800, 70], "content": "t2"},
    ])
    res = _make_ext(raw, tmp_path).extract(tiny_pdf, (1, 1))
    assert all(b.image_ref is None for b in res.pages[0].blocks)
    # 크롭 디렉토리는 생성되지 않아야 함
    from pathlib import Path
    assert not (tmp_path / "crops").exists()


# --- 테스트 케이스 2: 텍스트 0건 -----------------------------------------

def test_zero_text_blocks(tiny_pdf, tmp_path):
    # blocks 자체가 없는 응답
    res = _make_ext(_raw([]), tmp_path).extract(tiny_pdf, (1, 1))
    assert res.pages[0].blocks == []
    # 이미지만 있고 텍스트 블록이 전혀 없는 경우도 예외 없이 처리
    raw = _raw([{"order": None, "id": 0, "label": "image", "bbox": [10, 10, 200, 200], "content": ""}])
    res2 = _make_ext(raw, tmp_path).extract(tiny_pdf, (1, 1))
    assert [b.type for b in res2.pages[0].blocks] == ["figure"]
    assert res2.pages[0].blocks[0].text == ""


# --- 테스트 케이스 4(일부): 에러 처리 ------------------------------------

class _FakeResp:
    def __init__(self, status_code, payload=None, text="boom"):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


def _no_retry_ext():
    return ModalLayoutExtractor(ModalExtractorConfig(endpoint_url="http://fake", api_token="tok", max_retries=0, retry_backoff_s=0))


def test_endpoint_non_200_raises(monkeypatch):
    from app.extractors import modal_extractor
    monkeypatch.setattr(modal_extractor.httpx, "post", lambda *a, **k: _FakeResp(500))
    with pytest.raises(ExtractionError):
        _no_retry_ext()._call_endpoint(b"img")


def test_endpoint_network_error_raises(monkeypatch):
    from app.extractors import modal_extractor

    def boom(*a, **k):
        raise modal_extractor.httpx.ConnectError("no route")

    monkeypatch.setattr(modal_extractor.httpx, "post", boom)
    with pytest.raises(ExtractionError):
        _no_retry_ext()._call_endpoint(b"img")


# --- T6: transient 재시도 --------------------------------------------------

def test_retries_transient_500_then_succeeds(monkeypatch):
    """콜드스타트 500(lost track of input)류 → 재시도 후 200 성공."""
    from app.extractors import modal_extractor
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResp(500, text="Server has lost track of input")
        return _FakeResp(200, payload={"meta": {}, "blocks": []})

    monkeypatch.setattr(modal_extractor.httpx, "post", flaky)
    ext = ModalLayoutExtractor(ModalExtractorConfig(endpoint_url="http://fake", api_token="tok", max_retries=2, retry_backoff_s=0))
    assert ext._call_endpoint(b"img") == {"meta": {}, "blocks": []}
    assert calls["n"] == 2  # 1회 실패 + 1회 성공


def test_retries_exhausted_raises(monkeypatch):
    from app.extractors import modal_extractor
    calls = {"n": 0}

    def always_500(*a, **k):
        calls["n"] += 1
        return _FakeResp(500)

    monkeypatch.setattr(modal_extractor.httpx, "post", always_500)
    ext = ModalLayoutExtractor(ModalExtractorConfig(endpoint_url="http://fake", api_token="tok", max_retries=2, retry_backoff_s=0))
    with pytest.raises(ExtractionError):
        ext._call_endpoint(b"img")
    assert calls["n"] == 3  # 최초 1 + 재시도 2


def test_4xx_not_retried(monkeypatch):
    """4xx(인증 등 영구 오류)는 재시도하지 않고 즉시 실패."""
    from app.extractors import modal_extractor
    calls = {"n": 0}

    def unauthorized(*a, **k):
        calls["n"] += 1
        return _FakeResp(401, text="unauthorized")

    monkeypatch.setattr(modal_extractor.httpx, "post", unauthorized)
    ext = ModalLayoutExtractor(ModalExtractorConfig(endpoint_url="http://fake", api_token="tok", max_retries=2, retry_backoff_s=0))
    with pytest.raises(ExtractionError):
        ext._call_endpoint(b"img")
    assert calls["n"] == 1  # 재시도 없음


def test_state_intact_after_failure(tiny_pdf, tmp_path):
    """실패 후에도 상태 손상 없이 재시도 가능(다음 호출 성공)."""
    ext = ModalLayoutExtractor(ModalExtractorConfig(
        endpoint_url="http://fake", api_token="tok", render_dpi=200, crop_dir=str(tmp_path / "c"),
        max_retries=0, retry_backoff_s=0, warmup=False,
    ))

    def fail(_img):
        raise ExtractionError("boom")

    ext._call_endpoint = fail
    with pytest.raises(ExtractionError):
        ext.extract(tiny_pdf, (1, 1))

    # 동일 인스턴스로 다시(정상 응답) → 성공
    ext._call_endpoint = lambda _img: _raw([{"order": 1, "id": 0, "label": "text", "bbox": [0, 0, 10, 10], "content": "ok"}])
    res = ext.extract(tiny_pdf, (1, 1))
    assert res.pages[0].blocks[0].text == "ok"


def test_invalid_page_range(tiny_pdf, tmp_path):
    ext = _make_ext(_raw([]), tmp_path)
    with pytest.raises(ValueError):
        ext.extract(tiny_pdf, (0, 2))
    with pytest.raises(ValueError):
        ext.extract(tiny_pdf, (5, 3))


def test_missing_endpoint_url_raises():
    with pytest.raises(ValueError):
        ModalLayoutExtractor(ModalExtractorConfig(endpoint_url="", api_token="tok"))


# --- 팩토리(스왑 지점) ----------------------------------------------------

def _settings(backend):
    return config.Settings(
        extract_backend=backend,
        modal_endpoint_url="http://fake",
        modal_api_token="tok",
        render_dpi=200,
        request_timeout_s=5,
        crop_dir="/tmp/crops",
        max_retries=2,
        retry_backoff_s=0,
        warmup=False,
        fixtures_dir="/tmp/fixtures",
        llm_backend="mock",
        llm_model="claude-sonnet-4-6",
    )


# --- T7/A: 워밍업 핑 --------------------------------------------------------

def test_warmup_pings_health_before_extract(tiny_pdf, tmp_path, monkeypatch):
    from app.extractors import modal_extractor
    calls = {"health": 0}

    def fake_get(url, **k):
        calls["health"] += 1
        assert url.endswith("/health")
        return _FakeResp(200)

    monkeypatch.setattr(modal_extractor.httpx, "get", fake_get)
    ext = ModalLayoutExtractor(ModalExtractorConfig(
        endpoint_url="http://fake", api_token="tok", render_dpi=200, crop_dir=str(tmp_path / "c"),
        warmup=True, retry_backoff_s=0,
    ))
    ext._call_endpoint = lambda _img: _raw([])
    ext.extract(tiny_pdf, (1, 1))
    assert calls["health"] == 1  # 웜이면 즉시 200 → 1회


def test_warmup_disabled_skips_health(tiny_pdf, tmp_path, monkeypatch):
    from app.extractors import modal_extractor

    def boom_get(*a, **k):
        raise AssertionError("warmup=False인데 /health가 호출됨")

    monkeypatch.setattr(modal_extractor.httpx, "get", boom_get)
    _make_ext(_raw([]), tmp_path).extract(tiny_pdf, (1, 1))  # warmup=False → 호출 없음


def test_factory_selects_backend():
    assert isinstance(get_extractor(_settings("stub")), StubLayoutExtractor)
    assert isinstance(get_extractor(_settings("modal")), ModalLayoutExtractor)
    assert isinstance(get_extractor(_settings("fixture")), FixtureLayoutExtractor)
    with pytest.raises(NotImplementedError):
        get_extractor(_settings("local"))
    with pytest.raises(ValueError):
        get_extractor(_settings("nonsense"))


# --- FixtureLayoutExtractor (오프라인 재생) --------------------------------

def _write_fixture(fixtures_dir, page_no, blocks, w=833, h=833):
    import json
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / f"page{page_no}.json").write_text(
        json.dumps(_raw(blocks, w, h), ensure_ascii=False), encoding="utf-8"
    )


def test_fixture_extractor_replays_offline(tiny_pdf, tmp_path):
    """네트워크 없이 fixture를 재생 → 정규화 + 크롭까지 동일하게 동작."""
    fixtures = tmp_path / "fixtures"
    _write_fixture(fixtures, 1, [
        {"order": 1, "id": 0, "label": "text", "bbox": [0, 0, 800, 30], "content": "본문"},
        {"order": None, "id": 1, "label": "image", "bbox": [50, 50, 400, 300], "content": ""},
        {"order": 2, "id": 2, "label": "algorithm", "bbox": [0, 320, 800, 360], "content": "def f(): ..."},
    ])
    ext = FixtureLayoutExtractor(str(fixtures), render_dpi=200, crop_dir=str(tmp_path / "crops"))
    res = ext.extract(tiny_pdf, (1, 1))

    types = [b.type for b in res.pages[0].blocks]
    assert types == ["text", "figure", "code"]  # algorithm→code, image→figure
    fig = [b for b in res.pages[0].blocks if b.type == "figure"][0]
    from pathlib import Path
    assert fig.image_ref is not None and Path(fig.image_ref).is_file()


def test_fixture_extractor_missing_page_raises(tiny_pdf, tmp_path):
    ext = FixtureLayoutExtractor(str(tmp_path / "fixtures"), crop_dir=str(tmp_path / "crops"))
    with pytest.raises(ExtractionError):
        ext.extract(tiny_pdf, (1, 1))  # page1.json 없음


# --- 형광 표시(highlight) 추출 ------------------------------------------------

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
    """텍스트 레이어 없는 PDF + 형광 표시 (OCR 폴백 테스트용)."""
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    annot = page.add_highlight_annot(pymupdf.Rect(8, 38, 200, 62))
    annot.update()
    p = tmp_path / "no_text_highlighted.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def test_highlight_with_text_layer(highlighted_pdf, tmp_path):
    """형광 표시 영역의 텍스트 레이어에서 텍스트를 추출한다."""
    ext = _make_ext(_raw([]), tmp_path)
    res = ext.extract(highlighted_pdf, (1, 1))
    assert len(res.pages[0].highlights) == 1
    assert "Important" in res.pages[0].highlights[0]


def test_no_annotation_no_highlights(tiny_pdf, tmp_path):
    """형광 표시 없는 PDF → highlights 빈 리스트."""
    ext = _make_ext(_raw([]), tmp_path)
    res = ext.extract(tiny_pdf, (1, 1))
    assert res.pages[0].highlights == []


def test_highlight_ocr_fallback(no_text_highlighted_pdf, tmp_path):
    """텍스트 레이어 없을 때 OCR 블록으로 폴백한다."""
    # Annotation rect: Rect(8, 38, 200, 62) in PDF points
    # render_dpi=200 → scale = 200/72; pixel bbox ≈ [22, 105, 556, 172]
    sx = 200 / 72
    raw = _raw([{
        "order": 1, "id": 0, "label": "text",
        "bbox": [round(8 * sx), round(38 * sx), round(200 * sx), round(62 * sx)],
        "content": "OCR 폴백 텍스트",
    }])
    ext = _make_ext(raw, tmp_path)
    res = ext.extract(no_text_highlighted_pdf, (1, 1))
    assert res.pages[0].highlights == ["OCR 폴백 텍스트"]
