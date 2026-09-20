"""Domain errors.

They also inherit from the matching builtin exception so that callers written
against the pre-refactor behaviour (``ValueError``) keep working.
"""


class DomainError(Exception):
    """Base class for every business-rule violation raised by the domain."""


class InvalidStreamSettings(DomainError, ValueError):
    """The requested stream settings violate an invariant (e.g. non-positive chunk size)."""
