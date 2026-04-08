import re

from sqlalchemy.orm import Session


def generate_next_code(db: Session, model, field_name: str, prefix: str, width: int = 6) -> str:
    field = getattr(model, field_name)
    rows = db.query(field).filter(field.like(f"{prefix}%")).all()

    max_num = 0
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    for (value,) in rows:
        if not value:
            continue
        m = pattern.match(value)
        if not m:
            continue
        max_num = max(max_num, int(m.group(1)))

    return f"{prefix}{max_num + 1:0{width}d}"
