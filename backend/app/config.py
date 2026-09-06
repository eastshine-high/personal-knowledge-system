"""설정 — LayoutExtractor 구현/엔드포인트 스왑 지점.

`extract_backend`(modal=서버리스 GPU / fixture=캡처 응답 오프라인 재생 / stub / local)와
`modal_endpoint_url`만 바꾸면 추출 구현을 교체할 수 있다.
값은 환경변수에서 읽으며, 개발 편의를 위해 gitignored `backend/.env.modal`(KEY=VALUE)도 로드한다
(이미 설정된 실제 환경변수는 덮어쓰지 않는다).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# backend/app/config.py → parents[1] == backend/
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env.modal"


def _load_env_file(path: Path) -> None:
    """단순 KEY=VALUE 로더. 이미 존재하는 환경변수는 유지(실제 env 우선)."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    extract_backend: str        # "modal" | "fixture" | "stub" | "local"
    modal_endpoint_url: str     # 배포된 PaddleOCR-VL 엔드포인트 (서버리스 GPU)
    modal_api_token: str        # 엔드포인트 Bearer 토큰
    render_dpi: int             # PDF 페이지 렌더 DPI (bbox 좌표계 기준)
    request_timeout_s: float    # 추출 호출 타임아웃(콜드스타트 포함)
    crop_dir: str               # figure 크롭 저장 디렉토리
    max_retries: int            # transient(5xx/네트워크) 오류 재시도 횟수
    retry_backoff_s: float      # 재시도 백오프 기준 초 (선형: base×attempt)
    warmup: bool                # 추출 전 /health 핑으로 콜드스타트 흡수 (콜드에서도 <90초 유지)
    fixtures_dir: str           # EXTRACT_BACKEND=fixture 시 재생할 캡처 응답 디렉토리
    llm_backend: str            # 요약/리파인 LLM: "mock" | "anthropic" | "openai" | "local"


def get_settings() -> Settings:
    _load_env_file(_ENV_FILE)
    return Settings(
        extract_backend=os.getenv("EXTRACT_BACKEND", "modal"),
        modal_endpoint_url=os.getenv("MODAL_ENDPOINT_URL", ""),
        modal_api_token=os.getenv("MODAL_API_TOKEN", ""),
        render_dpi=int(os.getenv("RENDER_DPI", "200")),
        request_timeout_s=float(os.getenv("EXTRACT_TIMEOUT_S", "120")),
        # CWD 독립: 기본값은 backend/.crops 절대경로 (env로 재정의 가능)
        crop_dir=os.getenv("CROP_DIR", str(_ENV_FILE.parent / ".crops")),
        max_retries=int(os.getenv("EXTRACT_MAX_RETRIES", "2")),
        retry_backoff_s=float(os.getenv("EXTRACT_RETRY_BACKOFF_S", "2")),
        warmup=os.getenv("EXTRACT_WARMUP", "1") not in ("0", "false", "False", ""),
        fixtures_dir=os.getenv("FIXTURES_DIR", str(_ENV_FILE.parent / "tests" / "fixtures")),
        llm_backend=os.getenv("LLM_BACKEND", "mock"),
    )
