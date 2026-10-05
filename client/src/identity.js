export const teamKey = (code) => `draft:${code}:team`;

export function getTeam(code) {
  try {
    return localStorage.getItem(teamKey(code)) || "";
  } catch {
    return "";
  }
}

export function setTeam(code, name) {
  try {
    localStorage.setItem(teamKey(code), name);
  } catch {
    // The current tab can still use the joined team.
  }
}

export function clearTeam(code) {
  try {
    localStorage.removeItem(teamKey(code));
  } catch {
    // Storage may be blocked.
  }
}
