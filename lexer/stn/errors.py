"""STN parsing exceptions."""


class STNError(Exception):
    """Base exception for STN operations."""


class STNSyntaxError(STNError):
    """Raised when the input contains invalid STN syntax."""

    def __init__(self, message, line=None, col=None):
        self.line = line
        self.col = col
        if line is not None and col is not None:
            message = f"{message} (line {line}, col {col})"
        super().__init__(message)
