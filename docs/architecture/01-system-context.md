# 01. System Context (MVP)

Date: 2026-03-21
Status: Agreed

## Scope
Order system MVP architecture baseline.

## Decisions

1. Worker deployment model
- **Adopted:** Separate process (API and Worker are split)
- Reason:
  - Isolate heavy batch workloads from online API traffic
  - Better operational control (scale/restart independently)

2. Observability baseline
- **Adopted:** Structured logs + minimum metrics from day 1
- Reason:
  - Faster incident detection and triage
  - Supports SLA/SLO checks with low initial complexity

3. External integrations in MVP
- **Adopted:** Minimal but practical integration set
- Reason:
  - Avoid blind operations in production
  - Enable immediate business handoff for billing/export workflows

## Logical Architecture

```mermaid
flowchart LR
  U[User]
  FE[Frontend SPA\n(受注/配分/仕入/請求)]
  API[Backend API\n(/api/v1)]
  W[Worker / Batch\n(配分・請求バッチ)]
  DB[(PostgreSQL)]
  OBS[Observability\n(構造化ログ/メトリクス/通知)]

  U --> FE
  FE --> API
  API --> DB
  API --> W
  W --> DB
  API --> OBS
  W --> OBS
```

## MVP External Integrations (Minimum)

1. Email notification
- Targets: invoice finalized, batch failure, critical error
- Minimum implementation: 2-3 templates + single retry

2. Alert destination (choose one)
- Slack / Discord / PagerDuty (single route for MVP)
- Targets: worker failure rate spike, backlog stagnation, API 5xx spike

3. Accounting export
- Start with scheduled/static CSV export (no direct API coupling in MVP)

4. Lightweight webhook receiver
- Provide endpoint foundation for future inbound integrations
- Minimum: skeleton endpoint + basic signature/validation hooks

## Out of Scope (MVP)
- Full external accounting API bi-directional sync
- Complex workflow orchestration
- Multi-channel alert fan-out
