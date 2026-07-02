const API = "/api";

let state = {
  view: "all",
  folderId: null,
  messages: [],
  selectedId: null,
  folders: [],
  mailboxes: [],
  searchMode: false,
};

function $(id) {
  return document.getElementById(id);
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function showToast(text, type = "success") {
  const toast = $("toast");
  toast.textContent = text;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3500);
}

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch (_) {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

function renderFolders() {
  const list = $("folder-list");
  list.innerHTML = "";

  const allBtn = document.createElement("button");
  allBtn.className = `nav-item${state.view === "all" && !state.searchMode ? " active" : ""}`;
  allBtn.innerHTML = `<span>Все письма</span><span class="badge">${state.messages.length || ""}</span>`;
  allBtn.onclick = () => selectView("all");
  list.appendChild(allBtn);

  state.folders.forEach((folder) => {
    const btn = document.createElement("button");
    btn.className = `nav-item${state.view === "folder" && state.folderId === folder.id ? " active" : ""}`;
    btn.innerHTML = `<span>${escapeHtml(folder.name)}</span><span class="badge">${folder.message_count}</span>`;
    btn.onclick = () => selectFolder(folder.id);
    list.appendChild(btn);
  });
}

function renderMailboxes() {
  const list = $("mailbox-list");
  list.innerHTML = "";
  if (!state.mailboxes.length) {
    list.innerHTML = '<div class="empty-state" style="padding:0.5rem">Нет ящиков</div>';
    return;
  }
  state.mailboxes.forEach((mb) => {
    const card = document.createElement("div");
    card.className = "mailbox-card";
    card.innerHTML = `<strong>${escapeHtml(mb.name)}</strong><span>${escapeHtml(mb.email)}</span>`;
    list.appendChild(card);
  });
}

function renderMessages() {
  const list = $("message-list");
  list.innerHTML = "";

  if (!state.messages.length) {
    list.innerHTML = '<div class="empty-state">Писем нет</div>';
    renderDetail(null);
    return;
  }

  state.messages.forEach((msg) => {
    const btn = document.createElement("button");
    btn.className = `message-item${state.selectedId === msg.id ? " active" : ""}`;
    btn.innerHTML = `
      <div class="from">${escapeHtml(msg.sender_name || msg.sender_email)}</div>
      <div class="subject">${escapeHtml(msg.subject || "(без темы)")}</div>
      <div class="preview">${escapeHtml((msg.body_text || "").slice(0, 120))}</div>
      <div class="date">${formatDate(msg.received_at)}</div>
    `;
    btn.onclick = () => selectMessage(msg.id);
    list.appendChild(btn);
  });

  if (!state.selectedId && state.messages[0]) {
    selectMessage(state.messages[0].id);
  }
}

function renderDetail(message) {
  const panel = $("message-detail");
  if (!message) {
    panel.className = "message-detail empty";
    panel.innerHTML = "<p>Выберите письмо</p>";
    return;
  }

  panel.className = "message-detail";
  panel.innerHTML = `
    <div class="detail-header">
      <h1>${escapeHtml(message.subject || "(без темы)")}</h1>
    </div>
    <div class="detail-meta">
      <span><strong>От:</strong> ${escapeHtml(message.sender_name || "")} &lt;${escapeHtml(message.sender_email)}&gt;</span>
      <span><strong>Дата:</strong> ${formatDate(message.received_at)}</span>
    </div>
    <div class="detail-body">${escapeHtml(message.body_text || "")}</div>
  `;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function selectMessage(id) {
  state.selectedId = id;
  renderMessages();
  const message = state.messages.find((m) => m.id === id);
  renderDetail(message);
}

async function selectView(view) {
  state.view = view;
  state.folderId = null;
  state.searchMode = false;
  $("search-input").value = "";
  await loadMessages();
}

async function selectFolder(folderId) {
  state.view = "folder";
  state.folderId = folderId;
  state.searchMode = false;
  $("search-input").value = "";
  await loadMessages();
}

async function loadFolders() {
  state.folders = await api("/folders");
  renderFolders();
}

async function loadMailboxes() {
  state.mailboxes = await api("/mailboxes");
  renderMailboxes();
}

async function loadMessages() {
  let messages;
  if (state.view === "folder" && state.folderId) {
    messages = await api(`/folders/${state.folderId}/messages?limit=100`);
  } else {
    messages = await api("/messages?limit=100");
  }
  state.messages = messages;
  state.selectedId = null;
  renderFolders();
  renderMessages();
}

async function runSearch(query) {
  if (!query.trim()) {
    state.searchMode = false;
    await loadMessages();
    return;
  }

  const result = await api("/search", {
    method: "POST",
    body: JSON.stringify({ query, folder_id: state.folderId }),
  });

  state.searchMode = true;
  state.messages = result.messages;
  state.selectedId = null;
  renderMessages();
  showToast(`Найдено: ${result.total}`);
}

async function collectMail() {
  const btn = $("btn-collect");
  btn.disabled = true;
  btn.textContent = "Сбор...";
  try {
    const result = await api("/collect", { method: "POST" });
    showToast(
      `Собрано ${result.messages_fetched} писем, папок: ${result.folders_created}`
    );
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Собрать письма";
  }
}

async function organizeMail() {
  try {
    const result = await api("/organize", { method: "POST" });
    showToast(`Папок: ${result.folders_created}, перемещено: ${result.messages_moved}`);
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function openModal() {
  $("modal-overlay").classList.remove("hidden");
}

function closeModal() {
  $("modal-overlay").classList.add("hidden");
  $("mailbox-form").reset();
}

async function addMailbox(event) {
  event.preventDefault();
  const form = event.target;
  const payload = {
    name: form.name.value.trim(),
    email: form.email.value.trim(),
    imap_host: form.imap_host.value.trim(),
    imap_port: Number(form.imap_port.value),
    imap_ssl: form.imap_ssl.checked,
    username: form.username.value.trim(),
    password: form.password.value,
    source_folder: form.source_folder.value.trim() || "INBOX",
  };

  try {
    await api("/mailboxes", { method: "POST", body: JSON.stringify(payload) });
    showToast("Ящик добавлен");
    closeModal();
    await loadMailboxes();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function refreshAll() {
  await Promise.all([loadFolders(), loadMailboxes(), loadMessages()]);
}

function bindEvents() {
  $("search-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await runSearch($("search-input").value);
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  $("btn-collect").addEventListener("click", collectMail);
  $("btn-organize").addEventListener("click", organizeMail);
  $("btn-add-mailbox").addEventListener("click", openModal);
  $("btn-close-modal").addEventListener("click", closeModal);
  $("modal-overlay").addEventListener("click", (e) => {
    if (e.target.id === "modal-overlay") closeModal();
  });
  $("mailbox-form").addEventListener("submit", addMailbox);
}

async function init() {
  bindEvents();
  try {
    await refreshAll();
  } catch (err) {
    showToast(`Ошибка загрузки: ${err.message}`, "error");
  }
}

document.addEventListener("DOMContentLoaded", init);
