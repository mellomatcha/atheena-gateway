"""Token usage extraction, estimation, and Rupiah cost (FR-3.18 to FR-3.20).

Response text is only ever measured (character counts for estimation), never stored or logged.
"""

import json
import math
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Any

from app.gateway.errors import ApiFormat

# Rough characters-per-token ratio used only when the upstream reports no usage (FR-3.19).
CHARS_PER_TOKEN = 4


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0


@dataclass(frozen=True)
class Prices:
    """Rupiah per 1M tokens, copied into requests.price_snapshot (PRD §4.3.5)."""

    input: Decimal
    output: Decimal
    cache_write: Decimal
    cache_read: Decimal

    def snapshot(self) -> dict[str, str]:
        return {
            "input_per_m": str(self.input),
            "output_per_m": str(self.output),
            "cache_write_per_m": str(self.cache_write),
            "cache_read_per_m": str(self.cache_read),
        }


def compute_cost_idr(usage: Usage, prices: Prices) -> int:
    """FR-3.20: sum of tokens x price per 1M, rounded up to the next whole Rupiah."""
    total = (
        usage.input_tokens * prices.input
        + usage.output_tokens * prices.output
        + usage.cache_write_tokens * prices.cache_write
        + usage.cache_read_tokens * prices.cache_read
    ) / Decimal(1_000_000)
    return int(total.to_integral_value(rounding=ROUND_CEILING))


def estimate_tokens(chars: int) -> int:
    return math.ceil(chars / CHARS_PER_TOKEN) if chars > 0 else 0


def _int(value: Any) -> int:
    return value if isinstance(value, int) and value > 0 else 0


def _text_chars(value: Any) -> int:
    """Total length of every string inside a JSON value (prompt size for estimation)."""
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(_text_chars(item) for item in value)
    if isinstance(value, dict):
        return sum(_text_chars(item) for key, item in value.items() if key != "model")
    return 0


def estimate_input_tokens(body: dict[str, Any]) -> int:
    return estimate_tokens(
        _text_chars(body.get("messages"))
        + _text_chars(body.get("system"))
        + _text_chars(body.get("tools"))
    )


def usage_from_openai(raw: dict[str, Any]) -> Usage:
    """OpenAI `usage`: prompt_tokens includes cached tokens, so they are split out here."""
    details = raw.get("prompt_tokens_details") or {}
    cache_read = _int(details.get("cached_tokens"))
    # Not part of the OpenAI spec, but routers that translate from Anthropic report it.
    cache_write = _int(
        details.get("cache_creation_tokens")
        or details.get("cache_write_tokens")
        or raw.get("cache_creation_input_tokens")
    )
    prompt = _int(raw.get("prompt_tokens"))
    return Usage(
        input_tokens=max(prompt - cache_read - cache_write, 0),
        output_tokens=_int(raw.get("completion_tokens")),
        cache_write_tokens=cache_write,
        cache_read_tokens=cache_read,
    )


def merge_anthropic_usage(usage: Usage, raw: dict[str, Any]) -> None:
    """Anthropic `usage`: input excludes cache tokens; output in message_delta is cumulative."""
    if "input_tokens" in raw:
        usage.input_tokens = max(usage.input_tokens, _int(raw.get("input_tokens")))
    if "cache_creation_input_tokens" in raw:
        usage.cache_write_tokens = max(
            usage.cache_write_tokens, _int(raw.get("cache_creation_input_tokens"))
        )
    if "cache_read_input_tokens" in raw:
        usage.cache_read_tokens = max(
            usage.cache_read_tokens, _int(raw.get("cache_read_input_tokens"))
        )
    if "output_tokens" in raw:
        usage.output_tokens = max(usage.output_tokens, _int(raw.get("output_tokens")))


def _openai_output_chars(choices: Any, key: str) -> int:
    chars = 0
    if not isinstance(choices, list):
        return 0
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        part = choice.get(key) or {}
        if isinstance(part, dict):
            chars += _text_chars(part.get("content")) + _text_chars(part.get("reasoning_content"))
            chars += _text_chars(part.get("tool_calls"))
    return chars


class UsageTracker:
    """Accumulates usage from one upstream response, stream or not, in either format."""

    def __init__(self, api_format: ApiFormat) -> None:
        self.api_format = api_format
        self.usage = Usage()
        self.reported = False
        self.output_chars = 0

    def observe_event(self, data: dict[str, Any]) -> None:
        """One decoded SSE `data:` payload."""
        if self.api_format is ApiFormat.OPENAI:
            self.output_chars += _openai_output_chars(data.get("choices"), "delta")
            raw = data.get("usage")
            if isinstance(raw, dict) and raw:
                self.usage = usage_from_openai(raw)
                self.reported = True
            return
        event_type = data.get("type")
        if event_type == "message_start":
            message = data.get("message") or {}
            raw = message.get("usage") if isinstance(message, dict) else None
            if isinstance(raw, dict):
                merge_anthropic_usage(self.usage, raw)
        elif event_type == "message_delta":
            raw = data.get("usage")
            if isinstance(raw, dict):
                merge_anthropic_usage(self.usage, raw)
                # The final output count arrives here; message_start alone is partial.
                self.reported = True
        elif event_type == "content_block_delta":
            delta = data.get("delta") or {}
            if isinstance(delta, dict):
                for key in ("text", "partial_json", "thinking"):
                    self.output_chars += _text_chars(delta.get(key))

    def observe_body(self, data: dict[str, Any]) -> None:
        """A complete non-stream JSON response."""
        raw = data.get("usage")
        if self.api_format is ApiFormat.OPENAI:
            self.output_chars += _openai_output_chars(data.get("choices"), "message")
            if isinstance(raw, dict) and raw:
                self.usage = usage_from_openai(raw)
                self.reported = True
            return
        self.output_chars += _text_chars(data.get("content"))
        if isinstance(raw, dict) and raw:
            merge_anthropic_usage(self.usage, raw)
            self.reported = True

    def finalize(self, request_body: dict[str, Any]) -> tuple[Usage, bool]:
        """Return (usage, estimated). Missing fields are estimated from text length."""
        if self.reported:
            return self.usage, False
        usage = Usage(**vars(self.usage))
        if usage.input_tokens == 0 and usage.cache_read_tokens == 0:
            usage.input_tokens = estimate_input_tokens(request_body)
        usage.output_tokens = max(usage.output_tokens, estimate_tokens(self.output_chars))
        return usage, True


def parse_json(data: bytes | str) -> dict[str, Any] | None:
    try:
        value = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None
