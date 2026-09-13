# Sprint Contract — Sprint 4: 마무리·에지·통합 검증 — 2026-09-13

> `/plan`으로 작성. spec: `.claude/harness/spec.md`.

## 목표 (spec에서)
Sprint 3 골격 위에서 **spec의 미완성 UI 항목**을 채우고, mock으로 가려진 **에지 케이스 E2E**를 추가하며, **실 환경 smoke test**로 Modal+Claude 연동을 검증한다.

## 전체 스프린트 맵 (갱신)
- Sprint 0 — 스캐폴딩 & 스파이크 ✅
- Sprint 1 — LayoutExtractor + Modal + fixture ✅
- Sprint 2 — 노트 조립 + 리파인 엔진 ✅
- Sprint 3 — React UI ✅
- **Sprint 4 — 마무리·에지·통합 검증** ← *이번 계약*

## 확정된 설계 결정

| 항목 | 결정 | 이유 |
|------|------|------|
| 탭 구현 위치 | App.tsx 인라인 탭 바 | 단순, 별도 컴포넌트 불필요 |
| 진행 상태 | 단계 메시지 문자열 (폴링 없음) | 백엔드가 SSE 없으므로 타이머 기반 |
| 통합 smoke test | 수동 실행 + 결과 md 기록 | CI 없는 개인 도구 |

## 작업 단위

### 프론트엔드
- **F7** — 노트 탭/목록 전환: `notes.length > 1`일 때 탭 바 표시, 클릭으로 활성 노트 전환. PdfViewer도 선택 노트의 pages로 갱신
- **F8** — 진행 상태 단계 메시지: 세션 생성 중 "추출 중…→ 요약 중…" 단계 표시 (타이머 기반)

### Playwright E2E
- **E6a** — 텍스트 0건 에지: `POST /sessions` mock → 422 → 폼에 에러 메시지 표시
- **E6b** — 노트 2개 탭 전환: `notes: [note1, note2]` mock → 탭 바 표시 → 두 번째 탭 클릭 → 내용 전환
- **E6c** — 세션 생성 실패 재시도: 500 mock → 에러 표시 → 폼 재입력 → 두 번째 시도 성공

### 통합 검증
- **I1** — smoke test 문서: 실제 PDF + `uvicorn` + `npm run dev` 로컬 end-to-end 수동 1회. 결과 `.claude/harness/smoke-test-sprint4.md`에 기록

### 문서
- **D1** — `spec.md` 완료 조건 현황 갱신: Sprint 0~4 달성 항목 체크

## 완료 조건 (관찰 가능)
- [ ] `note_count=2`로 생성 시 탭 바 표시, 탭 클릭으로 노트·PDF뷰어 동시 전환
- [ ] 세션 생성 중 단계별 상태 메시지 표시 ("추출 중…" → "요약 중…")
- [ ] 텍스트 0건 에지 E2E PASS
- [ ] 노트 2개 탭 전환 E2E PASS
- [ ] 세션 실패 재시도 E2E PASS
- [ ] Playwright 전체 PASS (`npm run test:e2e`)
- [ ] pytest 76 passed 유지
- [ ] 빌드 오류 없음

## 테스트 케이스
| # | 시나리오 | 입력 | 기대 |
|---|---|---|---|
| 1 | 탭 전환 | notes 2개 mock | 탭 바 표시, 두 번째 탭 클릭 시 내용·PDF 페이지 전환 |
| 2 | 탭 없음 | notes 1개 mock | 탭 바 미표시 (현행 유지) |
| 3 | 텍스트 0건 | 422 mock | "요약할 텍스트가 없습니다" 에러 표시 |
| 4 | 실패 재시도 | 500 → 200 mock | 에러 표시 후 재입력 → 성공 |
| 5 | 진행 메시지 | 세션 생성 버튼 클릭 | 로딩 중 단계 메시지 표시 |

## 하드 임계값
- pytest: **76 passed 유지**
- E2E: 기존 E1~E5 + 신규 E6a~E6c 전부 PASS
- 빌드: `npm run build` 오류 없음

## 사용자 Sign-off
- [x] 사용자가 명시적으로 확인함 (F7부터 시작 지시)

## 변경 이력
- 2026-09-13: 초안 작성.
