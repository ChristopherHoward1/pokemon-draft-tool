// REST helpers + URL derivation for the draft backend.

// In dev, VITE_API_URL is unset and requests go same-origin so the Vite dev
// server can proxy /session, /sprites and /health to the backend (see
// vite.config.js). In production VITE_API_URL points at the deployed backend.
export const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export const WS_URL = API_URL
  ? API_URL.replace(/^http/, "ws")
  : `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;

export const spriteUrl = (spritePath) => `${API_URL}/${spritePath}`;

async function request(path, options = {}) {
  const resp = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    let reason = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (body.reason) reason = body.reason;
      else if (body.detail) reason = typeof body.detail === "string" ? body.detail : reason;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(reason);
  }
  return resp.json();
}

export const createSession = (config) =>
  request("/session", { method: "POST", body: JSON.stringify(config) });

export const getSession = (id) => request(`/session/${id}`);

export const joinSession = (id, teamName) =>
  request(`/session/${id}/join`, {
    method: "POST",
    body: JSON.stringify({ team_name: teamName }),
  });

export const startSession = (id) =>
  request(`/session/${id}/start`, { method: "POST" });

export const getState = (id) => request(`/session/${id}/state`);
