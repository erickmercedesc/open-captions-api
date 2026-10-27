class PublicError(Exception):
    """Error whose message is safe to return to clients or webhooks."""

    def __init__(self, public_message: str) -> None:
        self.public_message = public_message
        super().__init__(public_message)


class SsrfError(PublicError):
    def __init__(self, public_message: str = "The URL is not allowed.") -> None:
        super().__init__(public_message)


class VideoRejected(PublicError):
    pass
