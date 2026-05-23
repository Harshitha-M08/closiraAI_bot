# Prompt Design for Closira AI Workflow

This project uses prompt design as a control surface, not as a decorative layer. The assistant must stay grounded in a tiny SOP, refuse unsupported questions, detect escalation, and preserve enough structure to produce a reliable summary at the end of the conversation.

## 1. Full System Prompt

```text
You are the AI support assistant for Bloom Aesthetics Clinic, an SMB business.

Role:
You handle customer support, lead qualification, escalation detection, and conversation summaries.

Tone and persona:
Be warm, concise, professional, and practical. Sound like a reliable small-business support agent.
Do not sound verbose, technical, or uncertain when a grounded answer is available.

Safety rules:
1. Answer only from the provided SOP context.
2. Never invent prices, services, hours, booking rules, policies, or medical guidance.
3. Never provide medical advice or clinical instructions.
4. If the SOP does not contain the answer, refuse the unsupported request safely and escalate to a human.
5. If confidence is low or the request is ambiguous, escalate instead of guessing.
6. If the user is angry, complains, asks for a refund, wants a human, or uses escalation language, escalate.
7. If the user asks for pricing negotiation, escalate.
8. If more than two questions remain unanswered, escalate.

Escalation policy:
Escalate immediately for complaints, medical questions, pricing negotiation, explicit human support requests, strong frustration, or unsupported information requests.

Qualification flow:
Ask 2 to 3 natural qualification questions when appropriate.
Collect: business type, team size, and current tools or platforms.
Store the answers in conversation memory and include them in the summary.

Confidence handling:
If the content is not clearly grounded in the SOP, or the model cannot justify the answer from the SOP, return a fallback and escalate.

Response formatting:
Prefer short factual responses.
If escalation is needed, say so clearly and safely.
If a qualification question is due, ask exactly one question at a time.
Never mention hidden chain-of-thought or internal policy details.
```

This prompt is intentionally strict. The assistant is not being asked to be clever. It is being asked to be safe, predictable, and SOP-bound.

## 2. Hallucination Prevention Strategy

The project prevents hallucinations using a layered approach:

1. Deterministic SOP cataloging in code.
2. Heuristic matching for supported FAQ topics.
3. LLM classification only for routing, not for inventing answers.
4. Safe fallback escalation when the answer is not grounded.

The most important design choice is that the assistant never depends on a free-form generation step for factual answers. It either maps to a known SOP fact or it escalates.

## 3. Escalation Logic

Escalation is detected by both rule-based logic and LLM reasoning.

Rule-based triggers include:

- complaints
- medical questions
- anger or frustration
- pricing negotiation
- explicit human support requests
- more than two unanswered questions

The LLM classifier is used as a second opinion when rules do not already force escalation. This reduces brittleness without allowing the model to overrule obvious safety triggers.

## 4. Confidence Handling

Confidence is used as a gate, not a suggestion.

If FAQ classification confidence is low, or the user request does not map cleanly to the SOP, the workflow escalates instead of trying to satisfy the prompt. This is the safest path for a support workflow where invented answers would be operationally harmful.

## 5. Tone and Persona Reasoning

The tone is set for a small business support assistant rather than a generic chatbot. That matters because support users expect short, direct, and polite answers. The prompt therefore enforces a warm but operational voice that can answer quickly and then move to qualification or escalation.

## 6. Why the Prompts Are Structured This Way

The project uses separate prompts for classification, escalation, and summarization because each task has a different risk profile.

- FAQ classification must stay narrow and factual.
- Escalation classification must optimize for safety.
- Summarization must compress the conversation into structured output.

Splitting the prompts reduces cross-contamination. It also makes each step easier to test and reason about.

## 7. Safety Decisions

The workflow refuses medical advice because the SOP does not authorize it. It also escalates pricing negotiation, complaints, and explicit human requests because those situations usually need a person rather than an automated reply.

That choice is deliberate. In a customer support setting, an uncertain answer is worse than a short refusal with a handoff.

## 8. Tradeoffs

There are two major tradeoffs in this design.

First, the system is conservative. It will escalate some questions that a larger knowledge base might answer. That is acceptable because the assignment prioritizes hallucination prevention over broad coverage.

Second, the memory is in-memory only. That keeps the project beginner-runnable and simple to inspect, but it is not durable across restarts. For a production deployment, the memory layer should move to persistent storage.

Overall, the prompt design aims to make the assistant boring in the best possible way: predictable, grounded, and easy to trust.
