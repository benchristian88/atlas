# Encrypted Atlas backup and restore

H1/H1.1, H2 and H3 are **ACCEPTED**. The user confirms successful documented
H3 real-world acceptance including Docker; no finer observations are inferred.
See the [validation report](../testing/h3-encrypted-backup-restore.md). Native
lifecycle remains H6. Use the [H4 upgrade procedure](h4-upgrades.md), including
an encrypted backup before upgrading; existing npm audit findings remain open.

## What you protect

An `.atlasbackup` file contains the full PostgreSQL Atlas state and the source
application data-encryption material, inside passphrase-authenticated encryption.
It preserves accounts/password hashes, access assignments, customers/sites,
inventory, Services/Business Functions, relationships, accepted knowledge and
history, settings, documents, audit history and active MFA/recovery verifiers.

It does not contain application binaries/images, source `.env`, database or
Redis credentials, authentication signing key, bind/network/host settings,
certificates or proxy configuration. It is not a VM/container snapshot. Keep the
matching supported Atlas release available separately. A raw PostgreSQL dump is
still insufficient to move H2 MFA to a different data key.

Use a long passphrase, at least 12 characters, and keep it safely separate from
the archive. **Atlas cannot recover this backup if the passphrase is lost.**
There is no backdoor or recovery key. Keep downloaded archives in your own
protected storage; H3 does not provide continuous backups or server retention.

Only restore an archive from a trusted Atlas installation. Native PostgreSQL
dumps contain source-defined SQL; archive integrity is not a source identity
signature. Local/remote restore requires deliberate administrative control.

## Docker installation or upgrade

Use matching API/frontend code and the H2 key-addition helper if upgrading from
a configuration that lacks data encryption. Preserve existing secrets:

```bash
python3 infra/install/configuration.py --add-data-encryption-key --output .env
docker compose --env-file .env -f infra/docker/docker-compose.yml config --quiet
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --build --wait
```

The unprivileged API image includes PostgreSQL client 17, matching Compose's
PostgreSQL 17 server. No Docker socket or additional public port is required.
`atlas_state` provides private `/var/lib/atlas` staging/maintenance recovery;
keep it mounted across restarts and alongside `postgres_data` during recovery.
Never delete volumes to try to fix maintenance. The gateway remains the single
ingress and streams restore uploads with a 2 GiB limit. If you use an external
proxy such as NPM, allow the same upload size and streaming/time budget there.
Ordinary API requests retain the smaller gateway limit.

## Backup in the UI

1. Sign in as a **global Master Administrator**.
2. Open **Organisation → System Settings → Backup & Restore → Create backup**.
3. Enter and confirm the backup passphrase, then enter your current password.
4. Choose **Create encrypted backup** and wait for readiness.
5. Download the `.atlasbackup` file and keep its passphrase separately.

The server allows one download, expiring 15 minutes after readiness. A failed or
interrupted generation can be requested again. Credentials are never part of
the download URL. Browser progress does not reveal internal encryption material.

## Restore over an initialized installation

1. Preserve an independent verified backup/snapshot before planned destructive
   acceptance testing. Use disposable installations for failure drills.
2. Open **System Settings → Backup & Restore → Restore backup** as a global
   Master Administrator.
3. Select an archive (up to 2 GiB), enter its passphrase and your current password.
   If your account has MFA, enter a current authenticator or recovery code.
4. Type **RESTORE** and choose **Replace Atlas data**.
5. Keep the progress page open. Atlas authenticates/preflights before pausing
   normal operations; the upload authorization lasts ten minutes.
6. After success, sign in again using the account/password in the restored state.
   Its existing authenticator and valid recovery codes still work. Wait for a
   new authenticator code after restore; the current time step is retired.

The target keeps its database password/URL, Redis URL, signing/data keys, bind
address/port, host/proxy configuration and installation method. Application
settings stored in PostgreSQL are restored. MFA seeds are rewrapped to the
target data key; no source `.env` or signing key is needed. Source/target old
sessions and challenges are invalidated. Setup remains permanently closed.

Incorrect passphrase/corrupt/unsupported backup leaves application data in place;
normal password/factor verification still updates its security bookkeeping.
A failure after replacement attempts automatic rollback. A successful rollback
returns the original data and an explicit failure message. If rollback cannot
be verified, Atlas stays in maintenance and requires the local recovery below.

## Fresh installation restore

1. Install fresh Atlas with its own generated deployment secrets using the
   supported installer. Do not copy the source `.env`.
2. Open `/setup`, enter the one-time setup code shown in the target terminal,
   then choose **Restore existing Atlas backup**.
3. Select the encrypted archive and enter its passphrase. Restore creates no
   new administrator; it restores the accounts in the backup.
4. Wait for completion, then sign in using a restored account and its MFA.
5. Verify the expected knowledge, settings and target access URL. `/setup` is
   closed and its old code/authorizations no longer work.

The one-time H1 setup authorization is mandatory; being uninitialized is not
permission to import data. Archives without a valid usable Master account or
consistent active encrypted MFA do not become a successful installation.

## Compatibility and resource policy

Format v1 uses Argon2id (64 MiB, three iterations, one lane), AES-256-GCM and
authenticated component checksums. H3 accepts known H1-or-newer Alembic ancestors
of the running head and migrates forward. Unknown/newer schemas, future formats
and unsupported/compressed PostgreSQL encodings are rejected. PostgreSQL 16/17
require matching local client tools; PostgreSQL 17 is the tested/reference
deployment. A source PostgreSQL major cannot exceed the target major.

The archive/upload cap is 2 GiB. Staging needs room for upload, authenticated
decryption, dump copying and the local rollback archive; preflight requires at
least three archive sizes plus 64 MiB free, and larger live databases can require
more rollback space. Commands are bounded to 30 minutes each. Larger deployments
need an explicit future policy change, not a hidden force mode. One API runtime
per installation is supported; separate replicas/state directories are not.

## Local management and disaster recovery

UI and CLI use the same crypto/parser/database/rewrap/rollback service. CLI
passphrases are read interactively with `getpass`; there is no passphrase argument
or no-encryption portable mode. Confirm restore/recovery by typing **RESTORE**.
Local operators already hold protected deployment/database access, following the
H1/H2 break-glass boundary; CLI restore therefore does not require a web session.
Protect that host access.

Docker local creation (the output path is inside the container's protected state):

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml exec api \
  python -m scripts.backup create --output /var/lib/atlas/operator.atlasbackup
docker compose --env-file .env -f infra/docker/docker-compose.yml cp \
  api:/var/lib/atlas/operator.atlasbackup ./operator.atlasbackup
chmod 600 operator.atlasbackup
```

Remove the local operator archive after copying to your chosen protected storage;
unlike staged UI jobs, an explicitly chosen CLI output is operator-managed.
For import, copy the encrypted file into `/var/lib/atlas` with service-account
ownership and mode 0600. `docker compose cp` may retain host ownership, so check
it deliberately; do not make the state directory world-readable. Then:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml exec api \
  python -m scripts.backup restore --input /var/lib/atlas/operator.atlasbackup
```

If Atlas is in failed/crashed restore maintenance, retain `atlas_state` and use:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml exec api \
  python -m scripts.backup recover
```

If the API process cannot start at all, the same protected volumes/environment
can be accessed without starting another API server:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml run --rm \
  --no-deps api python -m scripts.backup recover
```

The recover command decrypts the retained local rollback archive with the
target's existing data key, restores/validates the original database, clears
stale Redis and releases maintenance only after success. No user backup
passphrase is needed for this **local rollback recovery**. It is not a portable
backup bypass. Do not delete the maintenance marker to force service open.
If the local encrypted rollback is unavailable, keep Atlas closed and use a
trusted user `.atlasbackup` with `python -m scripts.backup recover --input
/var/lib/atlas/operator.atlasbackup` (or native management's `backup recover
--input ...`). This explicitly confirmed local recovery authenticates the backup
and reuses the restore/rewrap service; failure leaves maintenance in place.

## Native/systemd support

Native prerequisites include PostgreSQL server/client 16 or 17 with matching
`pg_dump`/`pg_restore`, Redis and the existing Python/Node requirements. The API
unit adds `StateDirectory=atlas`, mode 0700, and `/var/lib/atlas`; it retains the
atlas service account, `/etc/atlas/atlas.env`, PrivateTmp, NoNewPrivileges,
ProtectSystem/ProtectHome and restart policy. The worker sees the same marker.

H4 bundles native nginx at the public Atlas endpoint, keeping API/web private.
Both bundled ingresses explicitly allow 2 GiB streamed restore uploads. Any
external proxy must allow the same bound. Real Debian 13 acceptance of the old
native installer found nginx's default 1 MiB limit caused HTTP 413 on a Docker-
created multi-MiB archive; a reserved restore authorization correctly remained
until its ten-minute expiry. This remediation fixes ingress, not H3 locking or
the archive format. Docker/native portability and target-local keys are preserved.
A fresh real native restore retest is required.

When updating an existing native deployment, install the matched code and pinned
requirements, copy the updated API/worker units using the existing upgrade
procedure, run `systemctl daemon-reload`, then restart services. Keep the existing
root:atlas 0640 environment file inside its 0750 directory. Target configuration
is not rewritten by importing a backup.

```bash
sudo -u atlas /opt/atlas/venv/bin/python /opt/atlas/infra/install/manage.py \
  backup create --output /var/lib/atlas/operator.atlasbackup
sudo -u atlas /opt/atlas/venv/bin/python /opt/atlas/infra/install/manage.py \
  backup restore --input /var/lib/atlas/operator.atlasbackup
sudo -u atlas /opt/atlas/venv/bin/python /opt/atlas/infra/install/manage.py \
  backup recover
```

If normal startup is unavailable, these commands still load protected target
configuration and use the shared domain service. Real native install/start/
restart/reboot acceptance remains the later H6 gate unless actually executed.

## Repeatable real Docker acceptance plan

Use the disposable Docker/LXC installation first. Do not capture passphrases,
QR/manual seeds, OTPs or recovery codes in artifacts.

1. Create representative curated records and enroll a disposable MFA account.
   Create/download an encrypted backup through System Settings.
2. Change/delete representative records and alter an application setting.
3. Attempt wrong-passphrase and corrupt-file restores; verify no live data change.
4. Restore correctly over that same disposable installation. Verify the backed-up
   state returned, later changes disappeared, accounts/RBAC/passwords work, MFA
   works, old sessions fail and audit completion exists.
5. Install a fresh target with different generated database/signing/data secrets.
   Restore the **same archive** through `/setup` with the target one-time code.
   Verify data, accounts, MFA/recovery, setup closure and target-local bind/
   network/secrets. Verify no source environment was required or copied.
6. Drill interrupted/failing restore and the local recover command on disposable
   data. Verify failure remains closed until recovery validates.
7. Only after the disposable flow passes, snapshot the representative homelab
   installation and repeat the supported backup/restore journey deliberately.

Record exact results in the H3 acceptance report. H2's accepted real Docker
upgrade is not evidence that these H3 steps have been performed.
