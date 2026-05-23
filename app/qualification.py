from __future__ import annotations

import re

from app.memory import ConversationState
from app.utils import QualificationResult, normalize_text, shorten_text


QUALIFICATION_FLOW = [
    {
        "key": "business_type",
        "question": "To help route this properly, what type of business do you run?",
    },
    {
        "key": "team_size",
        "question": "How large is your team right now?",
    },
    {
        "key": "current_tools",
        "question": "Which tools or platforms are you currently using?",
    },
]


def normalize_answer(question_key: str, message: str) -> str:
    cleaned = re.sub(r"\s+", " ", message.strip())
    cleaned = cleaned.rstrip(".")

    if question_key == "team_size":
        digit_match = re.search(r"\b\d+\b", cleaned)
        if digit_match:
            return digit_match.group(0)
        if any(token in normalize_text(cleaned) for token in ["solo", "one", "single"]):
            return "1"

    if question_key == "current_tools":
        parts = [part.strip() for part in re.split(r",| and | / |;", cleaned) if part.strip()]
        if parts:
            return ", ".join(parts[:4])

    if question_key == "business_type":
        lowered = normalize_text(cleaned)
        for prefix in ["we are ", "we run ", "i run ", "i work in ", "our business is "]:
            if prefix in lowered:
                index = lowered.find(prefix)
                return shorten_text(cleaned[index + len(prefix) :])

    return shorten_text(cleaned)


def capture_pending_answer(state: ConversationState, user_message: str) -> tuple[str | None, str | None]:
    if not state.pending_qualification_key:
        return None, None

    key = state.pending_qualification_key
    answer = normalize_answer(key, user_message)
    state.qualification_answers[key] = answer
    if key not in state.asked_questions:
        state.asked_questions.append(key)
    state.pending_qualification_key = None
    state.pending_qualification_question = None
    return key, answer


def next_qualification_question(state: ConversationState) -> tuple[str | None, str | None]:
    for item in QUALIFICATION_FLOW:
        if item["key"] not in state.qualification_answers:
            return item["key"], item["question"]
    return None, None


def build_qualification_result(state: ConversationState) -> QualificationResult:
    next_key, next_question = next_qualification_question(state)
    return QualificationResult(
        completed=next_key is None,
        next_question_key=next_key,
        next_question=next_question,
        answers=dict(state.qualification_answers),
        asked_questions=list(state.asked_questions),
    )

