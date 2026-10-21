# Sprint Contract — Sprint 7: OCR 범위와 대화 범위 분리 (주제별 2축) — 2026-10-20

> `/sprint-contract`로 작성. spec: `.claude/harness/spec-sprint7.md`. 사용자 sign-off 대기.

## 목표

1 PDF 아래 **주제별 '추출 세트'(OCR 범위)** 와 **주제별 '대화'(질의 범위)** 를 **독립 2축**으로 생성·관리한다. 둘은 페이지 단위 OCR 캐시만 공유하고, 대화가 미캐시 페이지를 포함하면 그때 해당 페이지만 OCR한다(기존 동작 보존).

## 전체 스프린트 맵

- Sprint 0~5 ✅ / Sprint 6 — 형광펜 색 검출/가중치 ✅
- **Sprint 7 — OCR 범위와 대화 범위 분리(주제별 2축)** ← *이번 계약*

---

## 작업 단위

### 백엔드

**B1 — DB 스키마** `app/db.py`
- `extractions` 테이블: `id TEXT PK, pdf_file_id TEXT FK, topic TEXT, pages_json TEXT, created_at TEXT`.
- `conversations.topic TEXT` 컬럼 추가. 기존 DB 멱등 마이그레이션: `PRAGMA table_info(conversations)`로 `topic` 부재 시에만 `ALTER TABLE ... ADD COLUMN topic TEXT`.

**B2 — 추출 세트 스키마** `app/schemas/` (신규 `extraction_schemas.py` + `__init__` re-export)
- `ExtractionCreate(topic: str, pages_str: str)`
- `ExtractionResponse(id, pdf_file_id, topic, pages: list[int], pages_display, created_at)`

**B3 — 추출 세트 쿼리/서비스** `app/application/extraction_repository.py` (fastapi import 금지)
- `row_to_extraction(row) -> ExtractionResponse`
- `insert_extraction(db, …) ` / `list_extractions(db, pdf_file_id)` / `delete_extraction(db, id)` (page_extractions 미삭제)

**B4 — 추출 세트 라우터** `app/presentation/extraction_router.py` (thin)
- `POST   /books/{book_id}/pdfs/{pdf_id}/extractions` → pages 파싱 → `get_or_extract`로 범위 OCR → insert → 201 `ExtractionResponse`
- `GET    /books/{book_id}/pdfs/{pdf_id}/extractions` → `list[ExtractionResponse]`
- `DELETE /books/{book_id}/pdfs/{pdf_id}/extractions/{id}` → 204 (페이지 캐시 보존)
- book/pdf 존재 검증(404), 잘못된 pages_str 422

**B5 — 대화 topic** `chat_schemas.py` · `chat_repository.py` · `chat_router.py`
- `ConversationResponse.topic: str | None`; `row_to_conv`에 topic 포함
- `persist_exchange`: 첫 메시지(`had_topic`=False)면 `topic` 자동 설정(첫 user 메시지 기반)
- `ConversationUpdate(topic: str)` + `PATCH /conversations/{id}` → topic 수정, `ConversationResponse` 반환
- `ChatExchange`에 `had_topic` 추가, send_message에서 전달

**B6 — 라우터 등록** `app/main.py`
- `extraction_router` include

### 프런트엔드

**F1 — 타입** `types.ts`
- `Extraction { id, pdf_file_id, topic, pages, pages_display, created_at }`
- `Conversation`에 `topic: string | null`

**F2 — API** `api.ts`
- `createExtraction(bookId, pdfId, topic, pagesStr)` / `getExtractions(bookId, pdfId)` / `deleteExtraction(bookId, pdfId, id)`
- `updateConversationTopic(convId, topic)` → `PATCH /conversations/{id}`

**F3 — ExtractionList 컴포넌트** `components/ExtractionList.tsx`
- PDF의 추출 세트 목록(주제 + pages_display) + 삭제 + `[+ 추출 세트]` 인라인 폼(주제 + 페이지 범위)

**F4 — ConversationList topic 표시/수정** `components/ConversationList.tsx`
- 항목에 topic 표시(없으면 title/"새 대화"), 주제 인라인 수정(연필) → `updateConversationTopic`

**F5 — App 2축 레이아웃** `App.tsx`
- PDF 선택 시 우측에 **'추출 세트' 섹션 + '대화' 섹션** 독립 표시 (`ExtractionList` + `ConversationList`)

### 테스트

**T1 — pytest `tests/test_extraction_api.py` (신규)**
- X1: 세트 생성(주제 "자료구조", "1-5") → 201 + `page_extractions`에 1~5 저장
- X2 캐시 공유: X1 후 대화 "3-7" 생성 → newly_extracted==2 (3~5 히트)
- X3 목록/삭제: 세트 2개 → 목록 2 → 1 삭제 → 목록 1 + page_extractions 보존
- 잘못된 pages_str → 422, 없는 pdf → 404
- 독립성: 세트만 생성(대화 0) 성공

**T2 — pytest `tests/test_chat_api.py` 확장**
- T-topic1: topic 없이 대화 생성 → 첫 메시지 전송 → `topic` 자동 설정
- T-topic2: `PATCH /conversations/{id}` topic="트랜스포머" → 응답 topic 반영
- R1 회귀: 세트 없이 대화 "9" 생성 → 9 on-demand OCR, 대화 정상(기존 테스트 유지)

**T3 — Playwright E2E `test/09-extraction-scope.spec.ts` (신규)**
- PDF 선택 → 추출 세트 폼 "자료구조 / 1-5" 생성 → 세트 목록 표시
- 별도로 대화 생성 → 대화 목록에 표시 (두 섹션 독립)

---

## 완료 조건

- [ ] `POST .../extractions` (주제+pages_str) → 범위 OCR(미캐시만) 후 201 세트 반환
- [ ] `GET .../extractions` → 해당 PDF 세트 목록
- [ ] `DELETE .../extractions/{id}` → 204, `page_extractions` 보존
- [ ] 세트 생성이 페이지 캐시를 채움 → 동일 페이지 대화는 재OCR 0회 (X2 newly_extracted==2)
- [ ] `conversations.topic` — 첫 메시지 시 자동 설정(비어있을 때만)
- [ ] `PATCH /conversations/{id}` topic 수정 → 응답 반영
- [ ] `ConversationResponse`에 topic 포함
- [ ] 세트 전혀 없이 대화 생성(on-demand OCR) 정상 — 기존 동작 회귀 없음
- [ ] 세트와 대화 독립 — 외래키로 서로 묶이지 않음(세트만/대화만 각각 생성 가능)
- [ ] 프런트: PDF 선택 시 '추출 세트'·'대화' 2개 섹션 각각 표시·생성·삭제
- [ ] `pytest` 전체(기존 114 + 신규) 통과 / `tsc --noEmit` 0 / `npm run test:e2e` 신규+기존 PASS

## 테스트 케이스 상세

| ID | 시나리오 | 입력 | 기대 출력 |
|----|---------|------|----------|
| X1 | 세트 생성+OCR | 주제 "자료구조", "1-5" | 201, page_extractions 1~5 |
| X2 | 캐시 공유 | X1 후 대화 "3-7" | newly_extracted==2 |
| X3 | 목록/삭제 | 세트 2개 → 1 삭제 | 목록 1, 캐시 보존 |
| X4 | 잘못된 범위 | pages "10-5" | 422 |
| X5 | 없는 PDF | 잘못된 pdf_id | 404 |
| TP1 | topic 자동 | topic 없이 생성 + 첫 메시지 | topic 자동 설정 |
| TP2 | topic 수정 | PATCH topic="트랜스포머" | 응답 topic 반영 |
| R1 | 회귀 on-demand | 세트 없이 대화 "9" | 9 OCR, 대화 정상 |
| E1 | E2E 2축 | 세트 "자료구조 1-5" + 대화 생성 | 두 섹션 각각 표시 |

## 하드 임계값

- 세트 생성 시 이미 캐시된 페이지 **재OCR 0회**
- 세트 삭제가 `page_extractions` **미삭제**
- 추출 세트 ↔ 대화 간 외래키 의존 **0**
- `pytest` 전체 통과 / `tsc` 0 / `npm run test:e2e` PASS

## 검증 방법

```bash
cd backend && pytest -v
cd frontend && npx tsc --noEmit
# E2E는 Node 24 (nvm use default) 후
npm run test:e2e        # 09-extraction-scope 포함
```

## 구현 순서

1. B1(스키마) → B2(세트 스키마) → B3(쿼리) → B4(라우터) → B6(등록) → T1
2. B5(대화 topic + PATCH) → T2
3. F1(타입) → F2(api) → F3(ExtractionList) → F4(ConversationList topic) → F5(App 2축)
4. T3(E2E)
5. 문서 갱신(architecture.md DB/흐름/설계결정 "독립 2축" + CLAUDE.md 도메인 용어 "추출 세트")

## 확정 결정 사항

| 항목 | 결정 | 이유 |
|------|------|------|
| 세트↔대화 관계 | 독립 2축 (FK 없음) | 사용자 승인 — 주제별 선OCR/조직화와 질의를 분리 |
| 대화 범위 편집 | 생성 시 확정(불가) | 이번 범위 밖, topic만 수정 |
| 세트 생성 OCR | 즉시 동기(get_or_extract) | 대화 생성과 동일 방식 |
| 세트 삭제 | 캐시 보존 | page_extractions는 PDF 공유 자원 |
| on-demand OCR | 기존 create_conversation 동작 유지 | 이미 미캐시 페이지만 추출 |
| 대화 topic 자동 | 첫 메시지에서(title과 동일 자리) | 입력 부담 0, 이후 수정 가능 |

## 변경 이력

- 2026-10-20 최초 작성

## 사용자 Sign-off
- [x] 사용자가 명시적으로 승인함 (2026-10-21)