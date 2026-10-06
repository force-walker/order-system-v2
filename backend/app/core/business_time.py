from datetime import datetime
from zoneinfo import ZoneInfo

HONG_KONG_TZ = ZoneInfo("Asia/Hong_Kong")


def hong_kong_today(now: datetime | None = None):
    value = now or datetime.now(HONG_KONG_TZ)
    if value.tzinfo is None:
        value = value.replace(tzinfo=HONG_KONG_TZ)
    return value.astimezone(HONG_KONG_TZ).date()
