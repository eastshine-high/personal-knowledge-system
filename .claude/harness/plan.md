# Sprint Contract — Sprint 3: React UI — 2026-09-13

> `/sprint-contract`로 작성. spec: `.claude/harness/spec.md`. 사용자 sign-off 대기.
> Sprint 0~2 계약은 `plan-sprint0~2.md`로 보존.

## 목표 (spec에서)
리파인 엔진(`build_session`/`NoteSession`)을 화면에 배선한다.
PDF 경로+범위+주제를 입력하면 노트가 생성되고, 채팅 패널에서 반복 다듬기·직접 편집·undo·내보내기까지 브라우저에서 완결된다.

## 전체 스프린트 맵 (갱신)
- Sprint 0 — 스캐폴딩 & 스파이크 ✅ (`plan-sprint0.md`)
- Sprint 1 — LayoutExtractor + Modal + fixture ✅ (`plan-sprint1.md`)
- Sprint 2 — 노트 조립 + 리파인 엔진(헤드리스, ADK) ✅ (`plan-sprint2.md`)
- **Sprint 3 — React UI** ← *이번 계약*
- Sprint 4 — 통합·에지·PII 검증 → `/evaluate`

## 확정된 설계 결정

| 항목 | 결정 | 이유 |
|------|------|------|
| PDF 뷰어 | **백엔드 렌더 이미지** | bbox 좌표가 백엔드 렌더 DPI 기준 → 오버레이 정확 |
| PDF 입력 | **로컬 경로 문자열** | 서버가 이미 파일시스템 접근 가능 |
| 세션 스토어 | **인메모리 dict** | 재시작 시 소멸 OK, 단순 |
| UI 스타일 | **순정 React + 최소 CSS** | 추후 디자인 시스템 적용 예정 |
| 연속 undo 버그 | **이번 스프린트 수정** | UI에서 undo 버튼 노출하므로 정확해야 함 |
| E2E mock | **`page.route()`** | 재현성·비용 0 |

## 작업 단위

### 백엔드 (FastAPI 엔드포인트)
- **B0** — 연속 undo 버그 수정: `undo()`가 `revert` 이벤트 건너뛰고 실질 변경 기준 탐색
  ```python
  real = [e for e in self.events if e.action != "revert"]
  return self.revert_to(real[-2].seq)
  ```
- **B1** — 인메모리 세션 스토어 + `POST /sessions` (build_session 배선, session_id 반환)
- **B2** — 노트·리파인 엔드포인트: `GET /sessions/{id}/notes`, `POST /sessions/{id}/refine`, `POST /sessions/{id}/notes/{note_id}/edit`, `POST /sessions/{id}/undo`
- **B3** — 페이지 이미지: `GET /sessions/{id}/pages/{page_num}` (PyMuPDF → PNG bytes)
- **B4** — 내보내기: `GET /sessions/{id}/export` (zip 스트리밍 다운로드)
- **B5** — CORS 설정 (localhost:5173 허용)

### 프론트엔드 (React + Vite)
- **F1** — API 클라이언트 (`frontend/src/api.ts`): fetch wrapper, 에러 핸들링
- **F2** — 입력 폼: PDF 경로, 페이지 범위(시작~끝), 주제, 가이드라인, 노트 수 → `POST /sessions`
- **F3** — PDF 뷰어: 백엔드 이미지 `<img>`, 이전/다음 페이지 내비게이션
- **F4** — 노트 패널: 마크다운 렌더링(raw 텍스트 기본), 편집 모드(textarea) 전환 + apply_edit 호출
- **F5** — 채팅 리파인 패널: instruction 입력 → `POST /refine`, events 히스토리 목록 표시
- **F6** — undo 버튼 + 내보내기 버튼(zip 다운로드)

### Playwright E2E
- **E1** — 황금 경로: 폼 입력 → 노트 생성 → 노트 패널에 내용 표시 (`page.route` mock)
- **E2** — 리파인: instruction 입력 → 노트 갱신 → events 패널에 지시 추가됨
- **E3** — undo: refine 후 undo → 이전 노트 복원 / 연속 undo 2회 올바른 방향
- **E4** — 직접 편집: 편집 저장 → UI에 반영
- **E5** — 내보내기: 내보내기 버튼 클릭 → zip 다운로드 트리거 확인

## 완료 조건 (관찰 가능)
- [ ] 입력 폼에서 PDF 경로+범위+주제 입력 후 노트 생성 가능
- [ ] PDF 뷰어에 페이지 이미지 표시, 이전/다음 페이지 동작
- [ ] 채팅 패널에서 instruction 입력 → 노트 갱신 → events 히스토리에 표시
- [ ] undo 연속 2회: 순방향 역재생(오실레이션 없음) — **B0 수정 포함**
- [ ] 직접 편집 → apply_edit → 다음 refine에 반영
- [ ] 내보내기 버튼 → zip 다운로드
- [ ] 잘못된 PDF 경로 → 오류 메시지 표시
- [ ] Playwright E2E: E1~E5 모두 PASS (`npm run test:e2e`)
- [ ] 기존 **63 pytest PASS 유지** (B0 포함 변경 후)

## 테스트 케이스
| # | 시나리오 | 입력 | 기대 |
|---|---|---|---|
| 1 | 황금 경로 | 로컬 PDF 경로 + 범위 + 주제 | 노트 생성됨, 마크다운 내용 표시 |
| 2 | PDF 뷰어 | 세션 생성 후 페이지 이동 | 이미지 로드, 페이지 번호 갱신 |
| 3 | 리파인 | instruction "더 짧게" 입력 | 노트 갱신, events 패널에 지시 표시 |
| 4 | 연속 undo | refine 2회 후 undo 2회 | start 상태 → refine1 상태 순서로 역재생 |
| 5 | 직접 편집 | 노트 텍스트 수정 + 저장 | 수정본 표시, 다음 refine이 수정본 기준 |
| 6 | 내보내기 | 내보내기 버튼 클릭 | zip 다운로드 시작 |
| 7 | 오류 처리 | 존재하지 않는 PDF 경로 | 폼에 오류 메시지 표시 |
| 8 | mock 격리 | page.route 전체 mock | 백엔드 없이 E2E PASS |

## 하드 임계값
- 기존 pytest: **63 passed 유지** (B0 수정 후 재확인)
- E2E: E1~E5 전부 PASS (`npm run test:e2e`)
- 빌드: `npm run build` 오류 없음
- CORS: 프론트엔드 → 백엔드 API 호출 정상

## 검증 방법
- 백엔드: `cd backend && pytest` (63 passed 유지 확인)
- E2E: `npm run test:e2e` (Playwright, page.route mock)
- 수동 확인: `uvicorn app.main:app --reload` + `npm run dev` → 브라우저 황금 경로 1회

## 영향 범위
- **수정**: `backend/app/notes/session.py` (B0 undo 버그), `backend/app/main.py` (엔드포인트 추가)
- **신규**: `frontend/src/` (컴포넌트·API 클라이언트), `test/*.spec.ts` (E2E)
- **외부 액션**: 없음 (백엔드 엔드포인트는 로컬만)
- **마이그레이션**: 없음

## 사용자 Sign-off
- [ ] 사용자가 명시적으로 확인함

## TODO (향후 과제)
- **전사 PKS 확장**: 파일 업로드(로컬 경로 → multipart), PostgreSQL 세션 스토어, 최소 인증(API 키 또는 SSO), 다중 사용자 세션 격리

## 변경 이력
- 2026-09-13: 초안 작성. 설계 확정: 백엔드 렌더 이미지·로컬 경로·인메모리 스토어. 연속 undo 버그(B0) 이번 스프린트 수정 포함.
- 2026-09-13: 전사 PKS 확장을 Sprint 4에서 TODO로 이동.

## 참조
- spec: `.claude/harness/spec.md`
- 이전 계약: `plan-sprint0~2.md`
- 추출 구현: `backend/app/extractor.py`, `backend/app/extractors/`
- 노트 엔진: `backend/app/notes/`, `backend/app/llm/`
- 다음 단계: Sprint 4 — 통합·에지·PII 검증 (`/evaluate`)
