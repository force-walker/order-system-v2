from fastapi import FastAPI, Request

from app.api.routes_allocations import router as allocations_router
from app.api.routes_audit import router as audit_router
from app.api.routes_auth import router as auth_router
from app.api.routes_batch import router as batch_router
from app.api.routes_customers import router as customers_router
from app.api.routes_invoices import router as invoices_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_orders import router as orders_router
from app.api.routes_products import router as products_router
from app.api.routes_purchase_results import router as purchase_results_router
from app.core.metrics import api_requests_total

app = FastAPI(title="Order System v2 API")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    response = await call_next(request)
    route = request.scope.get("route")
    path_label = getattr(route, "path", request.url.path)
    api_requests_total.labels(method=request.method, path=path_label, status=str(response.status_code)).inc()
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health")
def health_v1() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(metrics_router)
app.include_router(audit_router)
app.include_router(products_router)
app.include_router(customers_router)
app.include_router(orders_router)
app.include_router(allocations_router)
app.include_router(purchase_results_router)
app.include_router(invoices_router)
app.include_router(batch_router)
