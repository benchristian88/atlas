import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import test from "node:test";
import QRCode from "qrcode";
import { loginResult } from "../lib/login-result.mjs";

test("login distinguishes a scoped MFA challenge from an authenticated user", () => {
  const user = { email: "example@example.com", display_name: "Example" };
  assert.equal(loginResult({ user }), user);
  assert.equal(loginResult({ user, mfa_required: false }), user);
  assert.deepEqual(loginResult({ user: null, mfa_required: true }), { mfa_required: true });
  assert.throws(() => loginResult({ user, mfa_required: true }));
  assert.throws(() => loginResult({ user: null }));
});

test("local QR encoder accepts standard otpauth payloads deterministically", () => {
  const ephemeralSeed = randomBytes(20).toString("hex");
  const uri = `otpauth://totp/Atlas:example%40example.com?secret=${ephemeralSeed}&issuer=Atlas`;
  const first = QRCode.create(uri, { errorCorrectionLevel: "M" });
  const second = QRCode.create(uri, { errorCorrectionLevel: "M" });
  assert.equal(first.modules.size, second.modules.size);
  assert.deepEqual(first.modules.data, second.modules.data);
  assert.ok(first.modules.size >= 21);
});

test("MFA presentation retains manual enrollment and has no external QR or browser storage", () => {
  const security = readFileSync(new URL("../components/mfa-security.js", import.meta.url), "utf8");
  const login = readFileSync(new URL("../app/login/page.js", import.meta.url), "utf8");
  assert.match(security, /QRCode\.toCanvas/);
  assert.match(security, /Manual setup key/);
  assert.match(security, /Atlas cannot show these codes again/);
  assert.match(security, /current_password/);
  assert.match(login, /Use a recovery code/);
  assert.match(login, /verifyLoginMfa/);
  assert.doesNotMatch(security + login, /localStorage|sessionStorage|console\.|https?:\/\//);
});
