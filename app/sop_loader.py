from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_sop(path: str | Path) -> dict[str, Any]:
    sop_path = Path(path)
    if not sop_path.exists():
        raise FileNotFoundError(f"SOP file not found: {sop_path}")

    with sop_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    required_keys = ["business_name", "hours", "services", "booking", "escalation_triggers"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"SOP file is missing required key: {key}")

    return data


def build_faq_catalog(sop: dict[str, Any]) -> dict[str, dict[str, Any]]:
    services = sop.get("services", [])
    service_lookup = {service["name"].lower(): service for service in services}

    botox = service_lookup.get("botox", {})
    fillers = service_lookup.get("fillers", {})
    consultations = service_lookup.get("consultations", {})

    return {
        "business_hours": {
            "keywords": ["hours", "open", "opening", "closing", "available", "business hours"],
            "answer": f'{sop["business_name"]} is open {sop["hours"]}.',
        },
        "botox": {
            "keywords": ["botox", "tox", "injection"],
            "answer": f'Botox treatments start from {botox.get("price_from", "£200")}.',
        },
        "fillers": {
            "keywords": ["filler", "fillers", "dermal fillers"],
            "answer": f'Fillers start from {fillers.get("price_from", "£250")}.',
        },
        "consultations": {
            "keywords": ["consultation", "consultations", "consult"],
            "answer": f'Consultations are {consultations.get("price", "free")}.',
        },
        "booking": {
            "keywords": ["book", "booking", "appointment", "whatsapp", "website"],
            "answer": f'Bookings are available via {" or ".join(sop["booking"].get("channels", ["WhatsApp", "the website"]))}.',
        },
        "cancellation": {
            "keywords": ["cancel", "cancellation", "cancelation", "reschedule"],
            "answer": f'{sop["booking"].get("cancellation_notice", "24hr cancellation required").rstrip(".")}.',
        },
    }

