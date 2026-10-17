# Spec — Sprint 6: 평탄화 형광펜 색 검출 + 색상 가중치

> Planner 산출물. 구현 전 사용자 sign-off 필수.

## 목표 (1문장, 검증 가능)

GoodNotes처럼 **형광펜이 픽셀로 평탄화되어 PDF 주석이 없는** 문서에서도, 페이지 이미지의 **형광색을 검출**해 그 아래 텍스트를 추출하고, **색상별 가중치(기본: 초록 > 노랑)** 를 실어 요약/대화 LLM에 전달한다. 프론트엔드 체크박스로 켜고, 끄면 기존 로직 그대로 동작한다.

## 배경 (왜)

- 현재 `base_extractor._extract_highlights()`는 **PDF Highlight 주석(`page.annots()`)만** 읽는다.
- 실측(스파이크): 대상 파일 `algorithm-interview.pdf` 46p는 **주석 0개** — 형광펜이 평탄화된 픽셀. 노란 형광 5밴드를 **색 검출(순수 파이썬)로 자동 추출 성공**. 밑 글자는 **인쇄체**(OCR 친화).
- 즉 형광펜 가중치 배선(요약 `[READER_FOCUS]`, 대화 `[HIGHLIGHTS_JSON]`)은 이미 존재하나, **색 검출 경로 부재로 실제 GoodNotes 파일에서는 하나도 안 잡힌다.**

## In Scope

1. `_extract_highlights`에 **색 기반 검출 폴백** 추가 — 주석이 없을 때 렌더 픽셀에서 형광색 밴드를 찾아 기존 `_blocks_in_rect`(픽셀 rect ↔ OCR 블록 교집합)로 텍스트화.
2. **색상 태깅** — 각 형광 구절에 색(`yellow` | `green` | `other`)을 부착.
3. **색상 가중치 커스텀 설정** — `Settings`에 색→가중치 매핑(환경변수 재정의). 기본 `green=2.0, yellow=1.0, other=1.0`.
4. **프롬프트 가중 반영** — `[READER_FOCUS]`/`[HIGHLIGHTS_JSON]`이 색/가중치를 구분해 전달(초록을 상위 강조).
5. **요약 흐름 토글** — `CreateSessionRequest.use_highlights`(기본 false) 추가 + `InputForm` 체크박스. off면 highlights 미수집(기존 동작).
6. **대화 흐름** — 기존 체크박스 유지, 색 검출 혜택 자동 반영.
7. **numpy 의존성** 추가(`requirements.txt`) — 색 마스킹 벡터화.

## Out of Scope

- 손글씨 필기 OCR (별개 문제, 본 스프린트 제외).
- Google Drive 연동/자동 다운로드 (수동으로 로컬 경로 둔 PDF 대상).
- 밑줄/동그라미 등 형광펜 외 주석 검출.
- 형광펜 색상의 사용자별 다중 프로필(단일 사용자 가정; 설정은 전역 1벌).
- 프론트엔드에서의 색상 가중치 편집 UI (설정은 백엔드 config로; 프론트는 on/off 체크박스만).

## 완료 조건 (체크박스)

- [ ] 주석 없는 평탄화 노랑 형광펜 페이지에서 해당 텍스트가 `color="yellow"`로 추출된다.
- [ ] 초록 형광펜은 `color="green"`으로 추출된다.
- [ ] 형광펜 없는 페이지는 highlights가 빈 리스트다 (오검출 0).
- [ ] 기존 **주석 기반** 형광펜 경로가 회귀 없이 동작한다.
- [ ] 색상 가중치가 프롬프트에 반영된다 — 초록 구절이 노랑/기타보다 상위 강조로 표기된다.
- [ ] `Settings`의 색→가중치 매핑을 환경변수로 재정의할 수 있다.
- [ ] 요약 흐름: `use_highlights=false`(기본)면 `[READER_FOCUS]`가 프롬프트에 없다(기존 동작 보존).
- [ ] 요약 흐름: `InputForm` 체크박스 체크 시 `use_highlights=true`가 `/sessions` 요청에 실린다.
- [ ] 대화 흐름: 기존 체크박스로 색 검출 결과가 `[HIGHLIGHTS_JSON]`에 실린다.
- [ ] `pytest` 전체 통과 + 신규 색검출/가중치 테스트 통과.

## 테스트 케이스 (입력 → 출력)

> 결정성: 색 검출 테스트는 **pymupdf로 합성 PDF를 생성**(텍스트 + 색칠 rect)해 실행. 외부 파일/네트워크 불요.

- **T1 평탄화 노랑 검출**: 텍스트 위에 주석 아닌 노란 사각형이 그려진 합성 페이지 → highlights에 해당 텍스트, `color="yellow"` 1건. 주석은 0개.
- **T2 초록 검출**: 초록 사각형 → `color="green"`.
- **T3 주석 회귀**: 진짜 Highlight 주석이 있는 페이지 → 기존대로 추출(색은 주석 색/또는 `other`).
- **T4 무형광 오검출 0**: 색칠 없는 페이지 → highlights == [].
- **T5 가중치 프롬프트**: 초록 1 + 노랑 1 구절 → `_build_summarize_prompt` 출력에 초록이 '가장 중요' 그룹, 노랑이 '중요' 그룹으로 구분 표기.
- **T6 토글 off**: `use_highlights=false`로 `build_session` → SummarizeRequest.highlights 비어 프롬프트에 `[READER_FOCUS]` 없음.
- **T7 토글 on**: `use_highlights=true` → `[READER_FOCUS]` 포함.
- **T8 색 가중치 설정 재정의**: 환경변수로 `yellow=3.0` 지정 시 매핑에 반영.
- **T9 (Playwright E2E)**: `InputForm`에서 "형광펜 가중치 포함" 체크 → `/sessions` POST body에 `use_highlights:true`(page.route로 가로채 검증).

## 하드 임계값 (정량)

- 색 검출 성능: 200DPI 페이지 1장 색 마스킹 **< 100ms**(numpy 기준, 렌더 제외).
- 렌더 재사용: 색 검출은 추출 시 생성된 pixmap을 재사용해 **페이지당 추가 렌더 0회**.
- 오검출 상한: 형광펜 없는 페이지에서 highlights == 0건.
- 기본 색 가중치: `green=2.0 > yellow=1.0 = other=1.0`.

## 비기능 요구

- **PII**: 색 검출은 전부 로컬. 이미지·원문·형광 텍스트는 외부 미전송(LLM엔 텍스트만, 기존 경계 유지). 로그에 원문/형광 텍스트 미기록.
- **아키텍처 경계**: 색 검출은 `infrastructure/extractors`(base_extractor)에, 가중치→프롬프트는 `domain/notes` 및 `application/chat_service`에. `application`은 `fastapi` import 금지(유지).
- **인터페이스 안정성**: `LayoutExtractor.extract()` 시그니처 불변(토글은 collect/prompt 계층에서 게이팅). Modal/Fixture 구현 변경 없이 동작.
- **하위호환**: `highlights` 데이터 모델이 `list[str]`→색 부착 구조로 바뀌므로, 소비처(요약/대화/export) 전부 갱신. 기존 fixture/테스트 깨지지 않게 조정.
- **문서 갱신**: 데이터 모델·설정 추가를 `docs/architecture.md` + CLAUDE.md 관련 섹션에 같은 커밋으로 반영.

## 설계 메모 (Generator 자유도 내 권고)

- `Highlight` 구조: `{text: str, color: Literal["yellow","green","other"]}`. 가중치는 소비 시 `Settings` 매핑으로 조회(모델에 weight를 박지 않음 → 설정 변경이 과거 데이터에 영향).
- 색 분류: RGB/HSV 역치. 노랑 ≈ R,G 高·B 低 / 초록 ≈ G 高·R,B 低. 스파이크 역치(노랑: `r>180 and g>150 and b<160 and r+g-2b>80`)를 출발점으로, 초록 역치 추가 + sample p46로 튜닝.
- 밴드 묶기: 색상별 마스크 → 행 투영(`mask.any(axis=1)`) → 연속 행 그룹 → 픽셀 rect → `_blocks_in_rect`.
- 가중치 매핑은 `config.py`가 "커스텀 설정"의 집(단일 사용자) — 개인 편향(초록>노랑)을 env로 조정.
```