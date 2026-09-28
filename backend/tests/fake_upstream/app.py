"""Fake upstream router for tests: OpenAI and Anthropic endpoints, stream and non-stream.

The scenario is encoded in the upstream model id the gateway forwards, e.g.
`fake/ok?prompt=11&completion=7&cached=3`. Parameters:

- `prompt`, `completion`, `cached`, `cache_write`, `cache_read`: usage numbers to report.
- `nousage=1`: report no usage at all.
- `delay`: seconds before the response headers are sent.
- `ttft`: seconds between the headers and the first body byte (stream only).
- `status`: HTTP error status to return instead of a completion.
- `chunks`: number of content chunks (stream).
- `cut=N`: abort the connection after N content chunks (stream).
- `inband_error=N`: emit an in-band error event after N content chunks (stream).
- `hang=1`: after the first chunk, keep the stream open for a long time.

Every response embeds the upstream model id and a provider-style error prefix so tests can
assert neither leaks to the client. Requests received are kept in RECEIVED for inspection.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qsl

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

RESPONSE_TEXT = "SECRET-RESPONSE-TEXT jawaban dari model palsu"
LEAKY_ERROR = "[codebuddy/secret-upstream-model] [500]: internal provider failure"

RECEIVED: list[dict[str, Any]] = []


class Scenario:
    def __init__(self, model: str) -> None:
        _, _, query = model.partition("?")
        self.params = dict(parse_qsl(query))

    def int(self, name: str, default: int = 0) -> int:
        return int(self.params.get(name, default))

    def float(self, name: str, default: float = 0.0) -> float:
        return float(self.params.get(name, default))

    def flag(self, name: str) -> bool:
        return self.params.get(name) == "1"


def _chunks_text(n: int) -> list[str]:
    words = RESPONSE_TEXT.split(" ")
    return [words[i % len(words)] + " " for i in range(n)]


def _sse(data: dict[str, Any], event: str | None = None) -> bytes:
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {json.dumps(data)}\n\n".encode()


def _openai_usage(sc: Scenario) -> dict[str, Any]:
    usage: dict[str, Any] = {
        "prompt_tokens": sc.int("prompt", 11),
        "completion_tokens": sc.int("completion", 7),
        "total_tokens": sc.int("prompt", 11) + sc.int("completion", 7),
    }
    if sc.int("cached"):
        usage["prompt_tokens_details"] = {"cached_tokens": sc.int("cached")}
    return usage


def _anthropic_start_usage(sc: Scenario) -> dict[str, Any]:
    return {
        "input_tokens": sc.int("prompt", 11),
        "cache_creation_input_tokens": sc.int("cache_write"),
        "cache_read_input_tokens": sc.int("cache_read"),
        "output_tokens": 1,
    }


async def _openai_stream(model: str, sc: Scenario, include_usage: bool) -> AsyncIterator[bytes]:
    await asyncio.sleep(sc.float("ttft"))
    n = sc.int("chunks", 3)
    for i, text in enumerate(_chunks_text(n)):
        if sc.params.get("cut") == str(i):
            raise ConnectionAbortedError("fake upstream cut")
        if sc.params.get("inband_error") == str(i):
            yield _sse({"error": {"message": LEAKY_ERROR, "type": "server_error"}})
            return
        delta: dict[str, Any] = {"content": text}
        if i == 0:
            delta["role"] = "assistant"
        yield _sse(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [
                    {"index": 0, "delta": delta, "finish_reason": "stop" if i == n - 1 else None}
                ],
            }
        )
        if sc.flag("hang") and i == 0:
            await asyncio.sleep(60)
    if include_usage and not sc.flag("nousage"):
        yield _sse(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [],
                "usage": _openai_usage(sc),
            }
        )
    yield b"data: [DONE]\n\n"


async def _anthropic_stream(model: str, sc: Scenario) -> AsyncIterator[bytes]:
    await asyncio.sleep(sc.float("ttft"))
    start: dict[str, Any] = {
        "id": "msg_fake",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [],
    }
    if not sc.flag("nousage"):
        start["usage"] = _anthropic_start_usage(sc)
    yield _sse({"type": "message_start", "message": start}, "message_start")
    yield _sse(
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        "content_block_start",
    )
    n = sc.int("chunks", 3)
    for i, text in enumerate(_chunks_text(n)):
        if sc.params.get("cut") == str(i):
            raise ConnectionAbortedError("fake upstream cut")
        if sc.params.get("inband_error") == str(i):
            yield _sse(
                {"type": "error", "error": {"type": "api_error", "message": LEAKY_ERROR}}, "error"
            )
            return
        yield _sse(
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text},
            },
            "content_block_delta",
        )
        if sc.flag("hang") and i == 0:
            await asyncio.sleep(60)
    yield _sse({"type": "content_block_stop", "index": 0}, "content_block_stop")
    delta: dict[str, Any] = {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}
    if not sc.flag("nousage"):
        delta["usage"] = {"output_tokens": sc.int("completion", 7)}
    yield _sse(delta, "message_delta")
    yield _sse({"type": "message_stop"}, "message_stop")


async def _handle(request: Request, api_format: str) -> Response:
    body = await request.json()
    RECEIVED.append({"path": request.url.path, "headers": dict(request.headers), "body": body})
    model = body.get("model", "")
    sc = Scenario(model)
    await asyncio.sleep(sc.float("delay"))
    if sc.int("status"):
        return JSONResponse({"error": {"message": LEAKY_ERROR, "model": model}}, sc.int("status"))
    stream = body.get("stream") is True
    if api_format == "openai":
        if stream:
            include = bool((body.get("stream_options") or {}).get("include_usage"))
            return StreamingResponse(
                _openai_stream(model, sc, include), media_type="text/event-stream"
            )
        payload: dict[str, Any] = {
            "id": "chatcmpl-fake",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": RESPONSE_TEXT},
                    "finish_reason": "stop",
                }
            ],
        }
        if not sc.flag("nousage"):
            payload["usage"] = _openai_usage(sc)
        return JSONResponse(payload)
    if stream:
        return StreamingResponse(_anthropic_stream(model, sc), media_type="text/event-stream")
    message: dict[str, Any] = {
        "id": "msg_fake",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": RESPONSE_TEXT}],
        "stop_reason": "end_turn",
    }
    if not sc.flag("nousage"):
        message["usage"] = {**_anthropic_start_usage(sc), "output_tokens": sc.int("completion", 7)}
    return JSONResponse(message)


async def chat_completions(request: Request) -> Response:
    return await _handle(request, "openai")


async def messages(request: Request) -> Response:
    return await _handle(request, "anthropic")


app = Starlette(
    routes=[
        Route("/v1/chat/completions", chat_completions, methods=["POST"]),
        Route("/v1/messages", messages, methods=["POST"]),
    ]
)
