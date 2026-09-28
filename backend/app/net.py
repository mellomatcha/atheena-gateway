"""Client network metadata. Only a keyed hash of the IP is ever stored (PRD §7, §11)."""

import hashlib
import hmac

from fastapi import Request

from app.config import Settings


def client_ip_hash(request: Request) -> str | None:
    settings: Settings = request.app.state.settings
    ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "")
    if not ip:
        return None
    secret = settings.ip_hash_secret.get_secret_value().encode()
    if secret:
        return hmac.new(secret, ip.encode(), hashlib.sha256).hexdigest()
    return hashlib.sha256(ip.encode()).hexdigest()
