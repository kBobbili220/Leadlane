import { createService, listServices, ServiceRequestError } from "../../public/service-client.mjs";

/** Native apps require an absolute URL; localhost would refer to the phone. */
export function resolveApiUrl({ apiUrl, hostUri } = {}) {
  if (apiUrl?.trim()) {
    let url;
    try { url = new URL(apiUrl.trim()); } catch {
      throw new ServiceRequestError("The workspace connection is not configured correctly.");
    }
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
      throw new ServiceRequestError("The workspace connection is not configured correctly.");
    }
    return url.href.replace(/\/+$/, "");
  }
  // Expo's LAN server and FastAPI normally run on the same development machine.
  if (hostUri) {
    try {
      const host = new URL(`http://${hostUri}`).hostname;
      if (host && !host.endsWith(".exp.direct") && !host.endsWith(".expo.dev")) {
        return `http://${host}:8000`;
      }
    } catch { /* A missing/invalid host is handled below. */ }
  }
  throw new ServiceRequestError("Your workspace isn’t connected yet. Check the app’s connection settings.");
}

function transport(connection) {
  const baseUrl = resolveApiUrl(connection);
  const fetchImpl = connection?.fetchImpl ?? globalThis.fetch;
  return { accessToken: connection?.accessToken, fetchImpl: (path, options) => fetchImpl(`${baseUrl}${path}`, options) };
}

export function createNativeService(payload, connection) {
  return createService(payload, transport(connection));
}

export function listNativeServices(options, connection) {
  return listServices({ ...options, ...transport(connection) });
}
