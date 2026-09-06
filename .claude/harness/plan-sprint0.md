# Sprint Contract — Sprint 0: 스파이크 & 스캐폴딩 — 2026-08-17

> `/sprint-contract`로 작성. spec: `.claude/harness/spec.md`. 사용자 sign-off 완료(2026-08-17).

## 목표 (spec에서)
미지 요소(PaddleOCR-VL 실제 출력 형식)를 로컬에서 해소하고, FastAPI+React 뼈대와 테스트 하네스를 세워 이후 기능 스프린트의 토대를 만든다.

## 전체 스프린트 맵 (context)
- **Sprint 0 — 스파이크 & 스캐폴딩** ← *이번 계약*
- Sprint 1 — **서버리스 GPU 배포(Beam vs Modal PoC → 택일)** + `LayoutExtractor` 실제 구현: PDF+범위 → 정규화 블록[type,bbox,text,reading_order] + figure 크롭 저장
- Sprint 2 — 노트 조립: 추출 텍스트 → LLM 요약(mock) → 프론트매터 + 그림 첨부 + 1~N 노트 + 묶음 내보내기, PII 경계
- Sprint 3 — React UI: PDF.js 온디맨드 뷰어, 범위+주제 입력, 노트 미리보기/직접편집, 리파인 대화, 내보내기 + Playwright E2E(`page.route` mock)
- Sprint 4 — 통합·에지·PII 검증 → `/evaluate`

## 작업 단위 (Sprint 0) — 완료 ✅
**스캐폴딩**
- [x] T1: 리포 구조 생성 — `backend/`(FastAPI), `frontend/`(Vite+React), `tests/`(pytest), `test/`(기존 Playwright 유지)
- [x] T2: FastAPI 앱 골격 + `GET /health` 엔드포인트, `uvicorn` 기동 확인
- [x] T3: React(Vite) 앱 골격 + `package.json`에 `dev` 스크립트(포트 고정), `npm run dev` 기동 확인
- [x] T4: `playwright.config.ts`의 `webServer.command=npm run dev` + `baseURL` 포트 정합, 기존 `test/example.spec.ts` 통과
- [x] T5: pytest 셋업(`.venv` + pytest) + `tests/test_smoke.py`(healthcheck) 통과

**스파이크 (de-risk, 로컬 CPU)**
- [x] T6: 샘플 스캔 페이지 1장에 문서 파싱 **1회 실행(로컬 CPU)** → 실제 출력(레이아웃 JSON, **figure 영역 bbox**, 텍스트, **읽기 순서**) 캡처를 `docs/spike-paddleocr-vl.md`에 기록. *실행: PP-StructureV3(mobile, Intel Mac은 PaddleOCR-VL 미지원) + 추가로 PaddleOCR-VL을 Modal A10G에서 검증(Sprint 1 PoC).*
- [x] T7: `LayoutExtractor` **인터페이스 시그니처 확정**(추상 프로토콜) — 입력 `(pdf, page_range)` → 출력 `블록목록 + figure 크롭 참조`; 스파이크(T6) 출력 형식 반영(RAW_LABEL_MAP·nullable reading_order·render_dpi), 구현은 스텁

## 완료 조건 (관찰 가능) — 전부 충족 ✅ (/evaluate PASS, 2026-08-23)
- [x] `npm run dev`(Vite) 기동 + `pytest` 통과 + `npm run test:e2e` 기동(기존 example 통과)
- [x] `GET /health` → 200 (`{status:"ok"}`)
- [x] `docs/spike-paddleocr-vl.md`에 **실제 출력 예시**(figure bbox 형식·텍스트·읽기순서, 로컬 CPU 실행) 기록 — 산출물 JSON과 교차검증됨
- [x] `LayoutExtractor` 인터페이스 시그니처 확정(타입/입출력 명시, 스텁 존재)

## 테스트 케이스
| # | 시나리오 | 입력 | 기대 |
|---|---|---|---|
| 1 | 백엔드 스모크 | `GET /health` | 200 + `{status:"ok"}` |
| 2 | 프런트 기동 | `npm run dev` | baseURL 접속 시 앱 로드 |
| 3 | E2E 하네스 | `npm run test:e2e` | 기존 example 통과 |
| 4 | 스파이크 산출 | `docs/spike-paddleocr-vl.md` | figure bbox·텍스트·읽기순서 실캡처 존재 |

## 하드 임계값
- 품질: 린트 0, 타입 에러 0(설정 범위), 기존 테스트 전부 통과
- 스파이크: figure 영역 bbox가 **실제로 출력됨을 캡처로 증명**(추정 아님)

## 검증 방법
- API: `curl localhost:<port>/health` → 200
- 프런트: `npm run dev` 후 baseURL 접속 확인
- E2E: `npm run test:e2e` → `test-results.json` 통과
- 스파이크: `docs/spike-paddleocr-vl.md` 실산출물 리뷰(figure bbox·텍스트·읽기순서 캡처)
- 회의적 점검: figure가 없는 페이지·다단 컬럼 페이지에서도 읽기순서/영역이 나오는지 1건씩 확인

## 영향 범위
- 신규: `backend/`, `frontend/`, `tests/`, `docs/spike-paddleocr-vl.md`
- 변경: `package.json`(dev 스크립트), `playwright.config.ts`(webServer/포트)
- 유지: `test/example.spec.ts`
- 마이그레이션: 없음
- 외부 액션: 없음(GPU 계정 배포는 Sprint 1로 이동)

## 사용자 Sign-off
- [x] 사용자가 명시적으로 확인함 (2026-08-17)

## 변경 이력
- 2026-08-17: 초안 작성
- 2026-08-17: T7(서버리스 GPU 배포) → Sprint 1로 이동, 스파이크는 로컬 CPU 형식 확인으로 축소 (사유: GPU 계정 없이 인터페이스 확정 가능)
- 2026-08-23: **Sprint 0 완료.** /evaluate 1차 FAIL(프론트 @types 누락, 타입에러 20) → Generator 수정(@types/react·react-dom 추가, typecheck 스크립트, main.py 정리) → /evaluate 재검증 **PASS**.

## 참조
- spec: `.claude/harness/spec.md`
- 다음 단계: **Sprint 1** — `/sprint-contract` 후 Modal 배포를 실제 `LayoutExtractor` 구현으로 승격