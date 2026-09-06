from fastapi import FastAPI

app = FastAPI(title="PKS — PDF 개념 요약 노트 모듈")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}