from django.core.exceptions import PermissionDenied


class TenantContextMissing(RuntimeError):
    """Raised when tenant-owned data is accessed without a tenant boundary."""


class TenantBoundaryViolation(PermissionDenied):
    """Raised when a write attempts to cross the active tenant boundary."""
