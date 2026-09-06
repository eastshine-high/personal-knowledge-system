# Sprint Contract — Sprint 2: 노트 조립 + 리파인 엔진 — 2026-08-31

> `/sprint-contract`로 작성. spec: `.claude/harness/spec.md`. 사용자 sign-off 완료(2026-08-31).
> Sprint 0/1 계약은 `plan-sprint0.md`, `plan-sprint1.md`로 보존.

## 목표 (spec에서)
추출 결과 + 주제/가이드라인을 받아 **추출 텍스트만** LLM(mock)으로 초기 노트를 만들고,
**후속 지시·직접 편집으로 반복해 다듬는 헤드리스 리파인 엔진**을 제공한다. 완성물은 그림과 함께 번들로 내보낸다.
(채팅 UI는 Sprint 3)

## 전체 스프린트 맵 (갱신)
- Sprint 0 — 스캐폴딩 & 스파이크 ✅ (`plan-sprint0.md`)
- Sprint 1 — 서버리스 GPU + `LayoutExtractor` 실제 구현 ✅ (`plan-sprint1.md`; (f)<90초 콜드 실측만 보류) + fixture 오프라인 백엔드
- **Sprint 2 — 노트 조립 + 리파인 엔진(헤드리스, 대화형 상태)** ← *이번 계약*
- Sprint 3 — React UI: 리파인 엔진을 구동(PDF.js 뷰어, 범위+주제/가이드라인 입력, 노트 미리보기/직접편집, 채팅 리파인 패널, 내보내기) + Playwright E2E
- Sprint 4 — 통합·에지·PII 검증 → `/evaluate`

## 데이터 흐름 (연결 고리)
```
사용자: PDF + 범위(예: 250-255) + topic + guideline
  → 1. extract(pdf, range)              # Sprint1, 1회만. get_extractor()=오프라인이면 fixture
       → ExtractionResult(pages=[250..255], 각 페이지 text 블록(읽기순서)+figure 크롭)
  → 2. prepare_context(ExtractionResult)  # T2, PII 경계
       → text: (page, bbox.y) 정렬 스트림에서 text 블록만 이어붙임
       → figures: 각 figure를 최근접 caption과 페어링한 Figure{crop, caption, anchor}
  → 3. NoteSession.start(text, figures, topic, guideline, note_count) → 노트[]
       refine(instruction)/apply_edit() → 현재 노트만 갱신 (재추출 X)
  → 4. export() → zip(노트 md + 그림)
```
**핵심:** 추출(OCR)은 맨 앞 1회. `refine`은 원본 텍스트+현재 노트+지시를 LLM에 보내 **노트만** 갱신(재추출 없음).

## 핵심 추상
```
NoteSession
  context : text(읽기순서) + figures[Figure{crop,caption,anchor}]   ← PII 경계(LLM엔 텍스트만)
  notes   : 현재 노트[] (프론트매터 + 본문 + ![[그림]])
  history : [(지시, 결과 노트 버전), ...]
  start(topic, guideline, note_count) · refine(instruction) · apply_edit(note_id, md) · export()

LLMClient (범용, 스왑: mock | anthropic | openai호환 | local)   ← "그냥 LLM"
  complete(messages) -> text

notes 프롬프트 빌더 (LLMClient 위에서 요약/리파인 로직 + NoteDraft 파싱)
  summarize(client, text, *, topic, guideline, note_count) -> [NoteDraft(title, body)]
  refine(client, note_markdown, instruction, *, text)      -> NoteDraft
```

## 작업 단위 — 완료 ✅ (전부 구현·테스트)
- **T1** — `Note`/`NoteDraft` 모델 + 프론트매터 렌더(확정 스키마 `id/title/source/pages/topic/tags/created`, `id`·`created` 주입식·결정적)
- **T2** — 텍스트 추림 + **그림↔캡션 페어링**(PII 경계): 모든 블록 `(page, bbox.y)` 정렬 → text 컨텍스트 + `Figure{crop, caption, anchor}` 목록(최근접 caption 매칭, 임계값 초과 시 미매칭)
- **T3** — 범용 `LLMClient`(`complete(messages)->text`) + `MockLLMClient`(결정적) + 설정 스왑(`LLM_BACKEND=mock|anthropic|openai|local`, 실 어댑터는 스텁) + `notes`의 `summarize()`/`refine()` 프롬프트 빌더(→ NoteDraft 파싱)
- **T4** — `NoteSession.start()`: text+figures+topic+guideline+note_count → 초기 노트[](프론트매터+본문+`![[그림]]`+캡션)
- **T5** — `NoteSession.refine(instruction)` + `apply_edit()`: 현재 노트 갱신, history 기록, **직접 편집이 다음 refine 기준**
- **T6** — `build_session()` 오케스트레이션: `extract → prepare_context → NoteSession.start` (추출↔노트 연결)
- **T7** — 번들 내보내기(zip: 노트 md + 그림, 옵시디언 친화 파일명 `{source}-p{page}-fig{n}.png`)
- **T8** — 에지: 텍스트 0건("요약할 텍스트 없음", 빈 노트 방지), LLM 오류(예외·세션 상태 손상 없음), 노트 분할(N개 독립 프론트매터)
- **T9** — 단위/통합 테스트(mock + **합성 다중 페이지 ExtractionResult** + fixture 69/200/250)

## 완료 조건 (관찰 가능) — 전부 충족 ✅ (/evaluate PASS, 2026-09-06)
- [x] `start()`: **추출 텍스트만**으로 1~N 노트, 확정 프론트매터(7필드, `pages=[..]`), `![[그림]]`+캡션 첨부
- [x] `start()`가 **guideline(사용자 지시) 반영**
- [x] T2: 그림이 **캡션과 페어링**되어 앵커(위치)와 함께 보존; 텍스트 사이 그림 위치 안 엉킴
- [x] `refine(instruction)`: 현재 노트가 지시대로 갱신 + history 기록
- [x] `apply_edit()`: 직접 편집이 현재 상태 → **다음 refine 기준**
- [x] 프롬프트 힌트로 **1개(기본)/N개** 노트, 각 독립 프론트매터(id 상이)
- [x] `build_session()`으로 **추출→노트**가 한 흐름으로 연결
- [x] **번들(zip) 내보내기**(md + 그림)
- [x] 텍스트 0건 시 안내 + **빈 노트 저장 방지**
- [x] **PII**: LLM엔 텍스트만(이미지/bbox/원문 파일 미전송), 로그 원문 미기록 (spy 테스트 + 로깅 감사)
- [x] 단위 테스트 통과 + **기존 19 passed 유지** — 총 **56 passed**

## 테스트 케이스 (LLM은 mock으로 결정적)
| # | 시나리오 | 입력 | 기대 |
|---|---|---|---|
| 1 | start 정상 | fixture 200 추출 + topic + guideline | 노트 1개, 프론트매터 7필드, `![[그림]]`+캡션, guideline 반영 |
| 2 | 그림 페어링 | text 사이 figure+caption | Figure{crop,caption,anchor}, 위치 보존 |
| 3 | 다중 페이지 | 합성 ExtractionResult(3페이지) | text가 페이지·읽기순서로 이어짐 |
| 4 | refine | start 후 지시 | 지시 반영 새 버전, history +1 |
| 5 | apply_edit | 편집 후 refine | 편집본이 다음 refine 기준 |
| 6 | 노트 분할 | note_count=2 | 노트 2개, id 상이 |
| 7 | 텍스트 0건 | 텍스트 없는 추출 | 안내, 빈 노트 없음 |
| 8 | PII 경계 | summarize/refine 인자 검사 | 텍스트만, 이미지/bbox 없음 |
| 9 | LLM 오류 | mock 예외 | 예외, 세션 이전 노트 유지 |
| 10 | export | 세션 → zip | zip에 md + 그림 포함 |

## 하드 임계값
- 품질: 린트 0, 타입 0, 기존 테스트 전부 통과(**19 passed 유지**)
- 커버리지: 세션 start/refine/apply_edit/export + 텍스트추림·페어링(PII) 단위 테스트
- PII: 이미지·원문 파일 외부 미전송, 로그 원문 미기록

## 검증 방법
- 단위/통합: `cd backend && pytest` (Mock summarizer + 합성/fixture 추출)
- PII: `grep` 원문 로깅 없음 + summarize/refine 인자 감사
- 번들: 생성 zip에 md·그림 포함 확인

## 확정된 설계 결정 (sign-off)
- **LLM 추상 = 범용 `LLMClient`(complete) + notes 프롬프트 빌더 (B안)**. 공급자 독립: `mock|anthropic|openai호환(GPT/DeepSeek/Qwen/Ollama/vLLM)|local`. 실 어댑터는 후속. 프라이버시상 **로컬 오픈모델(예: Ollama Qwen)** 도 선택지(텍스트조차 외부 미전송).
- LLM: Sprint 2는 **mock만**(실 호출 후속) · 번들: **zip** · 그림 파일명: **rename** `{source}-p{page}-fig{n}.png`
- id: `hash(source+pages+topic)` · `created`: 주입식(결정적) · guideline: 1급 입력
- 대화 = **함수 호출 + 상태**(UI는 Sprint 3) · **직접 편집이 다음 refine 기준**
- 그림↔캡션 **페어링은 T2(note-prep)** 에서 수행(추출기 블록 계약은 불변) · 추출 1회, refine는 LLM만 반복
- 오프라인 테스트는 **합성 다중 페이지 ExtractionResult** 사용(fixture는 69/200/250 단일 페이지만)

## 영향 범위
- 신규: `backend/app/notes/`(models·summarizer·session·prepare·export), `backend/tests/test_notes.py`
- 변경: `backend/app/config.py`(`SUMMARIZER_BACKEND` 등)
- 외부 액션: 없음(실 Anthropic 호출은 후속)
- 마이그레이션: 없음

## 사용자 Sign-off
- [x] 사용자가 명시적으로 확인함 (2026-08-31)

## 변경 이력
- 2026-08-31: 초안 작성 + sign-off. Sprint 2를 "한 방 요약"에서 **대화형 리파인 엔진**으로 재구성(사용자 통찰). guideline 1급 입력, 그림↔캡션 T2 페어링, build_session 오케스트레이션, 추출 1회+refine LLM만.
- 2026-08-31: T3 재정의(사용자 결정 B) — `Summarizer` 작업 인터페이스 → **범용 `LLMClient` + notes 프롬프트 빌더**. 공급자 독립(anthropic/openai호환/로컬), 재사용성·프롬프트 단일화. (T1·T2 이미 구현·통과, 29→계속)
- 2026-09-06: **Sprint 2 완료.** 전 작업 구현(models·prepare+페어링·llm·summarize/refine·session·orchestrate·export). `/evaluate` PASS(완료조건 전부 + PII 감사) → 결함 #1(refine/편집 후 그림 임베드 소실·테스트 공백) 수정(임베드를 `to_markdown()`이 `figures`에서 렌더) → 재검증 **PASS**. 총 **56 passed**(extractor 19 유지). 결함 #2(다중 노트 시 그림 첫 노트에만)는 v1 의도로 기록.
- 2026-09-06: **계약 추가 — ADK 패턴 A (사용자 sign-off).** `NoteSession`을 Google ADK Session 개념으로 재구성: `state`(KV, prefix `user:`/`temp:` 규칙) + `events`(append-only, `state_delta` 스냅샷). 모든 변경은 이벤트 기록 경유(직접 수정 금지), **undo/revert 포함(이번 스프린트)**, `refine`이 최근 지시(events)를 프롬프트 맥락으로 주입(다중턴), `user:preferred_guideline` 폴백. `history`→`events` 정리(별칭 없음). 참고: `docs/adk-context-notes.md`.
  - 추가 완료조건: [모든 mutation이 event+state_delta 경유] · [refine이 이전 지시 맥락 사용] · [undo()/revert_to() 동작] · [user:preferred_guideline 폴백] · [temp: 키 미잔류] · [기존 56 passed 유지 + 신규 테스트 + /evaluate 재통과]
  - **결과: `/evaluate` 재검증 PASS** (총 **63 passed**, 19 baseline 유지, deepcopy 격리·PII·원자성 검증). 알려진 minor 제약: **다단계 undo 미지원**(단일 단계 undo만; 연속 undo는 revert 이벤트 근처 오실레이트) — 계약 미명세, 후속 개선 여지.

## 참조
- spec: `.claude/harness/spec.md`
- 이전 계약: `plan-sprint0.md`, `plan-sprint1.md`
- 추출 계약/구현: `backend/app/extractor.py`, `backend/app/extractors/`
- fixture: `backend/tests/fixtures/page{69,200,250}.json`
- 다음 단계: **Sprint 3 (React UI)** — 리파인 엔진(`build_session`/`NoteSession`)을 화면에 배선. `/sprint-contract` 후 착수.
- 구현 위치: `backend/app/notes/`, `backend/app/llm/`, `backend/tests/test_notes.py`