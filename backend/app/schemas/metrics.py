from pydantic import BaseModel


class MetricsApiSummary(BaseModel):
    requestsTotal: int
    errorRate5xx: float
    errors4xxTotal: int
    errors5xxTotal: int
    statusFamilyCounts: dict[str, int]
    p95LatencyMs: float | None
    endpointLatencyP95Ms: dict[str, float | None]
    endpointStatusCounts: dict[str, dict[str, int]]
    inflightRequests: float


class MetricsWorkerSummary(BaseModel):
    enqueuedTotal: int
    processedTotal: int
    failedTotal: int
    backlog: int
    oldestAgeSec: int


class MetricsDbSummary(BaseModel):
    connectionsInUse: int
    queryP95Ms: int
    errorsTotal: int
    deadlocksTotal: int


class MetricsSummaryResponse(BaseModel):
    timestamp: str
    api: MetricsApiSummary
    worker: MetricsWorkerSummary
    db: MetricsDbSummary
