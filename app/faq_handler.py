from __future__ import annotations

from typing import Any

from app.prompts import FAQ_CLASSIFIER_PROMPT
from app.sop_loader import build_faq_catalog
from app.utils import FAQResult, call_openai_json, contains_any, deduplicate_preserve_order, normalize_text


def _heuristic_topic_matches(message: str, catalog: dict[str, dict[str, Any]]) -> list[str]:
    normalized = normalize_text(message)
    matches: list[str] = []

    for topic, details in catalog.items():
        keywords = details.get("keywords", [])
        topic_matches = contains_any(normalized, keywords)
        if topic_matches:
            matches.append(topic)

    return deduplicate_preserve_order(matches)


def _compose_answer(topics: list[str], catalog: dict[str, dict[str, Any]]) -> str:
    ordered_topics = deduplicate_preserve_order(topics)
    answers = [catalog[topic]["answer"] for topic in ordered_topics if topic in catalog]
    return " ".join(answers)


def _normalize_llm_topics(raw_topics: Any, catalog: dict[str, dict[str, Any]]) -> list[str]:
    if not isinstance(raw_topics, list):
        return []

    allowed = set(catalog.keys())
    normalized: list[str] = []
    for item in raw_topics:
        if isinstance(item, str) and item in allowed:
            normalized.append(item)
    return deduplicate_preserve_order(normalized)


def handle_faq(message: str, sop: dict[str, Any], client: Any | None = None) -> FAQResult:
    catalog = build_faq_catalog(sop)
    heuristic_topics = _heuristic_topic_matches(message, catalog)

    if heuristic_topics:
        return FAQResult(
            supported=True,
            answer=_compose_answer(heuristic_topics, catalog),
            intent="faq_answer",
            confidence=0.92,
            matched_topics=heuristic_topics,
        )

    llm_data = call_openai_json(
        client,
        system_prompt=FAQ_CLASSIFIER_PROMPT,
        user_prompt=f"SOP catalog topics: {list(catalog.keys())}\n\nCustomer message: {message}",
    )

    if llm_data:
        supported = bool(llm_data.get("supported", False))
        confidence = float(llm_data.get("confidence", 0.0) or 0.0)
        topics = _normalize_llm_topics(llm_data.get("topics", []), catalog)

        if supported and topics and confidence >= 0.65:
            return FAQResult(
                supported=True,
                answer=_compose_answer(topics, catalog),
                intent="faq_answer",
                confidence=confidence,
                matched_topics=topics,
            )

        reason = str(llm_data.get("reason", "Question is not grounded in the SOP.")).strip()
        return FAQResult(
            supported=False,
            answer="",
            intent="unsupported",
            confidence=confidence,
            unsupported_reason=reason,
            should_escalate=True,
        )

    return FAQResult(
        supported=False,
        answer="",
        intent="unsupported",
        confidence=0.0,
        unsupported_reason="Question is not grounded in the SOP.",
        should_escalate=True,
    )

