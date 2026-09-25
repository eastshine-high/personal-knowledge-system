"""ModalLayoutExtractor — 배포된 PaddleOCR-VL 엔드포인트를 호출하는 LayoutExtractor 구현.

흐름(공유): PDF 페이지 범위 로컬 렌더 → 엔드포인트로 POST → RAW_LABEL_MAP 정규화 → ExtractionResult.
이 클래스는 raw 응답 획득(`_fetch_raw`)과 워밍업(`_before_extract`)만 정의하고, 렌더/정규화/크롭은
BaseLayoutExtractor가 담당한다.

PII: 페이지 이미지는 **우리 Modal 인스턴스**로만 전송(제3자 OCR 벤더 미전송). 원문 텍스트는 로그에 남기지 않는다.
"""
from __future__ import annotations

import time

import httpx

from ..config import Settings, get_settings
from .base import BaseLayoutExtractor, ExtractionError

__all__ = ["ModalLayoutExtractor", "ExtractionError"]


class ModalLayoutExtractor(BaseLayoutExtractor):
    """서버리스 GPU(Modal) 엔드포인트 기반 LayoutExtractor 구현."""

    def __init__(
        self,
        endpoint_url: str,
        api_token: str,
        *,
        render_dpi: int = 200,
        timeout_s: float = 120.0,
        crop_dir: str = "backend/.crops",
        max_retries: int = 2,
        retry_backoff_s: float = 2.0,
        warmup: bool = True,
    ) -> None:
        if not endpoint_url:
            raise ValueError("endpoint_url이 비어 있음 (MODAL_ENDPOINT_URL 설정 필요)")
        super().__init__(render_dpi=render_dpi, crop_dir=crop_dir)
        self._url = endpoint_url.rstrip("/")
        self._token = api_token
        self._timeout = timeout_s
        self._max_retries = max_retries
        self._retry_backoff_s = retry_backoff_s
        self._warmup = warmup

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "ModalLayoutExtractor":
        s = settings or get_settings()
        return cls(
            s.modal_endpoint_url,
            s.modal_api_token,
            render_dpi=s.render_dpi,
            timeout_s=s.request_timeout_s,
            crop_dir=s.crop_dir,
            max_retries=s.max_retries,
            retry_backoff_s=s.retry_backoff_s,
            warmup=s.warmup,
        )

    def _before_extract(self) -> None:
        if self._warmup:
            self._warmup_container()

    def _fetch_raw(self, page_no: int, img_bytes: bytes) -> dict:
        return self._call_endpoint(img_bytes)

    def _warmup_container(self) -> None:
        """추출 전 /health 핑으로 컨테이너를 깨운다(모델 로드 완료 후 200 응답).

        콜드스타트의 'lost track of input' 유실을 싼 /health가 흡수해, 이어지는 /parse는 웜 상태가 된다.
        best-effort: 실패해도 예외를 던지지 않는다(실제 /parse 호출이 자체 재시도로 처리).
        """
        for attempt in range(self._max_retries + 2):
            try:
                resp = httpx.get(f"{self._url}/health", timeout=self._timeout)
                if resp.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            if attempt < self._max_retries + 1:
                time.sleep(self._retry_backoff_s * (attempt + 1))

    def _call_endpoint(self, img_bytes: bytes) -> dict:
        """엔드포인트 호출. transient(5xx/네트워크/타임아웃)는 재시도, 4xx는 즉시 실패."""
        last_error: ExtractionError | None = None
        for attempt in range(self._max_retries + 1):
            result = self._try_post(img_bytes)
            if isinstance(result, dict):
                return result
            last_error = result
            if attempt < self._max_retries:
                time.sleep(self._retry_backoff_s * (attempt + 1))
        assert last_error is not None
        raise last_error

    def _try_post(self, img_bytes: bytes) -> "dict | ExtractionError":
        """엔드포인트에 1회 POST. 성공: dict 반환. transient: ExtractionError 반환. 4xx: raise."""
        try:
            resp = httpx.post(
                f"{self._url}/parse",
                headers={"Authorization": f"Bearer {self._token}"},
                content=img_bytes,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            return ExtractionError(f"endpoint 호출 실패: {exc}")
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError as exc:
                raise ExtractionError("endpoint 응답이 JSON이 아님") from exc
        if 500 <= resp.status_code < 600:
            return ExtractionError(f"endpoint {resp.status_code}: {resp.text[:200]}")
        raise ExtractionError(f"endpoint {resp.status_code}: {resp.text[:200]}")
