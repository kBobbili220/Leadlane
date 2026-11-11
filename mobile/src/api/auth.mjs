import { resolveApiUrl } from "./services.mjs";

export class AuthApiError extends Error {
  constructor(message, status) { super(message); this.name = "AuthApiError"; this.status = status; }
}

function validIdentity(data) {
  return data && typeof data.user?.id === "string" && typeof data.user?.full_name === "string"
    && typeof data.user?.email === "string" && typeof data.business?.id === "string"
    && typeof data.business?.name === "string" && data.role === "owner"
    && typeof data.expires_at === "string" && Number.isFinite(Date.parse(data.expires_at));
}

async function request(path, { body, token, connection = {}, timeoutMs = 20000 } = {}) {
  const base = resolveApiUrl(connection);
  const fetchImpl = connection.fetchImpl ?? globalThis.fetch;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(`${base}/api/v1/auth/${path}`, {
      method: path === "me" ? "GET" : "POST",
      headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}), signal: controller.signal,
    });
    if (!response.ok) {
      const messages = {
        401: path === "login" ? "Email or password is incorrect." : "Your session has expired. Please sign in again.",
        403: "Your business access is unavailable. Please contact your administrator.",
        409: "An account could not be created with these details. Try signing in if you already have one.",
        422: "Please check your email, password and account details.",
        429: "Too many attempts. Please wait before trying again.",
      };
      throw new AuthApiError(messages[response.status] ?? "Your workspace is unavailable right now. Please try again.", response.status);
    }
    if (path === "logout" && response.status === 204) return null;
    const data = await response.json();
    if (!validIdentity(data) || (path !== "me" && typeof data.access_token !== "string")) {
      throw new AuthApiError("We couldn’t confirm your session. Please try signing in.");
    }
    return data;
  } catch (error) {
    if (error instanceof AuthApiError) throw error;
    throw new AuthApiError("We couldn’t reach your workspace. Check your connection and try again.");
  } finally { clearTimeout(timer); }
}

export const registerOwner = (body, connection) => request("register", { body, connection });
export const loginOwner = (body, connection) => request("login", { body, connection });
export const getIdentity = (token, connection) => request("me", { token, connection });
export const logoutOwner = (token, connection) => request("logout", { token, connection });
