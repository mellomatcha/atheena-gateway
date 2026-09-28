"""Proxy errors rendered in the format of the endpoint that was called (FR-3.24).

Messages are fixed strings chosen by the portal. Upstream error bodies are never echoed: they
carry upstream model ids and provider names (FR-4.0) and may quote the prompt (PRD §4.3.4).
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum

from fastapi.responses import JSONResponse


class ApiFormat(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


# HTTP status -> (OpenAI error type, Anthropic error type).
_ERROR_TYPES: dict[int, tuple[str, str]] = {
    400: ("invalid_request_error", "invalid_request_error"),
    401: ("authentication_error", "authentication_error"),
    402: ("insufficient_quota", "billing_error"),
    403: ("permission_error", "permission_error"),
    404: ("not_found_error", "not_found_error"),
    413: ("invalid_request_error", "request_too_large"),
    429: ("rate_limit_error", "rate_limit_error"),
    502: ("api_error", "api_error"),
    504: ("api_error", "timeout_error"),
}


@dataclass
class GatewayError(Exception):
    status_code: int
    # Stable machine code, stored in requests.error_type.
    code: str
    message: str
    headers: dict[str, str] = field(default_factory=dict)

    def body(self, api_format: ApiFormat) -> dict[str, object]:
        openai_type, anthropic_type = _ERROR_TYPES.get(self.status_code, ("api_error", "api_error"))
        if api_format is ApiFormat.ANTHROPIC:
            return {"type": "error", "error": {"type": anthropic_type, "message": self.message}}
        return {
            "error": {
                "message": self.message,
                "type": openai_type,
                "param": None,
                "code": self.code,
            }
        }

    def response(self, api_format: ApiFormat) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code, content=self.body(api_format), headers=self.headers
        )

    def sse_event(self, api_format: ApiFormat) -> bytes:
        """The error as a stream event, for failures after the 200 status was already sent."""
        data = json.dumps(self.body(api_format))
        if api_format is ApiFormat.ANTHROPIC:
            return f"event: error\ndata: {data}\n\n".encode()
        return f"data: {data}\n\n".encode()


def invalid_key() -> GatewayError:
    return GatewayError(401, "invalid_api_key", "API key tidak valid, dicabut, atau akun nonaktif.")


def body_too_large(limit: int) -> GatewayError:
    return GatewayError(
        413, "body_too_large", f"Ukuran request melebihi batas {limit // (1024 * 1024)} MB."
    )


def invalid_request(message: str) -> GatewayError:
    return GatewayError(400, "invalid_request", message)


def model_not_allowed(requested: str, allowed: list[str]) -> GatewayError:
    listed = ", ".join(allowed) if allowed else "(tidak ada)"
    return GatewayError(
        403,
        "model_not_allowed",
        f"Model '{requested}' tidak tersedia untuk key ini. Model yang diizinkan: {listed}.",
    )


def insufficient_balance() -> GatewayError:
    return GatewayError(402, "insufficient_balance", "Saldo habis, silakan top-up.")


def daily_cap_exceeded(retry_after_s: int) -> GatewayError:
    return GatewayError(
        429,
        "daily_cap_exceeded",
        "Batas biaya harian sudah tercapai. Coba lagi besok.",
        headers={"Retry-After": str(retry_after_s)},
    )


def rate_limited(retry_after_s: int) -> GatewayError:
    return GatewayError(
        429,
        "rate_limited",
        "Terlalu banyak request. Coba lagi sebentar lagi.",
        headers={"Retry-After": str(retry_after_s)},
    )


def too_many_streams(limit: int) -> GatewayError:
    return GatewayError(
        429,
        "too_many_streams",
        f"Batas {limit} stream bersamaan tercapai. Tunggu stream lain selesai.",
        headers={"Retry-After": "5"},
    )


def project_official_only(project: str, model: str) -> GatewayError:
    return GatewayError(
        403,
        "project_official_only",
        f"Proyek '{project}' hanya boleh memakai model resmi; '{model}' adalah model eksperimen.",
    )


def upstream_failed(upstream_status: int) -> GatewayError:
    """Map an upstream HTTP error to a portal error without echoing the upstream body."""
    if upstream_status == 400:
        return GatewayError(400, "upstream_rejected", "Provider model menolak request ini.")
    if upstream_status == 413:
        return GatewayError(413, "upstream_rejected", "Request terlalu besar untuk model ini.")
    if upstream_status == 429:
        return GatewayError(
            429,
            "upstream_rate_limited",
            "Provider model sedang membatasi request. Coba lagi sebentar lagi.",
            headers={"Retry-After": "30"},
        )
    return GatewayError(
        502, "upstream_error", f"Provider model gagal memproses request (HTTP {upstream_status})."
    )


def upstream_unreachable() -> GatewayError:
    return GatewayError(502, "upstream_unreachable", "Provider model tidak bisa dihubungi.")


def upstream_timeout() -> GatewayError:
    return GatewayError(504, "upstream_timeout", "Provider model tidak merespons tepat waktu.")
