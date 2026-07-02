const BASE_PATH = window.location.pathname
  .replace(/\/login\/?$/, "")
  .replace(/\/$/, "") || "";
const API = `${BASE_PATH}/api`;

const form = document.getElementById("login-form");
const errorEl = document.getElementById("login-error");

function showError(message) {
  errorEl.textContent = message;
  errorEl.classList.remove("hidden");
}

async function checkSession() {
  const res = await fetch(`${API}/auth/me`, { credentials: "include" });
  if (res.ok) {
    window.location.href = BASE_PATH ? `${BASE_PATH}/` : "/";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorEl.classList.add("hidden");

  const data = new FormData(form);
  const payload = {
    username: String(data.get("username") || "").trim(),
    password: String(data.get("password") || ""),
  };

  try {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let detail = "Неверный логин или пароль";
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch (_) {}
      showError(detail);
      return;
    }

    window.location.href = BASE_PATH ? `${BASE_PATH}/` : "/";
  } catch (_) {
    showError("Не удалось подключиться к серверу");
  }
});

checkSession();
