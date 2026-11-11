import test from "node:test";
import assert from "node:assert/strict";
import { AuthApiError, getIdentity, loginOwner, logoutOwner, registerOwner } from "../src/api/auth.mjs";
import { restoreSession } from "../src/auth/session.mjs";
import { createNativeService, listNativeServices } from "../src/api/services.mjs";

const identity = { user: { id: "owner-id", email: "owner@example.com", full_name: "Owner" },
  business: { id: "business-id", name: "Detailer", slug: "detailer", currency: "USD", timezone: "UTC" },
  role: "owner", expires_at: "2027-01-01T00:00:00Z" };
const token = { ...identity, access_token: "random-test-session", token_type: "bearer" };
const connection = (fetchImpl) => ({ apiUrl: "http://workspace:8000", fetchImpl });
const response = (status, data) => ({ status, ok: status >= 200 && status < 300, json: async () => data });
const service = { id: "00000000-0000-4000-8000-000000000001", name: "Detail", description: null, base_price_minor: 15000, estimated_duration_minutes: null, unit_label: "vehicle", is_active: true };

test("login and registration use the correct JSON interfaces without trimming passwords", async () => {
  for (const [operation, path] of [[loginOwner, "login"], [registerOwner, "register"]]) {
    const password = " leading and trailing spaces ";
    const result = await operation({ email: "owner@example.com", password }, connection(async (url, options) => {
      assert.equal(url, `http://workspace:8000/api/v1/auth/${path}`);
      assert.equal(options.method, "POST");
      assert.equal(JSON.parse(options.body).password, password);
      return response(path === "register" ? 201 : 200, token);
    }));
    assert.equal(result.access_token, token.access_token);
  }
});

test("identity and logout use bearer headers, and logout accepts an empty 204", async () => {
  const config = connection(async (url, options) => {
    assert.equal(options.headers.Authorization, `Bearer ${token.access_token}`);
    if (url.endsWith("/me")) { assert.equal(options.method, "GET"); return response(200, identity); }
    assert.equal(options.method, "POST");
    return response(204);
  });
  assert.deepEqual(await getIdentity(token.access_token, config), identity);
  assert.equal(await logoutOwner(token.access_token, config), null);
});

test("API failures expose a status and safe message, never returned secrets", async () => {
  for (const status of [401, 403, 409, 422, 429, 503]) {
    await assert.rejects(loginOwner({}, connection(async () => response(status, { detail: "secret-server-internals" }))),
      (error) => error instanceof AuthApiError && error.status === status && !error.message.includes("secret-server-internals"));
  }
  await assert.rejects(loginOwner({}, connection(async () => { throw new TypeError("offline"); })),
    (error) => error.status === undefined);
});

test("session restoration loads identity before exposing a remembered token", async () => {
  let supplied;
  const result = await restoreSession({
    readToken: async () => token.access_token,
    loadIdentity: async (value) => { supplied = value; return identity; },
    deleteToken: async () => assert.fail("Valid session should remain stored"),
  });
  assert.equal(supplied, token.access_token);
  assert.equal(result.access_token, token.access_token);
  assert.equal(result.business.id, identity.business.id);
});

test("expired sessions are deleted; network/server failures retain them for retry", async () => {
  let deleted = 0;
  const deps = { readToken: async () => token.access_token, deleteToken: async () => { deleted += 1; } };
  assert.equal(await restoreSession({ ...deps, loadIdentity: async () => { throw new AuthApiError("expired", 401); } }), null);
  assert.equal(deleted, 1);
  for (const status of [undefined, 503, 403]) {
    await assert.rejects(restoreSession({ ...deps, loadIdentity: async () => { throw new AuthApiError("unavailable", status); } }));
  }
  assert.equal(deleted, 1);
});

test("storage errors do not fall back to unprotected persistence", async () => {
  await assert.rejects(restoreSession({ readToken: async () => { throw new Error("keystore unavailable"); }, loadIdentity: async () => assert.fail(), deleteToken: async () => assert.fail() }));
  assert.equal(await restoreSession({ readToken: async () => null, loadIdentity: async () => assert.fail(), deleteToken: async () => assert.fail() }), null);
});

test("native service create and catalog attach the authenticated session", async () => {
  const config = { ...connection(async (_url, options) => {
    assert.equal(options.headers.Authorization, `Bearer ${token.access_token}`);
    return options.method === "POST" ? response(201, service) : response(200, [service]);
  }), accessToken: token.access_token };
  assert.equal((await createNativeService({}, config)).id, service.id);
  assert.equal((await listNativeServices({}, config))[0].id, service.id);
});

test("service authentication failures are not reported as uncertain saves", async () => {
  await assert.rejects(createNativeService({}, connection(async () => response(401, {}))),
    (error) => error.status === 401 && error.uncertain === false);
});
