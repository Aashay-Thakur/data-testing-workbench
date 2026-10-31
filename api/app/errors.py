"""Errors that map to HTTP responses or stored check results."""


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UserError(AppError):
    """Bad request. Do not store a run."""


class QueryError(AppError):
    """A read failed or the relation is missing. Store this as an error run."""
