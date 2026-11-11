import test from "node:test";
import assert from "node:assert/strict";
import { createNativeService, listNativeServices, resolveApiUrl } from "../src/api/services.mjs";

const service = {
  id: "00000000-0000-4000-8000-000000000001", name: "Full detail", description: null,
  base_price_minor: 15000, estimated_duration_minutes: 120, unit_label: "vehicle", is_active: true,
};

test("explicit phone API address wins over the Metro host and normalizes trailing slashes", () => {
  assert.equal(resolveApiUrl({ apiUrl: "http://192.168.1.20:8000/", hostUri: "192.168.1.99:8081" }), "http://192.168.1.20:8000");
});

test("infers the computer API address from Expo LAN host without using phone localhost", () => {
  assert.equal(resolveApiUrl({ hostUri: "192.168.1.20:8081" }), "http://192.168.1.20:8000");
  assert.equal(resolveApiUrl({ hostUri: "10.0.2.2:8081" }), "http://10.0.2.2:8000");
  assert.equal(resolveApiUrl({ hostUri: "[fd00::1]:8081" }), "http://[fd00::1]:8000");
});

test("missing, tunnel, invalid or credential-bearing URLs do not send a request", () => {
  for (const connection of [
    {}, { hostUri: "project.exp.direct" }, { apiUrl: "not a url" },
    { apiUrl: "postgresql://user:password@host/db" }, { apiUrl: "http://user:password@host:8000" },
    { apiUrl: "http://host:8000?token=secret" }, { apiUrl: "http://host:8000#fragment" },
  ]) assert.throws(() => resolveApiUrl(connection));
});

test("native create posts to the actual computer API once and returns its record", async () => {
  let calls = 0;
  const result = await createNativeService({ name: "Full detail" }, {
    apiUrl: "http://192.168.1.20:8000",
    fetchImpl: async (url, options) => {
      calls += 1;
      assert.equal(url, "http://192.168.1.20:8000/api/v1/services");
      assert.equal(options.method, "POST");
      assert.deepEqual(JSON.parse(options.body), { name: "Full detail" });
      return { status: 201, ok: true, json: async () => service };
    },
  });
  assert.equal(calls, 1);
  assert.equal(result.id, service.id);
});

test("native catalog uses the same server and respects pagination", async () => {
  const rows = await listNativeServices({ offset: 50 }, {
    apiUrl: "https://workspace.example",
    fetchImpl: async (url, options) => {
      const parsed = new URL(url);
      assert.equal(parsed.origin, "https://workspace.example");
      assert.equal(parsed.searchParams.get("offset"), "50");
      assert.equal(options.method, "GET");
      return { status: 200, ok: true, json: async () => [service] };
    },
  });
  assert.equal(rows.length, 1);
});
