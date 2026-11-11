import test from "node:test";
import assert from "node:assert/strict";
import { buildServicePayload, createService, formatPrice, listServices, ServiceRequestError } from "../public/service-client.mjs";

const input = (changes = {}) => ({
  name: " Signature detail ", description: " Interior & exterior ", pricingMode: "fixed",
  price: "150.00", duration: "120", unit: "vehicle", isActive: true, ...changes,
});
const record = (changes = {}) => ({
  id: "00000000-0000-4000-8000-000000000001", name: "Signature detail", description: "Interior & exterior",
  base_price_minor: 15000, estimated_duration_minutes: 120, unit_label: "vehicle", is_active: true, ...changes,
});
const response = (status, body) => ({ status, ok: status >= 200 && status < 300, json: async () => body });

test("converts dollars to exact integer minor units and trims content", () => {
  const { payload, errors } = buildServicePayload(input({ price: "19.99" }));
  assert.deepEqual(errors, {});
  assert.equal(payload.base_price_minor, 1999);
  assert.equal(payload.name, "Signature detail");
  assert.equal(payload.description, "Interior & exterior");
  assert.equal(payload.estimated_duration_minutes, 120);
  assert.equal(payload.sort_order, 0);
  assert.equal(Object.hasOwn(payload, "business_id"), false);
});

test("custom pricing and omitted optional values remain null, not zero", () => {
  const { payload } = buildServicePayload(input({ pricingMode: "custom", price: "", duration: "", description: " ", isActive: false }));
  assert.equal(payload.base_price_minor, null);
  assert.equal(payload.estimated_duration_minutes, null);
  assert.equal(payload.description, null);
  assert.equal(payload.is_active, false);
});

test("zero-dollar services are allowed", () => {
  assert.equal(buildServicePayload(input({ price: "0" })).payload.base_price_minor, 0);
});

test("invalid prices never become a rounded or misleading amount", () => {
  for (const price of ["", "-1", "1.234", "1,500", "$150", "1e3", "Infinity", "90071992547409.92"]) {
    const result = buildServicePayload(input({ price }));
    assert.equal(result.payload, null, price);
    assert.ok(result.errors.price, price);
  }
  assert.equal(buildServicePayload(input({ price: "90071992547409.91" })).payload.base_price_minor, Number.MAX_SAFE_INTEGER);
});

test("validates names, integer durations, and known pricing units", () => {
  for (const duration of ["0", "-1", "1.5", "tomorrow", "2147483648"]) {
    assert.ok(buildServicePayload(input({ duration })).errors.duration, duration);
  }
  assert.ok(buildServicePayload(input({ name: "   " })).errors.name);
  assert.ok(buildServicePayload(input({ name: "a".repeat(201) })).errors.name);
  assert.ok(buildServicePayload(input({ unit: "unknown" })).errors.unit);
});

test("create sends the actual API payload and only resolves for a confirmed 201 record", async () => {
  const payload = buildServicePayload(input()).payload;
  let calls = 0;
  const result = await createService(payload, { fetchImpl: async (url, options) => {
    calls += 1;
    assert.equal(url, "/api/v1/services");
    assert.equal(options.method, "POST");
    assert.equal(options.headers["Content-Type"], "application/json");
    assert.deepEqual(JSON.parse(options.body), payload);
    return response(201, record());
  } });
  assert.equal(calls, 1);
  assert.equal(result.id, record().id);
});

test("server failures do not show success or automatically repeat a POST", async () => {
  let calls = 0;
  await assert.rejects(createService({}, { fetchImpl: async () => {
    calls += 1;
    return response(503, { detail: "Database is unavailable" });
  } }), (error) => error instanceof ServiceRequestError && error.uncertain);
  assert.equal(calls, 1);
});

test("an interrupted or malformed success response is treated as an unconfirmed save", async () => {
  for (const fetchImpl of [
    async () => { throw new TypeError("Network failed"); },
    async () => response(201, {}),
    async () => response(200, record()),
    async () => ({ status: 201, ok: true, json: async () => { throw new SyntaxError(); } }),
  ]) {
    await assert.rejects(createService({}, { fetchImpl }), (error) => error.uncertain === true);
  }
});

test("backend validation errors are mapped to the correct form fields", async () => {
  await assert.rejects(createService({}, { fetchImpl: async () => response(422, {
    detail: [{ loc: ["body", "base_price_minor"] }, { loc: ["body", "estimated_duration_minutes"] }],
  }) }), (error) => !error.uncertain && !!error.fields.price && !!error.fields.duration);
});

test("loads the persisted catalog with bounded pagination", async () => {
  const rows = await listServices({ offset: 50, fetchImpl: async (url, options) => {
    const parsed = new URL(url, "http://test");
    assert.equal(parsed.pathname, "/api/v1/services");
    assert.equal(parsed.searchParams.get("offset"), "50");
    assert.equal(parsed.searchParams.get("limit"), "50");
    assert.equal(parsed.searchParams.get("include_archived"), "true");
    assert.equal(options.method, "GET");
    return response(200, [record()]);
  } });
  assert.equal(rows[0].name, "Signature detail");
});

test("catalog fetch failures and invalid results are errors rather than an empty catalog", async () => {
  for (const body of [{ detail: "unexpected" }, [record({ base_price_minor: -1 })]]) {
    await assert.rejects(listServices({ fetchImpl: async () => response(200, body) }), ServiceRequestError);
  }
});

test("formats explicit free and custom prices distinctly", () => {
  assert.equal(formatPrice(0), "$0.00");
  assert.equal(formatPrice(15000), "$150.00");
  assert.equal(formatPrice(null), "Custom quote");
});
