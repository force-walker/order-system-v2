from fastapi import FastAPI

from app.api.routes_allocations import router as allocations_router
from app.api.routes_auth import router as auth_router
from app.api.routes_customers import router as customers_router
from app.api.routes_invoices import router as invoices_router
from app.api.routes_orders import router as orders_router
from app.api.routes_products import router as products_router
from app.api.routes_purchase_results import router as purchase_results_router

app = FastAPI(title="Order System v2 API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health")
def health_v1() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(products_router)
app.include_router(customers_router)
app.include_router(orders_router)
app.include_router(allocations_router)
app.include_router(purchase_results_router)
app.include_router(invoices_router)
