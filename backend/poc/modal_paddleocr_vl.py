"""Sprint 1 PoC — PaddleOCR-VL on Modal (serverless GPU, A10G).

목적(de-risk):
  1) 서버리스 GPU에 PaddleOCR-VL 배포가 실제로 되는지
  2) mobile OCR에서 깨졌던 한글이 VL(GPU)에서 제대로 인식되는지
  3) VL 출력이 PP-StructureV3와 같은 parsing_res_list 구조인지 (LayoutExtractor 계약 검증)

실행:
  .venv-modal/bin/modal run backend/poc/modal_paddleocr_vl.py
  # 옵션: --image-path docs/spike-page69.png

주의: GPU는 초당 과금. 첫 실행은 이미지 빌드 + 모델 다운로드로 수 분 소요.
"""
import json
import time

import modal

app = modal.App("paddleocr-vl-poc")

# paddlepaddle-gpu 3.2.1 (CUDA 12.6) + PaddleOCR-VL doc-parser
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libgl1", "libglib2.0-0", "libgomp1")
    .pip_install(
        "paddlepaddle-gpu==3.2.1",
        extra_index_url="https://www.paddlepaddle.org.cn/packages/stable/cu126/",
    )
    .pip_install("paddleocr[doc-parser]")
)

# 모델 가중치 캐시 (PaddleX는 ~/.paddlex 에 받음) — 재실행 시 다운로드 생략
model_cache = modal.Volume.from_name("paddlex-cache", create_if_missing=True)
# 추론 결과 저장용 (로컬 타임아웃/클라이언트 끊김과 무관하게 결과 보존)
output_vol = modal.Volume.from_name("vl-poc-output", create_if_missing=True)


@app.cls(
    gpu="A10G",
    image=image,
    volumes={"/root/.paddlex": model_cache, "/output": output_vol},
    timeout=1800,
)
class PaddleOCRVLModel:
    @modal.enter()
    def load(self):
        import paddle
        from paddleocr import PaddleOCRVL

        print("paddle:", paddle.__version__, "| compiled_with_cuda:", paddle.is_compiled_with_cuda())
        t0 = time.time()
        self.pipe = PaddleOCRVL(device="gpu")
        print(f"pipeline loaded in {time.time() - t0:.1f}s")

    @modal.method()
    def infer(self, img_bytes: bytes) -> dict:
        with open("/tmp/in.png", "wb") as f:
            f.write(img_bytes)

        t0 = time.time()
        results = list(self.pipe.predict("/tmp/in.png"))
        dt = time.time() - t0

        out_blocks = []
        meta = {}
        markdown = ""
        for res in results:
            data = res.json
            root = data.get("res", data)
            meta = {
                "width": root.get("width"),
                "height": root.get("height"),
                "labels": sorted({b.get("block_label") for b in root.get("parsing_res_list", [])}),
            }
            for b in root.get("parsing_res_list", []):
                bbox = b.get("block_bbox")
                try:
                    bbox = [float(x) for x in bbox]
                except Exception:
                    pass
                out_blocks.append({
                    "order": b.get("block_order"),
                    "id": b.get("block_id"),
                    "label": b.get("block_label"),
                    "bbox": bbox,
                    "content": b.get("block_content", ""),
                })
            try:
                markdown = res.markdown.get("markdown_texts", "") if isinstance(res.markdown, dict) else str(res.markdown)
            except Exception:
                markdown = ""

        result = {"predict_seconds": dt, "meta": meta, "blocks": out_blocks, "markdown": markdown}

        # 결과를 출력 Volume에 저장+커밋 (detach 실행 시 로컬로 안전하게 회수)
        with open("/output/page69_vl_result.json", "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        output_vol.commit()
        print(">>> result committed to output volume: /output/page69_vl_result.json")

        # 로그에도 블록 테이블 출력
        print(f">>> predict {dt:.1f}s | labels: {meta.get('labels')}")
        for b in out_blocks:
            c = (b["content"] or "").replace("\n", " ")[:50]
            print(f"  ord={b['order']} id={b['id']} {b['label']}: {c}")

        return result


@app.local_entrypoint()
def main(image_path: str = "docs/spike-page69.png"):
    with open(image_path, "rb") as f:
        data = f.read()

    print(f">>> sending {image_path} ({len(data)} bytes) to Modal A10G ...")
    result = PaddleOCRVLModel().infer.remote(data)

    print(f"\n>>> predict: {result['predict_seconds']:.1f}s | meta: {json.dumps(result['meta'], ensure_ascii=False)}")
    print(f"{'ord':>4} {'id':>3} {'label':<14} bbox                          | content")
    for b in result["blocks"]:
        bbox = [round(x, 1) for x in b["bbox"]] if isinstance(b["bbox"], list) else b["bbox"]
        content = (b["content"] or "").replace("\n", " ")[:50]
        print(f"{str(b['order']):>4} {str(b['id']):>3} {str(b['label']):<14} {str(bbox):<28} | {content}")

    # 결과를 로컬에 저장 (스파이크 문서 반영용)
    import pathlib
    outdir = pathlib.Path("docs/spike-out-vl")
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "page69_vl_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    print(f"\n>>> saved docs/spike-out-vl/page69_vl_result.json")