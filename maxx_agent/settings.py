"""
Environment-based settings for MaxxAgentFramework.

Read configuration from process environment (optionally loaded from a `.env` file
via `python-dotenv`). Copy `.env.example` to `.env` and customize — no need to
hardcode URLs or API keys in application code.

Example::

    from maxx_agent.settings import load_env_file, llm_endpoint_url

    load_env_file()  # optional, if python-dotenv is installed
    url = llm_endpoint_url()
"""

from __future__ import annotations

import os
from collections.abc import Mapping


def load_env_file(path: str = ".env") -> bool:
    """
    Load a `.env` file into ``os.environ`` if ``python-dotenv`` is installed.

    Returns:
        True if dotenv loaded the file, False if dotenv is missing or file absent.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    return bool(load_dotenv(path))


def _env_str(key: str, default: str) -> str:
    val = os.environ.get(key)
    return val if val is not None and val.strip() != "" else default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def llm_endpoint_url() -> str:
    """Custom / Maxx HTTP generation endpoint."""
    return _env_str("MAXX_LLM_ENDPOINT_URL", "http://localhost:8080/generate")


def llm_request_timeout_s() -> float:
    return _env_float("MAXX_LLM_REQUEST_TIMEOUT_S", 60.0)


def llm_api_key() -> str | None:
    key = os.environ.get("MAXX_LLM_API_KEY")
    return key if key and key.strip() else None


def llm_auth_headers() -> Mapping[str, str] | None:
    key = llm_api_key()
    if not key:
        return None
    return {"Authorization": f"Bearer {key}"}


def workspace_root() -> str:
    return _env_str("MAXX_WORKSPACE_ROOT", ".")


def allow_dangerous_tools() -> bool:
    return _env_bool("MAXX_ALLOW_DANGEROUS_TOOLS", False)


def enable_code_execution() -> bool:
    return _env_bool("MAXX_ENABLE_CODE_EXECUTION", False)


def web_search_endpoint_url() -> str | None:
    url = os.environ.get("MAXX_WEB_SEARCH_ENDPOINT_URL")
    return url if url and url.strip() else None


def agent_max_steps() -> int:
    return _env_int("MAXX_MAX_STEPS", 10)


def agent_temperature() -> float:
    return _env_float("MAXX_TEMPERATURE", 0.2)


def memory_window_size() -> int:
    return _env_int("MAXX_MEMORY_WINDOW_SIZE", 5)
