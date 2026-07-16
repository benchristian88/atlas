import test from "node:test";
import assert from "node:assert/strict";

import { apiUrl, normalizeApiBase } from "../lib/api-url.mjs";

test("defaults blank and unset API bases to /api", () => {
  assert.equal(normalizeApiBase(), "/api");
  assert.equal(normalizeApiBase(""), "/api");
  assert.equal(normalizeApiBase("   "), "/api");
});

test("joins relative API bases and endpoints without duplicate slashes", () => {
  assert.equal(apiUrl("/auth/login", "/api"), "/api/auth/login");
  assert.equal(apiUrl("auth/login", "/api/"), "/api/auth/login");
  assert.equal(apiUrl("/assets/abc?include=facts", "api"), "/api/assets/abc?include=facts");
  assert.equal(apiUrl("/health", "/"), "/health");
});

test("supports absolute split-origin API overrides", () => {
  assert.equal(
    apiUrl("/auth/login", "http://localhost:8000/api/"),
    "http://localhost:8000/api/auth/login",
  );
});
