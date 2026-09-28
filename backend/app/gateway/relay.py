"""Streaming relay between the upstream router and the client (FR-3.12 to FR-3.15).

A producer task reads the upstream response into a queue; `RelayResponse` drains the queue to
the client. Decoupling the two lets the response send heartbeats while the upstream is silent:

- stream: `: ping` SSE comments every interval until the first upstream byte arrives;
- non-stream: after an initial delay, a space before the JSON body every interval (leading
  whitespace keeps the JSON valid).

Until the first byte is sent to the client, upstream errors are returned with a proper HTTP
status. Once a 200 has been committed, errors are delivered in-band in the endpoint format.

Upstream payloads are rewritten on the way through: the upstream model id is replaced with the
public name and in-band upstream errors are replaced with portal errors, so upstream ids and
provider names never reach the client (FR-4.0). Bodies are never logged.
"""

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from app.gateway import errors
from app.gateway.errors import ApiFormat, GatewayError
from app.gateway.usage import UsageTracker, parse_json

logger = logging.getLogger(__name__)

# How much of an upstream error body is read (and discarded) before closing the connection.
ERROR_BODY_DRAIN_LIMIT = 64 * 1024
# Stream slots are refreshed at least this often while a stream is open.
SLOT_REFRESH_INTERVAL_S = 30.0

CLIENT_CLOSED_STATUS = 499
# SSE lines forwarded verbatim when an event has no data payload.
_SSE_PASSTHROUGH_PREFIXES = (b":", b"event:", b"id:", b"retry:")


@dataclass
class UpstreamCall:
    url: str
    headers: dict[str, str]
    body: bytes


@dataclass
class RelayOutcome:
    """What happened, handed to the finish callback that bills and records the request."""

    status_code: int = 200
    error: GatewayError | None = None
    upstream_status: int | None = None
    client_disconnected: bool = False
    ttft_ms: int | None = None
    started: float = field(default_factory=time.perf_counter)

    @property
    def upstream_accepted(self) -> bool:
        return self.upstream_status is not None and self.upstream_status < 400

    @property
    def latency_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)


@dataclass
class HeartbeatConfig:
    stream_interval_s: float
    nonstream_delay_s: float
    nonstream_interval_s: float


def rewrite_payload(obj: dict[str, Any], public_name: str) -> bool:
    """Replace upstream model ids with the public name in place. Returns True if changed."""
    changed = False
    if "model" in obj and obj["model"] != public_name:
        obj["model"] = public_name
        changed = True
    message = obj.get("message")
    if isinstance(message, dict) and "model" in message and message["model"] != public_name:
        message["model"] = public_name
        changed = True
    return changed


def is_inband_error(obj: dict[str, Any], api_format: ApiFormat) -> bool:
    if api_format is ApiFormat.ANTHROPIC:
        return obj.get("type") == "error"
    return "error" in obj and "choices" not in obj


class SseRewriter:
    """Splits an SSE byte stream into events, observes usage, and rewrites model ids."""

    def __init__(self, api_format: ApiFormat, public_name: str, tracker: UsageTracker) -> None:
        self.api_format = api_format
        self.public_name = public_name
        self.tracker = tracker
        self.buffer = b""
        self.inband_error = False

    def feed(self, chunk: bytes) -> bytes:
        self.buffer = (self.buffer + chunk).replace(b"\r\n", b"\n")
        out: list[bytes] = []
        while (end := self.buffer.find(b"\n\n")) != -1:
            block, self.buffer = self.buffer[:end], self.buffer[end + 2 :]
            rendered = self._event(block)
            if rendered:
                out.append(rendered)
        return b"".join(out)

    def flush(self) -> bytes:
        block, self.buffer = self.buffer.strip(b"\n"), b""
        return self._event(block) if block else b""

    def _event(self, block: bytes) -> bytes:
        lines = block.split(b"\n")
        data_lines = [line[5:].lstrip(b" ") for line in lines if line.startswith(b"data:")]
        if not data_lines:
            # Comments and field-only events carry no payload; anything else (for example a raw
            # JSON body where SSE was expected) is not forwarded unchecked.
            if all(line.startswith(_SSE_PASSTHROUGH_PREFIXES) or not line for line in lines):
                return block + b"\n\n"
            return b""
        data = b"\n".join(data_lines)
        if data.strip() == b"[DONE]":
            return block + b"\n\n"
        obj = parse_json(data)
        if obj is None:
            # Undecodable payloads could carry anything; drop rather than forward unchecked.
            return b""
        if is_inband_error(obj, self.api_format):
            self.inband_error = True
            return errors.upstream_failed(502).sse_event(self.api_format)
        self.tracker.observe_event(obj)
        if not rewrite_payload(obj, self.public_name):
            return block + b"\n\n"
        other = [line for line in lines if not line.startswith(b"data:")]
        payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()
        return b"\n".join([*other, b"data: " + payload]) + b"\n\n"


def rewrite_json_body(
    body: bytes, api_format: ApiFormat, public_name: str, tracker: UsageTracker
) -> bytes | None:
    """Rewrite a complete non-stream body. Returns None if it cannot be safely forwarded."""
    obj = parse_json(body)
    if obj is None or is_inband_error(obj, api_format):
        return None
    tracker.observe_body(obj)
    rewrite_payload(obj, public_name)
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()


async def produce(client: httpx.AsyncClient, call: UpstreamCall, queue: asyncio.Queue[Any]) -> None:
    try:
        async with client.stream("POST", call.url, headers=call.headers, content=call.body) as resp:
            await queue.put(("headers", resp.status_code, resp.headers.get("content-type")))
            received = 0
            async for chunk in resp.aiter_bytes():
                received += len(chunk)
                await queue.put(("data", chunk))
                if resp.status_code >= 400 and received > ERROR_BODY_DRAIN_LIMIT:
                    break
        await queue.put(("end",))
    except httpx.TimeoutException:
        await queue.put(("error", errors.upstream_timeout()))
    except httpx.HTTPError as exc:
        # Exception type only: messages can include URLs and upstream details.
        logger.warning("upstream request failed", extra={"exc_type": type(exc).__name__})
        await queue.put(("error", errors.upstream_unreachable()))


async def _listen_for_disconnect(receive: Receive, queue: asyncio.Queue[Any]) -> None:
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            await queue.put(("disconnect",))
            return


class RelayResponse(Response):
    """ASGI response that relays one upstream call with heartbeats and in-band errors."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        call: UpstreamCall,
        api_format: ApiFormat,
        is_stream: bool,
        public_name: str,
        tracker: UsageTracker,
        heartbeat: HeartbeatConfig,
        on_finish: Callable[[RelayOutcome], Awaitable[None]],
        on_alive: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        super().__init__()
        self.client = client
        self.call = call
        self.api_format = api_format
        self.is_stream = is_stream
        self.public_name = public_name
        self.tracker = tracker
        self.heartbeat = heartbeat
        self.on_finish = on_finish
        self.on_alive = on_alive
        self.outcome = RelayOutcome()
        self._committed = False
        self._send: Send | None = None

    @property
    def send(self) -> Send:
        if self._send is None:
            raise RuntimeError("RelayResponse used outside an ASGI call")
        return self._send

    async def _start(self, status: int, content_type: str) -> None:
        headers = [(b"content-type", content_type.encode())]
        if self.is_stream:
            headers += [(b"cache-control", b"no-cache"), (b"x-accel-buffering", b"no")]
        await self.send({"type": "http.response.start", "status": status, "headers": headers})
        self._committed = True

    async def _body(self, data: bytes, more: bool = True) -> None:
        await self.send({"type": "http.response.body", "body": data, "more_body": more})

    def _content_type(self) -> str:
        return "text/event-stream; charset=utf-8" if self.is_stream else "application/json"

    async def _fail(self, error: GatewayError) -> None:
        self.outcome.error = error
        self.outcome.status_code = error.status_code
        if not self._committed:
            body = json.dumps(error.body(self.api_format)).encode()
            headers = [(b"content-type", b"application/json")]
            headers += [(k.lower().encode(), v.encode()) for k, v in error.headers.items()]
            await self.send(
                {"type": "http.response.start", "status": error.status_code, "headers": headers}
            )
            self._committed = True
            await self._body(body, more=False)
        elif self.is_stream:
            await self._body(error.sse_event(self.api_format), more=False)
        else:
            await self._body(json.dumps(error.body(self.api_format)).encode(), more=False)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self._send = send
        queue: asyncio.Queue[Any] = asyncio.Queue()
        producer = asyncio.create_task(produce(self.client, self.call, queue))
        listener = asyncio.create_task(_listen_for_disconnect(receive, queue))
        try:
            await self._relay(queue)
        except OSError:
            # ASGI 2.4 servers raise on send() once the client has gone away.
            self.outcome.client_disconnected = True
        finally:
            for task in (producer, listener):
                task.cancel()
            for task in (producer, listener):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            if self.outcome.client_disconnected:
                self.outcome.status_code = CLIENT_CLOSED_STATUS
            # Billing must complete even if this task is being cancelled by the server.
            await asyncio.shield(self.on_finish(self.outcome))

    async def _relay(self, queue: asyncio.Queue[Any]) -> None:
        loop = asyncio.get_running_loop()
        hb = self.heartbeat
        first_delay = hb.stream_interval_s if self.is_stream else hb.nonstream_delay_s
        interval = hb.stream_interval_s if self.is_stream else hb.nonstream_interval_s
        next_heartbeat = loop.time() + first_delay
        last_alive = loop.time()
        first_byte_seen = False
        upstream_error_status: int | None = None
        rewriter = SseRewriter(self.api_format, self.public_name, self.tracker)
        body_parts: list[bytes] = []

        while True:
            if self.on_alive is not None and loop.time() - last_alive >= SLOT_REFRESH_INTERVAL_S:
                last_alive = loop.time()
                await self.on_alive()
            waiting_for_bytes = not first_byte_seen if self.is_stream else True
            timeout = max(next_heartbeat - loop.time(), 0) if waiting_for_bytes else None
            try:
                event = await asyncio.wait_for(queue.get(), timeout)
            except TimeoutError:
                if not self._committed:
                    await self._start(200, self._content_type())
                await self._body(b": ping\n\n" if self.is_stream else b" ")
                next_heartbeat = loop.time() + interval
                continue

            kind = event[0]
            if kind == "disconnect":
                self.outcome.client_disconnected = True
                return
            if kind == "error":
                await self._fail(event[1])
                return
            if kind == "headers":
                status, content_type = event[1], event[2]
                self.outcome.upstream_status = status
                if status >= 400:
                    upstream_error_status = status
                elif self.is_stream and not self._committed:
                    await self._start(200, content_type or self._content_type())
                continue
            if kind == "data":
                if upstream_error_status is not None:
                    continue  # drain and discard the upstream error body
                if not first_byte_seen:
                    first_byte_seen = True
                    self.outcome.ttft_ms = self.outcome.latency_ms
                if self.is_stream:
                    out = rewriter.feed(event[1])
                    if out:
                        await self._body(out)
                    if rewriter.inband_error:
                        self.outcome.error = errors.upstream_failed(502)
                        self.outcome.status_code = 502
                        await self._body(b"", more=False)
                        return
                else:
                    body_parts.append(event[1])
                continue
            # kind == "end"
            if upstream_error_status is not None:
                await self._fail(errors.upstream_failed(upstream_error_status))
                return
            if self.is_stream:
                tail = rewriter.flush()
                if not self._committed:
                    await self._start(200, self._content_type())
                await self._body(tail, more=False)
                if rewriter.inband_error:
                    self.outcome.error = errors.upstream_failed(502)
                    self.outcome.status_code = 502
                return
            body = rewrite_json_body(
                b"".join(body_parts), self.api_format, self.public_name, self.tracker
            )
            if body is None:
                await self._fail(errors.upstream_failed(502))
                return
            if not self._committed:
                await self._start(200, "application/json")
            await self._body(body, more=False)
            return
