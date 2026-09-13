class AppError(Exception):
    """Safe application error with an HTTP status and public message."""

    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
