const elements = {
  chatError: document.querySelector("#chat-error"),
  chatForm: document.querySelector("#chat-form"),
  conversationList: document.querySelector("#conversation-list"),
  conversationId: document.querySelector("#conversation-id"),
  copyIdButton: document.querySelector("#copy-id-button"),
  dropZone: document.querySelector("#drop-zone"),
  fileInput: document.querySelector("#file-input"),
  historyEmpty: document.querySelector("#history-empty"),
  liveStatus: document.querySelector("#live-status"),
  messageInput: document.querySelector("#message-input"),
  messages: document.querySelector("#messages"),
  newWorkspaceButton: document.querySelector("#new-workspace-button"),
  sendButton: document.querySelector("#send-button"),
  sourceCount: document.querySelector("#source-count"),
  sourceList: document.querySelector("#source-list"),
  sourcesEmpty: document.querySelector("#sources-empty"),
  suggestions: document.querySelector("#suggestions"),
  uploadList: document.querySelector("#upload-list"),
  welcome: document.querySelector("#welcome"),
  workspaceState: document.querySelector("#workspace-state"),
};

const state = {
  conversationId: crypto.randomUUID(),
  conversations: [],
  documents: [],
  messages: [],
  busy: false,
  uploading: false,
};

// Earlier versions restored the most recently opened workspace. The application
// now intentionally starts with a fresh chat while keeping saved chats server-side.
localStorage.removeItem("apex-policy-assistant-conversation");

function announce(message) {
  elements.liveStatus.textContent = "";
  window.setTimeout(() => {
    elements.liveStatus.textContent = message;
  }, 20);
}

function safeDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Indexed"
    : `Indexed ${date.toLocaleDateString(undefined, { day: "numeric", month: "short" })}`;
}

function parseError(payload, fallback) {
  if (typeof payload?.detail === "string") {
    return payload.detail;
  }
  if (Array.isArray(payload?.detail) && payload.detail[0]?.msg) {
    return payload.detail[0].msg;
  }
  return fallback;
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

function setConversationId(conversationId) {
  state.conversationId = conversationId;
  elements.conversationId.textContent = conversationId;
  elements.conversationId.title = conversationId;
}

function safeActivityDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Saved chat";
  return `Updated ${date.toLocaleDateString(undefined, { day: "numeric", month: "short" })}`;
}

function renderConversationHistory() {
  elements.conversationList.replaceChildren();
  elements.historyEmpty.hidden = state.conversations.length > 0;

  state.conversations.forEach((conversation) => {
    const item = document.createElement("li");
    item.className = "conversation-item";
    item.classList.toggle("is-active", conversation.conversation_id === state.conversationId);

    const openButton = document.createElement("button");
    openButton.className = "conversation-open";
    openButton.type = "button";
    openButton.dataset.conversationId = conversation.conversation_id;
    const title = document.createElement("strong");
    title.textContent = conversation.title;
    title.title = conversation.title;
    const details = document.createElement("small");
    details.textContent = `${safeActivityDate(conversation.updated_at)} · ${conversation.document_count} source${conversation.document_count === 1 ? "" : "s"}`;
    openButton.append(title, details);

    const deleteButton = document.createElement("button");
    deleteButton.className = "icon-button conversation-delete";
    deleteButton.type = "button";
    deleteButton.dataset.deleteConversationId = conversation.conversation_id;
    deleteButton.dataset.conversationTitle = conversation.title;
    deleteButton.setAttribute("aria-label", `Delete ${conversation.title}`);
    deleteButton.title = "Delete chat";
    deleteButton.textContent = "×";

    item.append(openButton, deleteButton);
    elements.conversationList.append(item);
  });
}

async function refreshConversationHistory() {
  try {
    const response = await fetch("/conversations");
    const payload = await readJson(response);
    if (!response.ok) {
      throw new Error(parseError(payload, "Saved chats could not be loaded."));
    }
    state.conversations = payload.conversations;
    renderConversationHistory();
  } catch {
    announce("Saved chats could not be refreshed.");
  }
}

function setControls() {
  const hasDocuments = state.documents.length > 0;
  const canSend = hasDocuments && !state.busy && elements.messageInput.value.trim().length > 0;
  elements.messageInput.disabled = !hasDocuments || state.busy;
  elements.sendButton.disabled = !canSend;
  elements.messageInput.placeholder = hasDocuments
    ? "Ask a question about your uploaded policies"
    : "Upload a policy to start asking questions";
  elements.workspaceState.textContent = hasDocuments
    ? `${state.documents.length} source${state.documents.length === 1 ? "" : "s"} ready`
    : "Add a source to begin";
  elements.workspaceState.classList.toggle("is-ready", hasDocuments);
  elements.suggestions.querySelectorAll("button").forEach((button) => {
    button.disabled = !hasDocuments || state.busy;
  });
}

function renderSources() {
  elements.sourceList.replaceChildren();
  elements.sourceCount.textContent = String(state.documents.length);
  elements.sourceCount.setAttribute(
    "aria-label",
    `${state.documents.length} indexed source${state.documents.length === 1 ? "" : "s"}`,
  );
  elements.sourcesEmpty.hidden = state.documents.length > 0;

  state.documents.forEach((source) => {
    const item = document.createElement("li");
    item.className = "source-item";

    const icon = document.createElement("span");
    icon.className = "file-icon";
    icon.textContent = "PDF";
    icon.setAttribute("aria-hidden", "true");

    const copy = document.createElement("span");
    copy.className = "source-copy";
    const name = document.createElement("strong");
    name.textContent = source.filename;
    name.title = source.filename;
    const details = document.createElement("small");
    details.textContent = `${safeDate(source.uploaded_at)} · ${source.chunks_indexed} chunks`;
    copy.append(name, details);

    const check = document.createElement("span");
    check.className = "source-check";
    check.textContent = "✓";
    check.setAttribute("aria-label", "Indexed");
    item.append(icon, copy, check);
    elements.sourceList.append(item);
  });
  setControls();
}

function createCitation(citation) {
  const item = document.createElement("span");
  item.className = "citation";
  const number = document.createElement("span");
  number.className = "citation-number";
  number.textContent = String(citation.id);
  const label = document.createElement("span");
  label.textContent = `${citation.filename} · page ${citation.page}`;
  item.append(number, label);
  return item;
}

function createMessage(message, options = {}) {
  const wrapper = document.createElement("article");
  wrapper.className = `message message-${message.role}`;

  if (message.role === "user") {
    const body = document.createElement("div");
    body.className = "message-body";
    body.textContent = message.content;
    wrapper.append(body);
    return wrapper;
  }

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = "A";
  avatar.setAttribute("aria-hidden", "true");

  const content = document.createElement("div");
  content.className = "message-content";
  const label = document.createElement("div");
  label.className = "message-label";
  label.append(document.createTextNode("Apex Assistant"));

  if (options.status && options.status !== "answered") {
    const status = document.createElement("span");
    status.className = `answer-status ${options.status}`;
    status.textContent = options.status === "conflicting_sources" ? "Policy conflict" : "Not found";
    label.append(status);
  }

  const text = document.createElement("div");
  text.className = "message-text";
  text.textContent = message.content;
  content.append(label, text);

  if (message.citations?.length) {
    const citations = document.createElement("div");
    citations.className = "citations";
    citations.setAttribute("aria-label", "Sources");
    message.citations.forEach((citation) => citations.append(createCitation(citation)));
    content.append(citations);
  }

  wrapper.append(avatar, content);
  return wrapper;
}

function renderMessages() {
  elements.messages.querySelectorAll(".message").forEach((message) => message.remove());
  elements.welcome.hidden = state.messages.length > 0;
  state.messages.forEach((message) => elements.messages.append(createMessage(message, { status: message.status })));
  scrollToLatest();
}

function scrollToLatest() {
  window.requestAnimationFrame(() => {
    elements.messages.scrollTop = elements.messages.scrollHeight;
  });
}

function showThinking() {
  const message = createMessage({ role: "assistant", content: "" });
  message.id = "thinking-message";
  message.querySelector(".message-text").replaceChildren();
  const dots = document.createElement("div");
  dots.className = "thinking-dots";
  dots.setAttribute("aria-label", "Apex Assistant is preparing an answer");
  dots.innerHTML = "<span></span><span></span><span></span>";
  message.querySelector(".message-text").append(dots);
  elements.messages.append(message);
  scrollToLatest();
}

function hideThinking() {
  document.querySelector("#thinking-message")?.remove();
}

function showChatError(message) {
  elements.chatError.textContent = message;
  elements.chatError.hidden = false;
  announce(message);
}

function clearChatError() {
  elements.chatError.hidden = true;
  elements.chatError.textContent = "";
}

function makeUploadStatus(file) {
  const item = document.createElement("div");
  item.className = "upload-item";
  const spinner = document.createElement("span");
  spinner.className = "spinner";
  spinner.setAttribute("aria-hidden", "true");
  const copy = document.createElement("span");
  copy.className = "upload-copy";
  const name = document.createElement("strong");
  name.textContent = file.name;
  const status = document.createElement("span");
  status.textContent = "Indexing policy…";
  copy.append(name, status);
  item.append(spinner, copy);
  elements.uploadList.append(item);
  return { item, status };
}

async function uploadFiles(fileList) {
  const files = [...fileList];
  if (!files.length || state.uploading) return;
  state.uploading = true;
  elements.fileInput.disabled = true;

  for (const file of files) {
    const view = makeUploadStatus(file);
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      view.item.classList.add("is-error");
      view.status.textContent = "Choose a PDF file.";
      continue;
    }

    const form = new FormData();
    form.append("conversation_id", state.conversationId);
    form.append("file", file);

    try {
      const response = await fetch("/upload", { method: "POST", body: form });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(parseError(payload, `Upload failed (${response.status}).`));
      }
      state.documents.push(payload);
      renderSources();
      await refreshConversationHistory();
      view.status.textContent = `Indexed ${payload.chunks_indexed} chunks`;
      view.item.remove();
      announce(`${file.name} is ready for questions.`);
    } catch (error) {
      view.item.classList.add("is-error");
      view.status.textContent = error instanceof Error ? error.message : "Upload failed.";
    }
  }

  state.uploading = false;
  elements.fileInput.disabled = false;
  elements.fileInput.value = "";
  setControls();
}

async function sendQuestion(question) {
  if (state.busy || !state.documents.length || !question.trim()) return;
  const cleanQuestion = question.trim();
  clearChatError();
  state.busy = true;
  state.messages.push({ role: "user", content: cleanQuestion, citations: [] });
  renderMessages();
  showThinking();
  elements.messageInput.value = "";
  elements.messageInput.style.height = "auto";
  setControls();
  announce("Preparing a grounded answer.");

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: state.conversationId, message: cleanQuestion }),
    });
    const payload = await readJson(response);
    if (!response.ok) {
      throw new Error(parseError(payload, `The assistant could not answer (${response.status}).`));
    }
    state.messages.push({
      role: "assistant",
      content: payload.answer,
      citations: payload.citations,
      status: payload.status,
    });
    hideThinking();
    renderMessages();
    await refreshConversationHistory();
    announce("Answer ready.");
  } catch (error) {
    hideThinking();
    state.messages.pop();
    renderMessages();
    elements.messageInput.value = cleanQuestion;
    showChatError(error instanceof Error ? error.message : "The assistant could not answer.");
  } finally {
    state.busy = false;
    setControls();
    elements.messageInput.focus();
  }
}

async function initializeWorkspace() {
  setConversationId(state.conversationId);
  renderSources();
  renderMessages();
  await refreshConversationHistory();
  announce("New empty chat ready.");
}

async function openConversation(conversationId) {
  if (state.busy || state.uploading || conversationId === state.conversationId) return;
  clearChatError();
  try {
    const response = await fetch(`/conversations/${encodeURIComponent(conversationId)}`);
    const payload = await readJson(response);
    if (!response.ok) {
      throw new Error(parseError(payload, "The saved chat could not be opened."));
    }
    setConversationId(conversationId);
    state.documents = payload.documents;
    state.messages = payload.messages;
    elements.messageInput.value = "";
    renderSources();
    renderMessages();
    renderConversationHistory();
    announce(`Opened ${state.conversations.find((item) => item.conversation_id === conversationId)?.title || "saved chat"}.`);
  } catch (error) {
    showChatError(error instanceof Error ? error.message : "The saved chat could not be opened.");
  }
}

async function deleteConversation(conversationId, title) {
  if (state.busy || state.uploading) return;
  if (!window.confirm(`Delete “${title}”? This permanently removes its messages and indexed documents.`)) {
    return;
  }
  clearChatError();
  try {
    const response = await fetch(`/conversations/${encodeURIComponent(conversationId)}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const payload = await readJson(response);
      throw new Error(parseError(payload, "The chat could not be deleted."));
    }
    if (conversationId === state.conversationId) {
      state.documents = [];
      state.messages = [];
      setConversationId(crypto.randomUUID());
      renderSources();
      renderMessages();
    }
    await refreshConversationHistory();
    announce(`${title} was deleted.`);
  } catch (error) {
    showChatError(error instanceof Error ? error.message : "The chat could not be deleted.");
  }
}

function startNewWorkspace() {
  const hasContent = state.documents.length > 0 || state.messages.length > 0;
  if (hasContent && !window.confirm("Start a new workspace? Your current conversation stays saved under its workspace ID.")) {
    return;
  }
  state.documents = [];
  state.messages = [];
  state.busy = false;
  clearChatError();
  setConversationId(crypto.randomUUID());
  renderSources();
  renderMessages();
  renderConversationHistory();
  elements.messageInput.value = "";
  announce("New empty workspace created.");
}

elements.fileInput.addEventListener("change", (event) => uploadFiles(event.target.files));

["dragenter", "dragover"].forEach((eventName) => {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.add("is-dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.remove("is-dragging");
  });
});

elements.dropZone.addEventListener("drop", (event) => uploadFiles(event.dataTransfer.files));

elements.chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendQuestion(elements.messageInput.value);
});

elements.messageInput.addEventListener("input", () => {
  elements.messageInput.style.height = "auto";
  elements.messageInput.style.height = `${Math.min(elements.messageInput.scrollHeight, 150)}px`;
  setControls();
});

elements.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.chatForm.requestSubmit();
  }
});

elements.suggestions.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;
  elements.messageInput.value = button.textContent;
  setControls();
  elements.messageInput.focus();
});

elements.copyIdButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(state.conversationId);
    announce("Workspace ID copied.");
  } catch {
    announce("The workspace ID could not be copied.");
  }
});

elements.newWorkspaceButton.addEventListener("click", startNewWorkspace);

elements.conversationList.addEventListener("click", (event) => {
  const deleteButton = event.target.closest("[data-delete-conversation-id]");
  if (deleteButton) {
    deleteConversation(
      deleteButton.dataset.deleteConversationId,
      deleteButton.dataset.conversationTitle,
    );
    return;
  }
  const openButton = event.target.closest("[data-conversation-id]");
  if (openButton) {
    openConversation(openButton.dataset.conversationId);
  }
});

initializeWorkspace();
