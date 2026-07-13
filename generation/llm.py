"""Provider-agnostic model client for ChronoGauntlet generation.

Supports Anthropic (Messages API) and any OpenAI-compatible /chat/completions
endpoint (OpenAI, DeepSeek, Together, OpenRouter, ...). Keys are read from the
environment / a repo-root `.env`, matching the sibling papers' convention. Only
the provider(s) you actually run need a key.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Load .env, searching (in order): the repo root (chronogauntlet/), the repo
# root's PARENT (so keys can live in a private workspace OUTSIDE the public repo),
# and cwd. Real environment variables always take precedence (override=False).
try:
    from dotenv import load_dotenv
    _repo_root = Path(__file__).resolve().parent.parent
    for _d in (_repo_root, _repo_root.parent, Path.cwd()):
        _f = _d / ".env"
        if _f.exists():
            load_dotenv(_f, override=False)
except ImportError:
    pass


@dataclass
class ModelSpec:
    name: str            # display name (stable id used in results)
    provider: str        # "anthropic" | "openai_compat"
    model_id: str        # provider-specific model id
    tier: str            # "frontier" | "open"
    api_key_env: str
    base_url: Optional[str] = None       # for openai_compat
    base_url_env: Optional[str] = None   # optional override env var
    # USD per 1M tokens (input, output); None -> cost left as tokens only
    price_in: Optional[float] = None
    price_out: Optional[float] = None
    # provider-specific extras (e.g. disable a hybrid-thinking model's reasoning)
    extra_body: Optional[dict] = None

    def key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env) or None

    def available(self) -> bool:
        return bool(self.key())

    def resolved_base_url(self) -> Optional[str]:
        if self.base_url_env and os.environ.get(self.base_url_env):
            return os.environ[self.base_url_env]
        return self.base_url


@dataclass
class GenResult:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: Optional[float] = None
    error: str = ""


def _cost(spec: ModelSpec, tin: int, tout: int) -> Optional[float]:
    if spec.price_in is None or spec.price_out is None:
        return None
    return tin / 1e6 * spec.price_in + tout / 1e6 * spec.price_out


def generate(spec: ModelSpec, system: str, user: str, *,
             temperature: float = 0.7, max_tokens: int = 1200,
             retries: int = 4) -> GenResult:
    """Call the model once; retry transient errors with exponential backoff."""
    last_err = ""
    for attempt in range(retries):
        try:
            if spec.provider == "anthropic":
                return _gen_anthropic(spec, system, user, temperature, max_tokens)
            elif spec.provider == "openai_compat":
                return _gen_openai(spec, system, user, temperature, max_tokens)
            else:
                return GenResult("", spec.name, 0, 0, 0.0, error=f"unknown provider {spec.provider}")
        except Exception as e:  # noqa: BLE001 - want to retry any transient failure
            last_err = f"{type(e).__name__}: {e}"
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return GenResult("", spec.name, 0, 0, 0.0, error=f"failed after {retries}: {last_err}")


# Per-model discovered API quirks, cached so we pay the 400-discovery cost once.
# token_param: 'max_tokens' or 'max_completion_tokens' (reasoning models need the latter).
# send_temperature: some frontier/reasoning models deprecate or reject temperature.
_QUIRKS: dict = {}


def _adapt_openai(kwargs: dict, msg: str) -> bool:
    """Strip/rename an offending param based on the API error text. True if changed."""
    m = msg.lower()
    if "max_completion_tokens" in m and "max_tokens" in kwargs:
        kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        return True
    if "temperature" in m and "temperature" in kwargs:
        kwargs.pop("temperature")
        return True
    return False


# Per-request wall-clock ceiling (seconds). Generous enough for a full reasoning
# completion at max_tokens, but bounded so a half-open socket can't wedge a worker
# thread indefinitely. SDK-level retries are disabled (max_retries=0) so our own
# generate() backoff loop is the single source of retries, not 4x2 nested.
_HTTP_TIMEOUT = 300.0


def _gen_anthropic(spec, system, user, temperature, max_tokens) -> GenResult:
    from anthropic import Anthropic
    client = Anthropic(api_key=spec.key(), timeout=_HTTP_TIMEOUT, max_retries=0)
    q = _QUIRKS.setdefault(spec.model_id, {})
    kwargs = dict(model=spec.model_id, system=system,
                  messages=[{"role": "user", "content": user}], max_tokens=max_tokens)
    if q.get("send_temperature", True):
        kwargs["temperature"] = temperature
    for _ in range(3):
        try:
            t0 = time.time()
            msg = client.messages.create(**kwargs)
            dt = (time.time() - t0) * 1000
            text = "".join(getattr(b, "text", "") for b in msg.content
                           if getattr(b, "type", "") == "text")
            tin, tout = msg.usage.input_tokens, msg.usage.output_tokens
            return GenResult(text, spec.name, tin, tout, dt, _cost(spec, tin, tout))
        except Exception as e:  # noqa: BLE001
            if "temperature" in str(e).lower() and "temperature" in kwargs:
                kwargs.pop("temperature"); q["send_temperature"] = False
                continue
            raise
    raise RuntimeError("anthropic param adaptation exhausted")


def _gen_openai(spec, system, user, temperature, max_tokens) -> GenResult:
    from openai import OpenAI
    client = OpenAI(api_key=spec.key(), base_url=spec.resolved_base_url(),
                    timeout=_HTTP_TIMEOUT, max_retries=0)
    q = _QUIRKS.setdefault(spec.model_id, {})
    token_param = q.get("token_param", "max_tokens")
    kwargs = {
        "model": spec.model_id,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        token_param: max_tokens,
    }
    if q.get("send_temperature", True):
        kwargs["temperature"] = temperature
    if spec.extra_body:
        kwargs["extra_body"] = spec.extra_body
    for _ in range(4):
        try:
            t0 = time.time()
            resp = client.chat.completions.create(**kwargs)
            dt = (time.time() - t0) * 1000
            text = resp.choices[0].message.content or ""
            u = resp.usage
            tin = getattr(u, "prompt_tokens", 0) or 0
            tout = getattr(u, "completion_tokens", 0) or 0
            return GenResult(text, spec.name, tin, tout, dt, _cost(spec, tin, tout))
        except Exception as e:  # noqa: BLE001
            before = dict(kwargs)
            if _adapt_openai(kwargs, str(e)):
                # remember the fix for subsequent calls to this model
                if "max_completion_tokens" in kwargs and "max_tokens" not in kwargs:
                    q["token_param"] = "max_completion_tokens"
                if "temperature" not in kwargs and "temperature" in before:
                    q["send_temperature"] = False
                continue
            raise
    raise RuntimeError("openai param adaptation exhausted")
