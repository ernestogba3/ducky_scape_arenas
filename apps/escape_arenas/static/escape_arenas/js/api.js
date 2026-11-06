// Helpers fetch con CSRF para hablar con los endpoints Django.

export async function apiGet(path) {
  const res = await fetch(path, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`GET ${path} → HTTP ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

export async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-CSRFToken": window.DUCKY.csrf,
    },
    credentials: "same-origin",
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST ${path} → HTTP ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}
