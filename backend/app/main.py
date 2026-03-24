from fastapi import FastAPI

from app.api.routes_products import router as products_router

app = FastAPI(title="Order System v2 API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(products_router)
