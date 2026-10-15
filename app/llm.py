"""Provider-agnostic explainer client (ticket: privacy and hardening).

Local-default posture: the template backend never sends anything
off-machine. HTTP backends (Ollama-style OpenAI-compatible endpoints)
require explicit per-request consent; without it they refuse instead of
calling out. Every call reports a data-flow description for the log.
"""

from __future__ import annotations

import json
import os
import urllib.request

from .advice import deterministic_explain
from .engine import PlanResult

LOCAL_BACKEND = "template-local"
HTTP_BACKENDS = ("ollama",)
KNOWN_BACKENDS = (LOCAL_BACKEND, *HTTP_BACKENDS)

AGGREGATE_FIELDS = (
    "available_cents",
    "total_expenses_cents",
    "leftover_cents",
    "savings_target_cents",
    "needs_total_cents",
    "wants_total_cents",
    "warning_rule_ids",
    "currency",
)


def default_backend() -> str:
    return os.environ.get("LLM_BACKEND", LOCAL_BACKEND)


def base_url() -> str:
    return os.environ.get("LLM_BASE_URL", "http://localhost:11434")


def generate(
    backend: str,
    prompt: str,
    plan: PlanResult,
    currency: str,
    *,
    allow_cloud: bool = False,
    timeout_s: float = 10.0,
) -> tuple[list[str], str]:
    """Return (suggestion lines, data-flow description)."""
    if backend not in KNOWN_BACKENDS:
        raise ValueError(f"unknown backend: {backend!r}")
    if backend == LOCAL_BACKEND:
        return (
            deterministic_explain(plan, currency),
            "No fields left this machine (local template backend).",
        )
    if not allow_cloud:
        raise PermissionError(
            f"backend {backend!r} needs explicit per-request consent"
        )
    body = json.dumps(
        {
            "model": os.environ.get("LLM_MODEL", "qwen2.5:3b"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
    ).encode()
    request = urllib.request.Request(
        base_url().rstrip("/") + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode())
    except OSError as exc:
        raise ConnectionError(f"backend {backend!r} unreachable: {exc}") from exc
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"backend {backend!r} bad response shape") from exc
    return (
        [line.strip("- ") for line in text.splitlines() if line.strip()],
        f"Sent to {base_url()}: {', '.join(AGGREGATE_FIELDS)}.",
    )
