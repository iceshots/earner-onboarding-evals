"""Errors raised by the tools. The message is written for the model to read and recover from."""


class ToolValidationError(ValueError):
    """An argument failed validation. Never reaches SQL; dispatch() turns it into {"error": ...}."""
