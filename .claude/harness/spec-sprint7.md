# Spec — Sprint 7: OCR 범위와 대화 범위 분리 (주제별 2축)

> Planner 산출물. 구현 전 사용자 sign-off 필수.

## 목표 (1문장, 검증 가능)

하나의 PDF 아래에서 **주제별 '추출 세트'(OCR 범위)** 와 **주제별 '대화'(질의 범위)** 를 **서로 독립적으로** 만들고 관리할 수 있다 — 둘은 페이지 단위 OCR 캐시만 공유하며, 대화가 캐시에 없는 페이지를 포함하면 그때 해당 페이지만 OCR한다.

## 배경 (왜 / 현황)

- 현재 `conversations`는 `pdf_file_id + pages_json + title`만 갖고 **topic(주제) 필드가 없다**. OCR 범위 = 대화 범위로 묶여 있다.
- `page_extractions`는 이미 `(pdf_file_id, page_num)` **페이지 단위 캐시** → OCR은 대화와 무관하게 공유되고, `create_conversation`은 **미캐시 페이지만 on-demand 추출**한다. (즉 "범위 벗어나면 그때 OCR"은 **이미 동작**하며 본 스프린트는 이를 **보존**한다.)
- 신규로 필요한 것: ① 주제별 OCR을 미리 떠두는 **추출 세트 엔티티**, ② 대화에 **topic** 부여(자동+수정), ③ 둘을 독립 2축으로 보여주는 UI.

## 용어

- **추출 세트(Extraction set)**: PDF 아래의 `(주제, 페이지 범위)` 단위. 생성 시 그 범위를 OCR(페이지 캐시 채움). 조직화 + 선(先)추출 용도. 대화와 **부모-자식 아님**.

## In Scope

1. 새 `extractions` 테이블 + API: 생성(주제+범위 → 범위 OCR, 페이지 캐시)/목록/삭제.
2. `conversations.topic` 컬럼 추가: 첫 메시지 전송 시 자동 생성(없을 때), 이후 **수정 endpoint**로 변경 가능.
3. 프런트: PDF 상세에 **'추출 세트' 목록 + '대화' 목록**(독립 2축) + 추출 세트 생성 폼(주제+페이지 범위) + 대화 주제 수정 UI.
4. 대화 생성 시 미캐시 페이지 on-demand OCR **기존 동작 보존**(회귀 없음).

## Out of Scope

- 추출 세트 ↔ 대화의 부모-자식 연결 / 대화가 특정 세트에 "속함".
- 대화의 **페이지 범위 사후 편집**(이번엔 topic만 편집; 범위는 생성 시 확정).
- 추출 세트 기반 요약 노트 생성(별도 모듈).
- 추출 세트 간 범위 겹침 병합/정규화(세트는 단순 기록; 캐시는 페이지 단위라 중복 OCR 없음).
- 추출 세트 범위 사후 편집.

## 완료 조건 (체크박스)

- [ ] `POST /books/{book_id}/pdfs/{pdf_id}/extractions` (주제+pages_str) → 범위 OCR(미캐시만) 후 추출 세트 생성·반환.
- [ ] `GET .../extractions` → 해당 PDF의 추출 세트 목록(주제, pages_display, created_at).
- [ ] `DELETE .../extractions/{id}` → 세트 삭제(페이지 캐시는 공유 자원이라 보존).
- [ ] 추출 세트 생성이 **페이지 캐시를 채운다**(동일 페이지를 쓰는 이후 대화는 재OCR 0회).
- [ ] `conversations`에 `topic` 컬럼 — 첫 메시지 시 topic이 비면 자동 생성(첫 메시지 기반).
- [ ] `PATCH /conversations/{id}` (topic) → 대화 주제 수정, 응답에 반영.
- [ ] `ConversationResponse`에 `topic` 포함.
- [ ] 대화 생성 범위가 어떤 추출 세트에도 없던 페이지를 포함 → 그 페이지만 on-demand OCR(기존 동작) PASS.
- [ ] 추출 세트와 대화는 **독립** — 세트 없이도 대화 생성 가능, 대화 없이도 세트 생성 가능.
- [ ] 프런트: PDF 선택 시 '추출 세트' 목록과 '대화' 목록이 **각각** 표시, 세트 생성 폼·대화 주제 수정 동작.
- [ ] `pytest` 전체(기존 114 + 신규) 통과 / `tsc --noEmit` 0 / `npm run test:e2e` 신규+기존 PASS.

## 테스트 케이스 (입력 → 출력)

- **X1 세트 생성+OCR**: 주제 "자료구조", pages "1-5" → 추출 세트 반환 + page_extractions에 1~5 저장.
- **X2 캐시 공유**: X1 후 대화를 pages "3-7"로 생성 → 3~5는 캐시 히트, 6~7만 추출(newly_extracted==2).
- **X3 세트 목록/삭제**: 세트 2개 생성 → 목록 2건 → 1개 삭제 → 목록 1건, page_extractions 보존.
- **T-topic1 자동**: topic 없이 대화 생성 → 첫 메시지 "어텐션이 뭐야" 전송 → topic 자동 설정.
- **T-topic2 수정**: `PATCH /conversations/{id}` topic="트랜스포머" → 응답 topic 반영.
- **R1 회귀(on-demand)**: 세트 전혀 없이 대화 pages "9" 생성 → 9 페이지 on-demand OCR, 대화 정상.
- **독립성**: 세트만 생성(대화 0) / 대화만 생성(세트 0) 각각 성공.
- **E(E2E)**: PDF 선택 → 추출 세트 생성 폼으로 "자료구조 1-5" → 목록 표시; 별도로 대화 생성 → 대화 목록에 표시(2축 분리).

## 하드 임계값 (정량)

- 추출 세트 생성 시 이미 캐시된 페이지는 **재OCR 0회**(페이지 단위 캐시 재사용).
- 세트 삭제가 `page_extractions`(공유 캐시)를 **삭제하지 않음**.
- 추출 세트 ↔ 대화 간 외래키 의존 **0**(독립 2축).
- `pytest` 전체 통과 / `tsc` 0 / `e2e` PASS.

## 비기능 요구

- **PII**: 변경 없음 — OCR/텍스트는 로컬·페이지 캐시, LLM엔 텍스트만(기존 경계 유지).
- **아키텍처 경계**: 추출 세트 로직은 presentation(라우터)+application(쿼리/서비스), OCR은 기존 `ocr_cache.get_or_extract` 재사용. `application`은 fastapi import 금지 유지.
- **DB 마이그레이션**: `extractions` 테이블 신규(CREATE IF NOT EXISTS), `conversations.topic` 컬럼 추가(ALTER 또는 신규 컬럼 멱등 처리). 기존 DB 호환.
- **문서 갱신**: 스키마/엔티티 변화를 `docs/architecture.md`(DB·데이터 흐름·설계 결정) + `CLAUDE.md`(도메인 용어) 같은 커밋 반영.

## 설계 메모 (Generator 자유도 내 권고)

- `extractions`: `id, pdf_file_id(FK), topic, pages_json, created_at`. 생성 시 `get_or_extract`로 범위 OCR.
- `conversations.topic`: nullable. 자동 생성은 첫 메시지 전송 시(현재 title 자동 로직 옆). topic 수정은 `PATCH /conversations/{id}`.
- UI: 좌측/상단에 PDF 선택 → 우측에 탭 또는 2개 섹션('추출 세트' / '대화'). 각 섹션 독립 생성.
- 범위 겹침은 허용·무처리(캐시가 페이지 단위라 비용 중복 없음).

## 열린 가정 (sign-off 시 확인)

- 추출 세트의 **목적은 "주제별 선(先)OCR + 조직화"** 이며 대화가 세트를 참조하지 않는다(독립 2축). 맞는지.
- 대화 **페이지 범위는 생성 시 확정**(사후 편집은 이번 범위 밖), topic만 수정 가능.
- 추출 세트 생성 시 범위를 **즉시 동기 OCR**(대화 생성과 동일 방식; 큰 범위는 느릴 수 있음).