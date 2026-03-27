from app.core.exception_mapping import map_integrity_error


class _Orig:
    def __init__(self, message: str, pgcode: str | None = None):
        self._message = message
        self.pgcode = pgcode

    def __str__(self) -> str:
        return self._message


class _FakeIntegrityError(Exception):
    def __init__(self, orig):
        self.orig = orig


def test_map_integrity_error_unique_violation_postgres_code():
    exc = _FakeIntegrityError(_Orig("duplicate key value violates unique constraint", pgcode="23505"))
    status, code, _ = map_integrity_error(exc)  # type: ignore[arg-type]
    assert status == 409
    assert code == "RESOURCE_ALREADY_EXISTS"


def test_map_integrity_error_check_violation_sqlite_message():
    exc = _FakeIntegrityError(_Orig("CHECK constraint failed: ck_invoices_due_date_gte_invoice_date"))
    status, code, _ = map_integrity_error(exc)  # type: ignore[arg-type]
    assert status == 422
    assert code == "VALIDATION_FAILED"


def test_map_integrity_error_foreign_key_violation():
    exc = _FakeIntegrityError(_Orig("insert or update violates foreign key constraint", pgcode="23503"))
    status, code, _ = map_integrity_error(exc)  # type: ignore[arg-type]
    assert status == 422
    assert code == "INVALID_REFERENCE"
