# Sprint Contract — Sprint 1: 서버리스 GPU 배포 + LayoutExtractor 실제 구현 — 2026-08-24

> `/sprint-contract`로 작성. spec: `.claude/harness/spec.md`. 사용자 sign-off 완료(2026-08-24).
> Sprint 0 계약은 `plan-sprint0.md`로 보존.

## 목표 (spec에서)
`LayoutExtractor.extract(pdf, page_range)`를 실제 구현한다 — PDF 페이지 범위를 로컬 렌더 →
**우리 Modal 인스턴스**의 PaddleOCR-VL로 추출 → 정규화 블록(type/bbox/reading_order/text) + figure 크롭 저장.
엔드포인트 설정만 바꿔 서버리스↔로컬 교체.

## 전체 스프린트 맵 (context)
- Sprint 0 — 스파이크 & 스캐폴딩 ✅ 완료 (`plan-sprint0.md`)
- **Sprint 1 — 서버리스 GPU 배포 + `LayoutExtractor` 실제 구현** ← *이번 계약*
- Sprint 2 — 노트 조립: 추출 텍스트 → LLM 요약(mock) → 프론트매터 + 그림 첨부 + 1~N 노트 + 묶음 내보내기, PII 경계
- Sprint 3 — React UI: PDF.js 온디맨드 뷰어, 범위+주제 입력, 노트 미리보기/직접편집, 리파인 대화, 내보내기 + Playwright E2E
- Sprint 4 — 통합·에지·PII 검증 → `/evaluate`

## 확정된 설계 결정 (sign-off 시)
- **Modal 노출 = HTTP 엔드포인트**(`modal deploy` → URL, 토큰 인증). spec의 "설정만 바꿔 URL 교체"에 정합.
- **콜드스타트 허용**(유휴 시 0 스케일다운). keep-warm 없음 — 성능 임계값(<90초, 콜드 포함) 내.
- **범위 = 추출까지만.** LLM 요약은 Sprint 2, UI는 Sprint 3, vLLM은 사용량 증가 시(보류).
- 다단 컬럼/figure-없는 샘플 페이지는 T7에서 사용자 확인 → **이 책엔 다단 없음(단단), figure-없는 대체로 page 200/250 사용**.

## 범위
- **In:** Modal 정식 배포(엔드포인트화), 페이지 렌더(PyMuPDF), 호출·정규화, figure 크롭, 설정 스왑, 단위테스트+에지, 실측 검증
- **Out(후속):** LLM 요약(Sprint 2), UI(Sprint 3), vLLM(사용량 증가 시)

## 작업 단위
- [x] **T1** — PoC를 정식 엔드포인트로: `modal deploy`로 상시 HTTP 엔드포인트(이미지 → parsing JSON), 토큰 인증(Modal Secret), A10G. 인증/에지(401/400//health) 실측 확인
- [x] **T2** — 백엔드 설정 도입: `requirements.txt`에 `pymupdf`, 엔드포인트 URL·구현 선택 config(env) — 서버리스↔로컬 스왑 지점
- [x] **T3** — `ModalLayoutExtractor.extract()`: 페이지 범위 렌더(200DPI) → 엔드포인트 호출 → `RAW_LABEL_MAP` 정규화 → `ExtractionResult` 조립
- [x] **T4** — figure 크롭: `image` 블록 bbox로 렌더 페이지 crop 저장, `image_ref`(절대경로) 설정. 다중 figure 지원
- [x] **T5** — 단위 테스트(호출 mock, 결정적): 정규화·nullable 순서·크롭 경로·라벨 매핑 + 에지(텍스트0/figure없음)
- [x] **T6** — 에러/타임아웃 처리: transient(5xx/네트워크) 재시도 + 4xx 즉시실패, 상태 손상 없음
- [~] **T7** — 회의적 실측: page 69/200/250 실측 완료(읽기순서·figure 크롭·한글 정상). 추가 반영: `algorithm→code` 라벨 + 워밍업 핑. **⏸ 라이브 재확인 2건(page200 `code` 타입·콜드 <90초)은 Modal 워크스페이스 비활성화로 보류**

## 완료 조건 (관찰 가능)  — (a)~(e) 충족 / (f) BLOCKED
- [x] `ModalLayoutExtractor(url).extract(pdf,(a,b))` → 정규화 블록 리스트 + figure `image_ref` 파일이 디스크에 생성
- [x] 블록 type이 정규화 집합(text/title/figure/figure_caption/formula/code/…)으로 매핑, reading_order nullable 처리
- [x] **PII 경계**: 이미지는 우리 Modal 인스턴스로만 전송(제3자 OCR 벤더 미전송), 로그에 원문 미기록 (코드 감사 통과)
- [x] 설정(env)만 바꿔 엔드포인트/구현 교체 가능 (`get_extractor()` 팩토리)
- [x] 단위 테스트(mock) 통과 + 에지(텍스트0/figure없음/에러) 처리 — **pytest 17 passed**
- [ ] ⏸ **추출(콜드스타트 포함) < 90초** 실측 1회 — **BLOCKED** (Modal 워크스페이스 비활성화; 워밍업 로직은 구현됨, 복구 후 실측 필요)

## 테스트 케이스 (호출 mock으로 결정적)
| # | 시나리오 | 입력 | 기대 |
|---|---|---|---|
| 1 | 정상 추출 | page 69 mock 응답 | 9블록 정규화, figure image_ref 생성, 순서 정상 |
| 2 | 텍스트 0건 | text 블록 없는 응답 | 예외 없이 처리, 빈 텍스트 표식 |
| 3 | figure 없음 | image 블록 없는 응답 | image_ref 없음, 텍스트 블록 정상 |
| 4 | 엔드포인트 에러/타임아웃 | mock 500/timeout | 명확한 예외, 상태 손상 없음, 재시도 가능 |
| 5 | 라벨 정규화 | display_formula/image/figure_title | formula/figure/figure_caption 매핑 |
| 6 | 실측(회의적) | 실제 Modal, 다단 컬럼·figure없음 각 1건 | 읽기순서·영역 합리적 |

## 하드 임계값
- 성능: 추출(콜드스타트 포함) **< 90초** (spec 기준)
- 품질: 린트 0, 타입 에러 0, 기존 테스트 전부 통과
- 커버리지: 신규 핵심 로직(렌더→호출→정규화→크롭) 단위 테스트
- PII: 이미지 제3자 미전송(우리 Modal만), 로그 원문 미기록

## 검증 방법
- 단위: `cd backend && pytest` (httpx 호출 mock)
- 실측: 배포 엔드포인트로 page 69 + 다단/figure없음 1건씩
- 스왑: env 변경으로 구현/URL 교체 확인

## 영향 범위
- 신규: `backend/app/extractors/modal_extractor.py`, `backend/app/config.py`, `backend/tests/test_extractor.py`, 정식 Modal 배포 스크립트(`backend/poc/` → 정식화)
- 변경: `backend/requirements.txt`(pymupdf/httpx), `backend/app/extractor.py`(구현체 연결)
- 외부 액션: **`modal deploy`(GPU 비용 발생)** — 사용자 인지
- 마이그레이션: 없음

## 사용자 Sign-off
- [x] 사용자가 명시적으로 확인함 (2026-08-24)

## 변경 이력
- 2026-08-24: 초안 작성 + sign-off. Modal=HTTP 엔드포인트, 콜드스타트 허용, 범위=추출까지, 다단 샘플은 T6 오픈.
- 2026-08-26: T1~T6 완료(구현+단위테스트 17 passed), T7 실측(page 69/200/250) 진행. 성능 대응=워밍업 핑(A), 코드 라벨(algorithm→code) 추가. **Modal 워크스페이스 비활성화(billing)로 T7 라이브 재확인·(f)<90초 실측 보류.** 핸드오프: `handoff-2026-08-26-0702.md`.
- 2026-08-29: `/evaluate` 실행(워크스페이스 비활성화 상태) → **PARTIAL** — 완료조건 (a)~(e) PASS(pytest 17 + PII 감사), (f)<90초는 BLOCKED. minor 2건(스테일 주석, 본 체크박스). 본 체크박스는 최신화 완료. **잔여: Modal 재활성화 → (f) 실측 → Sprint 1 완료.**

## 참조
- spec: `.claude/harness/spec.md`
- Sprint 0 계약: `plan-sprint0.md`
- 스파이크/PoC: `docs/spike-paddleocr-vl.md`, `backend/poc/modal_paddleocr_vl.py`
- 다음 단계: **Modal 워크스페이스 재활성화 → (f)<90초 콜드 실측 + page200 `code` 확인 → Sprint 1 완료 → Sprint 2(노트 조립)**
- 핸드오프: `handoff-2026-08-26-0702.md`