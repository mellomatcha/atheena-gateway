"""Client-facing gateway endpoints: /v1/models, /v1/chat/completions, /v1/messages."""

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.config import Settings
from app.gateway import errors
from app.gateway.billing import (
    RequestRecord,
    record_request,
    seconds_until_next_day_wib,
    spent_today_idr,
)
from app.gateway.errors import ApiFormat, GatewayError
from app.gateway.keys import KeyIdentity, extract_presented_key, resolve_key
from app.gateway.limits import (
    acquire_stream_slot,
    check_rate_limit,
    refresh_stream_slot,
    release_stream_slot,
)
from app.gateway.relay import HeartbeatConfig, RelayOutcome, RelayResponse, UpstreamCall
from app.gateway.settings_store import load_gateway_settings
from app.gateway.usage import Prices, UsageTracker, compute_cost_idr, parse_json
from app.logs import request_id_var
from app.models import AIModel, Project, User

logger = logging.getLogger(__name__)

router = APIRouter()

USER_AGENT_MAX = 200
PROJECT_MAX = 64
MODEL_NAME_MAX = 200
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"


def _request_uuid() -> uuid.UUID:
    value = request_id_var.get()
    return uuid.UUID(value) if value else uuid.uuid4()


def _client_ip_hash(request: Request, settings: Settings) -> str | None:
    ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "")
    if not ip:
        return None
    secret = settings.ip_hash_secret.get_secret_value().encode()
    if secret:
        return hmac.new(secret, ip.encode(), hashlib.sha256).hexdigest()
    return hashlib.sha256(ip.encode()).hexdigest()


def _project(request: Request) -> str | None:
    value = (request.headers.get("x-project") or "").strip().lower()
    return value[:PROJECT_MAX] or None


def _tier_allows(user_tier: str, min_tier: str) -> bool:
    return user_tier == "advanced" or min_tier == "basic"


async def allowed_models(session: AsyncSession, identity: KeyIdentity) -> list[AIModel]:
    """Active models allowed for the user's tier and the key's allowlist (FR-3.4, FR-4.4)."""
    models = (
        await session.scalars(
            select(AIModel).where(AIModel.is_active.is_(True)).order_by(AIModel.public_name)
        )
    ).all()
    return [
        model
        for model in models
        if _tier_allows(identity.user_tier, model.min_tier)
        and (identity.model_allowlist is None or model.public_name in identity.model_allowlist)
    ]


async def _authenticate(request: Request, session: AsyncSession) -> KeyIdentity:
    presented = extract_presented_key(
        request.headers.get("authorization"), request.headers.get("x-api-key")
    )
    identity = await resolve_key(request.app.state.redis, session, presented) if presented else None
    if identity is None:
        raise errors.invalid_key()
    return identity


async def _read_body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise errors.body_too_large(limit)
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise errors.body_too_large(limit)
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/v1/models")
async def list_models(request: Request) -> Response:
    api_format = ApiFormat.ANTHROPIC if "anthropic-version" in request.headers else ApiFormat.OPENAI
    async with request.app.state.sessionmaker() as session:
        try:
            identity = await _authenticate(request, session)
        except GatewayError as err:
            return err.response(api_format)
        models = await allowed_models(session, identity)
    if api_format is ApiFormat.ANTHROPIC:
        data = [
            {
                "type": "model",
                "id": m.public_name,
                "display_name": m.public_name,
                "created_at": m.created_at.isoformat(),
            }
            for m in models
        ]
        return JSONResponse(
            {
                "data": data,
                "has_more": False,
                "first_id": data[0]["id"] if data else None,
                "last_id": data[-1]["id"] if data else None,
            }
        )
    return JSONResponse(
        {
            "object": "list",
            "data": [
                {
                    "id": m.public_name,
                    "object": "model",
                    "created": int(m.created_at.timestamp()),
                    "owned_by": "atheena",
                }
                for m in models
            ],
        }
    )


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    return await _proxy(request, ApiFormat.OPENAI, "/chat/completions")


@router.post("/v1/messages")
async def messages(request: Request) -> Response:
    return await _proxy(request, ApiFormat.ANTHROPIC, "/messages")


async def _proxy(request: Request, api_format: ApiFormat, upstream_path: str) -> Response:
    state = request.app.state
    settings: Settings = state.settings
    rec = RequestRecord(
        request_id=_request_uuid(),
        endpoint=f"/v1{upstream_path}",
        started_at=datetime.now(UTC),
        status_code=0,
        project=_project(request),
        client_ip_hash=_client_ip_hash(request, settings),
        user_agent=(request.headers.get("user-agent") or "")[:USER_AGENT_MAX] or None,
    )
    started = time.perf_counter()
    stream_slot_held = False
    try:
        async with state.sessionmaker() as session:
            # FR-3.3: key valid and active, user active.
            identity = await _authenticate(request, session)
            rec.user_id, rec.api_key_id = identity.user_id, identity.api_key_id
            limits = await load_gateway_settings(session)

            # FR-3.9 runs before the model checks because the model name is inside the body.
            raw_body = await _read_body(request, limits.max_body_bytes)
            body = parse_json(raw_body)
            if body is None:
                raise errors.invalid_request("Body request harus berupa objek JSON.")
            model_name = body.get("model")
            if not isinstance(model_name, str) or not model_name:
                raise errors.invalid_request("Field 'model' wajib diisi.")
            rec.model_public_name = model_name[:MODEL_NAME_MAX]
            is_stream = body.get("stream") is True
            rec.is_stream = is_stream

            # FR-3.4: model in catalog, active, allowed for tier and key allowlist.
            allowed = await allowed_models(session, identity)
            model = next((m for m in allowed if m.public_name == model_name), None)
            if model is None:
                raise errors.model_not_allowed(model_name, [m.public_name for m in allowed])
            rec.model_id = model.id
            if model.api_format not in (api_format.value, "both"):
                raise errors.invalid_request(
                    f"Model '{model_name}' tidak mendukung endpoint {rec.endpoint}."
                )

            # FR-3.5: balance at or above the minimum.
            balance = await session.scalar(
                select(User.balance_idr).where(User.id == identity.user_id)
            )
            if balance is None or balance < limits.min_balance_idr:
                raise errors.insufficient_balance()

            # FR-3.6: daily cost caps per user and per key.
            user_cap = identity.user_daily_cap_idr
            if user_cap is None:
                user_cap = limits.default_user_daily_cap_idr
            if user_cap is not None and (
                await spent_today_idr(session, user_id=identity.user_id) >= user_cap
            ):
                raise errors.daily_cap_exceeded(seconds_until_next_day_wib())
            key_cap = identity.key_daily_cap_idr
            if key_cap is not None and (
                await spent_today_idr(session, api_key_id=identity.api_key_id) >= key_cap
            ):
                raise errors.daily_cap_exceeded(seconds_until_next_day_wib())

            # FR-3.7: requests per minute per key and per user.
            retry_after = await check_rate_limit(
                state.redis,
                identity.api_key_id,
                identity.user_id,
                limits.rate_limit_per_key_per_minute,
                limits.rate_limit_per_user_per_minute,
            )
            if retry_after:
                raise errors.rate_limited(retry_after)

            # FR-3.8: concurrent streams per user.
            if is_stream:
                if not await acquire_stream_slot(
                    state.redis,
                    identity.user_id,
                    str(rec.request_id),
                    limits.max_concurrent_streams_per_user,
                ):
                    raise errors.too_many_streams(limits.max_concurrent_streams_per_user)
                stream_slot_held = True

            # FR-3.10: official-only projects reject experimental models.
            if rec.project is not None and model.category != "official":
                official_only = await session.scalar(
                    select(Project.official_only).where(Project.slug == rec.project)
                )
                if official_only:
                    raise errors.project_official_only(rec.project, model.public_name)
    except GatewayError as err:
        if stream_slot_held and rec.user_id is not None:
            await release_stream_slot(state.redis, rec.user_id, str(rec.request_id))
        rec.status_code, rec.error_type = err.status_code, err.code
        rec.latency_ms = int((time.perf_counter() - started) * 1000)
        await record_request(state.sessionmaker, rec)
        _log_finish(rec)
        return err.response(api_format)

    return _relay(request, api_format, upstream_path, rec, body, model, identity, started)


def _upstream_call(
    request: Request,
    settings: Settings,
    api_format: ApiFormat,
    upstream_path: str,
    body: dict[str, Any],
    model: AIModel,
    is_stream: bool,
) -> UpstreamCall:
    forwarded = dict(body)
    forwarded["model"] = model.upstream_id  # FR-3.11
    if api_format is ApiFormat.OPENAI and is_stream:
        # FR-3.13: make the last chunk carry usage.
        options = forwarded.get("stream_options")
        forwarded["stream_options"] = {
            **(options if isinstance(options, dict) else {}),
            "include_usage": True,
        }
    # FR-3.16: only what the upstream needs; the portal key and X-Project are never forwarded.
    headers = {
        "authorization": f"Bearer {settings.upstream_api_key.get_secret_value()}",
        "content-type": "application/json",
        "accept": "text/event-stream" if is_stream else "application/json",
        "accept-encoding": "identity",
    }
    if api_format is ApiFormat.ANTHROPIC:
        # FR-3.12: native Anthropic request; version and beta flags keep cache_control intact.
        headers["anthropic-version"] = (
            request.headers.get("anthropic-version") or DEFAULT_ANTHROPIC_VERSION
        )
        if beta := request.headers.get("anthropic-beta"):
            headers["anthropic-beta"] = beta
    return UpstreamCall(
        url=settings.upstream_base_url.rstrip("/") + upstream_path,
        headers=headers,
        body=json.dumps(forwarded, ensure_ascii=False).encode(),
    )


def _relay(
    request: Request,
    api_format: ApiFormat,
    upstream_path: str,
    rec: RequestRecord,
    body: dict[str, Any],
    model: AIModel,
    identity: KeyIdentity,
    started: float,
) -> RelayResponse:
    state = request.app.state
    settings: Settings = state.settings
    tracker = UsageTracker(api_format)
    prices = Prices(
        input=model.price_input_per_m,
        output=model.price_output_per_m,
        cache_write=model.price_cache_write_per_m,
        cache_read=model.price_cache_read_per_m,
    )
    slot_id = str(rec.request_id)

    async def on_finish(outcome: RelayOutcome) -> None:
        try:
            if outcome.upstream_accepted and (
                outcome.error is None or outcome.client_disconnected or tracker.output_chars > 0
            ):
                usage, estimated = tracker.finalize(body)
            else:
                # FR-3.22: failed at the upstream, record whatever usage was reported.
                usage, estimated = tracker.usage, False
            rec.usage, rec.usage_estimated = usage, estimated
            rec.price_snapshot = prices.snapshot()
            rec.cost_idr = compute_cost_idr(usage, prices)
            rec.status_code = outcome.status_code
            if outcome.client_disconnected:
                rec.error_type = "client_disconnected"
            elif outcome.error is not None:
                rec.error_type = outcome.error.code
            rec.ttft_ms = outcome.ttft_ms
            rec.latency_ms = int((time.perf_counter() - started) * 1000)
            await record_request(state.sessionmaker, rec)
            _log_finish(rec)
        except Exception as exc:
            logger.error("failed to record request", extra={"exc_type": type(exc).__name__})
        finally:
            if rec.is_stream:
                await release_stream_slot(state.redis, identity.user_id, slot_id)

    async def on_alive() -> None:
        await refresh_stream_slot(state.redis, identity.user_id, slot_id)

    return RelayResponse(
        client=state.upstream,
        call=_upstream_call(
            request, settings, api_format, upstream_path, body, model, rec.is_stream
        ),
        api_format=api_format,
        is_stream=rec.is_stream,
        public_name=model.public_name,
        tracker=tracker,
        heartbeat=HeartbeatConfig(
            stream_interval_s=settings.stream_heartbeat_interval_s,
            nonstream_delay_s=settings.nonstream_heartbeat_delay_s,
            nonstream_interval_s=settings.nonstream_heartbeat_interval_s,
        ),
        on_finish=on_finish,
        on_alive=on_alive if rec.is_stream else None,
    )


def _log_finish(rec: RequestRecord) -> None:
    """One metadata-only line per proxied request (PRD §12); never prompt or response text."""
    logger.info(
        "proxy request",
        extra={
            "user_id": str(rec.user_id) if rec.user_id else None,
            "api_key_id": str(rec.api_key_id) if rec.api_key_id else None,
            "model": rec.model_public_name,
            "project": rec.project,
            "endpoint": rec.endpoint,
            "stream": rec.is_stream,
            "status": rec.status_code,
            "error_type": rec.error_type,
            "input_tokens": rec.usage.input_tokens,
            "output_tokens": rec.usage.output_tokens,
            "cache_write_tokens": rec.usage.cache_write_tokens,
            "cache_read_tokens": rec.usage.cache_read_tokens,
            "usage_estimated": rec.usage_estimated,
            "cost_idr": rec.cost_idr,
            "latency_ms": rec.latency_ms,
            "ttft_ms": rec.ttft_ms,
        },
    )
