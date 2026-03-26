from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from starlette.responses import Response

api_requests_total = Counter(
    "order_system_v2_api_requests_total",
    "Total API requests",
    ["method", "path", "status"],
)


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
