# Architecture Diagram (Logical, MVP v2)

Date: 2026-03-17

## 1) Logical Component Diagram

```mermaid
flowchart LR
  U[User Browser] --> FE[Frontend SPA]
  FE --> API[Backend API /api/v1]

  API --> DB[(PostgreSQL)]
  API --> W[Batch/Worker\nAllocation / Invoice Jobs]
  W --> DB

  API --> OBS[Observability\nStructured Logs / Metrics / Alerts]
  W --> OBS
```

## 2) Runtime / Environment Diagram

```mermaid
flowchart TB
  subgraph PROD[Production]
    FEp[Frontend]
    APIp[API]
    Wp[Worker]
    DBp[(PostgreSQL)]
    MONp[Monitoring]

    FEp --> APIp
    APIp --> DBp
    APIp --> Wp
    Wp --> DBp
    APIp --> MONp
    Wp --> MONp
  end

  subgraph STG[Staging]
    FEs[Frontend]
    APIs[API]
    Ws[Worker]
    DBs[(PostgreSQL)]

    FEs --> APIs
    APIs --> DBs
    APIs --> Ws
    Ws --> DBs
  end
```

## 3) Key Operational Notes
- Status transitions are explicit user-triggered bulk actions.
- Line status is updated first; no automatic order status promotion in MVP.
- Server-side authoritative amount/tax calculation.
- Catch-weight validation is enforced at invoice finalize.
- Audit logs required for critical actions (cancel/override/reset/unlock).
