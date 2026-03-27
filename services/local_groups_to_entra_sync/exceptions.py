class AuthenticationError(Exception):
    """Raised when the token request to the Microsoft identity platform fails.

    The message should contain the HTTP status code and error description
    returned by the identity platform.
    """

    def __init__(self, message: str):
        super().__init__(message)
