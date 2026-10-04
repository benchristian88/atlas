# Local MFA deployment and recovery

H2 requires migration `20261004_0026` and a matched API/frontend version. Existing
accounts remain unenrolled, with their passwords and access assignments intact.
H1/H1.1 is **ACCEPTED** on real Debian Docker/LXC; native/systemd real lifecycle
acceptance remains an H6 item. [H2 acceptance](../testing/h2-local-two-factor-authentication.md)
records H2 ACCEPTED on automated/browser evidence and the supplied real Docker
upgrades and user confirmation, without inferring more granular manual actions.

## Install or upgrade configuration

Fresh Docker and systemd installers automatically generate independent
`ATLAS_DATA_ENCRYPTION_KEY` material. Docker retains `.env` mode `0600`; native
retains root:atlas `/etc/atlas/atlas.env` mode `0640` inside `0750`. No key is
displayed or passed to the web container/build. Protect this file like database
credentials. This is application bootstrap material, not an Atlas System Setting.

For an existing Docker/developer checkout whose protected `.env` lacks the key:

```bash
python3 infra/install/configuration.py --add-data-encryption-key --output .env
docker compose --env-file .env -f infra/docker/docker-compose.yml config --quiet
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --build --wait
```

The helper adds only missing material, preserves every existing credential and
file permission, refuses symlinks and refuses replacing an invalid existing key.
It never prints the key. Do not regenerate the entire environment to upgrade.
For fresh development, copy `.env.example`, restrict it with `chmod 600 .env`,
then use the helper. Configure the auth signing key independently as in README.
Direct developer processes need the explicit key in their normal environment
before enabling MFA; non-MFA development without a key remains supported.

For native configuration, use the matching checkout's helper locally as root:

```bash
sudo python3 infra/install/configuration.py --add-data-encryption-key \
  --output /etc/atlas/atlas.env
sudo systemctl restart atlas-api
```

Retain H1's ownership/permissions, deployment paths and restart policies. Normal
matched-code upgrade preparation still applies. Production startup fails closed
if the required key is absent or not 64 hexadecimal characters. Changing it after
MFA enrollment makes the existing seeds unreadable; do not rotate it casually.

**Atlas MFA encrypted data depends on ATLAS_DATA_ENCRYPTION_KEY.** Preserve this
key with protected database-backup configuration. PostgreSQL alone is insufficient
to restore MFA to a new installation. H3 now includes the source key material inside its passphrase-encrypted backup
payload, then rewraps MFA to the target key. See [H3 backup/restore](h3-backup-restore.md).
H2 alone supplied no backup engine and never put a copy of the key in PostgreSQL.

## Account use

In **My profile → Two-factor authentication**, choose Enable, re-enter your
password, scan the locally rendered QR with a standard TOTP authenticator or
enter the manual key, then enter a current six-digit code. Save the 12 recovery
codes shown once. Each works once; Atlas cannot display them later.

Future login verifies the password first, then asks for an authenticator code or
an explicitly selected recovery code. A code already used for confirmation,
login or management cannot be reused in its time window; wait for a new code.
Synchronize the server/device clocks. Excessive incorrect codes require a new
login and may temporarily block that account's verification.

Profile provides recovery-code regeneration, authenticator replacement and
disable. Regeneration needs password plus current TOTP and invalidates all old
codes. Replacement/disable need password plus the existing TOTP or recovery code.
Replacement keeps the old authenticator active until the new one is confirmed.
No mandatory enrollment, trusted devices or email/SMS recovery is included.

## Administrator and local break-glass reset

A global Master Administrator can reset another account from **Organisation →
Users → Reset MFA**. Self-reset must use Profile verification. Reset never shows
old credentials and never changes the password. It revokes normal sessions,
pending login challenges, pending enrollment and all recovery codes, and audits
the actor and target.

For a sole administrator who has lost both authenticator and recovery codes,
use the local deployment management command. Docker requires an interactive
terminal for confirmation (do not add `-T`):

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml exec api \
  python -m scripts.mfa reset --user <exact-account-email>
```

Native/systemd:

```bash
sudo -u atlas /opt/atlas/venv/bin/python \
  /opt/atlas/infra/install/manage.py mfa reset --user <exact-account-email>
```

At the prompt type `RESET`. Any other response, EOF or interruption cancels.
There is no force/noninteractive bypass flag. Exactly one existing email must
match. The command uses local deployment/database access, retires authentication
material, invalidates sessions, leaves the password unchanged and records
`auth.mfa_local_reset` with the local-operator identity. It prints no old secret
or recovery code. Protect host/container access; this tool is never exposed as
an unauthenticated API or recovery URL. The account can sign in with its existing
password and deliberately enroll a replacement factor afterward.
