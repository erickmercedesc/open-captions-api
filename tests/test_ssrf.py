import pytest

from capservice.errors import SsrfError
from capservice.ssrf import validate_public_https_url


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/video.mp4",
        "https://127.0.0.1/video.mp4",
        "https://localhost/video.mp4",
        "https://10.0.0.1/video.mp4",
        "https://192.168.1.10/hook",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/video.mp4",
        "file:///etc/passwd",
        "https://user:pass@example.com/video.mp4",
        "https://metadata.google.internal/",
        "https://host.local/video.mp4",
    ],
)
def test_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(SsrfError):
        validate_public_https_url(url)


def test_accepts_public_https() -> None:
    assert validate_public_https_url("https://example.com/video.mp4").startswith("https://")
