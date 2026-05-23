from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.escalation import detect_escalation
from app.faq_handler import handle_faq
from app.logger import append_escalation_log, ensure_log_file
from app.memory import ConversationMemoryStore
from app.qualification import build_qualification_result, capture_pending_answer, next_qualification_question
from app.sop_loader import load_sop
from app.summarizer import generate_summary
from app.utils import (
    ChatRequest,
    ChatResponse,
    EscalationLogEntry,
    HealthResponse,
    SummaryRequest,
    create_openai_client,
    utc_now,
)


load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
SOP_PATH = BASE_DIR / "data" / "sop.json"
LOG_PATH = BASE_DIR / "logs" / "escalation_logs.json"

app = FastAPI(title="Closira AI Workflow", version="1.0.0")
memory_store = ConversationMemoryStore()
openai_client = create_openai_client()
sop_data = load_sop(SOP_PATH)
ensure_log_file(LOG_PATH)

FRONTEND_DIR = BASE_DIR / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


def _build_safe_escalation_message(reason: str) -> str:
    if reason:
        return f"I’m not confident about that information, so I’ll escalate this to a human agent. Reason: {reason}."
    return "I’m not confident about that information, so I’ll escalate this to a human agent."


def _finalize_turn(session_id: str, assistant_message: str, stage: str) -> None:
    memory_store.record_assistant_message(session_id, assistant_message, stage)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), openai_ready=openai_client is not None)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    state = memory_store.record_user_message(request.session_id, request.message)

    if state.pending_qualification_key:
        capture_pending_answer(state, request.message)

    faq_result = handle_faq(request.message, sop_data, openai_client)
    escalation_result = detect_escalation(
        request.message,
        state,
        sop_data,
        openai_client,
        faq_supported=faq_result.supported,
        faq_confidence=faq_result.confidence,
    )

    if faq_result.should_escalate and not escalation_result.escalate:
        escalation_result = escalation_result.model_copy(update={
            "escalate": True,
            "reason": faq_result.unsupported_reason or "Question is not grounded in the SOP.",
            "confidence": max(escalation_result.confidence, faq_result.confidence),
            "matched_triggers": escalation_result.matched_triggers or ["Unsupported SOP question"],
            "source": "faq_validation",
        })

    if escalation_result.escalate:
        state = memory_store.record_escalation(request.session_id, escalation_result.reason, request.message)
        memory_store.set_customer_intent(request.session_id, "escalation")
        state = memory_store.get_state(request.session_id)
        memory_store.add_sop_gap(request.session_id, f"Escalated due to: {escalation_result.reason}")

        assistant_message = _build_safe_escalation_message(escalation_result.reason)
        _finalize_turn(request.session_id, assistant_message, "escalation")

        append_escalation_log(
            LOG_PATH,
            EscalationLogEntry(
                timestamp=utc_now(),
                customer_message=request.message,
                escalation_reason=escalation_result.reason,
                conversation_state=state.snapshot(),
            ),
        )

        qualification_result = build_qualification_result(state)
        return ChatResponse(
            session_id=request.session_id,
            stage="escalation",
            response=assistant_message,
            faq=faq_result,
            qualification=qualification_result,
            escalation=escalation_result,
            memory=state.snapshot(),
        )

    response_parts: list[str] = []

    if faq_result.supported and faq_result.answer:
        response_parts.append(faq_result.answer)
        memory_store.set_customer_intent(request.session_id, faq_result.intent)
    else:
        response_parts.append("I’m not confident about that information, so I’ll escalate this to a human agent.")

    qualification_key, qualification_question = next_qualification_question(state)
    qualification_result = build_qualification_result(state)

    if qualification_key and qualification_question and not state.pending_qualification_key and not state.is_qualification_complete():
        state.pending_qualification_key = qualification_key
        state.pending_qualification_question = qualification_question
        if qualification_key not in state.asked_questions:
            state.asked_questions.append(qualification_key)
        response_parts.append(qualification_question)
        qualification_result = build_qualification_result(state)
    elif state.is_qualification_complete():
        qualification_result.completed = True

    assistant_message = " ".join(part.strip() for part in response_parts if part.strip())
    _finalize_turn(request.session_id, assistant_message, "faq")

    return ChatResponse(
        session_id=request.session_id,
        stage="faq",
        response=assistant_message,
        faq=faq_result,
        qualification=qualification_result,
        escalation=escalation_result,
        memory=state.snapshot(),
    )


@app.post("/summary")
def summary(request: SummaryRequest) -> dict[str, Any]:
    state = memory_store.get_state(request.session_id)
    result = generate_summary(state, sop_data, openai_client)
    return {
        "session_id": request.session_id,
        "summary": result.model_dump(),
        "memory": state.snapshot(),
    }
