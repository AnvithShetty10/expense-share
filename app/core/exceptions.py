"""Custom exception classes"""
from typing import Any, Optional


class AppException(Exception):
    """Base exception for application errors"""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_type: str = "AppError",
        details: Optional[Any] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.details = details
        super().__init__(self.message)


class ValidationError(AppException):
    """Validation error exception"""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_type="ValidationError",
            details=details
        )


class NotFoundError(AppException):
    """Resource not found exception"""

    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=404,
            error_type="NotFoundError",
            details=details
        )


class AuthenticationError(AppException):
    """Authentication failure exception"""

    def __init__(self, message: str = "Authentication failed", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=401,
            error_type="AuthenticationError",
            details=details
        )


class AuthorizationError(AppException):
    """Authorization/permission denied exception"""

    def __init__(self, message: str = "Permission denied", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=403,
            error_type="AuthorizationError",
            details=details
        )


class DatabaseError(AppException):
    """Database operation error exception"""

    def __init__(self, message: str = "Database error occurred", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_type="DatabaseError",
            details=details
        )


class ConflictError(AppException):
    """Resource conflict exception (e.g., duplicate entry)"""

    def __init__(self, message: str = "Resource already exists", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=409,
            error_type="ConflictError",
            details=details
        )
