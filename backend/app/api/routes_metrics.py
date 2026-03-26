from fastapi import APIRouter

from app.core.metrics import metrics_response

router = APIRouter(tags=["metrics"])


@router.get("/api/v1/metrics")
def metrics():
    return metrics_response()
