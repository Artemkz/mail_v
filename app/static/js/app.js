const BASE_PATH = window.location.pathname.replace(/\/$/, "") || "";
const API = `${BASE_PATH}/api`;

let state = {
  view: "inbox",
  folderId: null,
  messages: [],
  selectedId: null,
  checkedIds: new Set(),
  folders: [],
  mailboxes: [],
  stats: { total_inbox: 0, unread: 0, starred: 0, archived: 0 },
  searchMode: false,
  editingMailboxId: null,
  settingsOpen: false,
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
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (res.status === 401) {
    window.location.href = `${BASE_PATH}/login`;
    throw new Error("Требуется авторизация");
  }
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

  const systemViews = [
    { id: "inbox", label: "Входящие", count: state.stats.total_inbox },
    { id: "unread", label: "Непрочитанные", count: state.stats.unread },
    { id: "starred", label: "Избранное", count: state.stats.starred },
    { id: "archive", label: "Архив", count: state.stats.archived },
  ];

  systemViews.forEach((item) => {
    const btn = document.createElement("button");
    btn.className = `nav-item${state.view === item.id && !state.searchMode ? " active" : ""}`;
    btn.innerHTML = `<span>${item.label}</span><span class="badge">${item.count || ""}</span>`;
    btn.onclick = () => selectView(item.id);
    list.appendChild(btn);
  });

  if (state.folders.length) {
    const title = document.createElement("div");
    title.className = "section-title section-title-inline";
    title.textContent = "По отправителям";
    list.appendChild(title);
  }

  state.folders.forEach((folder) => {
    const btn = document.createElement("button");
    btn.className = `nav-item${state.view === "folder" && state.folderId === folder.id ? " active" : ""}`;
    btn.innerHTML = `<span>${escapeHtml(folder.name)}</span><span class="badge">${folder.message_count}</span>`;
    btn.onclick = () => selectFolder(folder.id);
    list.appendChild(btn);
  });

  updateBulkFolderSelect();
}

function renderMailboxes() {
  const list = $("mailbox-list");
  const badge = $("settings-badge");
  list.innerHTML = "";

  if (state.mailboxes.length) {
    badge.textContent = state.mailboxes.length;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }

  if (!state.mailboxes.length) {
    list.innerHTML = '<div class="empty-state" style="padding:0.5rem">Нет ящиков</div>';
    return;
  }
  state.mailboxes.forEach((mb) => {
    const card = document.createElement("div");
    card.className = `mailbox-card${mb.is_consolidation_target ? " consolidation-target" : ""}${mb.is_active === false ? " inactive" : ""}`;
    card.innerHTML = `
      <div class="mailbox-card-body">
        <strong>${escapeHtml(mb.name)}${mb.is_consolidation_target ? ' <span class="target-badge">сборник</span>' : ""}${mb.is_active === false ? ' <span class="target-badge">выкл</span>' : ""}</strong>
        <span>${escapeHtml(mb.email)}</span>
      </div>
      <div class="mailbox-card-actions">
        <button class="btn btn-secondary btn-sm btn-icon" type="button" title="Редактировать настройки">✎</button>
        <button class="btn btn-secondary btn-sm btn-icon" type="button" title="Сделать ящиком-сборником">★</button>
        <button class="btn btn-danger btn-sm btn-icon" type="button" title="Удалить ящик">✕</button>
      </div>
    `;
    const [editBtn, targetBtn, deleteBtn] = card.querySelectorAll("button");
    editBtn.onclick = (e) => {
      e.stopPropagation();
      openEditModal(mb);
    };
    targetBtn.onclick = (e) => {
      e.stopPropagation();
      setConsolidationTarget(mb.id, mb.email);
    };
    deleteBtn.onclick = (e) => {
      e.stopPropagation();
      deleteMailbox(mb.id, mb.email);
    };
    list.appendChild(card);
  });
}

function updateBulkFolderSelect() {
  const select = $("bulk-move-folder");
  if (!select) return;
  const current = select.value;
  select.innerHTML = '<option value="">Переместить...</option><option value="0">Без папки</option>';
  state.folders.forEach((folder) => {
    const option = document.createElement("option");
    option.value = folder.id;
    option.textContent = folder.name;
    select.appendChild(option);
  });
  select.value = current;
}

function updateBulkToolbar() {
  const bulk = $("bulk-actions");
  const selectAll = $("select-all");
  if (!bulk || !selectAll) return;

  const hasChecked = state.checkedIds.size > 0;
  bulk.classList.toggle("hidden", !hasChecked);
  selectAll.checked = state.messages.length > 0 && state.checkedIds.size === state.messages.length;
  selectAll.indeterminate =
    state.checkedIds.size > 0 && state.checkedIds.size < state.messages.length;
}

function toggleChecked(id, checked) {
  if (checked) {
    state.checkedIds.add(id);
  } else {
    state.checkedIds.delete(id);
  }
  updateBulkToolbar();
}

function renderMessages() {
  const list = $("message-list");
  list.innerHTML = "";

  if (!state.messages.length) {
    list.innerHTML = '<div class="empty-state">Писем нет</div>';
    renderDetail(null);
    updateBulkToolbar();
    return;
  }

  state.messages.forEach((msg) => {
    const wrap = document.createElement("div");
    wrap.className = "message-item-wrap";

    const check = document.createElement("input");
    check.type = "checkbox";
    check.className = "message-check";
    check.checked = state.checkedIds.has(msg.id);
    check.onclick = (e) => {
      e.stopPropagation();
      toggleChecked(msg.id, check.checked);
    };

    const starBtn = document.createElement("button");
    starBtn.className = `btn btn-sm btn-icon star-btn${msg.is_starred ? " starred" : ""}`;
    starBtn.type = "button";
    starBtn.title = msg.is_starred ? "Убрать из избранного" : "В избранное";
    starBtn.textContent = msg.is_starred ? "★" : "☆";
    starBtn.onclick = (e) => {
      e.stopPropagation();
      toggleStar(msg);
    };

    const btn = document.createElement("button");
    btn.className = `message-item${state.selectedId === msg.id ? " active" : ""}${msg.is_read ? "" : " unread"}`;
    btn.innerHTML = `
      <div class="message-item-top">
        <span class="from">${escapeHtml(msg.sender_name || msg.sender_email)}</span>
        ${msg.is_starred ? '<span class="inline-star">★</span>' : ""}
      </div>
      <div class="subject">${escapeHtml(msg.subject || "(без темы)")}</div>
      <div class="preview">${escapeHtml((msg.body_text || "").slice(0, 120))}</div>
      <div class="message-item-bottom">
        <span class="mailbox-tag">${escapeHtml(msg.mailbox_email || "")}</span>
        <span class="date">${formatDate(msg.received_at)}</span>
      </div>
    `;
    btn.onclick = () => selectMessage(msg.id);

    const delBtn = document.createElement("button");
    delBtn.className = "btn btn-danger btn-sm btn-icon message-delete-btn";
    delBtn.type = "button";
    delBtn.title = "Удалить";
    delBtn.textContent = "✕";
    delBtn.onclick = (e) => {
      e.stopPropagation();
      deleteMessage(msg.id);
    };

    wrap.appendChild(check);
    wrap.appendChild(starBtn);
    wrap.appendChild(btn);
    wrap.appendChild(delBtn);
    list.appendChild(wrap);
  });

  if (!state.selectedId && state.messages[0]) {
    selectMessage(state.messages[0].id, false);
  }

  updateBulkToolbar();
}

function renderDetail(message) {
  const panel = $("message-detail");
  if (!message) {
    panel.className = "message-detail empty";
    panel.innerHTML = "<p>Выберите письмо</p>";
    return;
  }

  const folderOptions = state.folders
    .map(
      (folder) =>
        `<option value="${folder.id}"${message.folder_id === folder.id ? " selected" : ""}>${escapeHtml(folder.name)}</option>`
    )
    .join("");

  panel.className = "message-detail";
  panel.innerHTML = `
    <div class="detail-actions">
      <button id="btn-reply" class="btn btn-secondary btn-sm" type="button">Ответить</button>
      <button id="btn-forward" class="btn btn-secondary btn-sm" type="button">Переслать</button>
      <button id="btn-copy" class="btn btn-secondary btn-sm" type="button">Копировать</button>
      <button id="btn-toggle-read" class="btn btn-secondary btn-sm" type="button">${message.is_read ? "Непрочитано" : "Прочитано"}</button>
      <button id="btn-toggle-star" class="btn btn-secondary btn-sm" type="button">${message.is_starred ? "★ Избранное" : "☆ В избранное"}</button>
      <button id="btn-archive" class="btn btn-secondary btn-sm" type="button">${message.is_archived ? "Из архива" : "В архив"}</button>
      <select id="detail-move-folder" class="toolbar-select">
        <option value="">Папка...</option>
        <option value="0"${message.folder_id == null ? " selected" : ""}>Без папки</option>
        ${folderOptions}
      </select>
      <button id="btn-delete-message" class="btn btn-danger btn-sm" type="button">Удалить</button>
    </div>
    <div class="detail-header">
      <h1>${escapeHtml(message.subject || "(без темы)")}</h1>
    </div>
    <div class="detail-meta">
      <span><strong>От:</strong> ${escapeHtml(message.sender_name || "")} &lt;${escapeHtml(message.sender_email)}&gt;</span>
      <span><strong>Ящик:</strong> ${escapeHtml(message.mailbox_email || "—")}</span>
      <span><strong>Дата:</strong> ${formatDate(message.received_at)}</span>
    </div>
    <div class="detail-body">${escapeHtml(message.body_text || "")}</div>
  `;

  $("btn-reply").onclick = () => replyToMessage(message);
  $("btn-forward").onclick = () => forwardMessage(message);
  $("btn-copy").onclick = () => copyMessage(message);
  $("btn-toggle-read").onclick = () => toggleRead(message);
  $("btn-toggle-star").onclick = () => toggleStar(message);
  $("btn-archive").onclick = () => toggleArchive(message);
  $("detail-move-folder").onchange = (e) => moveMessageToFolder(message.id, e.target.value);
  $("btn-delete-message").onclick = () => deleteMessage(message.id);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function selectMessage(id, markRead = true) {
  state.selectedId = id;
  renderMessages();
  const message = state.messages.find((m) => m.id === id);
  renderDetail(message);
  if (markRead && message && !message.is_read) {
    patchMessage(id, { is_read: true });
  }
}

async function patchMessage(id, payload) {
  try {
    const updated = await api(`/messages/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    state.messages = state.messages.map((m) => (m.id === id ? updated : m));
    await loadStats();
    renderFolders();
    if (state.selectedId === id) {
      renderDetail(updated);
    }
    renderMessages();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function replyToMessage(message) {
  const subject = message.subject?.startsWith("Re:") ? message.subject : `Re: ${message.subject || ""}`;
  window.location.href = `mailto:${encodeURIComponent(message.sender_email)}?subject=${encodeURIComponent(subject)}`;
}

function forwardMessage(message) {
  const subject = message.subject?.startsWith("Fwd:") ? message.subject : `Fwd: ${message.subject || ""}`;
  const body = `\n\n---------- Пересланное сообщение ----------\nОт: ${message.sender_name || message.sender_email}\nТема: ${message.subject || ""}\n\n${message.body_text || ""}`;
  window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

async function copyMessage(message) {
  const text = `От: ${message.sender_name || message.sender_email} <${message.sender_email}>\nТема: ${message.subject || ""}\nДата: ${formatDate(message.received_at)}\n\n${message.body_text || ""}`;
  try {
    await navigator.clipboard.writeText(text);
    showToast("Текст письма скопирован");
  } catch (_) {
    showToast("Не удалось скопировать", "error");
  }
}

async function toggleRead(message) {
  await patchMessage(message.id, { is_read: !message.is_read });
}

async function toggleStar(message) {
  await patchMessage(message.id, { is_starred: !message.is_starred });
}

async function toggleArchive(message) {
  await patchMessage(message.id, { is_archived: !message.is_archived });
  if (state.view === "inbox" || state.view === "unread" || state.view === "starred") {
    state.messages = state.messages.filter((m) => m.id !== message.id);
    state.selectedId = null;
    await loadStats();
    renderFolders();
    renderMessages();
  }
}

async function moveMessageToFolder(id, value) {
  if (value === "") return;
  await patchMessage(id, { folder_id: Number(value) });
  $("detail-move-folder").value = "";
}

async function bulkAction(action, folderId = null) {
  const ids = [...state.checkedIds];
  if (!ids.length) return;

  if (action === "delete") {
    if (!confirm(`Удалить ${ids.length} писем с сервера?`)) return;
    for (const id of ids) {
      try {
        await api(`/messages/${id}`, { method: "DELETE" });
      } catch (err) {
        showToast(err.message, "error");
      }
    }
    state.checkedIds.clear();
    showToast(`Удалено писем: ${ids.length}`);
    await refreshAll();
    return;
  }

  const payload = { message_ids: ids, action };
  if (folderId !== null) payload.folder_id = folderId;

  try {
    const result = await api("/messages/bulk", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.checkedIds.clear();
    showToast(`Обработано писем: ${result.affected}`);
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function markAllRead() {
  try {
    const archived = state.view === "archive";
    const folderParam = state.view === "folder" && state.folderId ? `?folder_id=${state.folderId}` : archived ? "?archived=true" : "";
    const result = await api(`/messages/mark-all-read${folderParam}`, { method: "POST" });
    showToast(`Помечено прочитанными: ${result.marked}`);
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
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

async function loadStats() {
  state.stats = await api("/messages/stats");
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
    messages = await api(`/messages?limit=100&filter=${state.view}`);
  }
  state.messages = messages;
  state.selectedId = null;
  state.checkedIds.clear();
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

async function consolidateMail() {
  const target = state.mailboxes.find((mb) => mb.is_consolidation_target);
  if (!target) {
    showToast("Сначала выберите ящик-сборник (кнопка ★ у ящика)", "error");
    return;
  }

  if (
    !confirm(
      `Скопировать письма со всех ящиков в ${target.email}?\nПисьма останутся в исходных ящиках и появятся в сборнике.`
    )
  ) {
    return;
  }

  const btn = $("btn-consolidate");
  btn.disabled = true;
  btn.textContent = "Сбор...";
  try {
    const result = await api("/consolidate", { method: "POST" });
    let text = `Скопировано ${result.messages_copied} писем в ${result.destination_email}`;
    if (result.messages_skipped) {
      text += `, пропущено: ${result.messages_skipped}`;
    }
    if (result.errors?.length) {
      text += `. Ошибок: ${result.errors.length}`;
    }
    showToast(text, result.errors?.length ? "error" : "success");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "В один ящик";
  }
}

async function setConsolidationTarget(id, email) {
  try {
    await api(`/mailboxes/${id}/consolidation-target`, { method: "PATCH" });
    showToast(`${email} — ящик-сборник`);
    await loadMailboxes();
  } catch (err) {
    showToast(err.message, "error");
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

function openAddModal() {
  state.editingMailboxId = null;
  $("modal-title").textContent = "Добавить IMAP-ящик";
  $("mailbox-form").reset();
  $("mailbox-form").password.required = true;
  $("password-hint").classList.add("hidden");
  $("modal-overlay").classList.remove("hidden");
}

function openEditModal(mailbox) {
  state.editingMailboxId = mailbox.id;
  $("modal-title").textContent = "Редактировать ящик";
  const form = $("mailbox-form");
  form.name.value = mailbox.name;
  form.email.value = mailbox.email;
  form.imap_host.value = mailbox.imap_host;
  form.imap_port.value = mailbox.imap_port;
  form.imap_ssl.checked = mailbox.imap_ssl;
  form.is_active.checked = mailbox.is_active;
  form.username.value = mailbox.username;
  form.password.value = "";
  form.password.required = false;
  form.source_folder.value = mailbox.source_folder;
  $("password-hint").classList.remove("hidden");
  $("modal-overlay").classList.remove("hidden");
}

function closeModal() {
  $("modal-overlay").classList.add("hidden");
  state.editingMailboxId = null;
  $("mailbox-form").reset();
  $("mailbox-form").password.required = true;
  $("password-hint").classList.add("hidden");
}

async function saveMailbox(event) {
  event.preventDefault();
  const form = event.target;
  const payload = {
    name: form.name.value.trim(),
    email: form.email.value.trim(),
    imap_host: form.imap_host.value.trim(),
    imap_port: Number(form.imap_port.value),
    imap_ssl: form.imap_ssl.checked,
    is_active: form.is_active.checked,
    username: form.username.value.trim(),
    source_folder: form.source_folder.value.trim() || "INBOX",
  };

  const password = form.password.value;
  if (state.editingMailboxId) {
    if (password) {
      payload.password = password;
    }
  } else {
    if (!password) {
      showToast("Укажите пароль", "error");
      return;
    }
    payload.password = password;
  }

  try {
    if (state.editingMailboxId) {
      await api(`/mailboxes/${state.editingMailboxId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      showToast("Настройки ящика сохранены");
    } else {
      await api("/mailboxes", { method: "POST", body: JSON.stringify(payload) });
      showToast("Ящик добавлен");
    }
    closeModal();
    await loadMailboxes();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deleteMailbox(id, email) {
  if (!confirm(`Удалить ящик ${email}?\nВсе письма этого ящика в приложении будут удалены.`)) {
    return;
  }
  try {
    const result = await api(`/mailboxes/${id}`, { method: "DELETE" });
    showToast(result.detail || "Ящик удалён");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deleteMessage(id) {
  if (!confirm("Удалить письмо из приложения и с почтового сервера?")) {
    return;
  }
  try {
    const result = await api(`/messages/${id}`, { method: "DELETE" });
    showToast(result.detail || "Письмо удалено");
    state.messages = state.messages.filter((m) => m.id !== id);
    if (state.selectedId === id) {
      state.selectedId = null;
    }
    state.checkedIds.delete(id);
    await loadStats();
    renderFolders();
    renderMessages();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function refreshAll() {
  await Promise.all([loadStats(), loadFolders(), loadMailboxes(), loadMessages()]);
}

function toggleSettings() {
  state.settingsOpen = !state.settingsOpen;
  $("settings-panel").classList.toggle("hidden", !state.settingsOpen);
  $("btn-settings").classList.toggle("active", state.settingsOpen);
  $("btn-settings").setAttribute("aria-expanded", state.settingsOpen ? "true" : "false");
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
  $("btn-consolidate").addEventListener("click", consolidateMail);
  $("btn-organize").addEventListener("click", organizeMail);
  $("btn-settings").addEventListener("click", toggleSettings);
  $("btn-add-mailbox").addEventListener("click", openAddModal);
  $("btn-mark-all-read").addEventListener("click", markAllRead);
  $("select-all").addEventListener("change", (e) => {
    if (e.target.checked) {
      state.messages.forEach((m) => state.checkedIds.add(m.id));
    } else {
      state.checkedIds.clear();
    }
    renderMessages();
  });
  $("bulk-read").addEventListener("click", () => bulkAction("read"));
  $("bulk-unread").addEventListener("click", () => bulkAction("unread"));
  $("bulk-star").addEventListener("click", () => bulkAction("star"));
  $("bulk-archive").addEventListener("click", () => bulkAction("archive"));
  $("bulk-delete").addEventListener("click", () => bulkAction("delete"));
  $("bulk-move-folder").addEventListener("change", (e) => {
    if (e.target.value === "") return;
    bulkAction("move", Number(e.target.value));
    e.target.value = "";
  });
  $("btn-close-modal").addEventListener("click", closeModal);
  $("modal-overlay").addEventListener("click", (e) => {
    if (e.target.id === "modal-overlay") closeModal();
  });
  $("mailbox-form").addEventListener("submit", saveMailbox);
  const logoutBtn = $("btn-logout");
  if (logoutBtn) logoutBtn.addEventListener("click", logout);
}

async function logout() {
  try {
    await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
  } finally {
    window.location.href = `${BASE_PATH}/login`;
  }
}

async function ensureAuth() {
  const res = await fetch(`${API}/auth/me`, { credentials: "include" });
  if (!res.ok) {
    window.location.href = `${BASE_PATH}/login`;
    return false;
  }
  return true;
}

async function init() {
  bindEvents();
  if (!(await ensureAuth())) return;
  try {
    await refreshAll();
  } catch (err) {
    showToast(`Ошибка загрузки: ${err.message}`, "error");
  }
}

document.addEventListener("DOMContentLoaded", init);
