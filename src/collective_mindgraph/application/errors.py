"""Application failures that transport adapters may map to typed responses."""


class ProviderUnavailableError(RuntimeError):
    """Requested local capability has no available configured adapter."""
