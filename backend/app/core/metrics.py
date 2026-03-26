from datetime import UTC, datetime

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

api_requests_total = Counter(
    "order_system_v2_api_requests_total",
    "Total API requests",
    ["method", "path", "status"],
)

api_request_errors_total = Counter(
    "order_system_v2_api_request_errors_total",
    "API request errors by status family",
    ["status_family"],
)

api_request_duration_ms = Histogram(
    "order_system_v2_api_request_duration_ms",
    "API request duration in milliseconds",
    ["method", "path"],
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
)

inflight_requests = Gauge(
    "order_system_v2_inflight_requests",
    "In-flight API requests",
)


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def metrics_summary_response() -> dict:
    req_total = 0.0
    err_total = 0.0
    for sample in api_requests_total.collect()[0].samples:
        if sample.name.endswith("_total"):
            req_total += float(sample.value)
            status = str(sample.labels.get("status", ""))
            if status.startswith("5"):
                err_total += float(sample.value)

    err_rate = (err_total / req_total) if req_total > 0 else 0.0

    # best-effort p95 approximation from histogram buckets is omitted in MVP summary.
    p95 = None

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "api": {
            "requestsTotal": int(req_total),
            "errorRate5xx": round(err_rate, 6),
            "p95LatencyMs": p95,
            "inflightRequests": float(inflight_requests.collect()[0].samples[0].value),
        },
        "worker": {
            "enqueuedTotal": 0,
            "processedTotal": 0,
            "failedTotal": 0,
            "backlog": 0,
            "oldestAgeSec": 0,
        },
        "db": {
            "connectionsInUse": 0,
            "queryP95Ms": 0,
            "errorsTotal": 0,
            "deadlocksTotal": 0,
        },
    }
