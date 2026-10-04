# H2 local two-factor authentication

H2 extends [Atlas authentication](authentication-and-access-control.md). PostgreSQL
remains authoritative, and successful MFA issues the existing Atlas session.
This is optional local TOTP for individual accounts. No external Atlas service,
email, SMS, push, passkeys, SSO, remembered devices or mandatory-MFA policy is
implemented. [Acceptance evidence](../testing/h2-local-two-factor-authentication.md)
distinguishes implementation from release acceptance.

## Cryptographic material

[PyOTP](https://pyauth.github.io/pyotp/) supplies RFC 6238 TOTP: SHA-1, six digits,
30 seconds, issuer `Atlas`, account label the Atlas email. Seeds contain 160
random bits (32 base32 characters). Verification checks the current step and at
most one adjacent step each way. Clock synchronization remains an operator
responsibility.

`ATLAS_DATA_ENCRYPTION_KEY` is independent application bootstrap cryptographic
material: 32 random bytes represented by 64 hex characters. It is never derived
from `AUTH_SECRET_KEY`, stored in PostgreSQL or delivered to the web service.
[cryptography AES-GCM](https://cryptography.io/en/latest/hazmat/primitives/aead/)
encrypts seeds with fresh 12-byte random nonces, a 128-bit authentication tag
included in the ciphertext, version `1`, and account-bound associated data.
Both pending and active seeds are encrypted. Wrong key, tampering, unsupported
version or wrong account binding fails closed with a sanitized operator-facing
availability error.

Docker and systemd fresh installers generate the key independently into their
existing protected environment files. Production API startup refuses missing or
malformed material. Development can start without a key for non-MFA work but
requires an explicitly configured valid key before enrollment. There is no
hardcoded encryption fallback. See [deployment and recovery](../deployment/h2-mfa.md).

**Atlas MFA encrypted data depends on ATLAS_DATA_ENCRYPTION_KEY.** Restoring
PostgreSQL alone to an installation with a different key cannot decrypt seeds.
H3 includes the source key material inside its passphrase-encrypted backup
payload and rewraps active/pending MFA to the target key without importing
deployment secrets. H2 alone supplied no backup engine or key rotation. See
[H3 backup and restore](encrypted-backup-restore.md); retain protected
configuration with any raw PostgreSQL-only backups.

## State and transactions

`users.mfa_enabled` is the existing account status flag. `user_mfa` is one-to-one
with the account and holds encrypted active/pending seeds, their nonce/version,
confirmation/enrollment timestamps, pending ID/expiry, attempt protection and
last accepted TOTP step. `mfa_recovery_codes` holds one-way verifiers and consumed
timestamps. `mfa_challenges` permits one current login attempt per account.
Foreign keys cascade authentication material when an account is deleted.

Every MFA mutation takes the existing user row lock first and reloads current
state. This includes password login, enrollment/replacement, code consumption,
verification, regeneration and resets. The lock serializes API processes and
prevents duplicate confirmation, accepted-step replay and recovery-code races.
Factor changes, recovery verifiers, challenge revocation, session generation and
audit commit together. A failure rolls them back. Credential failure counters
commit deliberately before a sanitized authentication error is returned.

Revision `20261004_0026` adds these three tables. All existing users migrate with
MFA disabled, including any pre-H2 reserved status flag; identities, hashes,
assignments, inventory and accepted knowledge are retained.

## Enrollment and management

Profile Security begins enrollment only after current-password verification.
An enabled account must also verify its current TOTP or a recovery code before
replacement begins. Pending enrollment lasts ten minutes; a new attempt replaces
the old pending attempt. Five invalid confirmations retire it. Pending state
never changes ordinary login or retires the active factor. Cancel clears it.

The enrollment response deliberately returns the manual key and standard
`otpauth` payload once. The frontend renders its QR locally with
[qrcode](https://github.com/soldair/node-qrcode) onto a canvas. No URI is fetched,
navigated to, or sent to a remote QR provider. The key and recovery codes live
only in component memory and clear on completion/expiry/navigation. MFA responses
are `Cache-Control: no-store`; no subsequent status API reveals an active seed.

Confirmation proves possession, promotes the pending seed and records its used
step atomically, then creates exactly 12 recovery codes. Each code has 120 random
bits: 24 characters from a 32-character alphabet, shown as six groups of four.
Case, spaces and hyphens are presentation only. SHA-256 with an account-bound
domain prefix stores a one-way verifier suitable for these high-entropy values.
All verifiers, including consumed rows, are compared with `compare_digest`
without early exit. Successful consumption commits with authentication. Codes
are displayed only in the generation response; the UI supports copy and print.

Regeneration requires current password and a new valid TOTP, replaces every old
verifier atomically and displays 12 new codes once. Self-disable requires current
password plus TOTP or recovery, deletes active/pending factors and recovery codes,
clears replay state and invalidates challenges. Enable, replacement and disable
increment the existing session version, revoke older sessions and refresh only
the requesting browser's normal session. Password change preserves active MFA,
clears pending enrollment, invalidates challenges and uses H1 session revocation.

## Two-stage login

After valid password authentication, an enabled account receives no normal
session. `/api/auth/login` returns `{user: null, mfa_required: true}` and issues a
five-minute `atlas_mfa` HttpOnly/SameSite=Lax cookie scoped to `/api/auth/mfa`.
The signed audience `atlas-mfa-login`, account ID, session version and random
attempt ID must match the PostgreSQL attempt. Prior attempts are invalidated.
The cookie uses H1's effective HTTPS Secure policy. It cannot authenticate normal
Atlas endpoints, even when supplied as a bearer credential. The frontend keeps
the verification step on the existing public `/login` route. Cancel revokes the
exact attempt. Refresh can require starting password login again.

`POST /api/auth/mfa/verify` accepts either TOTP or explicitly selected recovery.
Success consumes the attempt and issues the ordinary H1 session. Accepted TOTP
steps must strictly exceed the saved step, including the enrollment step. Five
invalid attempts exhaust the challenge and impose the existing fifteen-minute
lockout convention on that account's factor verification, across restarts and
processes. Password reauthentication uses existing account password counters.
No global lockout is created. Existing generic invalid-password behavior does
not reveal MFA state before a valid password.

## Administration, audit and browser security

The existing safe user administration response exposes only `mfa_enabled`.
`POST /api/users/{id}/reset-mfa` requires global `users.edit` and the protected
global Master Administrator boundary. Target permission dominance is retained.
Self-reset is rejected in favor of Profile verification. Reset retires factors,
codes and attempts and revokes all normal sessions; it does not reset passwords.
The local CLI supplies sole-administrator recovery with explicit confirmation,
an exact existing email and a durable local-operator audit event. There is no
unauthenticated remote recovery endpoint.

Audit events include `auth.mfa_enabled`, `auth.mfa_replaced`,
`auth.mfa_recovery_regenerated`, `auth.mfa_recovery_used`, `auth.mfa_disabled`,
`auth.mfa_admin_reset`, `auth.mfa_local_reset`, scoped challenge creation and
sanitized verification failures. Existing normal login/logout events remain.
Actor and target are explicit. OTPs, seeds, QR payloads, codes and keys are absent
from event metadata. Audit redaction also recognizes MFA credential field names.

H1 Origin/SameSite defenses apply to all MFA mutations and admin reset. Validation
errors for auth/user operations return a generic message without raw input,
exception context or submitted field names. Status/enrollment/admin operations
retain backend authorization. Customer/site permissions and operational domain
models do not change. This H2 diff review does not replace H6's whole-product
security review.
