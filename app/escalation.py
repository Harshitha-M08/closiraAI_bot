from __future__ import annotations

from typing import Any

from app.prompts import ESCALATION_PROMPT
from app.utils import EscalationResult, call_openai_json, contains_any, normalize_text


MEDICAL_KEYWORDS = [
    "medical",
    "side effect",
    "side effects",
    "pain",
    "dosage",
    "dose",
    "aftercare",
    "risk",
    "risks",
    "pregnant",
    "allergic",
    "safety",
    "procedure",
    "treatment plan",
]

FRUSTRATION_KEYWORDS = [
    "angry",
    "frustrated",
    "bad service",
    "complaint",
    "refund",
    "disappointed",
    "upset",
    "terrible",
    "worst",
    "not happy",
    "lawsuit",
]

PRICING_NEGOTIATION_KEYWORDS = [
    "discount",
    "cheaper",
    "lower price",
    "negotiate",
    "best price",
    "reduce",
    "match",
    "deal",
    "special offer",
]

HUMAN_SUPPORT_KEYWORDS = [
    "human agent",
    "human",
    "manager",
    "supervisor",
    "speak to someone",
    "speak to a human",
    "representative",
    "real person",
]

UNANSWERABLE_KEYWORDS = [
    "can you do",
    "do you offer",
    "what is your",
    "tell me about",
    "how much is",
]


def _rule_based_reasons(message: str, unanswered_question_count: int) -> list[str]:
    reasons: list[str] = []
    normalized = normalize_text(message)

    if contains_any(normalized, MEDICAL_KEYWORDS):
        reasons.append("Medical question detected")
    if contains_any(normalized, FRUSTRATION_KEYWORDS):
        reasons.append("Customer frustration or complaint detected")
    if contains_any(normalized, PRICING_NEGOTIATION_KEYWORDS):
        reasons.append("Pricing negotiation detected")
    if contains_any(normalized, HUMAN_SUPPORT_KEYWORDS):
        reasons.append("Explicit human support request detected")
    if unanswered_question_count > 2:
        reasons.append("More than 2 unanswered questions")

    return reasons


def _is_low_confidence(message: str, faq_supported: bool, faq_confidence: float) -> bool:
    if faq_supported:
        return False
    normalized = normalize_text(message)
    if contains_any(normalized, UNANSWERABLE_KEYWORDS):
        return True
    return faq_confidence < 0.65


def detect_escalation(
    message: str,
    state: Any,
    sop: dict[str, Any],
    client: Any | None = None,
    *,
    faq_supported: bool = False,
    faq_confidence: float = 0.0,
) -> EscalationResult:
    rule_reasons = _rule_based_reasons(message, getattr(state, "unanswered_question_count", 0))

    if _is_low_confidence(message, faq_supported, faq_confidence):
        rule_reasons.append("Low confidence information request")

    if rule_reasons:
        return EscalationResult(
            escalate=True,
            reason=rule_reasons[0],
            confidence=0.95,
            matched_triggers=rule_reasons,
            source="rule_based",
        )

    llm_data = call_openai_json(
        client,
        system_prompt=ESCALATION_PROMPT,
        user_prompt=(
            f"Customer message: {message}\n"
            f"Unanswered question count: {getattr(state, 'unanswered_question_count', 0)}\n"
            f"Current qualification answers: {getattr(state, 'qualification_answers', {})}\n"
            f"Known SOP escalation triggers: {sop.get('escalation_triggers', [])}"
        ),
    )

    if llm_data:
        escalate = bool(llm_data.get("escalate", False))
        confidence = float(llm_data.get("confidence", 0.0) or 0.0)
        reason = str(llm_data.get("reason", "")).strip()
        matched_triggers = [str(item) for item in llm_data.get("matched_triggers", []) if isinstance(item, str)]

        if escalate and confidence >= 0.55:
            return EscalationResult(
                escalate=True,
                reason=reason or "Escalation required",
                confidence=confidence,
                matched_triggers=matched_triggers,
                source="llm",
            )

    return EscalationResult(
        escalate=False,
        reason="",
        confidence=0.0,
        matched_triggers=[],
        source="rule_based",
    )

