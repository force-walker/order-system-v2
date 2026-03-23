# 99. Open Questions / Assumptions (MVP v2)

Date: 2026-03-22
Status: For Infra/DevOps handoff

## Open Questions

As of this baseline, there are **no blocking open architecture questions**.

## Assumptions

1. Deployment
- API and Worker run as separate processes from MVP start.
- Staging and Production environments are both available.

2. Data and Migration
- Existing schema/data will be aligned using Alembic revisions and precheck SQL.
- DB backups are taken before migration execution.

3. Security
- HTTPS is available in runtime environments.
- JWT signing secret management is provided by environment/config.

4. Observability
- Structured logs can be collected centrally.
- Minimum metrics and alert routing destination (one channel) are available.

5. External integrations
- Email delivery service is reachable for minimum notification use-cases.
- Accounting handoff starts with CSV export (not direct API integration).

## Non-blocking Follow-ups (vNext candidates)
- Queue infrastructure hardening (dedicated broker) if backlog growth appears.
- Advanced alert routing/fan-out and on-call workflow.
- Fine-grained post-unlock editable-field restrictions.
- Bi-directional accounting integration.
