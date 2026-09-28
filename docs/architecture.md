# Architecture

## 전체 구조

```
personal-knowledge-system/
├── backend/        # Python + FastAPI
├── frontend/       # React + Vite
├── docs/
│   ├── architecture.md   ← 이 파일
│   ├── spikes/           # OCR 실험 결과
│   └── research/         # 기술 리서치 노트
└── test/           # Playwright E2E
```

---

## 백엔드 — DDD 레이어드 아키텍처

의존 방향: `presentation → application → domain ← infrastructure`

```
backend/app/
├── presentation/       # HTTP 핸들러 · DI · 스키마 변환. FastAPI 허용
│   ├── notes_router.py
│   ├── chat_router.py
│   └── library_router.py
│
├── application/        # 유스케이스 · DB 쿼리. FastAPI import 금지
│   ├── chat_service.py
│   ├── chat_repository.py
│   └── library_repository.py
│
├── domain/             # 순수 모델 · 인터페이스. 외부 라이브러리 의존 금지
│   ├── extractor.py            # LayoutExtractor 인터페이스 + Block/BBox 모델
│   └── notes/
│       ├── note_models.py      # Note, NoteDraft 모델
│       ├── note_session.py     # NoteSession (상태 + 이벤트)
│       ├── note_prepare.py     # 추출 결과 → LLM 입력 변환
│       ├── note_summarize.py   # LLM 요약 호출
│       ├── note_orchestrate.py # 세션 빌드 오케스트레이션
│       └── note_export.py      # ZIP 번들 생성
│
├── infrastructure/     # 외부 시스템 구현체
│   ├── llm_client.py           # LLMClient 프로토콜 + 타입
│   ├── anthropic_llm_client.py # 실 Claude API 클라이언트
│   ├── mock_llm_client.py      # 테스트용 결정적 mock
│   ├── chat_prompt.py          # 자유 대화 프롬프트 빌더
│   ├── ocr_cache.py            # SQLite 기반 OCR 결과 캐시
│   ├── note_session_store.py   # 인메모리 세션 레지스트리
│   └── extractors/
│       ├── base_extractor.py   # 렌더 루프 + 정규화 공유 로직
│       ├── modal_extractor.py  # 서버리스 GPU (PaddleOCR-VL)
│       └── fixture_extractor.py # 오프라인 재생 (개발·테스트용)
│
├── schemas/            # 공용 Pydantic DTO (__init__.py에서 전체 re-export)
│   ├── notes_schemas.py
│   ├── chat_schemas.py
│   └── library_schemas.py
│
├── config.py           # Settings — 환경변수 + .env.modal 로드
├── db.py               # SQLite 연결 + 스키마 초기화
├── pages.py            # 페이지 번호 파싱/포매팅 유틸
└── main.py             # FastAPI 앱 진입점
```

### 레이어 규칙

| 레이어 | FastAPI import | 외부 라이브러리 |
|--------|---------------|----------------|
| `presentation/` | 허용 | 허용 |
| `application/` | **금지** | 허용 |
| `domain/` | **금지** | **금지** |
| `infrastructure/` | **금지** | 허용 |

### 파일 명명 규칙

디렉토리 없이 파일명만 봐도 역할이 명확해야 한다.

- 서비스: `chat_service.py`
- 리포지토리: `library_repository.py`, `chat_repository.py`
- 클라이언트 구현체: `anthropic_llm_client.py`, `mock_llm_client.py`
- 라우터: `notes_router.py`, `chat_router.py`

---

## 프런트엔드

```
frontend/src/
├── components/     # 재사용 UI 컴포넌트
├── pages/          # 라우트 단위 페이지
├── hooks/          # 커스텀 React 훅
└── api/            # 백엔드 API 클라이언트
```

---

## 데이터 흐름 — PDF 요약 노트 생성

```
PDF 업로드
  → presentation/notes_router.py
  → domain/notes/note_orchestrate.py (build_session)
      → infrastructure/ocr_cache.py (캐시 확인)
      → infrastructure/extractors/modal_extractor.py (OCR, 미캐시 페이지만)
      → domain/notes/note_prepare.py (블록 → LLM 입력)
      → domain/notes/note_summarize.py (LLM 요약 호출)
  → NoteSession 반환 (노트 목록 + 이벤트 이력)
```

## 데이터 흐름 — 자유 대화

```
사용자 메시지
  → presentation/chat_router.py
  → application/chat_service.py
      → infrastructure/ocr_cache.py (컨텍스트 페이지 로드)
      → infrastructure/chat_prompt.py (메시지 조립)
      → infrastructure/anthropic_llm_client.py (LLM 호출)
  → 응답 반환 + DB 히스토리 저장 (application/chat_repository.py)
```

---

## 설계 결정 이력

| 결정 | 이유 |
|------|------|
| DDD 레이어드 아키텍처 | 레이어명이 역할을 드러냄. `presentation/`, `application/`, `domain/`, `infrastructure/` |
| 파일명에 도메인 prefix | `service.py` 대신 `chat_service.py` — 디렉토리 없이 파일명만 봐도 역할 식별 |
| LLM에 텍스트만 전송 | PII 보호 — 이미지·bbox·원문 파일은 외부 미전송 |
| OCR 결과 SQLite 캐시 | 동일 PDF 재처리 방지. 페이지 단위 부분 캐시 지원 |
| fixture_extractor | 오프라인 개발·테스트용. Modal 비용 없이 재현 가능한 실행 |
