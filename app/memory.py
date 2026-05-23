from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.utils import utc_now


QUALIFICATION_KEYS = ["business_type", "team_size", "current_tools"]


@dataclass
class ConversationState:
    session_id: str
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    user_messages: list[str] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)
    turn_history: list[dict[str, Any]] = field(default_factory=list)
    qualification_answers: dict[str, str] = field(default_factory=dict)
    asked_questions: list[str] = field(default_factory=list)
    pending_qualification_key: str | None = None
    pending_qualification_question: str | None = None
    escalation_history: list[dict[str, Any]] = field(default_factory=list)
    unanswered_question_count: int = 0
    sop_gaps: list[str] = field(default_factory=list)
    customer_intent: str = "unknown"
    escalated: bool = False
    escalation_reason: str = ""
    last_stage: str = "faq"

    def is_qualification_complete(self) -> bool:
        return all(key in self.qualification_answers for key in QUALIFICATION_KEYS)

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "user_messages": list(self.user_messages),
            "assistant_messages": list(self.assistant_messages),
            "turn_history": list(self.turn_history),
            "qualification_answers": dict(self.qualification_answers),
            "asked_questions": list(self.asked_questions),
            "pending_qualification_key": self.pending_qualification_key,
            "pending_qualification_question": self.pending_qualification_question,
            "escalation_history": list(self.escalation_history),
            "unanswered_question_count": self.unanswered_question_count,
            "sop_gaps": list(self.sop_gaps),
            "customer_intent": self.customer_intent,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
            "last_stage": self.last_stage,
        }


class ConversationMemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ConversationState] = {}

    def get_state(self, session_id: str) -> ConversationState:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationState(session_id=session_id)
        return self._sessions[session_id]

    def record_user_message(self, session_id: str, message: str) -> ConversationState:
        state = self.get_state(session_id)
        state.user_messages.append(message)
        state.turn_history.append({"role": "user", "message": message, "timestamp": utc_now()})
        state.updated_at = utc_now()
        return state

    def record_assistant_message(self, session_id: str, message: str, stage: str) -> ConversationState:
        state = self.get_state(session_id)
        state.assistant_messages.append(message)
        state.turn_history.append({"role": "assistant", "message": message, "stage": stage, "timestamp": utc_now()})
        state.updated_at = utc_now()
        state.last_stage = stage
        return state

    def record_escalation(self, session_id: str, reason: str, message: str) -> ConversationState:
        state = self.get_state(session_id)
        state.escalated = True
        state.escalation_reason = reason
        state.escalation_history.append({"reason": reason, "message": message, "timestamp": utc_now()})
        state.updated_at = utc_now()
        return state

    def record_qualification_answer(self, session_id: str, key: str, answer: str) -> ConversationState:
        state = self.get_state(session_id)
        state.qualification_answers[key] = answer
        if key not in state.asked_questions:
            state.asked_questions.append(key)
        state.pending_qualification_key = None
        state.pending_qualification_question = None
        state.updated_at = utc_now()
        return state

    def increment_unanswered_questions(self, session_id: str) -> ConversationState:
        state = self.get_state(session_id)
        state.unanswered_question_count += 1
        state.updated_at = utc_now()
        return state

    def add_sop_gap(self, session_id: str, gap: str) -> ConversationState:
        state = self.get_state(session_id)
        if gap not in state.sop_gaps:
            state.sop_gaps.append(gap)
        state.updated_at = utc_now()
        return state

    def set_customer_intent(self, session_id: str, intent: str) -> ConversationState:
        state = self.get_state(session_id)
        state.customer_intent = intent
        state.updated_at = utc_now()
        return state

