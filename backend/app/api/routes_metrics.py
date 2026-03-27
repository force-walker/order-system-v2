from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, require_roles
from app.core.metrics import metrics_response, metrics_summary_response
from app.schemas.metrics import MetricsSummaryResponse

router = APIRouter(tags=["metrics"])


@router.get("/api/v1/metrics")
def metrics():
    return metrics_response()


@router.get("/api/v1/ops/metrics/summary", response_model=MetricsSummaryResponse)
def metrics_summary(auth: AuthContext = Depends(require_roles("admin"))) -> MetricsSummaryResponse:
    return MetricsSummaryResponse.model_validate(metrics_summary_response())
