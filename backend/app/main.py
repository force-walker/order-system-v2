from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
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
from app.api.routes_supplier_product_mappings import router as supplier_product_mappings_router
from app.api.routes_suppliers import router as suppliers_router
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


def _error_payload(code: str, message: str, details: list[dict] | None = None) -> dict:
    return {"detail": {"code": code, "message": message, "details": details}}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    detail_rows = []
    for e in exc.errors():
        detail_rows.append({"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")})
    return JSONResponse(status_code=422, content=_error_payload("VALIDATION_ERROR", "request validation failed", detail_rows))


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code", "HTTP_ERROR")
        message = detail.get("message", str(code))
        details = detail.get("details")
        return JSONResponse(status_code=exc.status_code, content=_error_payload(code, message, details))
    return JSONResponse(status_code=exc.status_code, content=_error_payload("HTTP_ERROR", str(detail)))


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, exc: IntegrityError):
    status, code, message = map_integrity_error(exc)
    return JSONResponse(status_code=status, content=_error_payload(code, message))


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(_: Request, __: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content=_error_payload("DB_ERROR", "database operation failed"),
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
app.include_router(suppliers_router)
app.include_router(supplier_product_mappings_router)
app.include_router(orders_router)
app.include_router(allocations_router)
app.include_router(purchase_results_router)
app.include_router(invoices_router)
app.include_router(batch_router)
