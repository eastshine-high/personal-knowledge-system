# Sprint Contract — Sprint 5: 서재 + 자유 대화 — 2026-09-21

> `/sprint-contract`로 작성. spec: `.claude/harness/spec-sprint5.md`. 사용자 sign-off 대기.

## 목표

사용자가 서재에 책(PDF 묶음)을 등록하고, 특정 PDF의 페이지를 지정해 LLM과 자유 대화를 시작하거나 이어갈 수 있으며, OCR 결과는 캐시해 중복 추출을 생략한다.

## 전체 스프린트 맵

- Sprint 0 — 스캐폴딩 & 스파이크 ✅
- Sprint 1 — LayoutExtractor + Modal + fixture ✅
- Sprint 2 — 노트 조립 + 리파인 엔진 ✅
- Sprint 3 — React UI ✅
- Sprint 4 — 통합·에지·Anthropic LLM ✅
- **Sprint 5 — 서재 + 자유 대화** ← *이번 계약*

---

## 작업 단위

### 백엔드

**B0 — SQLite 연결 모듈** `backend/app/db.py`
- `get_db() → sqlite3.Connection` (thread-local)
- `init_db()` — `CREATE TABLE IF NOT EXISTS` 5개 테이블 전부
- `main.py` startup 이벤트에서 `init_db()` 호출
- `.gitignore`에 `backend/pks.db` 추가

**B1 — 페이지 범위 파서** `backend/app/pages.py`
- `parse_pages("10-15, 21") → [10,11,12,13,14,15,21]`
  - 단일(`5`), 범위(`10-15`), 혼합(`1-3, 7, 10-12`) 모두 지원
  - 정렬·중복제거·역순범위/음수 ValueError
- `format_pages([10,11,12,13,14,15,21]) → "p.10-15, 21"` (연속 구간 압축)

**B2 — Pydantic 스키마** `backend/app/schemas.py` 확장
- `BookCreate(title)`, `BookResponse(id, title, created_at, pdf_files)`
- `PdfFileCreate(label, pdf_path)`, `PdfFileResponse(id, book_id, label, pdf_path, created_at)`
- `ConversationResponse(id, book_id, pdf_file_id, pages, pages_display, title, created_at)`
- `MessageCreate(content)`, `MessageResponse(id, role, content, created_at)`
- `ChatResponse(conversation, message)` — 메시지 전송 응답

**B3 — 서재 라우터** `backend/app/library_router.py`
- `GET  /books` → `list[BookResponse]`
- `POST /books` → `BookResponse` (201)
- `POST /books/{book_id}/pdfs` → `PdfFileResponse` (201), pdf_path 존재 검증
- `DELETE /books/{book_id}/pdfs/{pdf_id}` → 204

**B4 — OCR 캐시 레이어** `backend/app/ocr_cache.py`
```python
def get_or_extract(
    db, pdf_file_id: str, pages: list[int],
    pdf_path: str, extractor: LayoutExtractor
) -> list[PageExtraction]:
    # 1. 캐시 조회 → 히트 페이지 분리
    # 2. 미스 페이지 → extractor.extract() → DB INSERT
    # 3. 전체 병합 후 반환
```
- `PageExtraction(page_num, blocks)` 반환 타입

**B5 — 자유 대화 프롬프트 빌더** `backend/app/llm/chat_prompt.py`
- `build_chat_messages(context_text: str, history: list[dict]) → list[Message]`
  - system: `[CONTEXT]\n{context_text}`
  - history: `role=user/assistant` 순서대로
- 컨텍스트 길이 초과 시 오래된 메시지 앞에서 제거 (CONTEXT 블록 유지)

**B6 — 대화 라우터** `backend/app/chat_router.py`
- `GET  /books/{book_id}/conversations` → `list[ConversationResponse]`
- `POST /books/{book_id}/conversations`
  - body: `{pdf_file_id, pages_str}` (`"10-15, 21"` 형식)
  - OCR 캐시 경유 추출 → conversations INSERT → `ConversationResponse`
- `GET  /conversations/{id}/messages` → `list[MessageResponse]`
- `POST /conversations/{id}/messages`
  - body: `MessageCreate(content)`
  - DB에서 히스토리 로드 → LLM 호출 → 양쪽 메시지 INSERT → `ChatResponse`

**B7 — main.py 라우터 등록**
- `library_router`, `chat_router` include
- startup: `init_db()`

---

### 프론트엔드

**F1 — 타입 정의** `frontend/src/types.ts` 확장
- `Book`, `PdfFile`, `Conversation`, `Message`, `ChatResponse`

**F2 — API 클라이언트 확장** `frontend/src/api.ts`
- `getBooks()`, `createBook()`, `addPdf()`, `deletePdf()`
- `getConversations()`, `createConversation()`
- `getMessages()`, `sendMessage()`

**F3 — LibraryPanel 컴포넌트** `frontend/src/components/LibraryPanel.tsx`
- 책 목록 (아코디언: 클릭 시 PDF 목록 펼침)
- 각 PDF 항목: 레이블 + 클릭 선택 + 삭제 버튼
- 하단: `[+ 책 추가]` 버튼 → 인라인 폼(책 제목 입력)
- PDF 목록 하단: `[+ PDF 추가]` 버튼 → 인라인 폼(경로 + 레이블)

**F4 — ConversationList 컴포넌트** `frontend/src/components/ConversationList.tsx`
- PDF 선택 시 해당 PDF의 대화 목록
- 각 항목: 제목(또는 "새 대화") + 페이지 범위 표시(`p.10-15, 21`)
- `[새 대화]` 버튼 → NewChatForm 표시

**F5 — NewChatForm 컴포넌트** `frontend/src/components/NewChatForm.tsx`
- 페이지 범위 입력 (`"10-15, 21"` placeholder)
- `[시작]` 버튼 → `POST /books/{id}/conversations`
- 진행 중 스피너, 에러 표시

**F6 — ChatPanel 컴포넌트** `frontend/src/components/ChatPanel.tsx`
- 메시지 목록 (user: 오른쪽 버블, assistant: 왼쪽)
- 하단 입력창 + `[전송]` (Enter 전송, Shift+Enter 줄바꿈)
- 로딩 중 어시스턴트 버블 표시

**F7 — MockLLMClient 자유 대화 지원** `backend/app/llm/client.py`
- `task == "chat"` 분기 추가
- `[CONTEXT]` + `[HISTORY]` 블록 파싱 → 결정적 응답 반환

**F8 — App.tsx 레이아웃 개편**
- 좌측: `LibraryPanel` (고정 너비 240px)
- 우측: 상태에 따라
  - PDF 미선택 → "서재에서 PDF를 선택하세요" 안내
  - PDF 선택 → `ConversationList` + `NewChatForm` / `ChatPanel`
- 우측 상단: "노트 생성" 버튼 → 클릭 시 기존 `InputForm` 모달로 표시
  - 모달 외부 클릭 또는 ESC → 닫힘, 세션 생성 성공 시 자동 닫힘

---

### 테스트

**T1 — pytest `test_pages.py`**
- `parse_pages` 정상·에지(단일, 혼합, 역순 에러, 음수 에러)
- `format_pages` 연속 압축 확인

**T2 — pytest `test_ocr_cache.py`**
- 캐시 미스 → extractor 호출 + DB 저장
- 캐시 히트 → extractor 미호출 + DB 반환
- 부분 캐시(일부 히트, 일부 미스) → 미스만 추출

**T3 — pytest `test_library_api.py`**
- 책 생성 → 조회
- PDF 등록(존재하는 경로) → 목록 포함
- PDF 등록(없는 경로) → 404
- PDF 삭제 → 목록에서 제거

**T4 — pytest `test_chat_api.py`**
- 새 대화 생성 → conversation 반환, OCR 캐시 저장 확인
- 메시지 전송 → assistant 응답 반환, messages 2건 저장
- 이어서 대화 → 히스토리 포함 응답

**T5 — Playwright E2E** `test/07-library.spec.ts`
- S5a: 책 추가 + PDF 2개 등록 → 서재 트리 표시
- S5b: PDF 선택 → 페이지 입력 → 새 대화 → 메시지 표시
- S5c: 목록에서 기존 대화 클릭 → 메시지 이어서 전송
- S5d: 기존 노트 생성(회귀) — fixture page 69 → 노트 생성 정상

---

## 완료 조건

- [ ] `GET /books`, `POST /books` 동작
- [ ] `POST /books/{id}/pdfs` — 없는 경로면 404, 있는 경로면 201
- [ ] `POST /books/{id}/conversations` — OCR 캐시 경유, conversation 생성
- [ ] 동일 pdf_file_id + page_num 두 번째 요청 → extractor 미호출 (T2 확인)
- [ ] `POST /conversations/{id}/messages` → assistant 응답 반환
- [ ] 서재 패널에 책/PDF 트리 표시
- [ ] 페이지 입력 `"10-15, 21"` → 대화 시작 → 채팅 화면
- [ ] 대화 목록에 `p.10-15, 21` 형식 표시
- [ ] 기존 대화 선택 → 이어서 전송 가능
- [ ] 기존 노트 생성 워크플로우 회귀 없음 (S5d PASS)
- [ ] `pytest` 전부 통과 (기존 76개 + 신규)
- [ ] `tsc --noEmit` 에러 0

## 테스트 케이스 상세

| ID | 시나리오 | 입력 | 기대 출력 |
|----|---------|------|----------|
| S5a | 책+PDF 등록 | 책 제목 "어텐션", PDF 경로 2개 | 서재 트리에 표시 |
| S5b | 새 대화 | PDF 선택 + `"69, 200"` | 채팅 화면, LLM mock 응답 |
| S5c | 이어서 대화 | 기존 대화 클릭 + 메시지 | 히스토리 포함 응답 |
| S5d | 회귀 | 노트 생성 fixture page 69 | 기존 노트 생성 정상 |
| U1 | 페이지 파싱 | `"1-3, 7, 10-12"` | `[1,2,3,7,10,11,12]` |
| U2 | 캐시 히트 | 동일 pdf+page 2회 | extractor 1회만 호출 |
| U3 | 잘못된 경로 | 없는 pdf_path | 404 |

## 하드 임계값

- 캐시 히트 시 대화 시작 응답 < 5초
- `pytest` 기존 76개 + 신규 전부 통과
- `tsc --noEmit` 에러 0
- `npm run test:e2e` S5a~S5d PASS

## 검증 방법

```bash
# 백엔드 단위
cd backend && pytest -v

# 타입 체크
cd frontend && npx tsc --noEmit

# E2E (백엔드 + 프론트엔드 동시 실행 필요)
npm run test:e2e
```

## 구현 순서

1. B0 → B1 → B2 (인프라·파서·스키마)
2. B3 → T3 (서재 API)
3. B4 → T2 (OCR 캐시)
4. B5 → B6 → T4 (대화 API)
5. B7 (라우터 등록)
6. F1 → F2 → F7 (타입·API·Mock 확장)
7. F3 → F4 → F5 → F6 (컴포넌트)
8. F8 (레이아웃)
9. T5 (E2E)

## 확정 결정 사항

| 항목 | 결정 | 이유 |
|------|------|------|
| 노트 생성 진입점 | **버튼 → 모달** | 서재 레이아웃 유지, 기존 InputForm 재사용 |
| 페이지 입력 형식 | `"10-15, 21"` 혼합 | 단일·연속·비연속 모두 지원 |
| OCR 캐시 키 | `(pdf_file_id, page_num)` | PDF 파일 단위 독립 캐시 |
| DB 파일 | `backend/pks.db` | gitignored |

## 사용자 Sign-off
- [x] 사용자가 명시적으로 확인함 (2026-09-21)
