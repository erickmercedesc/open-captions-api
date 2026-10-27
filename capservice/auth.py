import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from capservice.config import Settings, get_settings


def _extract_token(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def require_api_key(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    provided = _extract_token(authorization, x_api_key)
    expected = settings.api_key
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
