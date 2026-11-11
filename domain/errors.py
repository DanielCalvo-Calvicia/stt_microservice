"""Domain errors.

They also inherit from the matching builtin exception so that callers written
against the pre-refactor behaviour (``ValueError``) keep working.
"""


class DomainError(Exception):
    """Base class for every business-rule violation raised by the domain."""


class InvalidAudioUtterance(DomainError, ValueError):
    """An utterance violates an invariant (e.g. a non-positive sample rate or half a sample of audio)."""
