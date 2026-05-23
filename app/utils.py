from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class EscalationResult(BaseModel):
    escalate: bool = False
    reason: str = ""
    confidence: float = 0.0
    matched_triggers: list[str] = Field(default_factory=list)
    source: str = "rule_based"


class FAQResult(BaseModel):
    supported: bool = False
    answer: str = ""
    intent: str = "unknown"
    confidence: float = 0.0
    matched_topics: list[str] = Field(default_factory=list)
    unsupported_reason: str = ""
    should_escalate: bool = False


class QualificationResult(BaseModel):
    completed: bool = False
    next_question_key: str | None = None
    next_question: str | None = None
    answers: dict[str, str] = Field(default_factory=dict)
    asked_questions: list[str] = Field(default_factory=list)


class SummaryResult(BaseModel):
    customer_intent: str = "unknown"
    key_details_collected: dict[str, str] = Field(default_factory=dict)
    qualification_data: dict[str, str] = Field(default_factory=dict)
    escalation_status: bool = False
    escalation_reason: str = ""
    sop_gaps_identified: list[str] = Field(default_factory=list)
    recommended_next_action: str = ""


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class SummaryRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    session_id: str
    stage: str
    response: str
    faq: FAQResult
    qualification: QualificationResult
    escalation: EscalationResult
    memory: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    model: str
    openai_ready: bool


class EscalationLogEntry(BaseModel):
    timestamp: str
    customer_message: str
    escalation_reason: str
    conversation_state: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def contains_any(text: str, keywords: list[str]) -> list[str]:
    normalized = normalize_text(text)
    matches: list[str] = []
    for keyword in keywords:
        if keyword in normalized:
            matches.append(keyword)
    return matches


def deduplicate_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def safe_json_loads(payload: str | None) -> dict[str, Any] | None:
    if payload is None:
        return None

    cleaned = payload.strip()
    if not cleaned:
        return None

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None


def create_openai_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def call_openai_json(
    client: OpenAI | None,
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
    max_attempts: int = 3,
) -> dict[str, Any] | None:
    if client is None:
        return None

    chosen_model = model or DEFAULT_MODEL
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(
                model=chosen_model,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content or ""
            parsed = safe_json_loads(content)
            if parsed is None:
                raise ValueError("OpenAI response was not valid JSON")
            return parsed
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < max_attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))

    if last_error is not None:
        # If the error is an authentication/invalid API key error, don't raise -
        # treat as OpenAI unavailable and return None so callers can fall back
        # to deterministic SOP behavior. For other errors, re-raise.
        msg = str(last_error).lower()
        if "invalid_api_key" in msg or "authenticationerror" in type(last_error).__name__.lower():
            return None
        raise last_error
    return None


def shorten_text(text: str, max_length: int = 160) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 3].rstrip() + "..."

