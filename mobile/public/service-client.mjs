/** Shared native/browser API validation. No credentials or database access here. */
const MAX_MONEY = BigInt(Number.MAX_SAFE_INTEGER);
const MAX_DURATION = 2 ** 31 - 1;

export class ServiceRequestError extends Error {
  constructor(message, { uncertain = false, fields = {}, status } = {}) {
    super(message);
    this.name = "ServiceRequestError";
    this.uncertain = uncertain;
    this.fields = fields;
    this.status = status;
  }
}

export function buildServicePayload(values) {
  const errors = {};
  const name = String(values.name ?? "").trim();
  if (!name) errors.name = "Give your service a name.";
  else if (name.length > 200) errors.name = "Keep the name to 200 characters or fewer.";

  let basePrice = null;
  if (values.pricingMode !== "custom") {
    const price = String(values.price ?? "").trim();
    if (!/^\d+(\.\d{1,2})?$/.test(price)) {
      errors.price = "Enter a price like 150 or 150.00.";
    } else {
      const [whole, fraction = ""] = price.split(".");
      const minor = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
      if (minor > MAX_MONEY) errors.price = "Please use a smaller starting price.";
      else basePrice = Number(minor);
    }
  }

  const duration = String(values.duration ?? "").trim();
  let minutes = null;
  if (duration) {
    if (!/^\d+$/.test(duration) || Number(duration) < 1 || Number(duration) > MAX_DURATION) {
      errors.duration = "Enter a whole number of minutes greater than zero.";
    } else minutes = Number(duration);
  }
  if (!["vehicle", "package", "hour", "service"].includes(values.unit)) {
    errors.unit = "Choose how this service is priced.";
  }
  if (Object.keys(errors).length) return { payload: null, errors };

  return {
    errors,
    payload: {
      name,
      description: String(values.description ?? "").trim() || null,
      base_price_minor: basePrice,
      estimated_duration_minutes: minutes,
      unit_label: values.unit,
      is_active: Boolean(values.isActive),
      sort_order: 0,
    },
  };
}

export function formatPrice(minor) {
  if (minor === null) return "Custom quote";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(minor / 100);
}

function isService(value) {
  return value && typeof value === "object"
    && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.id)
    && typeof value.name === "string" && value.name.trim().length > 0
    && (value.description === null || typeof value.description === "string")
    && (value.base_price_minor === null || (Number.isSafeInteger(value.base_price_minor) && value.base_price_minor >= 0))
    && (value.estimated_duration_minutes === null || (Number.isInteger(value.estimated_duration_minutes) && value.estimated_duration_minutes > 0))
    && typeof value.unit_label === "string" && typeof value.is_active === "boolean";
}

async function request(path, { method = "GET", body, accessToken, fetchImpl = globalThis.fetch, timeoutMs = 20000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(path, {
      method,
      headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}), ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
      signal: controller.signal,
    });
    let data;
    try { data = await response.json(); } catch { data = null; }
    if (!response.ok) {
      const fields = {};
      if (response.status === 422 && Array.isArray(data?.detail)) {
        const names = { name: "name", base_price_minor: "price", estimated_duration_minutes: "duration", unit_label: "unit" };
        for (const error of data.detail) {
          const key = names[error.loc?.[1]];
          if (key) fields[key] = "Please check this value and try again.";
        }
      }
      const uncertain = method === "POST" && response.status >= 500;
      throw new ServiceRequestError(
        response.status === 401 ? "Your session has expired. Please sign in again."
          : response.status === 403 ? "Your business access is unavailable."
          : uncertain ? "We couldn’t confirm the save. Check your services before trying again."
          : response.status === 422 ? "Please check the highlighted details."
          : method === "POST" ? "We couldn’t save this service. Please try again in a moment."
          : "We couldn’t load your services. Please try again in a moment.",
        { uncertain, fields, status: response.status },
      );
    }
    return { data, status: response.status };
  } catch (error) {
    if (error instanceof ServiceRequestError) throw error;
    throw new ServiceRequestError(
      method === "POST" ? "We couldn’t confirm the save. Check your services before trying again."
        : "We couldn’t load your services. Check your connection and try again.",
      { uncertain: method === "POST" },
    );
  } finally {
    clearTimeout(timer);
  }
}

export async function createService(payload, options = {}) {
  const { data, status } = await request("/api/v1/services", { ...options, method: "POST", body: payload });
  if (status !== 201 || !isService(data)) {
    throw new ServiceRequestError("We couldn’t confirm the save. Check your services before trying again.", { uncertain: true });
  }
  return data;
}

export async function listServices({ offset = 0, limit = 50, ...options } = {}) {
  const params = new URLSearchParams({ include_archived: "true", limit: String(limit), offset: String(offset) });
  const { data } = await request(`/api/v1/services?${params}`, options);
  if (!Array.isArray(data) || !data.every(isService)) {
    throw new ServiceRequestError("We couldn’t load your services. Please try again.");
  }
  return data;
}
