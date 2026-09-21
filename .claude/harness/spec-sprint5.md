# Spec — Sprint 5: 서재 + 자유 대화 — 2026-09-21

> `/plan Sprint 5`로 작성. 사용자 sign-off 대기.

## 목표 (1문장)
사용자가 서재에 책(PDF 묶음)을 등록하고, 특정 PDF의 페이지를 지정해 LLM과 자유 대화를 시작하거나 이어갈 수 있으며, OCR 결과는 캐시해 중복 추출을 생략한다.

## 배경
기존 "PDF 경로 직접 입력 → 노트 생성" 워크플로우는 유지한다.
Sprint 5는 그 위에 **서재(책 관리)** 와 **자유 대화(채팅)** 를 더하는 확장이다.
OCR은 비싸므로 동일 페이지는 재추출하지 않는다.

## In Scope

### 서재 (Library)
- 책 등록: 제목 입력
- 책 아래 PDF 파일 등록: PDF 파일명(로컬 경로) + 레이블(예: "1부", "ch2")
- 좌측 패널에 책 목록 표시, 책 클릭 시 PDF 파일 목록 펼침
- PDF 파일 추가/삭제

### 자유 대화 (Free Chat)
- PDF 선택 → 페이지 범위 입력(`10-15, 21` 형식) → 새 대화 시작
- 대화 시작 시 지정 페이지 텍스트를 고정 컨텍스트로 추출(OCR 캐시 우선)
- 사용자 ↔ LLM 멀티턴 채팅(고정 컨텍스트 유지)
- 기존 대화 목록에서 이어서 대화
- 대화 목록에 페이지 범위 표시(`p.10-15, 21`)

### OCR 캐시
- `page_extractions(pdf_file_id, page_num)` SQLite 테이블에 저장
- 새 대화 시 해당 페이지 캐시 존재하면 Modal 호출 생략, 직접 재사용
- 캐시 단위: PDF 파일 × 페이지 번호

### 기존 기능 유지
- 기존 노트 생성 워크플로우(InputForm → NotePanel → RefineChat) 그대로 존재

## Out of Scope
- 서재 PDF 파일 업로드(로컬 경로 입력만)
- 대화 삭제·이름 변경
- 대화 중 페이지 범위 변경
- 노트 생성 워크플로우와 서재의 통합(별도 UI로 공존)
- 캐시 무효화·재추출 트리거

## 화면 구조

```
┌─────────────────┬──────────────────────────────────────┐
│  서재 패널      │  메인 영역                            │
│                 │                                      │
│  📚 책 목록     │  (책/PDF 미선택)  →  안내 메시지      │
│  └ ch1.pdf      │  (PDF 선택)       →  대화 목록 +      │
│  └ ch2.pdf      │                      새 대화 버튼     │
│  [+ PDF 추가]   │  (대화 선택/시작) →  채팅 화면        │
│                 │                                      │
│  [+ 책 추가]    │                                      │
└─────────────────┴──────────────────────────────────────┘
```

- 기존 노트 생성 UI(InputForm)는 별도 진입점 유지(예: 상단 탭 또는 버튼)

## 데이터 모델 (SQLite)

```sql
CREATE TABLE books (
  id         TEXT PRIMARY KEY,
  title      TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE pdf_files (
  id         TEXT PRIMARY KEY,
  book_id    TEXT NOT NULL REFERENCES books(id),
  label      TEXT NOT NULL,   -- "1부", "ch2" 등 사용자 레이블
  pdf_path   TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE page_extractions (
  pdf_file_id TEXT    NOT NULL,
  page_num    INTEGER NOT NULL,
  json        TEXT    NOT NULL,  -- ExtractionResult JSON 직렬화
  created_at  TEXT    NOT NULL,
  PRIMARY KEY (pdf_file_id, page_num)
);

CREATE TABLE conversations (
  id          TEXT PRIMARY KEY,
  book_id     TEXT NOT NULL REFERENCES books(id),
  pdf_file_id TEXT NOT NULL REFERENCES pdf_files(id),
  pages_json  TEXT NOT NULL,   -- JSON 배열: [10,11,12,13,14,15,21]
  title       TEXT,            -- 자동 생성(첫 메시지 앞 20자) 또는 미지정
  created_at  TEXT NOT NULL
);

CREATE TABLE messages (
  id              TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  role            TEXT NOT NULL,  -- "user" | "assistant"
  content         TEXT NOT NULL,
  created_at      TEXT NOT NULL
);
```

## 페이지 범위 입력 규칙

| 입력 예 | 파싱 결과 |
|---------|----------|
| `42-44` | [42, 43, 44] |
| `10-15, 21` | [10, 11, 12, 13, 14, 15, 21] |
| `5` | [5] |
| `1-3, 7, 10-12` | [1, 2, 3, 7, 10, 11, 12] |

- 중복·역순 입력은 정규화(정렬·중복제거)
- 유효하지 않은 입력(음수, 범위 역전)은 즉시 에러 표시

## OCR 캐시 흐름

```
대화 시작 요청 (pdf_file_id, pages=[10..15, 21])
    ↓
DB 조회: 캐시 있는 페이지 분리
    ├── 캐시 있음 [10,11,13] → JSON 역직렬화 → ExtractionResult
    └── 캐시 없음 [12,14,15,21] → Modal 호출 → DB 저장 → ExtractionResult
    ↓
전체 페이지 ExtractionResult 병합 → 텍스트 추출
    ↓
LLM 고정 컨텍스트로 주입 → 대화 시작
```

## 자유 대화 LLM 컨텍스트 규약

- 시스템 프롬프트: `[CONTEXT]` 블록에 추출 텍스트 고정
- 멀티턴: conversations의 messages 전체를 순서대로 전달
- 컨텍스트 길이 초과 시: 오래된 메시지 앞에서부터 제거(단, [CONTEXT]는 유지)

## API 엔드포인트 (신규)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/books` | 책 목록 |
| `POST` | `/books` | 책 등록 |
| `POST` | `/books/{id}/pdfs` | PDF 파일 등록 |
| `DELETE` | `/books/{book_id}/pdfs/{pdf_id}` | PDF 파일 삭제 |
| `GET` | `/books/{book_id}/conversations` | 대화 목록 |
| `POST` | `/books/{book_id}/conversations` | 새 대화 시작 |
| `POST` | `/conversations/{id}/messages` | 메시지 전송 → 응답 반환 |
| `GET` | `/conversations/{id}/messages` | 메시지 목록 |

## 완료 조건

- [ ] 책 등록 → 서재 패널에 표시
- [ ] 책 아래 PDF 파일 등록 (로컬 경로 + 레이블)
- [ ] PDF 선택 → `10-15, 21` 형식 페이지 입력 → 새 대화 시작
- [ ] 동일 페이지 두 번째 대화 시 Modal 호출 없이 캐시 사용
- [ ] 대화 목록에 페이지 범위 표시 (`p.10-15, 21`)
- [ ] 기존 대화 클릭 → 이어서 대화 가능
- [ ] 기존 노트 생성 워크플로우 회귀 없음

## 테스트 케이스

1. **책/PDF 등록:** 책 추가 → PDF 2개 등록 → 서재에 트리 표시
2. **새 대화:** PDF 선택 → `69, 200` 입력 → 대화 시작 → LLM 응답 반환
3. **OCR 캐시:** 동일 PDF + 동일 페이지로 두 번째 대화 시작 → `page_extractions` 재사용, Modal 미호출
4. **이어서 대화:** 기존 대화 선택 → 추가 메시지 전송 → 히스토리 포함 응답
5. **페이지 파싱:** `1-3, 7, 10-12` 입력 → [1,2,3,7,10,11,12] 정규화
6. **회귀:** 기존 노트 생성(fixture 모드 page 69) → 노트 생성 정상 동작

## 하드 임계값

- 캐시 히트 시 대화 시작 < 5초 (Modal 호출 없음)
- 타입 에러 0, 기존 pytest 전부 통과

## 비기능

- SQLite DB 파일: `backend/pks.db` (`.gitignore` 추가)
- DB 초기화: 앱 시작 시 `CREATE TABLE IF NOT EXISTS`

## 사용자 Sign-off
- [x] 사용자가 명시적으로 확인함 (2026-09-21)
