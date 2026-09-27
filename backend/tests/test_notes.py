"""노트 조립 + 리파인 엔진 BDD 명세 (Sprint 2). LLM은 mock으로 결정적."""
from __future__ import annotations

import pytest
from app.domain.extractor import BBox, Block, ExtractionResult, PageExtraction
from app.infrastructure import get_llm_client
from app.infrastructure.mock_llm_client import MockLLMClient
from app.domain.notes import (
    Note,
    NoteDraft,
    NoteFigure,
    EmptyTextError,
    NoteSession,
    PreparedContext,
    PreparedFigure,
    BuildSessionRequest,
    SessionConfig,
    build_session,
    make_note_id,
    prepare_context,
    refine,
    summarize,
)
from app.domain.notes.note_models import NoteKey
from app.domain.notes.note_summarize import SummarizeRequest, RefineRequest


# ---------------------------------------------------------------------------
# 공용 헬퍼 / 픽스처
# ---------------------------------------------------------------------------

class _BoomLLMClient:
    """complete()가 항상 예외를 던지는 테스트용 LLM — 오류 처리 검증용."""
    def complete(self, messages): raise RuntimeError("LLM 다운")


class _SpyLLMClient:
    """LLM에 실제로 전달된 메시지를 기록 — PII 경계 검증용."""
    def __init__(self):
        self.seen = []
        self._mock = MockLLMClient()
    def complete(self, messages):
        self.seen.append(messages)
        return self._mock.complete(messages)
    def all_content(self):
        return "\n".join(m.content for msgs in self.seen for m in msgs)


class _FakeExtractor:
    """extract()가 미리 준비한 결과를 돌려주는 테스트용 추출기."""
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
        client=MockLLMClient(), context=ctx,
        config=SessionConfig(source=note_source, pages=pages or [200], topic=topic, guideline=guideline, created="2026-08-31"),
    )

def _blk(btype, y, text="", ref=None, h=20):
    return Block(type=btype, bbox=BBox(0, y, 100, y + h), reading_order=None, text=text, image_ref=ref)

def _result(pages_blocks):
    pages = [PageExtraction(page=pg, blocks=blks) for pg, blks in pages_blocks.items()]
    return ExtractionResult(source="s.pdf", pages=pages)


# ---------------------------------------------------------------------------
# Describe: 노트 모델 + 프론트매터
# ---------------------------------------------------------------------------

class DescribeNoteModel:
    """Note 모델 직렬화(프론트매터·ID)의 동작 명세."""

    def test_frontmatter_contains_all_required_fields(self):
        # Given a note with all metadata
        note = Note(
            id="abc123", title="셀프 어텐션", source="Building-AI-Agent.pdf",
            pages=[42, 43, 44], topic="어텐션 메커니즘", created="2026-08-31", body="본문 요약.",
        )

        # When rendered to markdown
        md = note.to_markdown()

        # Then all frontmatter fields appear and body follows the closing ---
        assert md.startswith("---\n")
        for field in (
            "id: abc123", 'title: "셀프 어텐션"', 'source: "Building-AI-Agent.pdf"',
            "pages: [42, 43, 44]", 'topic: "어텐션 메커니즘"', "tags: []", "created: 2026-08-31",
        ):
            assert field in md, field
        assert "---\n\n본문 요약." in md

    def test_frontmatter_escapes_double_quotes_in_title(self):
        # Given a title that contains double quotes
        note = Note(id="x", title='제목 "인용" 포함', source="s.pdf", pages=[1], topic="t", created="2026-01-01")

        # When rendered
        md = note.to_markdown()

        # Then the quotes are YAML-escaped
        assert 'title: "제목 \\"인용\\" 포함"' in md

    def test_note_id_is_deterministic_and_unique_per_key(self):
        # Given the same NoteKey, the id is always equal
        assert make_note_id(NoteKey("s.pdf", [42, 43], "topic")) == make_note_id(NoteKey("s.pdf", [42, 43], "topic"))

        # And different indexes or page ranges produce different ids
        assert make_note_id(NoteKey("s.pdf", [42, 43], "topic", 0)) != make_note_id(NoteKey("s.pdf", [42, 43], "topic", 1))
        assert make_note_id(NoteKey("s.pdf", [42], "topic")) != make_note_id(NoteKey("s.pdf", [43], "topic"))

    def test_note_draft_stores_title_and_body(self):
        d = NoteDraft(title="T", body="B")
        assert d.title == "T" and d.body == "B"

    def test_note_figure_stores_embed_name_and_caption(self):
        f = NoteFigure(embed_name="s-p1-fig1.png", source_path="/tmp/crop.png", caption="그림 1")
        assert f.embed_name.endswith(".png") and f.caption == "그림 1"


# ---------------------------------------------------------------------------
# Describe: 텍스트 추림 + 그림↔캡션 페어링
# ---------------------------------------------------------------------------

class DescribePrepareContext:
    """prepare_context 의 텍스트 추림·그림 페어링 동작 명세."""

    def test_pairs_figure_with_nearest_caption_in_reading_order(self):
        # Given blocks with a figure followed immediately by its caption
        res = _result({200: [
            _blk("header", 76, "머리글"),
            _blk("code", 100, "print(x)"),
            _blk("text", 200, "본문 앞"),
            _blk("figure", 700, "", ref="/crop/p200_fig.png", h=550),
            _blk("figure_caption", 1270, "그림 5.21 벡터 DB"),
            _blk("text", 1400, "본문 뒤"),
            _blk("number", 2200, "200"),
        ]})

        # When context is prepared
        ctx = prepare_context(res)

        # Then only content blocks appear in text; the figure is paired with its caption
        assert ctx.text == "print(x)\n\n본문 앞\n\n본문 뒤"
        assert len(ctx.figures) == 1
        fig = ctx.figures[0]
        assert fig.caption == "그림 5.21 벡터 DB"
        assert fig.source_path == "/crop/p200_fig.png"
        assert fig.anchor_index == 2
        assert fig.page == 200

    def test_multipage_text_follows_page_then_y_order(self):
        # Given text blocks spread across two pages
        res = _result({
            250: [_blk("text", 100, "250-A"), _blk("text", 300, "250-B")],
            251: [_blk("text", 100, "251-A")],
        })

        # When prepared
        ctx = prepare_context(res)

        # Then the text is page-then-y ordered and no figures are present
        assert ctx.text == "250-A\n\n250-B\n\n251-A"
        assert ctx.figures == []

    def test_figure_without_nearby_caption_has_empty_caption(self):
        # Given a figure with no caption block
        res = _result({1: [_blk("text", 100, "본문"), _blk("figure", 300, "", ref="/crop/f.png")]})

        # When prepared
        ctx = prepare_context(res)

        # Then the figure's caption is empty
        assert len(ctx.figures) == 1 and ctx.figures[0].caption == ""

    def test_caption_beyond_distance_threshold_is_not_paired(self):
        # Given a caption that is farther than the threshold
        res = _result({1: [
            _blk("figure", 100, "", ref="/crop/f.png"),
            _blk("figure_caption", 2000, "멀리 있는 캡션"),
        ]})

        # When prepared with a 250px threshold
        ctx = prepare_context(res, caption_gap_threshold_px=250)

        # Then the distant caption is not paired with the figure
        assert ctx.figures[0].caption == ""

    def test_image_paths_and_coordinates_are_excluded_from_llm_text(self):
        # Given a page with a figure whose crop path is sensitive
        res = _result({1: [
            _blk("text", 100, "요약할 본문"),
            _blk("figure", 300, "", ref="/secret/crop/path.png"),
        ]})

        # When prepared
        ctx = prepare_context(res)

        # Then neither the image path nor any coordinate appears in the LLM-bound text
        assert "/secret/crop/path.png" not in ctx.text
        assert ctx.text == "요약할 본문"


# ---------------------------------------------------------------------------
# Describe: summarize / refine 프롬프트 빌더
# ---------------------------------------------------------------------------

class DescribeSummarize:
    """summarize / refine 프롬프트 빌더 동작 명세."""

    def test_llm_client_factory_returns_correct_implementation(self):
        from app.config import Settings
        def _s(backend):
            return Settings(
                extract_backend="fixture", modal_endpoint_url="", modal_api_token="",
                render_dpi=200, request_timeout_s=5, crop_dir="/tmp", max_retries=0,
                retry_backoff_s=0, warmup=False, fixtures_dir="/tmp", llm_backend=backend,
                llm_model="claude-sonnet-4-6",
            )
        assert isinstance(get_llm_client(_s("mock")), MockLLMClient)
        from app.infrastructure.anthropic_llm_client import AnthropicLLMClient
        assert isinstance(get_llm_client(_s("anthropic")), AnthropicLLMClient)
        for stub in ("openai", "local"):
            with pytest.raises(NotImplementedError): get_llm_client(_s(stub))
        with pytest.raises(ValueError): get_llm_client(_s("nonsense"))

    def test_summarize_reflects_topic_and_guideline_in_output(self):
        # Given a request with topic and guideline
        req = SummarizeRequest(
            text="쿼리 키 값으로 어텐션을 계산한다. 스케일드 닷프로덕트.",
            topic="셀프 어텐션", guideline="수식 중심으로",
        )

        # When summarized
        drafts = summarize(MockLLMClient(), req)

        # Then a single draft reflects both the topic and guideline
        assert len(drafts) == 1
        assert drafts[0].title == "셀프 어텐션"
        assert "수식 중심으로" in drafts[0].body
        assert "쿼리 키 값" in drafts[0].body

    def test_summarize_produces_distinct_drafts_per_aspect(self):
        # Given a request for 2 notes
        req = SummarizeRequest(text="본문 텍스트.", topic="주제", note_count=2)

        # When summarized
        drafts = summarize(MockLLMClient(), req)

        # Then two distinct drafts are returned
        assert len(drafts) == 2
        assert drafts[0].title != drafts[1].title

    def test_refine_incorporates_instruction_and_preserves_title(self):
        # Given an existing note and a refinement instruction
        req = RefineRequest(
            note_markdown='TITLE: 원본 제목\n\n원본 본문입니다.',
            instruction="더 짧게 요약해줘",
            text="원문 텍스트.",
        )

        # When refined
        d = refine(MockLLMClient(), req)

        # Then the instruction appears in the body and the original title is preserved
        assert d.title == "원본 제목"
        assert "더 짧게 요약해줘" in d.body

    def test_parse_draft_is_lenient_when_title_marker_absent(self):
        # Given LLM output that has no "TITLE:" prefix
        from app.domain.notes.note_summarize import _parse_draft
        d = _parse_draft("그냥 첫 줄\n둘째 줄")

        # Then the first line becomes the title
        assert d.title == "그냥 첫 줄"
        assert "둘째 줄" in d.body


# ---------------------------------------------------------------------------
# Describe: NoteSession.start
# ---------------------------------------------------------------------------

class DescribeNoteSessionStart:
    """NoteSession.start 의 노트 조립·그림 첨부 동작 명세."""

    def test_builds_note_with_frontmatter_and_obsidian_embed(self):
        # Given a context that contains a figure
        ctx = _ctx(figures=[_pfig("/crop/p200_fig.png", "그림 5.21 벡터 DB", page=200)])

        # When started
        notes = _session(ctx, topic="RAG").start()

        # Then the note has frontmatter, an Obsidian embed, and the figure is in state (not body)
        assert len(notes) == 1
        md = notes[0].to_markdown()
        assert 'topic: "RAG"' in md and "created: 2026-08-31" in md
        assert "![[Building-AI-Agent-p200-fig1.png]]" in md
        assert "그림 5.21 벡터 DB" in md
        assert "![[" not in notes[0].body
        assert notes[0].figures[0].source_path == "/crop/p200_fig.png"

    def test_guideline_is_reflected_in_note_body(self):
        # Given a guideline is set on the session
        notes = _session(_ctx(), guideline="초보자용으로").start()

        # Then the guideline appears in the generated body
        assert "초보자용으로" in notes[0].body

    def test_multiple_notes_have_distinct_ids_and_only_first_has_figure(self):
        # Given a request for 2 notes
        ctx = _ctx(figures=[_pfig("/crop/f.png", "cap")])
        notes = _session(ctx).start(note_count=2)

        # Then ids differ and only the first note has the figure
        assert notes[0].id != notes[1].id
        assert len(notes[0].figures) == 1
        assert len(notes[1].figures) == 0

    def test_multiple_figures_on_same_page_get_sequential_names(self):
        # Given two figures on the same page
        ctx = _ctx(figures=[_pfig("/crop/a.png", "A", page=250), _pfig("/crop/b.png", "B", page=250)])

        # When started
        note = _session(ctx, pages=[250]).start()[0]

        # Then they are named -fig1, -fig2
        assert [f.embed_name for f in note.figures] == [
            "Building-AI-Agent-p250-fig1.png",
            "Building-AI-Agent-p250-fig2.png",
        ]

    def test_crop_failed_figure_is_excluded_from_note(self):
        # Given a figure with an empty source_path (crop failure)
        ctx = _ctx(figures=[_pfig("", "크롭 실패")])

        # When started
        note = _session(ctx).start()[0]

        # Then no figures are attached and no embed appears
        assert note.figures == []
        assert "![[" not in note.to_markdown()

    def test_empty_text_raises_and_produces_no_notes(self):
        # Given a context with only whitespace
        sess = _session(_ctx(text="   "))

        # When start is attempted
        with pytest.raises(EmptyTextError):
            sess.start()

        # Then the session has no notes
        assert sess.notes == []

    def test_llm_error_propagates_without_corrupting_state(self):
        # Given an LLM that always fails
        sess = _session(_ctx())
        sess.client = _BoomLLMClient()

        # When start is attempted
        with pytest.raises(RuntimeError):
            sess.start()

        # Then the session state is untouched
        assert sess.notes == []


# ---------------------------------------------------------------------------
# Describe: NoteSession.refine + apply_edit
# ---------------------------------------------------------------------------

class DescribeNoteSessionRefine:
    """NoteSession refine · apply_edit 의 동작 명세."""

    def test_refine_updates_body_while_preserving_frontmatter_and_figures(self):
        # Given a started session with a figure
        ctx = _ctx(figures=[_pfig("/crop/f.png", "cap")])
        sess = _session(ctx, topic="RAG")
        note = sess.start()[0]
        before_id, before_figs = note.id, list(note.figures)

        # When refined
        sess.refine("더 짧게 요약해줘")

        # Then the body is updated but id, source, pages, and figures are unchanged
        assert "더 짧게 요약해줘" in note.body
        assert note.id == before_id and note.figures == before_figs
        assert sess.events[-1].action == "refine"

    def test_apply_edit_replaces_body_and_is_used_as_basis_for_next_refine(self):
        # Given a note that has been directly edited
        sess = _session(_ctx())
        note = sess.start()[0]
        sess.apply_edit(note.id, "내가 직접 쓴 본문이다.")
        assert note.body == "내가 직접 쓴 본문이다."

        # When refined afterwards
        sess.refine("보강해줘")

        # Then the edited content is used as the refine basis
        assert "내가 직접 쓴 본문이다." in note.body
        assert "[리파인 반영: 보강해줘]" in note.body

    def test_refine_without_note_id_updates_all_notes(self):
        # Given a session with 2 notes
        notes = _session(_ctx()).start(note_count=2)

        # When refined without specifying a note_id
        _session(_ctx()).notes  # (unused, just shows intent)
        sess = _session(_ctx())
        notes = sess.start(note_count=2)
        sess.refine("톤 통일")

        # Then all notes are updated
        assert all("톤 통일" in n.body for n in notes)

    def test_unknown_note_id_raises_value_error(self):
        # Given a started session
        sess = _session(_ctx())
        sess.start()

        # Then operations with an unknown id raise ValueError
        with pytest.raises(ValueError): sess.refine("x", note_id="없는id")
        with pytest.raises(ValueError): sess.apply_edit("없는id", "본문")

    def test_llm_error_during_refine_leaves_previous_notes_intact(self):
        # Given a started session, then the LLM goes down
        sess = _session(_ctx())
        note = sess.start()[0]
        before_body = note.body
        sess.client = _BoomLLMClient()

        # When refine fails
        with pytest.raises(RuntimeError): sess.refine("다듬어줘")

        # Then the previous note is intact and no failed event was appended
        assert note.body == before_body
        assert sess.events[-1].action == "start"

    def test_figure_embed_survives_refine_and_direct_edit(self):
        """결함 #1 회귀: body 변경 후에도 그림 임베드가 유지된다."""
        # Given a note with a figure
        ctx = _ctx(figures=[_pfig("/crop/f.png", "그림 1", page=200)])
        sess = _session(ctx)
        note = sess.start()[0]
        embed = "![[Building-AI-Agent-p200-fig1.png]]"
        assert embed in note.to_markdown()

        # When body is replaced by refine, then by direct edit
        sess.refine("본문 재작성")
        assert embed in note.to_markdown()
        sess.apply_edit(note.id, "완전히 새로 쓴 본문")

        # Then the embed is still present (figures are 1st-class state, not part of body)
        assert embed in note.to_markdown()


# ---------------------------------------------------------------------------
# Describe: build_session 오케스트레이션
# ---------------------------------------------------------------------------

class DescribeBuildSession:
    """build_session(추출→준비→세션 시작) 오케스트레이션의 동작 명세."""

    def test_connects_extract_prepare_and_start_into_a_ready_session(self):
        # Given an extractor result with text and a captioned figure
        res = _result({
            250: [
                _blk("text", 100, "250 본문"),
                _blk("figure", 300, "", ref="/c/f250.png", h=200),
                _blk("figure_caption", 520, "그림 A"),
            ],
            251: [_blk("text", 100, "251 본문")],
        })
        res.source = "Building-AI-Agent.pdf"
        fake = _FakeExtractor(res)

        # When build_session is called
        sess = build_session(
            BuildSessionRequest(pdf_path="x.pdf", page_range=(250, 251), topic="지식그래프", created="2026-09-02"),
            extractor=fake, client=MockLLMClient(),
        )

        # Then the extractor was called once and the session contains a well-formed note
        assert fake.calls == [("x.pdf", (250, 251))]
        note = sess.notes[0]
        assert note.source == "Building-AI-Agent.pdf"
        assert note.pages == [250, 251]
        assert "250 본문" in note.body
        assert note.figures[0].embed_name == "Building-AI-Agent-p250-fig1.png"
        assert note.figures[0].caption == "그림 A"

    def test_note_count_is_respected(self):
        # Given a request for 2 notes
        res = _result({1: [_blk("text", 100, "본문")]})

        # When build_session is called with note_count=2
        sess = build_session(
            BuildSessionRequest(pdf_path="x.pdf", page_range=(1, 1), topic="t", created="2026-09-02", note_count=2),
            extractor=_FakeExtractor(res), client=MockLLMClient(),
        )

        # Then 2 notes are created
        assert len(sess.notes) == 2

    def test_pdf_with_no_text_raises_empty_text_error(self):
        # Given a PDF whose pages contain only figures
        res = _result({1: [_blk("figure", 100, "", ref="/c/f.png")]})

        # Then EmptyTextError is raised
        with pytest.raises(EmptyTextError):
            build_session(
                BuildSessionRequest(pdf_path="x.pdf", page_range=(1, 1), topic="t", created="2026-09-02"),
                extractor=_FakeExtractor(res), client=MockLLMClient(),
            )


# ---------------------------------------------------------------------------
# Describe: 번들 내보내기(zip)
# ---------------------------------------------------------------------------

class DescribeNoteSessionExport:
    """세션 export(zip 번들 생성)의 동작 명세."""

    def test_bundle_contains_markdown_and_figure_file(self, tmp_path):
        import zipfile
        # Given a started session with a real figure file
        crop = tmp_path / "crop.png"
        crop.write_bytes(b"\x89PNG fake")
        ctx = _ctx(figures=[_pfig(str(crop), "그림 1", page=200)])
        sess = _session(ctx, topic="RAG")
        sess.start()

        # When exported
        out = sess.export(str(tmp_path / "bundle.zip"))

        # Then the zip contains the markdown and the figure embed
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            assert "RAG.md" in names
            assert "Building-AI-Agent-p200-fig1.png" in names
            assert "![[Building-AI-Agent-p200-fig1.png]]" in zf.read("RAG.md").decode()

    def test_export_without_notes_raises(self, tmp_path):
        # Given a session that was never started
        sess = _session(_ctx())

        # Then export raises ValueError
        with pytest.raises(ValueError):
            sess.export(str(tmp_path / "x.zip"))

    def test_missing_figure_file_is_silently_skipped(self, tmp_path):
        import zipfile
        # Given a figure whose source file does not exist
        ctx = _ctx(figures=[_pfig("/does/not/exist.png", "없음", page=1)])
        sess = _session(ctx, pages=[1])
        sess.start()

        # When exported
        out = sess.export(str(tmp_path / "b.zip"))

        # Then the markdown is present but the missing image is not bundled
        with zipfile.ZipFile(out) as zf:
            assert any(n.endswith(".md") for n in zf.namelist())
            assert not any(n.endswith(".png") for n in zf.namelist())

    def test_title_with_path_separators_is_sanitized_in_filename(self, tmp_path):
        import zipfile
        # Given a topic containing characters forbidden in filenames
        sess = _session(_ctx(), topic="RAG/파이프라인: 개요")
        sess.start()

        # When exported
        out = sess.export(str(tmp_path / "b.zip"))

        # Then the resulting .md filename contains no forbidden characters
        with zipfile.ZipFile(out) as zf:
            md = [n for n in zf.namelist() if n.endswith(".md")][0]
            assert "/" not in md and ":" not in md


# ---------------------------------------------------------------------------
# Describe: PII 보장
# ---------------------------------------------------------------------------

class DescribePiiGuarantees:
    """이미지 경로·좌표가 LLM에 전달되지 않는다는 PII 경계 명세."""

    def test_image_paths_and_bbox_never_reach_llm(self):
        # Given a spy LLM and a context with a figure at a sensitive path
        spy = _SpyLLMClient()
        ctx = _ctx(text="본문 텍스트", figures=[_pfig("/secret/crop/p1.png", "cap", page=1)])
        sess = NoteSession(
            client=spy, context=ctx,
            config=SessionConfig(source="s.pdf", pages=[1], topic="t", guideline=None, created="2026-09-02"),
        )

        # When the session is used end-to-end
        sess.start()
        sess.refine("다듬어")
        content = spy.all_content()

        # Then neither the image path nor any bbox coordinate reaches the LLM
        assert "/secret/crop/p1.png" not in content
        assert "bbox" not in content.lower()


# ---------------------------------------------------------------------------
# Describe: 전체 흐름 (build → refine → edit → export)
# ---------------------------------------------------------------------------

class DescribeFullFlow:
    """build_session → refine → apply_edit → export 전체 흐름 명세."""

    def test_final_edit_is_reflected_in_export_and_figure_persists(self, tmp_path):
        import zipfile
        # Given a multi-page result with a figure
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
            BuildSessionRequest(pdf_path="x.pdf", page_range=(250, 251), topic="지식그래프", created="2026-09-02"),
            extractor=_FakeExtractor(res), client=MockLLMClient(),
        )

        # When refined then directly edited
        note = sess.notes[0]
        sess.refine("불릿으로 바꿔줘")
        sess.apply_edit(note.id, "사용자가 확정한 최종 본문.")

        # Then the export contains the final edit and the figure embed
        out = sess.export(str(tmp_path / "final.zip"))
        with zipfile.ZipFile(out) as zf:
            md = zf.read("지식그래프.md").decode()
            assert "사용자가 확정한 최종 본문." in md
            assert "![[Building-AI-Agent-p250-fig1.png]]" in md
            assert "Building-AI-Agent-p250-fig1.png" in zf.namelist()
        assert [e.action for e in sess.events] == ["start", "refine", "apply_edit"]


# ---------------------------------------------------------------------------
# Describe: ADK 스타일 state · events · undo
# ---------------------------------------------------------------------------

class DescribeSessionStateAndEvents:
    """NoteSession 의 state · events · undo 동작 명세."""

    def test_notes_are_accessible_via_state(self):
        # Given a started session
        sess = _session(_ctx())
        sess.start()

        # Then notes are the same object as state["notes"]
        assert sess.notes is sess.state["notes"]
        assert sess.events[0].action == "start"
        assert "notes" in sess.events[0].state_delta

    def test_refine_injects_prior_instructions_into_llm_context(self):
        """다중턴: 이전 refine 지시가 다음 refine의 LLM 맥락에 주입된다."""
        # Given a session with a prior refine recorded
        spy = _SpyLLMClient()
        sess = NoteSession(
            client=spy, context=_ctx(),
            config=SessionConfig(source="s.pdf", pages=[1], topic="t", guideline=None, created="2026-09-06"),
        )
        sess.start()
        sess.refine("첫 지시 A")
        spy.seen.clear()

        # When a second refine is issued
        sess.refine("둘째 지시 B")
        content = spy.all_content()

        # Then the first instruction appears in the context passed to the LLM
        assert "첫 지시 A" in content
        assert "둘째 지시 B" in content

    def test_user_preferred_guideline_is_used_when_no_session_guideline(self):
        # Given no session-level guideline but a user-preferred one
        sess = NoteSession(
            client=MockLLMClient(), context=_ctx(),
            config=SessionConfig(source="s.pdf", pages=[1], topic="t", guideline=None,
                                  created="2026-09-06", user_preferred_guideline="수식 중심"),
        )

        # When started
        note = sess.start()[0]

        # Then the user preference is reflected
        assert "수식 중심" in note.body

    def test_undo_reverts_note_to_state_before_last_action(self):
        # Given a session that has been refined
        sess = _session(_ctx(text="원문 텍스트"))
        sess.start()
        start_body = sess.notes[0].body
        sess.refine("불릿으로")

        # When undone
        sess.undo()

        # Then the note is back to the start body
        assert sess.notes[0].body == start_body
        assert sess.events[-1].action == "revert"

    def test_revert_to_specific_event_seq(self):
        # Given a session with two refines
        sess = _session(_ctx())
        sess.start()       # seq 0
        sess.refine("A")   # seq 1
        sess.refine("B")   # seq 2
        a_body = sess.events[1].state_delta["notes"][0].body

        # When reverted to seq 1
        sess.revert_to(1)

        # Then the note matches the seq 1 snapshot
        assert sess.notes[0].body == a_body

    def test_undo_without_prior_state_raises(self):
        # Given a session with only one event
        sess = _session(_ctx())
        sess.start()

        # Then undo raises ValueError
        with pytest.raises(ValueError): sess.undo()

    def test_sequential_undo_moves_backward_without_oscillation(self):
        # Given two sequential refines
        sess = _session(_ctx(text="원문 텍스트"))
        sess.start()
        start_body = sess.notes[0].body
        sess.refine("A 지시")
        body_after_a = sess.notes[0].body
        sess.refine("B 지시")
        assert sess.notes[0].body != body_after_a

        # When undone twice
        sess.undo()
        assert sess.notes[0].body == body_after_a

        sess.undo()

        # Then we arrive at start, not back to B (no oscillation)
        assert sess.notes[0].body == start_body

    def test_event_snapshot_is_immutable_after_further_changes(self):
        # Given a recorded start event snapshot
        sess = _session(_ctx())
        sess.start()
        body_at_start = sess.notes[0].body
        assert sess.events[0].state_delta["notes"][0].body == body_at_start

        # When a refine changes the note
        sess.refine("변경")

        # Then the event 0 snapshot is unchanged (deepcopy)
        assert sess.events[0].state_delta["notes"][0].body == body_at_start
