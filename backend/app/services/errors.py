"""Domain exceptions — every service raises these; API maps them to HTTP."""
from __future__ import annotations


class AccountingError(Exception):
    code = "ACCOUNTING_ERROR"
    status = 422


class UnbalancedEntryError(AccountingError):
    code = "UNBALANCED"


class BadAccountError(AccountingError):
    code = "BAD_ACCOUNT"
    status = 404


class PeriodClosedError(AccountingError):
    code = "PERIOD_CLOSED"
    status = 409


class NoPeriodError(AccountingError):
    code = "NO_PERIOD"
    status = 409


class DuplicateEventError(AccountingError):
    code = "DUPLICATE_EVENT"
    status = 200  # replay -> same result, HTTP 200


class EventConflictError(AccountingError):
    code = "EVENT_CONFLICT"
    status = 409


class ImmutablePostedError(AccountingError):
    code = "POSTED_IMMUTABLE"
    status = 409


class SelfApprovalError(AccountingError):
    code = "SELF_APPROVAL"
    status = 403


class BadStateError(AccountingError):
    code = "BAD_STATE"
    status = 409


class NotFoundError(AccountingError):
    code = "NOT_FOUND"
    status = 404


class ForbiddenError(AccountingError):
    code = "FORBIDDEN"
    status = 403


class AlreadyReversedError(AccountingError):
    code = "ALREADY_REVERSED"
    status = 409


class ValidationError(AccountingError):
    code = "VALIDATION_ERROR"
    status = 422
