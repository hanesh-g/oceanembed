"""Domain exception classes for business logic errors."""


class DomainError(Exception):
    """Base class for all domain-specific errors."""

    pass


class ResourceNotFoundError(DomainError):
    """Raised when a requested resource cannot be found."""

    pass


class ResourceExistsError(DomainError):
    """Raised when attempting to create a resource that already exists."""

    pass


class ValidationError(DomainError):
    """Raised when data validation fails."""

    pass
