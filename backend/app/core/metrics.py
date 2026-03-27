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


def _approx_p95_from_buckets(bucket_pairs: list[tuple[float, float]]) -> float | None:
    if not bucket_pairs:
        return None
    total = bucket_pairs[-1][1]
    if total <= 0:
        return None
    target = total * 0.95
    for upper_bound, cumulative in bucket_pairs:
        if cumulative >= target:
            return upper_bound
    return bucket_pairs[-1][0]


def metrics_summary_response() -> dict:
    req_total = 0.0
    err_4xx_total = 0.0
    err_5xx_total = 0.0
    status_family_counts = {"4xx": 0, "5xx": 0}
    endpoint_status_counts: dict[str, dict[str, int]] = {}

    for sample in api_requests_total.collect()[0].samples:
        if not sample.name.endswith("_total"):
            continue

        value = float(sample.value)
        req_total += value

        method = str(sample.labels.get("method", ""))
        path = str(sample.labels.get("path", ""))
        status = str(sample.labels.get("status", ""))
        key = f"{method} {path}".strip()
        endpoint_status_counts.setdefault(key, {})
        endpoint_status_counts[key][status] = int(endpoint_status_counts[key].get(status, 0) + value)

        if status.startswith("4"):
            err_4xx_total += value
            status_family_counts["4xx"] += int(value)
        if status.startswith("5"):
            err_5xx_total += value
            status_family_counts["5xx"] += int(value)

    err_rate_5xx = (err_5xx_total / req_total) if req_total > 0 else 0.0

    bucket_by_endpoint: dict[str, list[tuple[float, float]]] = {}
    for sample in api_request_duration_ms.collect()[0].samples:
        if not sample.name.endswith("_bucket"):
            continue
        method = str(sample.labels.get("method", ""))
        path = str(sample.labels.get("path", ""))
        le = str(sample.labels.get("le", ""))
        if le == "+Inf":
            continue
        try:
            upper_bound = float(le)
        except ValueError:
            continue
        key = f"{method} {path}".strip()
        bucket_by_endpoint.setdefault(key, []).append((upper_bound, float(sample.value)))

    endpoint_latency_p95: dict[str, float | None] = {}
    for key, buckets in bucket_by_endpoint.items():
        buckets.sort(key=lambda x: x[0])
        endpoint_latency_p95[key] = _approx_p95_from_buckets(buckets)

    p95_values = [v for v in endpoint_latency_p95.values() if v is not None]
    global_p95 = max(p95_values) if p95_values else None

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "api": {
            "requestsTotal": int(req_total),
            "errorRate5xx": round(err_rate_5xx, 6),
            "errors4xxTotal": int(err_4xx_total),
            "errors5xxTotal": int(err_5xx_total),
            "statusFamilyCounts": status_family_counts,
            "p95LatencyMs": global_p95,
            "endpointLatencyP95Ms": endpoint_latency_p95,
            "endpointStatusCounts": endpoint_status_counts,
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
