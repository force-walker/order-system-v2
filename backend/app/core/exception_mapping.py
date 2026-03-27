from sqlalchemy.exc import IntegrityError


def map_integrity_error(exc: IntegrityError) -> tuple[int, str, str]:
    """Map DB integrity errors to API-facing status/code/message.

    Returns: (http_status, error_code, message)
    """

    pgcode = getattr(getattr(exc, "orig", None), "pgcode", None)
    raw = str(getattr(exc, "orig", exc)).lower()

    if pgcode == "23505" or "unique constraint" in raw or "unique failed" in raw:
        return 409, "RESOURCE_ALREADY_EXISTS", "resource already exists"

    if pgcode == "23503" or "foreign key constraint" in raw:
        return 422, "INVALID_REFERENCE", "invalid foreign key reference"

    if pgcode == "23514" or "check constraint" in raw:
        return 422, "VALIDATION_FAILED", "check constraint violated"

    if pgcode == "23502" or "not null constraint" in raw:
        return 422, "VALIDATION_FAILED", "required field is missing"

    if pgcode == "22001" or "value too long" in raw:
        return 422, "VALIDATION_FAILED", "value too long"

    return 409, "CONSTRAINT_VIOLATION", "constraint violation"
