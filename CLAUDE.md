# personal-knowledge-system

> 개인 지식 시스템(PKS). **현재 1차 모듈: PDF 개념 요약 노트 모듈** — 스캔+OCR된 PDF의 특정 페이지 범위·주제를 지정하면, 로컬에서 그림·텍스트를 추출하고 LLM이 텍스트를 요약해 프론트매터가 붙은 마크다운 노트를 만들어 사용자가 옵시디언(PKM)으로 옮기는 도구. 벡터 색인·검색(Qdrant)은 예정된 **후속 모듈**.

## 기술 스택 (1차 모듈)
- **백엔드**: Python + FastAPI (`backend/`)
- **프런트엔드**: React + Vite (`frontend/`)
- **문서 레이아웃 추출**: PaddleOCR-VL(오픈웨이트) — 서버리스 GPU에서 시작, 장비 확보 시 로컬. `backend/app/extractor.py`의 `LayoutExtractor` 인터페이스로 교체
- **요약 LLM**: Anthropic Claude (텍스트만 전송; **이미지·원문은 외부 미전송**). 1차 단일 모델
- **문서 소스**: 스캔+OCR PDF (1차), Obsidian vault (추후)
- **테스트**: pytest (`backend/`) + Playwright (`frontend/` 웹 UI E2E)

> **후속 모듈(이번 범위 밖):** Qdrant 벡터 색인/검색, LangChain 질의. 산출물(프론트매터 노트)은 후속 색인이 그대로 소비하도록 Qdrant-ready로 만든다.
> 상세 스펙·계약은 `.claude/harness/spec.md`, `.claude/harness/plan.md` 참조.

## 하네스 운영

이 프로젝트는 **Harness 표준 개발 환경**을 따른다. 전체 원칙은 `~/.claude/harness/`를 참조.

### Harness 모드
- 모드: **on**  <!-- on | lite | off -->
- 이유: PDF 수집 → 임베딩 → Qdrant 색인 → LangChain 질의 → (선택) UI로 이어지는 다기능 실제 프로젝트. 각 기능마다 완료 정의 합의와 회의적 검증이 이득.

선택지:
- `on`: 풀 워크플로우 적용 (모든 기능 개발 시 /plan → /sprint-contract → /evaluate)
- `lite`: spec만 작성, sprint-contract와 evaluate는 사용자 명시 호출 시에만
- `off`: 하네스 비활성. 어떤 자동 권고도 하지 않음.

### 핵심 워크플로우 (모드 on 기준)
```
/grill (선택) → /plan → /sprint-contract → [구현] → /evaluate → /handoff (선택)
```

### 산출물 위치
- `.claude/harness/spec.md` — Planner 산출물 (요구사항 → spec)
- `.claude/harness/plan.md` — 스프린트 계약 (완료 정의)
- `.claude/harness/eval-checklist.md` — Evaluator 체크리스트
- `.claude/harness/handoff-*.md` — 세션 핸드오프 문서

### 현재 단계 확인
```
/harness-status
```

## 프로젝트 고유 규칙

<!-- 스택이 확정되면 채워 넣기: 디렉토리 구조, 청킹/임베딩 파라미터, Qdrant 컬렉션 스키마, 도메인 용어 등 -->

### 빌드 / 실행
```bash
# 백엔드 (FastAPI)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://localhost:8000 — /health 로 확인

# 프런트엔드 (React + Vite)
cd frontend && npm install
npm run dev                          # http://localhost:5173
```

### 테스트 — 백엔드 (pytest 표준, `backend/`)
```bash
# 첫 셋업 (한 번만)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 실행
cd backend && pytest              # 전체
cd backend && pytest -v           # 상세
```
- 테스트 파일: `backend/tests/test_*.py` (plan.md의 테스트 케이스 1개 = 테스트 함수 1개)
- 외부 API(임베딩/LLM 등)와 Qdrant는 mock 또는 로컬 인스턴스로 결정적 실행 확보

### 테스트 — 웹 UI (Playwright 표준, UI 도입 시)
```bash
# 첫 셋업 (한 번만)
npm install
npx playwright install chromium    # ~200MB

# E2E 실행
npm run test:e2e          # 전체 케이스
npm run test:e2e:ui       # Playwright UI 모드 (디버깅용)
npm run test:e2e:headed   # 브라우저 보면서 실행
```
- `test:e2e`는 루트 `playwright.config.ts`의 webServer가 `frontend/`에서 `npm run dev`(Vite, 포트 5173)를 띄운다 (`webServer.cwd: 'frontend'`).
- 실행 전 `cd frontend && npm install` 필요.
- 테스트 파일: `test/*.spec.ts` (plan.md의 테스트 케이스 1개 = spec 1개)
- 외부 API는 `page.route()`로 mock — 재현성 ↑, 비용 0
- `/evaluate` subagent가 자동으로 `npm run test:e2e` 실행 + `test-results.json` 파싱

### 백엔드 코딩 컨벤션 (`backend/`)

- **단일 책임**: 파일 하나는 하나의 책임만 진다. 역할이 다르면 파일을 나눈다.
- **파일 책임 주석**: 파일을 새로 만들 때 첫 줄에 그 파일의 책임을 docstring으로 명시한다.
- **함수 길이**: 가급적 6줄 이내. 최대 20줄을 넘지 않는다.
- **함수 주석**: 함수의 역할을 한 줄로 요약하고, 파라미터와 반환 타입을 설명한다.
- **파라미터 수**: 파라미터는 3개를 넘지 않는다. 초과 시 dataclass 또는 TypedDict로 묶는다.

### 테스트 작성 컨벤션 — BDD 패턴 (pytest)

- **구조**: 테스트 본문을 `# Given`, `# When`, `# Then` 3단 주석으로 구분. 단계가 자명하면 생략 가능.
- **명명**: `test_[동작 또는 시나리오]` — 구현 용어가 아닌 행동·의도 중심의 이름. 테스트명이 명세처럼 읽혀야 한다.
- **그루핑**: 같은 대상의 시나리오는 `class Describe[대상]:` 또는 `class When[조건]:`으로 묶는다. 관련 테스트가 3개 이하면 클래스 생략.
- **픽스처**: 반복되는 Given 상태는 `@pytest.fixture`로 추출. 클래스 간 공유 픽스처는 모듈 최상위에 선언.
- **어시션**: 실패 이유가 자명하도록 값보다 의미를 검사. 인라인 주석으로 검증 의도 명시.

---

## 도메인 용어

**1차 모듈 용어**

| 용어 | 의미 |
|------|------|
| Block | 레이아웃 추출이 검출한 페이지 영역(text/title/figure/figure_caption/table)과 읽기 순서 |
| Figure crop | figure 블록 영역을 원본 페이지 이미지에서 잘라낸 이미지 (외부 미전송) |
| Summary note | 추출 텍스트를 LLM이 요약한 마크다운 노트(프론트매터 포함) |
| LayoutExtractor | PDF+페이지범위 → 정규화 블록/크롭을 내는 교체가능 인터페이스 |

**후속 모듈(Qdrant) 용어**

| 용어 | 의미 |
|------|------|
| Document | 색인 대상 원본 (PDF, 추후 Obsidian 노트) |
| Chunk | Document를 임베딩 단위로 분할한 텍스트 조각 (요약 노트가 자연스러운 청크 경계) |
| Collection | Qdrant의 벡터 저장 단위 |
| Retrieval | 질의 임베딩과 유사한 Chunk를 벡터 검색으로 가져오는 단계 |

## 평가 시 특별 주의 사항
- **검색 품질**: retrieval이 질의와 무관한 chunk를 반환하지 않는지 (관련성 확인)
- **PII / 개인 데이터**: 개인 문서를 다루므로 외부 API로 원문이 새지 않는지, 로그에 원문이 남지 않는지 점검
- **재현성**: 임베딩/LLM 호출은 테스트에서 mock 또는 고정 시드로 결정적이게

---

**상속**: 글로벌 `~/.claude/CLAUDE.md`와 `harness/` 원칙이 자동 적용된다.
