"""노트 조립 + 리파인 엔진 테스트 (Sprint 2). LLM은 mock으로 결정적."""
from __future__ import annotations

from app.extractor import BBox, Block, ExtractionResult, PageExtraction
from app.llm import MockLLMClient, get_llm_client
from app.notes import (
    Note,
    NoteDraft,
    NoteFigure,
    EmptyTextError,
    NoteSession,
    PreparedContext,
    PreparedFigure,
    build_session,
    make_note_id,
    prepare_context,
    refine,
    summarize,
)


class _BoomLLMClient:
    """complete()가 항상 예외를 던지는 테스트용 LLM (오류 처리 검증)."""

    def complete(self, messages):
        raise RuntimeError("LLM 다운")


class _SpyLLMClient:
    """LLM에 실제로 전달된 메시지를 기록(PII 경계 검증). mock에 위임."""

    def __init__(self):
        self.seen = []
        self._mock = MockLLMClient()

    def complete(self, messages):
        self.seen.append(messages)
        return self._mock.complete(messages)

    def all_content(self):
        return "\n".join(m.content for msgs in self.seen for m in msgs)


class _FakeExtractor:
    """extract()가 미리 준비한 ExtractionResult를 돌려주는 테스트용 추출기."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def extract(self, pdf_path, page_range):
        self.calls.append((pdf_path, page_range))
        return self.result


def _ctx(text="쿼리 키 값으로 어텐션을 계산한다.", figures=None):
    return PreparedContext(text=text, figures=figures or [])


def _pfig(source_path, caption, page=200):
    return PreparedFigure(source_path=source_path, caption=caption, page=page, anchor_index=1, bbox=BBox(0, 0, 1, 1))


def _session(ctx, *, note_source="Building-AI-Agent.pdf", pages=None, topic="셀프 어텐션", guideline=None):
    return NoteSession(
        client=MockLLMClient(), context=ctx, source=note_source,
        pages=pages or [200], topic=topic, guideline=guideline, created="2026-08-31",
    )


def _blk(btype, y, text="", ref=None, h=20):
    """세로 위치 y·높이 h로 배치된 블록 하나 (bbox=(0,y,100,y+h))."""
    return Block(type=btype, bbox=BBox(0, y, 100, y + h), reading_order=None, text=text, image_ref=ref)


def _result(pages_blocks):
    """{page_no: [blocks]} → ExtractionResult."""
    pages = [PageExtraction(page=pg, blocks=blks) for pg, blks in pages_blocks.items()]
    return ExtractionResult(source="s.pdf", pages=pages)


# --- T1: 모델 + 프론트매터 ------------------------------------------------

def test_frontmatter_has_all_fields():
    note = Note(
        id="abc123",
        title="셀프 어텐션",
        source="Building-AI-Agent.pdf",
        pages=[42, 43, 44],
        topic="어텐션 메커니즘",
        created="2026-08-31",
        body="본문 요약.",
    )
    md = note.to_markdown()
    assert md.startswith("---\n")
    for line in (
        "id: abc123",
        'title: "셀프 어텐션"',
        'source: "Building-AI-Agent.pdf"',
        "pages: [42, 43, 44]",
        'topic: "어텐션 메커니즘"',
        "tags: []",
        "created: 2026-08-31",
    ):
        assert line in md, line
    # 프론트매터가 닫히고 본문이 뒤에 온다
    assert "---\n\n본문 요약." in md


def test_frontmatter_escapes_quotes():
    note = Note(
        id="x", title='제목 "인용" 포함', source="s.pdf", pages=[1],
        topic="t", created="2026-01-01",
    )
    assert 'title: "제목 \\"인용\\" 포함"' in note.to_markdown()


def test_note_id_is_deterministic_and_distinct():
    a = make_note_id("s.pdf", [42, 43], "topic")
    b = make_note_id("s.pdf", [42, 43], "topic")
    assert a == b  # 같은 입력 → 같은 id
    # 노트 index가 다르면(분할) 다른 id
    assert make_note_id("s.pdf", [42, 43], "topic", 0) != make_note_id("s.pdf", [42, 43], "topic", 1)
    # 범위/주제가 다르면 다른 id
    assert make_note_id("s.pdf", [42], "topic") != make_note_id("s.pdf", [43], "topic")


def test_note_draft_shape():
    d = NoteDraft(title="T", body="B")
    assert d.title == "T" and d.body == "B"


def test_note_figure_shape():
    f = NoteFigure(embed_name="s-p1-fig1.png", source_path="/tmp/crop.png", caption="그림 1")
    assert f.embed_name.endswith(".png") and f.caption == "그림 1"


# --- T2: 텍스트 추림 + 그림↔캡션 페어링 -----------------------------------

def test_prepare_pairs_figure_with_caption_and_keeps_order():
    # page 200 유사: code, para1, [figure, caption], para2, (header/number 잡음)
    res = _result({200: [
        _blk("header", 76, "머리글"),
        _blk("code", 100, "print(x)"),
        _blk("text", 200, "본문 앞"),
        _blk("figure", 700, "", ref="/crop/p200_fig.png", h=550),  # 큰 그림 (700~1250)
        _blk("figure_caption", 1270, "그림 5.21 벡터 DB"),   # 그림 바로 아래(gap 20)
        _blk("text", 1400, "본문 뒤"),
        _blk("number", 2200, "200"),
    ]})
    ctx = prepare_context(res)

    # 텍스트: content 블록만, 읽기순서 유지 (header/number/caption 제외)
    assert ctx.text == "print(x)\n\n본문 앞\n\n본문 뒤"
    # 그림 1개, 캡션 페어링, 앵커=그림 앞 텍스트 2개(code, para1)
    assert len(ctx.figures) == 1
    fig = ctx.figures[0]
    assert fig.caption == "그림 5.21 벡터 DB"
    assert fig.source_path == "/crop/p200_fig.png"
    assert fig.anchor_index == 2
    assert fig.page == 200


def test_prepare_multipage_text_in_page_then_reading_order():
    res = _result({
        250: [_blk("text", 100, "250-A"), _blk("text", 300, "250-B")],
        251: [_blk("text", 100, "251-A")],
    })
    ctx = prepare_context(res)
    assert ctx.text == "250-A\n\n250-B\n\n251-A"
    assert ctx.figures == []


def test_prepare_figure_without_caption():
    res = _result({1: [
        _blk("text", 100, "본문"),
        _blk("figure", 300, "", ref="/crop/f.png"),
        # 캡션 없음
    ]})
    ctx = prepare_context(res)
    assert len(ctx.figures) == 1 and ctx.figures[0].caption == ""


def test_prepare_distant_caption_not_paired():
    # 캡션이 임계값보다 멀리 있으면 페어링 안 함
    res = _result({1: [
        _blk("figure", 100, "", ref="/crop/f.png"),
        _blk("figure_caption", 2000, "멀리 있는 캡션"),
    ]})
    ctx = prepare_context(res, caption_gap_threshold_px=250)
    assert ctx.figures[0].caption == ""


def test_prepare_pii_text_excludes_paths_and_bbox():
    res = _result({1: [
        _blk("text", 100, "요약할 본문"),
        _blk("figure", 300, "", ref="/secret/crop/path.png"),
    ]})
    ctx = prepare_context(res)
    # LLM으로 갈 text에 이미지 경로/좌표가 섞이지 않는다
    assert "/secret/crop/path.png" not in ctx.text
    assert ctx.text == "요약할 본문"


# --- T3: LLMClient + summarize/refine 프롬프트 빌더 ------------------------

def test_get_llm_client_mock_and_stubs():
    from app.config import Settings

    def _s(backend):
        return Settings(
            extract_backend="fixture", modal_endpoint_url="", modal_api_token="",
            render_dpi=200, request_timeout_s=5, crop_dir="/tmp", max_retries=0,
            retry_backoff_s=0, warmup=False, fixtures_dir="/tmp", llm_backend=backend,
        )

    assert isinstance(get_llm_client(_s("mock")), MockLLMClient)
    import pytest
    for stub in ("anthropic", "openai", "local"):
        with pytest.raises(NotImplementedError):
            get_llm_client(_s(stub))
    with pytest.raises(ValueError):
        get_llm_client(_s("nonsense"))


def test_summarize_reflects_topic_and_guideline():
    drafts = summarize(
        MockLLMClient(), "쿼리 키 값으로 어텐션을 계산한다. 스케일드 닷프로덕트.",
        topic="셀프 어텐션", guideline="수식 중심으로",
    )
    assert len(drafts) == 1
    d = drafts[0]
    assert d.title == "셀프 어텐션"          # topic 반영
    assert "수식 중심으로" in d.body          # guideline 반영
    assert "쿼리 키 값" in d.body             # 원문 발췌 반영


def test_summarize_multiple_notes():
    drafts = summarize(MockLLMClient(), "본문 텍스트.", topic="주제", note_count=2)
    assert len(drafts) == 2
    # 관점(aspect)이 제목에 반영되어 서로 구분됨
    assert drafts[0].title != drafts[1].title


def test_refine_reflects_instruction():
    d = refine(
        MockLLMClient(),
        'TITLE: 원본 제목\n\n원본 본문입니다.',
        "더 짧게 요약해줘",
        text="원문 텍스트.",
    )
    assert d.title == "원본 제목"                     # 기존 제목 유지
    assert "더 짧게 요약해줘" in d.body                # 지시 반영


def test_parse_draft_lenient_without_title():
    # TITLE: 없는 출력도 관대하게 파싱
    from app.notes.summarize import _parse_draft

    d = _parse_draft("그냥 첫 줄\n둘째 줄")
    assert d.title == "그냥 첫 줄"
    assert "둘째 줄" in d.body


# --- T4: NoteSession.start (조립 + 그림 첨부) ------------------------------

def test_start_builds_note_with_frontmatter_and_figure():
    ctx = _ctx(figures=[_pfig("/crop/p200_fig.png", "그림 5.21 벡터 DB", page=200)])
    notes = _session(ctx, topic="RAG").start()
    assert len(notes) == 1
    note = notes[0]
    # 프론트매터 렌더 확인
    md = note.to_markdown()
    assert 'topic: "RAG"' in md and "created: 2026-08-31" in md
    # 그림 첨부: 옵시디언 파일명 rename + 캡션 (to_markdown이 figures에서 렌더)
    md_note = note.to_markdown()
    assert "![[Building-AI-Agent-p200-fig1.png]]" in md_note
    assert "그림 5.21 벡터 DB" in md_note
    assert "![[" not in note.body  # body에는 임베드가 없다(figures에서만 렌더)
    assert len(note.figures) == 1
    assert note.figures[0].embed_name == "Building-AI-Agent-p200-fig1.png"
    assert note.figures[0].source_path == "/crop/p200_fig.png"


def test_start_guideline_reflected_in_note():
    notes = _session(_ctx(), guideline="초보자용으로").start()
    assert "초보자용으로" in notes[0].body


def test_start_multiple_notes_distinct_ids():
    ctx = _ctx(figures=[_pfig("/crop/f.png", "cap")])
    notes = _session(ctx).start(note_count=2)
    assert len(notes) == 2
    assert notes[0].id != notes[1].id
    # v1: 그림은 첫 노트에만 첨부
    assert len(notes[0].figures) == 1
    assert len(notes[1].figures) == 0


def test_start_renames_multiple_figures_same_page():
    ctx = _ctx(figures=[
        _pfig("/crop/a.png", "A", page=250),
        _pfig("/crop/b.png", "B", page=250),
    ])
    note = _session(ctx, pages=[250]).start()[0]
    names = [f.embed_name for f in note.figures]
    assert names == ["Building-AI-Agent-p250-fig1.png", "Building-AI-Agent-p250-fig2.png"]


def test_start_skips_crop_failed_figure():
    ctx = _ctx(figures=[_pfig("", "크롭 실패")])  # source_path 빈 값
    note = _session(ctx).start()[0]
    assert note.figures == []
    assert "![[" not in note.to_markdown()


def test_figure_embed_survives_refine_and_edit():
    """결함 #1 회귀: refine·apply_edit로 body를 바꿔도 export md에 그림 임베드가 유지."""
    ctx = _ctx(figures=[_pfig("/crop/f.png", "그림 1", page=200)])
    sess = _session(ctx)
    note = sess.start()[0]
    embed = "![[Building-AI-Agent-p200-fig1.png]]"
    assert embed in note.to_markdown()

    sess.refine("본문 재작성")            # body 통째로 갱신
    assert embed in note.to_markdown()   # 여전히 유지

    sess.apply_edit(note.id, "완전히 새로 쓴 본문")  # 직접 편집으로 body 교체
    assert embed in note.to_markdown()   # 그래도 유지 (figures 1급 상태)


# --- T5: refine + apply_edit ---------------------------------------------

def test_refine_updates_note_and_preserves_frontmatter():
    ctx = _ctx(figures=[_pfig("/crop/f.png", "cap")])
    sess = _session(ctx, topic="RAG")
    note = sess.start()[0]
    before_id, before_source, before_pages = note.id, note.source, note.pages
    before_figs = list(note.figures)

    sess.refine("더 짧게 요약해줘")
    # 지시 반영
    assert "더 짧게 요약해줘" in note.body
    # 프론트매터·그림 유지
    assert note.id == before_id and note.source == before_source and note.pages == before_pages
    assert note.figures == before_figs
    # history 기록
    assert sess.history[-1]["action"] == "refine"
    assert sess.history[-1]["instruction"] == "더 짧게 요약해줘"


def test_apply_edit_becomes_basis_for_next_refine():
    sess = _session(_ctx())
    note = sess.start()[0]
    sess.apply_edit(note.id, "내가 직접 쓴 본문이다.")
    assert note.body == "내가 직접 쓴 본문이다."
    assert sess.history[-1]["action"] == "apply_edit"

    # 이후 refine이 편집본을 기준으로 함 (mock이 현재 본문을 에코)
    sess.refine("보강해줘")
    assert "내가 직접 쓴 본문이다." in note.body
    assert "[리파인 반영: 보강해줘]" in note.body


def test_refine_all_notes_when_no_id():
    sess = _session(_ctx())
    notes = sess.start(note_count=2)
    sess.refine("톤 통일")
    assert all("톤 통일" in n.body for n in notes)


def test_refine_and_edit_unknown_id_raises():
    sess = _session(_ctx())
    sess.start()
    import pytest
    with pytest.raises(ValueError):
        sess.refine("x", note_id="없는id")
    with pytest.raises(ValueError):
        sess.apply_edit("없는id", "본문")


# --- T6: build_session 오케스트레이션 -------------------------------------

def test_build_session_connects_extract_prepare_start():
    res = _result({
        250: [
            _blk("text", 100, "250 본문"),
            _blk("figure", 300, "", ref="/c/f250.png", h=200),   # 300~500
            _blk("figure_caption", 520, "그림 A"),                # gap 20 → 페어링
        ],
        251: [_blk("text", 100, "251 본문")],
    })
    res.source = "Building-AI-Agent.pdf"
    fake = _FakeExtractor(res)

    sess = build_session(
        "x.pdf", (250, 251), topic="지식그래프", created="2026-09-02",
        extractor=fake, client=MockLLMClient(),
    )
    # 추출이 범위로 1회 호출됨
    assert fake.calls == [("x.pdf", (250, 251))]
    # start까지 실행되어 노트 존재
    assert len(sess.notes) == 1
    note = sess.notes[0]
    assert note.source == "Building-AI-Agent.pdf"
    assert note.pages == [250, 251]           # 실제 추출된 페이지
    assert "250 본문" in note.body            # 다중 페이지 텍스트 연결
    # 그림 첨부(rename + 캡션 페어링)
    assert note.figures[0].embed_name == "Building-AI-Agent-p250-fig1.png"
    assert note.figures[0].caption == "그림 A"


def test_build_session_note_count():
    res = _result({1: [_blk("text", 100, "본문")]})
    sess = build_session(
        "x.pdf", (1, 1), topic="t", created="2026-09-02", note_count=2,
        extractor=_FakeExtractor(res), client=MockLLMClient(),
    )
    assert len(sess.notes) == 2


# --- T7: 에지 (텍스트 0건 / LLM 오류) -------------------------------------

def test_start_empty_text_raises_and_saves_nothing():
    import pytest
    sess = _session(_ctx(text="   "))  # 공백뿐
    with pytest.raises(EmptyTextError):
        sess.start()
    assert sess.notes == []  # 빈 노트 저장 안 함


def test_build_session_empty_text_raises():
    import pytest
    # figure만 있고 텍스트 블록 없음
    res = _result({1: [_blk("figure", 100, "", ref="/c/f.png")]})
    with pytest.raises(EmptyTextError):
        build_session("x.pdf", (1, 1), topic="t", created="2026-09-02",
                      extractor=_FakeExtractor(res), client=MockLLMClient())


def test_start_llm_error_propagates_and_state_intact():
    import pytest
    sess = _session(_ctx())
    sess.client = _BoomLLMClient()
    with pytest.raises(RuntimeError):
        sess.start()
    assert sess.notes == []  # 상태 손상 없음


def test_refine_llm_error_keeps_previous_notes():
    sess = _session(_ctx())
    note = sess.start()[0]           # mock으로 정상 생성
    before_body = note.body
    sess.client = _BoomLLMClient()   # 이후 LLM 다운
    import pytest
    with pytest.raises(RuntimeError):
        sess.refine("다듬어줘")
    # 이전 노트가 그대로 유지(부분 갱신 없음)
    assert note.body == before_body
    assert sess.history[-1]["action"] == "start"  # 실패한 refine은 history에 안 남음


# --- 번들 내보내기(zip) ---------------------------------------------------

def test_export_bundle_contains_md_and_figure(tmp_path):
    import zipfile

    crop = tmp_path / "crop.png"
    crop.write_bytes(b"\x89PNG fake")  # 더미 그림 파일
    ctx = _ctx(figures=[_pfig(str(crop), "그림 1", page=200)])
    sess = _session(ctx, topic="RAG")
    sess.start()

    out = sess.export(str(tmp_path / "bundle.zip"))
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        # 노트 md (제목 기반 파일명) + 그림(embed_name)
        assert "RAG.md" in names
        assert "Building-AI-Agent-p200-fig1.png" in names
        # md 내용에 프론트매터 + 임베드 포함
        md = zf.read("RAG.md").decode("utf-8")
        assert "![[Building-AI-Agent-p200-fig1.png]]" in md


def test_export_no_notes_raises(tmp_path):
    import pytest
    sess = _session(_ctx())  # start 안 함 → notes 없음
    with pytest.raises(ValueError):
        sess.export(str(tmp_path / "x.zip"))


def test_export_skips_missing_figure_file(tmp_path):
    import zipfile
    ctx = _ctx(figures=[_pfig("/does/not/exist.png", "없음", page=1)])
    sess = _session(ctx, pages=[1])
    sess.start()
    out = sess.export(str(tmp_path / "b.zip"))
    with zipfile.ZipFile(out) as zf:
        # md는 있지만 없는 그림 파일은 번들에 안 들어감
        assert any(n.endswith(".md") for n in zf.namelist())
        assert not any(n.endswith(".png") for n in zf.namelist())


def test_export_sanitizes_title_filename(tmp_path):
    import zipfile
    sess = _session(_ctx(), topic="RAG/파이프라인: 개요")
    sess.start()
    out = sess.export(str(tmp_path / "b.zip"))
    with zipfile.ZipFile(out) as zf:
        md = [n for n in zf.namelist() if n.endswith(".md")][0]
        assert "/" not in md and ":" not in md  # 금지문자 치환됨


# --- 통합 + PII 경계 ------------------------------------------------------

def test_pii_no_image_path_reaches_llm():
    spy = _SpyLLMClient()
    ctx = _ctx(text="본문 텍스트", figures=[_pfig("/secret/crop/p1.png", "cap", page=1)])
    sess = NoteSession(
        client=spy, context=ctx, source="s.pdf", pages=[1],
        topic="t", guideline=None, created="2026-09-02",
    )
    sess.start()
    sess.refine("다듬어")
    content = spy.all_content()
    assert "/secret/crop/p1.png" not in content   # 이미지 경로 미전송
    assert "bbox" not in content.lower()           # 좌표 미전송


def test_full_flow_build_refine_edit_export(tmp_path):
    import zipfile

    crop = tmp_path / "c.png"
    crop.write_bytes(b"\x89PNG fake")
    res = _result({
        250: [
            _blk("text", 100, "원문 A"),
            _blk("figure", 300, "", ref=str(crop), h=200),
            _blk("figure_caption", 520, "그림 A"),
        ],
        251: [_blk("text", 100, "원문 B")],
    })
    res.source = "Building-AI-Agent.pdf"

    sess = build_session(
        "x.pdf", (250, 251), topic="지식그래프", created="2026-09-02",
        extractor=_FakeExtractor(res), client=MockLLMClient(),
    )
    note = sess.notes[0]
    sess.refine("불릿으로 바꿔줘")
    sess.apply_edit(note.id, "사용자가 확정한 최종 본문.")

    out = sess.export(str(tmp_path / "final.zip"))
    with zipfile.ZipFile(out) as zf:
        md = zf.read("지식그래프.md").decode("utf-8")
        assert "사용자가 확정한 최종 본문." in md          # 직접 편집 최종 반영
        assert "![[Building-AI-Agent-p250-fig1.png]]" in md  # 편집 후에도 md에 임베드 유지
        assert "Building-AI-Agent-p250-fig1.png" in zf.namelist()  # 그림 번들에 포함
    assert [h["action"] for h in sess.history] == ["start", "refine", "apply_edit"]
