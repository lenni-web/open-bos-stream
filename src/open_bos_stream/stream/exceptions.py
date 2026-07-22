"""
Stream-specific exceptions.
"""


class StreamError(Exception):
    """Base class for stream-related errors."""

class ConfigurationError(StreamError):
    """Invalid stream configuration."""