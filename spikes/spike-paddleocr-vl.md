# 스파이크 — PaddleOCR 문서 파싱 출력 형식 확인 (로컬 CPU)

> **Sprint 0 / T6.** 목적: 문서 파싱 파이프라인이 스캔 페이지에서 실제로 내주는 출력
> (레이아웃 블록, **figure 영역 bbox**, 텍스트, **읽기 순서**) 형식을 확인해
> `backend/app/extractor.py`의 `LayoutExtractor` 계약(Block/BBox 필드)을 확정한다.
>
> ✅ **상태: 실행 완료(2026-08-18).** 아래 "실제 출력 캡처"는 로컬 CPU에서
> 표본 1페이지를 실제로 돌린 산출물이다(추정 아님).

## 실행에 사용한 도구 (중요)

- **실행 도구: PaddleOCR `PP-StructureV3` (mobile 모델), 로컬 CPU.**
- **PaddleOCR-VL이 아님.** PaddleOCR-VL은 `paddlepaddle 3.2.1+`를 요구하는데,
  이 개발기가 **macOS x86_64(Intel)**이고 Intel Mac용 paddlepaddle 휠은 **3.0.0까지만**
  배포된다(공식 CPU 인덱스 확인). 즉 **Intel Mac에는 PaddleOCR-VL 네이티브 설치 불가.**
  - 참고: **Apple Silicon(arm64)** 은 3.2.1~3.3.1 휠이 있어 PaddleOCR-VL이 CPU로 돌아간다
    (단 paddle은 Metal/MPS 백엔드가 없어 M칩 **GPU**는 못 씀 — CPU 추론만).
- **왜 PP-StructureV3로 대체했나:** T6의 목적은 "인식 품질"이 아니라 `LayoutExtractor`
  **계약 필드**(type·bbox·읽기순서·figure 영역) 확정이다. PP-StructureV3와 PaddleOCR-VL은
  **동일한 `parsing_res_list` 출력 구조**를 공유하므로, 계약 확정에는 PP-StructureV3로 충분하다.
  실제 **한글 인식 품질**(mobile OCR은 한글이 깨짐, 아래 캡처 참조)은 **Sprint 1의 서버리스
  GPU에서 PaddleOCR-VL로** 검증한다. → **실제 VL 실행 결과는 하단 "Sprint 1 PoC" 섹션 참조**
  (Modal A10G에서 한글·수식 정확 인식 확인 완료).

## 실행 환경 / 절차 (재현용)

```bash
# 격리 venv (Intel Mac, CPU)
python3 -m venv .venv-spike
.venv-spike/bin/pip install "paddlepaddle==3.0.0"   # Intel mac 최대 버전
.venv-spike/bin/pip install "paddleocr"             # 3.7.0 설치됨

# 표본: Building-AI-Agent.pdf 69페이지를 PyMuPDF로 200DPI PNG 렌더 → docs/spike-page69.png (1653x2337)
```

```python
from paddleocr import PPStructureV3
pipe = PPStructureV3(
    device="cpu",
    layout_detection_model_name="PP-DocLayout-S",     # 경량
    text_detection_model_name="PP-OCRv5_mobile_det",  # 경량
    text_recognition_model_name="PP-OCRv5_mobile_rec", # 경량
    use_doc_orientation_classify=False, use_doc_unwarping=False,
    use_textline_orientation=False, use_formula_recognition=False,
    use_table_recognition=False, use_seal_recognition=False, use_chart_recognition=False,
)
for res in pipe.predict("docs/spike-page69.png"):
    res.save_to_json("docs/spike-out"); res.save_to_markdown("docs/spike-out")
```

- **성능(참고):** mobile 모델 기준 init **16.5s** + predict **40.4s** ≈ 총 **57초**/페이지 (Intel Mac CPU).
  - server 모델(`PP-OCRv5_server_*` + `PP-DocLayout_plus-L`, PPStructureV3 기본값)은 같은 CPU에서
    **10분+에도 미완주** → 로컬 CPU 스파이크에는 **mobile 모델 강제 권장.**
- **산출물:** `docs/spike-out/spike-page69_res.json`(전체 구조), `docs/spike-out/spike-page69.md`,
  `docs/spike-out/imgs/`, 입력 `docs/spike-page69.png`.

## 확인 항목 (체크) — 실측 결과

- [x] **figure 영역 bbox가 출력되는가** → **예.** `image` 라벨 블록으로 나옴: `block_bbox [170,698,1445,1265]`.
- [x] **figure_caption(주석)이 별도 블록으로 구분되는가** → **예.** `figure_title` 라벨(그림 아래 `[676,1301,960,1331]`).
- [x] **텍스트 블록에 읽기 순서가 제공되는가** → **예.** `block_order`(정수). 단 **비-본문 블록은 `null`**(header/image/figure_title/number).
- [ ] 다단 컬럼 페이지에서 읽기 순서가 올바른가 → **미검증**(69페이지는 단단 컬럼). Sprint 1에서 다단 페이지로 추가 확인.
- [x] **figure 없는 페이지에서도 정상 동작하는가** → 부분. 본 페이지엔 figure 존재. figure 없는 케이스는 Sprint 1 확인.
- [x] **블록 type 분류값 목록** → 아래 "라벨 taxonomy" 참조.

## 실제 출력 캡처 (붙여넣기)

**결과 객체 top-level 키:**
```
['input_path', 'page_index', 'page_count', 'width', 'height',
 'model_settings', 'parsing_res_list', 'doc_preprocessor_res',
 'layout_det_res', 'overall_ocr_res']
page size (width x height, px): 1653 x 2337   # 200DPI 렌더 이미지 픽셀 (595x841pt 원본)
```

**`parsing_res_list[]` 각 블록의 필드:**
```
block_label   : str   레이아웃 종류 (text/title/image/figure_title/formula/header/number ...)
block_content : str   인식 텍스트 (image 블록엔 내부 OCR 텍스트가 들어감)
block_bbox    : [x1, y1, x2, y2]  정수 픽셀, 좌상단 원점 (렌더 이미지 좌표계)
block_id      : int   레이아웃 영역 인덱스
block_order   : int | null   읽기 순서 (본문 흐름). 비-흐름 블록은 null
```

**페이지 69 검출 블록 9개 (order / id / label / bbox):**
```
ord  id  label          bbox                        의미
null  0  header         [1177,  77, 1555, 102]      장 머리글
  1   1  text           [ 154, 205, 1459, 309]      본문 단락
  2   2  text           [ 146, 341, 1464, 647]      본문 단락
null  3  image          [ 170, 698, 1445,1265]      ★ figure(셀프 어텐션 다이어그램)
null  4  figure_title   [ 676,1301,  960,1331]      ★ 그림 캡션(원문 "그림 2-N")
  3   5  text           [ 154,1413, 1469,1651]      본문 단락
  4   6  formula        [ 558,1690, 1035,1728]      수식 (Q=X·Wq, K=X·Wk, V=X·Wv)
  5   7  text           [ 152,1775, 1468,2084]      본문 단락
null  8  number         [1445,2202, 1472,2231]      페이지 번호 "69"
```

**`layout_det_res.boxes[]` (레이아웃 검출 원본, bbox는 float):**
```
{'cls_id': 2, 'label': 'text', 'score': 0.953,
 'coordinate': [152.43, 1775.06, 1468.56, 2084.37]}   # [x1,y1,x2,y2] float 픽셀
```

**라벨 taxonomy (본 페이지 관측 + `model_settings.markdown_ignore_labels` 노출):**
```
관측:  text, header, image, figure_title, formula, number
추가(파이프라인이 인지):  footnote, header_image, footer, footer_image, aside_text
그 외 PP-StructureV3 라벨(문서 기준): title/doc_title, table, chart, seal
```

**⚠️ 한글 인식 품질(mobile OCR):** `block_content`의 한글이 심하게 깨짐
(예: text 블록이 `"probabitity mass0答.D.司scaled dot-product atten..."`, formula가 `"Q= X·W,K = X· W,V = X· WV"`).
mobile rec가 CN/EN 중심이라 한글 스캔에 약하다. **레이아웃(bbox·순서)은 신뢰 가능하나 텍스트 내용은
mobile로는 신뢰 불가** → 실제 인식은 Sprint 1의 PaddleOCR-VL에서.

## 계약 반영 결과 (→ `backend/app/extractor.py`)

현행 `extractor.py`와 실측 간 **불일치 3건**을 확인. Sprint 0 / T7에서 아래로 조정 필요:

1. **`BlockType` 라벨명 불일치.** 현행 `figure`, `figure_caption`은 실제 출력에 없음.
   - `figure` → **`image`**, `figure_caption` → **`figure_title`** 로 정정.
   - 누락 라벨 추가 권장: `header`, `footer`, `number`, `formula`, `footnote`, `table`, `chart`, `aside_text` 등.
   - 정규화 전략 택1: (a) 원 라벨을 그대로 보존, (b) 내부 표준(figure/caption 등)으로 매핑 테이블 유지.
2. **`reading_order`는 `int | None`.** 현행 `int` 필수는 틀림 — 비-흐름 블록(header/image/number 등)은 `null`.
   → `reading_order: int | None` 으로 완화.
3. **BBox 좌표계 = 렌더 이미지 픽셀(좌상단 원점), PDF 포인트 아님.** 값은 렌더 **DPI에 종속**(본 스파이크 200DPI).
   → 계약에 **render DPI(또는 scale)를 함께 보존**해야 figure 크롭/원본 매핑이 가능. `BBox` 주석 보강.
   - **figure 크롭 방법(확정):** `image` 블록 `block_bbox`로 렌더 페이지 PNG를 crop → `image_ref`에 저장.

일치 확인된 부분:
- `Block` 필드 골격(type/bbox/text/reading_order/image_ref)은 실측 구조와 정합.
- `BBox`는 `[x0,y0,x1,y1]` 4-튜플로 정합(픽셀·좌상단 원점).

## Sprint 1 PoC — 실제 PaddleOCR-VL (Modal 서버리스 GPU) 결과 (2026-08-22)

위 PP-StructureV3(mobile, on-device)와 달리, **진짜 PaddleOCR-VL을 Modal 서버리스 GPU에서**
같은 페이지(69)로 실행했다. 목적: (1) 서버리스 GPU 배포 가능성 de-risk, (2) 한글 인식 품질,
(3) VL 출력이 PP-Structure와 같은 계약 구조인지 확인.

**환경/배포:**
- Modal(A10G GPU) + `paddlepaddle-gpu==3.2.1`(CUDA 12.6, `cu126` 인덱스) + `paddleocr[doc-parser]`.
- 모델: **PaddleOCR-VL-1.6 (0.9B)** + 레이아웃 `PP-DocLayoutV3`. 가중치는 Modal Volume에 캐시.
- 코드: `backend/poc/modal_paddleocr_vl.py` (실행: `modal run --detach ...`).

**성능:**
- 이미지 빌드 **~13분(최초 1회, Modal이 캐시)**, 모델 로드 **4.4s(캐시)~26s(콜드)**, **추론 20.6s/페이지(A10G)**.
- ⚠️ **T4는 부적합** — vLLM 가속이 아닌 `paddle_dynamic` 엔진이라 T4에선 10분+ 미완주. **A10G 이상 권장**(또는 vLLM 백엔드 도입).
- ⚠️ **detach 필수** — 클라이언트 연결이 끊기면 원격 함수가 취소됨. `--detach` + 결과를 Volume에 커밋해 회수.

**한글 인식 품질 — mobile 대비 극적 개선 (동일 페이지):**
| 블록 | PP-StructureV3 mobile | PaddleOCR-VL |
|---|---|---|
| header | `2三人：A0` (깨짐) | `2장 트랜스포머: 현대 AI 혁명 이면의 모델` ✅ |
| text | `probabitity mass0答.D.司...` (깨짐) | `앞 장에서 살펴본 것처럼, 벡터의 길이가...` ✅ 전문 정확 |
| figure_title | `二2.5三0` (깨짐) | `그림2.5전개된셀프어텐션` ✅ (원문 "그림 2.5") |
| 수식 | 이미지로 크롭(인식 안 함) | **LaTeX**: `$$ \mathbf{Q}=\mathbf{X}\cdot\mathbf{W}^{Q},... $$` ✅ |

→ **한글·수식 인식은 VL이 압도적.** 계획대로 실제 인식기는 VL(GPU)로 가는 것이 옳음을 실증.

**출력 구조 — PP-Structure와 동일(계약 검증됨):**
- 동일한 `parsing_res_list` + `block_label/block_content/block_bbox/block_id/block_order`.
- `block_bbox` = `[x1,y1,x2,y2]` **float** 픽셀, 좌상단 원점(1653x2337, 200DPI). `block_order` nullable(동일).
- **라벨 차이 주의:** VL은 수식을 **`display_formula`** 로 냄(PP-Struct mobile은 `formula`). figure=`image`, caption=`figure_title`는 동일.
- VL 관측 라벨: `header, text, image, figure_title, display_formula, number`.
- 산출물: `docs/spike-out-vl/page69_vl_result.json`.

**계약(extractor.py)에 추가 반영할 점:**
- BlockType에 `display_formula`(및 `formula`) 포함 — 또는 수식류를 하나로 정규화.
- `BBox`는 float 확정(VL은 float, PP-Struct parsing_res_list는 int로 나오므로 float로 수용).
- 나머지(figure=image, caption=figure_title, reading_order nullable, DPI 종속 픽셀)는 VL에서도 동일하게 확인됨.

## 다음
- **T7:** 위 계약 반영 사항(라벨명·nullable·float·DPI)을 `backend/app/extractor.py`에 반영해 시그니처 확정(구현은 스텁 유지).
- **Sprint 1(정식):** `/sprint-contract` 후 — Modal 배포를 `LayoutExtractor` 실제 구현으로 승격(엔드포인트화), 다단 컬럼·figure-없는 페이지·표 페이지 추가 검증.
- **vLLM 가속 — 보류(결정 2026-08-23):** 현재 A10G 비가속(20.6s/page)로 충분. **사용량이 늘어 배치/동시 처리가 필요해지면** 그때 vLLM 도입(2-tier: `genai_server` + 공식 Docker 이미지, GPU CC≥8.0, `max_num_seqs` 튜닝). 트리거: 다량 PDF 일괄 추출 워크로드 확정.