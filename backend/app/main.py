from fastapi import FastAPI

from app.api.routes_customers import router as customers_router
from app.api.routes_orders import router as orders_router
from app.api.routes_products import router as products_router

app = FastAPI(title="Order System v2 API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(products_router)
app.include_router(customers_router)
app.include_router(orders_router)
