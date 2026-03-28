from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

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
from app.core.exception_mapping import map_integrity_error
from app.core.metrics import api_request_duration_ms, api_request_errors_total, api_requests_total, inflight_requests

app = FastAPI(title="Order System v2 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, exc: IntegrityError):
    status, code, message = map_integrity_error(exc)
    return JSONResponse(status_code=status, content={"detail": {"code": code, "message": message}})


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(_: Request, __: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "DB_ERROR", "message": "database operation failed"}},
    )


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started = perf_counter()
    inflight_requests.inc()
    try:
        response = await call_next(request)
    finally:
        inflight_requests.dec()

    elapsed_ms = (perf_counter() - started) * 1000
    route = request.scope.get("route")
    path_label = getattr(route, "path", request.url.path)
    status = str(response.status_code)

    api_requests_total.labels(method=request.method, path=path_label, status=status).inc()
    api_request_duration_ms.labels(method=request.method, path=path_label).observe(elapsed_ms)
    if status.startswith("4") or status.startswith("5"):
        api_request_errors_total.labels(status_family=f"{status[0]}xx").inc()

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
