# Sprint Contract — Sprint 6: 평탄화 형광펜 색 검출 + 색상 가중치 — 2026-10-17

> `/sprint-contract`로 작성. spec: `.claude/harness/spec-sprint6.md`. 사용자 sign-off 대기.

## 목표

GoodNotes처럼 형광펜이 픽셀로 평탄화된(주석 없는) PDF에서도 **형광색을 검출**해 아래 텍스트를 추출하고, **색상별 가중치(기본 초록>노랑, config 커스텀)** 를 실어 요약/대화 LLM에 전달한다. 프론트 체크박스로 켜며, 끄면 기존 동작 그대로다.

## 전체 스프린트 맵

- Sprint 0~4 ✅ / Sprint 5 — 서재 + 자유 대화 ✅
- **Sprint 6 — 평탄화 형광펜 색 검출 + 색상 가중치** ← *이번 계약*

---

## 작업 단위

### 백엔드

**B1 — `Highlight` 데이터 모델** `app/domain/extractor.py`
- `@dataclass Highlight{ text: str; color: Literal["yellow","green","other"] }`
- `PageExtraction.highlights: list[str]` → `list[Highlight]` 로 변경
- docstring의 highlights 설명 갱신

**B2 — 색 검출 모듈 (신규)** `app/infrastructure/extractors/highlight_color.py`
- `detect_color_bands(pix: pymupdf.Pixmap) -> list[tuple[pymupdf.Rect, str]]`
  - numpy로 RGB 마스킹 → 색상별(yellow/green) 마스크
  - 행 투영(`mask.any(axis=1)`) → 연속 밴드 → 렌더 픽셀 Rect + color
  - 역치 출발점(스파이크): 노랑 `r>180 & g>150 & b<160 & r+g-2b>80`; 초록은 `g`가 `r,b`보다 뚜렷이 높음. sample p46로 튜닝
- 파일 책임 docstring 첫 줄 명시

**B3 — base_extractor 색 폴백 통합** `app/infrastructure/extractors/base_extractor.py`
- `extract()`에서 OCR용으로 만든 `pix`를 `_assemble_page`로 전달(추가 렌더 0회)
- `_extract_highlights(page, blocks, pix)`:
  - 기존 주석 경로 유지 → 각 결과에 `color`(주석색 분류 or `"other"`) 부착
  - **주석이 없을 때** `detect_color_bands(pix)` → 각 밴드 Rect를 `_blocks_in_rect`로 텍스트화 → `Highlight(text, color)`
  - 중복 제거는 `(text,color)` 기준
- 반환 타입 `list[Highlight]`

**B4 — 색 가중치 설정** `app/config.py`
- `Settings.highlight_color_weights: dict[str, float]`
- env `HIGHLIGHT_WEIGHT_GREEN/YELLOW/OTHER`, 기본 `2.0 / 1.0 / 1.0`

**B5 — 요약 프롬프트 가중** `app/domain/notes/note_summarize.py`
- `SummarizeRequest.highlights: list[Highlight] | None`
- `_build_summarize_prompt`: 가중치(Settings 조회)로 2그룹 분리 —
  `[READER_FOCUS]` 안에 **"가장 중요(강조)"**(가중 상위=초록) / **"중요"**(그외) 구분 표기

**B6 — 대화 프롬프트 가중** `app/application/chat_service.py`
- `collect_page_highlights` → `list[Highlight]`(색 보존), `use_highlights=False`면 []
- `build_sys_content`: `[HIGHLIGHTS_JSON]`을 `[{text,color,weight}]` 형태로 직렬화

**B7 — 요약 흐름 토글** `schemas/notes_schemas.py` · `notes_router.py` · `note_orchestrate.py`
- `CreateSessionRequest.use_highlights: bool = False`
- `BuildSessionRequest.use_highlights: bool = False` → `build_session`에서 게이팅
- `_collect_highlights(result, use_highlights)`: False면 [] 반환(기존=항상수집에서 변경)

**B8 — 가중치 조회 헬퍼 공유**
- Settings의 색→가중치 조회를 요약/대화 양쪽에서 쓰도록 작은 헬퍼(`weight_for(color)`) 배치 (domain은 fastapi/config 직접 의존 금지 → 가중치는 호출 측에서 주입하거나 순수 함수로)

**B9 — 의존성** `backend/requirements.txt`
- `numpy` 추가

### 프론트엔드

**F1 — `InputForm.tsx`** 체크박스 "형광펜 가중치 포함" + `useHighlights` state → `createSession`에 전달

**F2 — `api.ts`** `createSession` 파라미터에 `use_highlights?: boolean` 추가, body 포함
- (대화 흐름 `NewChatForm`/`createConversation` 체크박스는 **이미 존재 → 변경 없음**)

### 테스트

**T1 — `tests/test_highlight_color.py` (신규)**
- 노랑 밴드만 있는 합성 pixmap → `("yellow", rect)` 검출
- 초록 밴드 → `("green", rect)`
- 무채색 페이지 → [] (오검출 0)

**T2 — `tests/test_extractor.py` 확장 + 회귀**
- 신규: 평탄화 노랑(주석 아님, `draw_rect(fill, fill_opacity=0.4)` + OCR 블록) → `Highlight(text, "yellow")`, 주석 0개
- 신규: 평탄화 초록 → `"green"`
- **회귀 갱신**: 기존 `DescribeHighlightExtraction` 3종을 `Highlight` 구조로 수정
  (`highlights[0].text`, `.color`) — 주석 경로 동작 보존

**T3 — `tests/test_notes.py` (요약 가중/토글)**
- 초록+노랑 → `_build_summarize_prompt` 출력에 초록='가장 중요' 그룹, 노랑='중요' 그룹
- `use_highlights=False` → `[READER_FOCUS]` 없음 / `True` → 있음

**T4 — `tests/test_api.py` 또는 config 테스트**
- `HIGHLIGHT_WEIGHT_YELLOW=3.0` env → Settings 매핑 반영

**T5 — `tests/test_chat_api.py` 확장**
- `use_highlights=true` + 색 highlights → `[HIGHLIGHTS_JSON]`에 `{text,color,weight}` 포함

**T6 — Playwright E2E `test/08-highlight-weight.spec.ts` (신규)**
- 노트 생성 모달 `InputForm`에서 "형광펜 가중치 포함" 체크 → `/sessions` POST body에 `use_highlights:true` (page.route로 가로채 검증)
- 회귀: 체크 해제 시 `use_highlights:false`

---

## 완료 조건

- [ ] 주석 없는 평탄화 노랑 형광펜 → `Highlight(text, "yellow")` 추출 (T2)
- [ ] 초록 형광펜 → `"green"` 추출 (T2)
- [ ] 형광펜 없는 페이지 → highlights == [] (T1/T2, 오검출 0)
- [ ] 기존 주석 기반 경로 회귀 없음 (T2 갱신 3종 PASS)
- [ ] 초록 구절이 프롬프트에서 노랑보다 상위 강조로 표기 (T3)
- [ ] `HIGHLIGHT_WEIGHT_*` env로 가중치 재정의 가능 (T4)
- [ ] 요약: `use_highlights=false`(기본) → `[READER_FOCUS]` 없음 (기존 동작 보존)
- [ ] 요약: `InputForm` 체크 → `/sessions` 요청에 `use_highlights:true` (T6)
- [ ] 대화: 색 가중치가 `[HIGHLIGHTS_JSON]`에 반영 (T5)
- [ ] 색 검출이 추출 시 pixmap 재사용(페이지당 추가 렌더 0회)
- [ ] `pytest` 전체(기존 104 + 신규) 통과
- [ ] `tsc --noEmit` 에러 0
- [ ] `npm run test:e2e` 신규 + 기존 PASS
- [ ] **실제 p46 수동 검증**: `~/books/Computer science/algorithm-interview.pdf` 46p에서 알려진 노란 형광 구절(예: "직접 만든 코드여야 … 방법이 가장 좋다")이 `color="yellow"`로 추출됨을 눈으로 확인 (비결정적, CI 제외)

## 테스트 케이스 상세

| ID | 시나리오 | 입력 | 기대 출력 |
|----|---------|------|----------|
| H1 | 평탄화 노랑 | 노란 반투명 rect + OCR 블록, 주석 0 | `Highlight("…","yellow")` |
| H2 | 평탄화 초록 | 초록 rect | `Highlight("…","green")` |
| H3 | 무형광 | 색칠 없음 | `[]` |
| H4 | 주석 회귀 | `add_highlight_annot` | 기존대로 추출 + color 부착 |
| W1 | 가중 프롬프트 | 초록1+노랑1 | 초록='가장 중요', 노랑='중요' |
| W2 | 가중 설정 | `HIGHLIGHT_WEIGHT_YELLOW=3.0` | 매핑 yellow=3.0 |
| G1 | 토글 off | `use_highlights=false` | `[READER_FOCUS]` 없음 |
| G2 | 토글 on | `use_highlights=true` | `[READER_FOCUS]` 있음 |
| E1 | E2E 체크 | 체크박스 on | `/sessions` body `use_highlights:true` |

## 하드 임계값

- 색 마스킹(numpy) 200DPI 1페이지 **< 100ms** (렌더 제외)
- 색 검출 추가 렌더 **0회** (pixmap 재사용)
- 오검출: 무형광 페이지 highlights == 0건
- 기본 가중치 `green=2.0 > yellow=1.0 = other=1.0`
- `pytest` 전체 통과 / `tsc --noEmit` 0 / `npm run test:e2e` PASS

## 검증 방법

```bash
cd backend && pytest -v                 # 단위·통합 (신규 색검출/가중/토글)
cd frontend && npx tsc --noEmit         # 타입
npm run test:e2e                        # E2E (08-highlight-weight 포함)

# 실제 파일 수동 검증 (구현 후 1회, 상커밋 금지)
#   algorithm-interview.pdf 46p → color 검출이 노란 형광 구절을 "yellow"로 추출하는지 눈으로 확인
```

## 구현 순서

1. B9 (numpy) → B1 (모델) → B2 (색검출) → T1
2. B3 (base_extractor 통합) → T2 (+회귀 갱신)
3. B4 (설정) → B8 (가중 헬퍼) → W2
4. B5 (요약 프롬프트) → B7 (토글) → T3/G1/G2
5. B6 (대화 프롬프트) → T5
6. F2 (api) → F1 (체크박스) → T6
7. 문서 갱신 (architecture.md + CLAUDE.md 데이터 모델/설정)

## 확정 결정 사항

| 항목 | 결정 | 이유 |
|------|------|------|
| 적용 범위 | 요약+대화 둘 다 | 공통 `_extract_highlights`가 양쪽 소스 |
| 색 검출 라이브러리 | numpy | 색상별 마스크 분리 깔끔·빠름 |
| 색 가중치 집 | `config.py`(env) | 단일 사용자의 커스텀 설정 |
| 기본 가중치 | green=2, yellow=1, other=1 | 사용자 개인 편향(초록 중시) |
| 토글 OFF 의미 | highlights 미수집 = 기존 동작 | "끄면 기존 로직 그대로" |
| extract() 시그니처 | 불변 | Modal/Fixture 교체성 유지 |
| 색 검출 실행 | 추출 시 항상(저비용) | 토글은 collect/prompt 계층 게이팅 |
| 주석 경로 유지 여부 | **유지(안전망)** | 실제 파일(algorithm-interview.pdf) 725p 전부 주석 0개 — 기존 주석 경로는 합성 테스트로만 검증된 투기적 경로. 그러나 향후 진짜 주석 PDF 대비 저비용 안전망으로 존치 |

## 변경 이력

- 2026-10-17 최초 작성
- 2026-10-17 실제 p46 수동 검증을 완료 조건·검증 방법에 추가 (사용자 요청)

## 사용자 Sign-off
- [x] 사용자가 명시적으로 승인함 (2026-10-17)
