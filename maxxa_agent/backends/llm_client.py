"""
LLM client abstractions and backend implementations.

Backends provided:
- `HFInferenceClient`: Hugging Face Inference API (text generation)
- `OpenAIClient`: OpenAI API (optional dependency)
- `CustomEndpointClient`: generic HTTP JSON endpoint that returns generated text

The Agent depends only on the `LLMClient` interface, not on any provider SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol

import httpx


class LLMClient(Protocol):
    """A minimal interface for an LLM text-generation backend."""

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Generate a completion string for the given prompt."""


class LLMBackendError(RuntimeError):
    """Raised for backend failures (HTTP errors, provider errors, invalid responses)."""


@dataclass(frozen=True, slots=True)
class CustomEndpointClient:
    """
    Generic JSON HTTP endpoint backend.

    The endpoint is expected to accept a POST with JSON:
      { "prompt": "...", "temperature": 0.2, "max_tokens": 123, "stop": ["..."], ... }

    And respond with either:
      { "text": "..." }
    or
      { "output": "..." }
    or OpenAI-style:
      { "choices": [ { "text": "..." } ] }
    """

    endpoint_url: str
    request_timeout_s: float = 30.0
    headers: Optional[Mapping[str, str]] = None

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> str:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if stop is not None:
            payload["stop"] = stop
        if extra:
            payload.update(dict(extra))

        try:
            with httpx.Client(timeout=self.request_timeout_s, headers=self.headers) as client:
                resp = client.post(self.endpoint_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise LLMBackendError(f"Custom endpoint HTTP error: {e}") from e
        except ValueError as e:
            raise LLMBackendError(f"Custom endpoint returned non-JSON: {e}") from e

        if isinstance(data, dict):
            if isinstance(data.get("text"), str):
                return data["text"]
            if isinstance(data.get("output"), str):
                return data["output"]
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict) and isinstance(first.get("text"), str):
                    return first["text"]

        raise LLMBackendError("Custom endpoint response missing generated text.")


@dataclass(frozen=True, slots=True)
class HFInferenceClient:
    """
    Hugging Face Inference API backend.

    This uses the HF Inference API endpoint:
      POST https://api-inference.huggingface.co/models/{model_id}
    """

    model_id: str
    api_token: str
    request_timeout_s: float = 30.0

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> str:
        url = f"https://api-inference.huggingface.co/models/{self.model_id}"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        params: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            params["max_new_tokens"] = max_tokens
        if extra:
            params.update(dict(extra))

        payload: dict[str, Any] = {"inputs": prompt, "parameters": params}

        try:
            with httpx.Client(timeout=self.request_timeout_s, headers=headers) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise LLMBackendError(f"HF Inference HTTP error: {e}") from e
        except ValueError as e:
            raise LLMBackendError(f"HF Inference returned non-JSON: {e}") from e

        # HF can return a list of generated texts, or dict with error.
        if isinstance(data, dict) and isinstance(data.get("error"), str):
            raise LLMBackendError(f"HF Inference error: {data['error']}")
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict) and isinstance(first.get("generated_text"), str):
                text = first["generated_text"]
                # `generated_text` often contains the prompt; attempt to strip prefix.
                if text.startswith(prompt):
                    text = text[len(prompt) :]
                return text

        raise LLMBackendError("HF Inference response missing generated_text.")


@dataclass(frozen=True, slots=True)
class OpenAIClient:
    """
    OpenAI backend (optional dependency).

    Requires `openai` to be installed (see `pyproject.toml` optional deps).
    """

    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    request_timeout_s: float = 30.0

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> str:
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise LLMBackendError(
                "OpenAI backend requires optional dependency. Install with: pip install -e \".[openai]\""
            ) from e

        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.request_timeout_s)

        # Prefer Responses API if available; fall back to chat completions if not.
        kwargs: dict[str, Any] = {}
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        if stop is not None:
            kwargs["stop"] = stop
        if extra:
            kwargs.update(dict(extra))

        try:
            # Newer SDK exposes responses.create
            if hasattr(client, "responses"):
                resp = client.responses.create(
                    model=self.model,
                    input=prompt,
                    temperature=temperature,
                    **kwargs,
                )
                # SDK returns a rich object; try common accessors.
                text = getattr(resp, "output_text", None)
                if isinstance(text, str) and text:
                    return text
                # Fallback: try to stringify
                raise LLMBackendError("OpenAI response missing output_text.")

            # Older style: chat.completions.create
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
                **(dict(extra) if extra else {}),
            )
            if resp.choices and resp.choices[0].message and resp.choices[0].message.content:
                return resp.choices[0].message.content
        except Exception as e:  # noqa: BLE001
            raise LLMBackendError(f"OpenAI backend error: {e}") from e

        raise LLMBackendError("OpenAI response missing generated text.")

