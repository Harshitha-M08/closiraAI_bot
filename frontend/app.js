const API_BASE = "";

const elements = {
  sessionId: document.getElementById("sessionId"),
  newSessionBtn: document.getElementById("newSessionBtn"),
  healthBtn: document.getElementById("healthBtn"),
  summaryBtn: document.getElementById("summaryBtn"),
  sendBtn: document.getElementById("sendBtn"),
  messageInput: document.getElementById("messageInput"),
  chatLog: document.getElementById("chatLog"),
  currentSessionLabel: document.getElementById("currentSessionLabel"),
  summaryOutput: document.getElementById("summaryOutput"),
  stateOutput: document.getElementById("stateOutput"),
  healthStatus: document.getElementById("healthStatus"),
  healthCopy: document.getElementById("healthCopy"),
  faqMetric: document.getElementById("faqMetric"),
  escalationMetric: document.getElementById("escalationMetric"),
  qualificationMetric: document.getElementById("qualificationMetric"),
};

const storeKey = "closira-session-id";
const conversationKeyPrefix = "closira-conversation-";

function randomSessionId() {
  return `demo-${Math.random().toString(16).slice(2, 8)}`;
}

function getSessionId() {
  return elements.sessionId.value.trim() || localStorage.getItem(storeKey) || randomSessionId();
}

function setSessionId(sessionId) {
  elements.sessionId.value = sessionId;
  elements.currentSessionLabel.textContent = `Session: ${sessionId}`;
  localStorage.setItem(storeKey, sessionId);
}

function loadConversation(sessionId) {
  const raw = localStorage.getItem(conversationKeyPrefix + sessionId);
  return raw ? JSON.parse(raw) : [];
}

function saveConversation(sessionId, conversation) {
  localStorage.setItem(conversationKeyPrefix + sessionId, JSON.stringify(conversation));
}

function renderConversation() {
  const conversation = loadConversation(getSessionId());
  elements.chatLog.innerHTML = "";

  if (!conversation.length) {
    elements.chatLog.innerHTML = `
      <div class="message assistant">
        <div class="message-meta"><span>Assistant</span><span>Ready</span></div>
        <div class="message-text">Ask about a service, trigger a complaint, or continue the qualification flow.</div>
      </div>
    `;
    return;
  }

  for (const item of conversation) {
    const node = document.createElement("div");
    node.className = `message ${item.role}`;
    const displayTags = (item.tags || []).filter(t => t && t !== item.stage);
    node.innerHTML = `
      <div class="message-meta">
        <span>${item.role === "user" ? "Customer" : "Assistant"}</span>
        <span>${item.stage || "message"}</span>
      </div>
      <div class="message-text"></div>
      <div class="message-tags">
        ${displayTags.map(tag => `<span class="tag ${tag}">${tag}</span>`).join("")}
      </div>
    `;
    node.querySelector(".message-text").textContent = item.text;
    elements.chatLog.appendChild(node);
  }
}

function uniqueTags(tags) {
  return [...new Set(tags.filter(Boolean))];
}

function appendConversationEntry(entry) {
  const sessionId = getSessionId();
  const conversation = loadConversation(sessionId);
  conversation.push(entry);
  saveConversation(sessionId, conversation);
  renderConversation();
}

function setTyping(show) {
  const existing = document.getElementById("typingRow");
  if (show) {
    if (existing) return;
    const node = document.createElement("div");
    node.id = "typingRow";
    node.className = "message assistant";
    node.innerHTML = `
      <div class="message-meta"><span>Assistant</span><span>Typing</span></div>
      <div class="assistant-typing"><span></span><span></span><span></span></div>
    `;
    elements.chatLog.appendChild(node);
    elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
    return;
  }
  if (existing) existing.remove();
}

function updateMetrics(response) {
  const faqCount = response?.faq?.supported ? 1 : 0;
  const escalationCount = response?.escalation?.escalate ? 1 : 0;
  const qualificationAnswers = Object.keys(response?.qualification?.answers || {}).length;
  const asked = Math.max(1, response?.qualification?.asked_questions?.length || 0);

  elements.faqMetric.textContent = faqCount.toString();
  elements.escalationMetric.textContent = escalationCount.toString();
  elements.qualificationMetric.textContent = `${Math.round((qualificationAnswers / asked) * 100)}%`;
}

async function postJson(path, payload) {
  const response = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

async function sendMessage(message) {
  const sessionId = getSessionId();
  setSessionId(sessionId);
  appendConversationEntry({ role: "user", text: message, stage: "message", tags: [] });
  setTyping(true);

  try {
    const payload = await postJson("/chat", { session_id: sessionId, message });
    setTyping(false);

    appendConversationEntry({
      role: "assistant",
      text: payload.response,
      stage: payload.stage,
      tags: uniqueTags([payload.stage, payload.escalation?.escalate ? "escalation" : "faq"]),
    });

    elements.stateOutput.textContent = JSON.stringify(payload.memory, null, 2);
    updateMetrics(payload);
    await refreshSummary();
  } catch (error) {
    setTyping(false);
    appendConversationEntry({
      role: "assistant",
      text: `Request failed: ${error.message}`,
      stage: "error",
      tags: ["escalation"],
    });
    elements.healthStatus.textContent = "API error";
    elements.healthCopy.textContent = error.message;
  }
}

async function refreshSummary() {
  const sessionId = getSessionId();
  const payload = await postJson("/summary", { session_id: sessionId });
  elements.summaryOutput.textContent = JSON.stringify(payload.summary, null, 2);
  elements.stateOutput.textContent = JSON.stringify(payload.memory, null, 2);
}

async function checkHealth() {
  try {
    const response = await fetch("/health");
    const payload = await response.json();
    elements.healthStatus.textContent = payload.openai_ready ? "API ready" : "SOP mode";
    elements.healthCopy.textContent = `${payload.status} • model ${payload.model}`;
  } catch (error) {
    elements.healthStatus.textContent = "Offline";
    elements.healthCopy.textContent = error.message;
  }
}

function bootstrap() {
  const savedSession = localStorage.getItem(storeKey) || randomSessionId();
  setSessionId(savedSession);
  renderConversation();
  checkHealth();

  elements.newSessionBtn.addEventListener("click", () => {
    const sessionId = randomSessionId();
    setSessionId(sessionId);
    saveConversation(sessionId, []);
    renderConversation();
    elements.summaryOutput.textContent = "New session ready.";
    elements.stateOutput.textContent = "No session activity yet.";
  });

  elements.healthBtn.addEventListener("click", checkHealth);
  elements.summaryBtn.addEventListener("click", () => refreshSummary().catch(error => {
    elements.summaryOutput.textContent = error.message;
  }));
  elements.sendBtn.addEventListener("click", () => {
    const text = elements.messageInput.value.trim();
    if (!text) return;
    elements.messageInput.value = "";
    sendMessage(text);
  });

  elements.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.sendBtn.click();
    }
  });

  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      elements.messageInput.value = button.getAttribute("data-prompt") || "";
      elements.messageInput.focus();
    });
  });
}

bootstrap();