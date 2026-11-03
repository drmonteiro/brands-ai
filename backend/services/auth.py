"""
API authentication.

The frontend exchanges a logged-in session for a short-lived JWT
(frontend/app/api/auth/backend-token/route.ts) and sends it on every request.

AUTH_ENFORCED defaults to true. It's false only during rollout, when requests
without a valid token are logged but allowed. With no usable secret, every token
is rejected, so a configuration mistake closes the API rather than opening it.
"""

import logging
import os
from typing import Any, Dict, Optional

import jwt
from fastapi import Header, HTTPException, Request

logger = logging.getLogger("services.auth")

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "lanca-frontend"
JWT_AUDIENCE = "lanca-backend"
MIN_SECRET_LENGTH = 32


def auth_enforced() -> bool:
    return os.getenv("AUTH_ENFORCED", "true").strip().lower() not in ("false", "0", "no", "off")


def verify_token(token: str) -> Dict[str, Any]:
    """Returns the token's claims. Raises jwt.InvalidTokenError if it isn't valid."""
    secret = os.getenv("BACKEND_JWT_SECRET", "")
    if len(secret) < MIN_SECRET_LENGTH:
        raise jwt.InvalidTokenError("BACKEND_JWT_SECRET is missing or too short")
    return jwt.decode(
        token,
        secret,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        options={"require": ["exp", "sub", "iss", "aud"]},
    )


async def require_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Optional[Dict[str, Any]]:
    scheme, _, token = (authorization or "").partition(" ")
    try:
        if scheme.lower() != "bearer" or not token:
            raise jwt.InvalidTokenError("no bearer token")
        return verify_token(token.strip())
    except jwt.InvalidTokenError as e:
        if auth_enforced():
            raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.") from e
        logger.warning("AUTH_NOT_ENFORCED %s %s: %s", request.method, request.url.path, e)
        return None


def _webhook_url(request: Request) -> str:
    """The URL Twilio signed. The app sits behind a proxy, so it can't be read directly."""
    configured = os.getenv("TWILIO_WEBHOOK_URL", "").strip()
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
    return f"{proto}://{host}{request.url.path}"


async def verify_twilio_signature(request: Request) -> None:
    """Twilio can't send a user token, so the WhatsApp webhook checks Twilio's signature instead."""
    from twilio.request_validator import RequestValidator

    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    signature = request.headers.get("x-twilio-signature", "")
    form = await request.form()
    valid = bool(auth_token and signature) and RequestValidator(auth_token).validate(
        _webhook_url(request), dict(form), signature
    )
    if valid:
        return
    if auth_enforced():
        raise HTTPException(status_code=403, detail="Assinatura inválida.")
    logger.warning("AUTH_NOT_ENFORCED %s %s: invalid Twilio signature", request.method, request.url.path)
