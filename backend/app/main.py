from fastapi import FastAPI

app = FastAPI(title="Order System v2 API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
