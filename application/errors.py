class ApplicationError(Exception):
    """Base class for failures of a use case that are not business-rule violations."""


class NoActiveStream(ApplicationError, RuntimeError):
    """The shared transcription stream was requested before any stream was set.

    Also a RuntimeError so callers written against the previous behaviour keep working.
    """


class SharedStreamForwardingError(ApplicationError):
    """Transcribing the shared stream failed; delivered to the reader of ``get_stream``."""


class EngineNotConfigured(ApplicationError, RuntimeError):
    """The selected transcription engine is missing a required setting (e.g. an API key)."""


class StreamSettingsMismatch(ApplicationError, ValueError):
    """A request names stream settings that differ from the ones the active stream was set with."""
