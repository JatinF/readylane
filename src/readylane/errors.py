"""Errors the HTTP layer maps to status codes."""


class GateError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
