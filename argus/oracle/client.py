"""Oracle — LLM client with multi-provider support and graceful degradation."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class OracleConfig:
    """Configuration for the Oracle LLM client."""

    provider: str = "anthropic"  # anthropic, openai, google
    model: str = "claude-sonnet-4-20250514"
    api_key: Optional[str] = None
    cache_ttl_seconds: int = 600
    cache_max_entries: int = 256
    timeout_seconds: float = 30.0


@dataclass
class OracleResponse:
    """An Oracle response."""

    text: str
    provider: str
    model: str
    used_cache: bool = False
    degraded: bool = False  # True if fell back to template
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "used_cache": self.used_cache,
            "degraded": self.degraded,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


@dataclass
class _CacheEntry:
    key: str
    response: OracleResponse
    created_at: float


class _ResponseCache:
    """Simple TTL cache for Oracle responses."""

    def __init__(self, ttl_seconds: int, max_entries: int):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, _CacheEntry] = {}

    def _key(self, prompt: str, **kwargs: Any) -> str:
        payload = json.dumps({"prompt": prompt, **kwargs}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, prompt: str, **kwargs: Any) -> Optional[OracleResponse]:
        key = self._key(prompt, **kwargs)
        entry = self._entries.get(key)
        if entry is None:
            return None
        if (time.time() - entry.created_at) > self.ttl_seconds:
            # Expired
            del self._entries[key]
            return None
        # Return a copy with used_cache=True
        cached = OracleResponse(
            text=entry.response.text,
            provider=entry.response.provider,
            model=entry.response.model,
            used_cache=True,
            degraded=entry.response.degraded,
            metadata=entry.response.metadata.copy(),
        )
        return cached

    def set(self, prompt: str, response: OracleResponse, **kwargs: Any) -> None:
        if self.ttl_seconds <= 0:
            return
        key = self._key(prompt, **kwargs)
        self._entries[key] = _CacheEntry(
            key=key, response=response, created_at=time.time()
        )
        # Evict oldest if over max
        if len(self._entries) > self.max_entries:
            oldest_key = min(self._entries, key=lambda k: self._entries[k].created_at)
            del self._entries[oldest_key]

    def clear(self) -> None:
        self._entries.clear()


# ---------------------------------------------------------------------------
# Provider adapters
# ---------------------------------------------------------------------------


def _call_anthropic(prompt: str, model: str, api_key: str, timeout: float) -> str:
    """Call Anthropic API."""
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key, timeout=timeout)
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    except ImportError:
        raise RuntimeError("anthropic package not installed. pip install anthropic")
    except Exception as e:
        raise RuntimeError(f"Anthropic API call failed: {e}") from e


def _call_openai(prompt: str, model: str, api_key: str, timeout: float) -> str:
    """Call OpenAI API."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=timeout)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return resp.choices[0].message.content or ""
    except ImportError:
        raise RuntimeError("openai package not installed. pip install openai")
    except Exception as e:
        raise RuntimeError(f"OpenAI API call failed: {e}") from e


def _call_google(prompt: str, model: str, api_key: str, timeout: float) -> str:
    """Call Google Gemini API."""
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        m = genai.GenerativeModel(model)
        resp = m.generate_content(prompt)
        return resp.text or ""
    except ImportError:
        raise RuntimeError("google-generativeai package not installed. pip install google-generativeai")
    except Exception as e:
        raise RuntimeError(f"Google API call failed: {e}") from e


_PROVIDER_DISPATCH = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "google": _call_google,
}


# ---------------------------------------------------------------------------
# OracleClient
# ---------------------------------------------------------------------------


@dataclass
class OracleClient:
    """Oracle LLM client with provider abstraction and graceful degradation.

    When no API key is set or the API call fails, Oracle falls back to
    static templates and marks the response as degraded=True.
    """

    config: OracleConfig
    cache: _ResponseCache = field(init=False)

    def __post_init__(self) -> None:
        self.cache = _ResponseCache(
            ttl_seconds=self.config.cache_ttl_seconds,
            max_entries=self.config.cache_max_entries,
        )
        # Auto-detect API key from env if not set
        if self.config.api_key is None:
            self.config.api_key = self._detect_api_key()

    def _detect_api_key(self) -> Optional[str]:
        """Look up the API key based on provider from env vars."""
        env_keys = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GEMINI_API_KEY",
        }
        env_var = env_keys.get(self.config.provider, "LLM_API_KEY")
        return os.environ.get(env_var)

    def is_available(self) -> bool:
        """Whether Oracle can make a real LLM call (API key set)."""
        return self.config.api_key is not None and self.config.api_key != ""

    def query(
        self,
        prompt: str,
        *,
        template: str,
        provider: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> OracleResponse:
        """Query the LLM, falling back to the static template when unavailable.

        Args:
            prompt: The user prompt
            template: Static template to use as fallback
            provider: Override the configured provider
            model: Override the configured model
            **kwargs: Extra context passed to cache key (for caching)
        """
        # Check cache first
        cached = self.cache.get(prompt, **kwargs)
        if cached is not None:
            return cached

        provider = provider or self.config.provider
        model = model or self.config.model
        api_key = self.config.api_key

        if not api_key or provider not in _PROVIDER_DISPATCH:
            # Fallback to template
            response = OracleResponse(
                text=template,
                provider=provider,
                model=model,
                used_cache=False,
                degraded=True,
                metadata={"reason": "no_api_key_or_unknown_provider"},
            )
            self.cache.set(prompt, response, **kwargs)
            return response

        try:
            fn = _PROVIDER_DISPATCH[provider]
            text = fn(prompt, model, api_key, self.config.timeout_seconds)
            response = OracleResponse(
                text=text,
                provider=provider,
                model=model,
                used_cache=False,
                degraded=False,
            )
        except Exception as e:
            # API call failed: fall back to template
            response = OracleResponse(
                text=template,
                provider=provider,
                model=model,
                used_cache=False,
                degraded=True,
                metadata={"error": str(e)},
            )

        self.cache.set(prompt, response, **kwargs)
        return response


# ---------------------------------------------------------------------------
# Template fallback helpers
# ---------------------------------------------------------------------------


def template_fallback(
    kind: str,
    data: dict[str, Any],
) -> str:
    """Render a static fallback template based on kind + data."""
    if kind == "archetype_description":
        return (
            f"**{data.get('name', 'Archetype')}** — {data.get('objective', '')}\n\n"
            f"Channel: {data.get('channel', 'unknown')}, "
            f"Rail: {data.get('rail', 'unknown')}.\n\n"
            f"Known mitigations: "
            + ", ".join(data.get("mitigations", []))
        )
    elif kind == "results_narration":
        return (
            f"Experiment summary:\n"
            f"- Policies compared: {data.get('n_policies', 'N/A')}\n"
            f"- Best avg reward: {data.get('best_avg_reward', 'N/A')}\n"
            f"- Significant vs random: "
            f"{data.get('sig_vs_random', 'N/A')}\n\n"
            "See the Ledger artifact for full numbers."
        )
    elif kind == "evidence_chat":
        return (
            f"I can't answer without an active LLM key, but here is what the "
            f"Ledger says about '{data.get('topic', 'this topic')}':\n\n"
            f"{data.get('artifact_excerpt', '(no artifact available)')}\n\n"
            "Set an LLM_API_KEY environment variable for richer answers."
        )
    else:
        return "(Template not available.)"