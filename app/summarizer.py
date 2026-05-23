from __future__ import annotations

from typing import Any

from app.prompts import SUMMARY_PROMPT
from app.utils import SummaryResult, call_openai_json, deduplicate_preserve_order


def _build_deterministic_summary(state: Any) -> SummaryResult:
    key_details = {
        "user_messages": str(len(getattr(state, "user_messages", []))),
        "assistant_messages": str(len(getattr(state, "assistant_messages", []))),
        "last_stage": str(getattr(state, "last_stage", "unknown")),
    }

    qualification_data = dict(getattr(state, "qualification_answers", {}))
    sop_gaps = deduplicate_preserve_order(list(getattr(state, "sop_gaps", [])))
    escalation_status = bool(getattr(state, "escalated", False))
    escalation_reason = str(getattr(state, "escalation_reason", ""))

    if escalation_status:
        recommended_action = "Hand off to a human agent using the logged escalation reason."
    elif len(qualification_data) < 3:
        recommended_action = "Continue the qualification flow and collect the remaining answers."
    else:
        recommended_action = "Proceed with normal follow-up using the collected qualification details."

    return SummaryResult(
        customer_intent=str(getattr(state, "customer_intent", "unknown")),
        key_details_collected=key_details,
        qualification_data=qualification_data,
        escalation_status=escalation_status,
        escalation_reason=escalation_reason,
        sop_gaps_identified=sop_gaps,
        recommended_next_action=recommended_action,
    )


def generate_summary(state: Any, sop: dict[str, Any], client: Any | None = None) -> SummaryResult:
    deterministic = _build_deterministic_summary(state)

    llm_data = call_openai_json(
        client,
        system_prompt=SUMMARY_PROMPT,
        user_prompt=(
            f"Conversation state: {getattr(state, 'snapshot', lambda: {})()}\n"
            f"SOP business name: {sop.get('business_name')}\n"
            f"SOP hours: {sop.get('hours')}\n"
            f"SOP services: {sop.get('services')}\n"
            f"SOP booking: {sop.get('booking')}\n"
            f"SOP gaps already detected: {getattr(state, 'sop_gaps', [])}"
        ),
        temperature=0.0,
    )

    if not llm_data:
        return deterministic

    try:
        parsed = SummaryResult.model_validate(llm_data)
    except Exception:  # noqa: BLE001
        return deterministic

    if not parsed.recommended_next_action:
        parsed.recommended_next_action = deterministic.recommended_next_action
    if not parsed.sop_gaps_identified:
        parsed.sop_gaps_identified = deterministic.sop_gaps_identified
    if not parsed.customer_intent:
        parsed.customer_intent = deterministic.customer_intent
    if not parsed.key_details_collected:
        parsed.key_details_collected = deterministic.key_details_collected
    if not parsed.qualification_data:
        parsed.qualification_data = deterministic.qualification_data
    if not parsed.escalation_reason:
        parsed.escalation_reason = deterministic.escalation_reason

    return parsed

