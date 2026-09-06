"""Sprint 1 T1 — PaddleOCR-VL 배포형 HTTP 엔드포인트 (Modal, A10G).

배포:  .venv-modal/bin/modal deploy backend/deploy/paddleocr_vl_app.py
호출:  POST <endpoint>/parse
       - header: Authorization: Bearer <API_TOKEN>
       - body:   원본 페이지 이미지 bytes (PNG/JPG)
반환:  {predict_seconds, meta:{width,height,labels}, blocks:[{order,id,label,bbox,content}], markdown}

인증: Modal Secret 'paddleocr-vl-auth'의 API_TOKEN 과 Bearer 토큰 대조.
콜드스타트 허용(scaledown_window=300s → 유휴 시 0 스케일다운). GPU CC≥8.0(A10G).
"""
import json
import time

import modal

app = modal.App("paddleocr-vl")

# paddlepaddle-gpu 3.2.1 (CUDA 12.6) + PaddleOCR-VL doc-parser + fastapi(엔드포인트용)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libgl1", "libglib2.0-0", "libgomp1")
    .pip_install(
        "paddlepaddle-gpu==3.2.1",
        extra_index_url="https://www.paddlepaddle.org.cn/packages/stable/cu126/",
    )
    .pip_install("paddleocr[doc-parser]")
    .pip_install("fastapi[standard]")
)

model_cache = modal.Volume.from_name("paddlex-cache", create_if_missing=True)
auth_secret = modal.Secret.from_name("paddleocr-vl-auth")  # API_TOKEN


def _infer(pipe, img_bytes: bytes) -> dict:
    """이미지 bytes → 정규화 이전 원시 블록 dict (parsing_res_list 기반)."""
    with open("/tmp/in.png", "wb") as f:
        f.write(img_bytes)

    t0 = time.time()
    results = list(pipe.predict("/tmp/in.png"))
    dt = time.time() - t0

    blocks, meta, markdown = [], {}, ""
    for res in results:
        root = res.json.get("res", res.json)
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
            blocks.append({
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

    return {"predict_seconds": dt, "meta": meta, "blocks": blocks, "markdown": markdown}


@app.function(
    gpu="A10G",
    image=image,
    volumes={"/root/.paddlex": model_cache},
    secrets=[auth_secret],
    scaledown_window=300,
    timeout=600,
)
@modal.concurrent(max_inputs=1)  # GPU 추론은 컨테이너당 1건씩
@modal.asgi_app()
def web():
    import os

    from fastapi import FastAPI, HTTPException, Request
    from paddleocr import PaddleOCRVL

    web_app = FastAPI(title="paddleocr-vl")
    pipe = PaddleOCRVL(device="gpu")  # 컨테이너 기동 시 1회 로드

    @web_app.get("/health")
    def health():
        return {"status": "ok"}

    @web_app.post("/parse")
    async def parse(request: Request):
        token = os.environ.get("API_TOKEN", "")
        if not token or request.headers.get("authorization", "") != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="unauthorized")
        img = await request.body()
        if not img:
            raise HTTPException(status_code=400, detail="empty body")
        return _infer(pipe, img)

    return web_app
