> **Historical validation record.** Original implementation and hosted-run evidence; subsequent confirmation is appended below.

Local implementation validation on 2026-10-04 used Python **3.14.7**, Node
**24.19.0**, PostgreSQL/client **17.11**, Redis **7.4.6** and a temporary nginx
**1.28.3** build on macOS:

| Executed check | Result |
| --- | --- |
| Full canonical API/SDK/Proxmox suite using the new database helper | **853 passed, zero skipped**, 151.13 seconds; JUnit has no failures/errors. Generated environment permissions and refusal to reuse an existing cluster also passed; disposable databases/processes were removed. |
| Shared H4 selector | **258 passed**, 14.96 seconds; existing deprecation warnings remain. |
| `npm ci --no-audit`, `npm test`, `NEXT_TELEMETRY_DISABLED=1 npm run build` | Locked installation, **279 passed, zero skipped**, production build passed. Audit was not rerun. |
| Both workflow YAML files, actionlint **1.7.7**, `bash -n` on CI shell helpers | Passed. Five CI contract tests also passed in the full suite and the final focused recheck. |
| `compileall`, Alembic head assertion, whitespace checks | Passed; single existing `20261004_0026` head, no migrations. |
| Metadata, `build --dry-run --worktree`, independent verifier, actual `sha256sum -c SHA256SUMS` | Both package archives and manifest passed. Local uncommitted artifacts use the explicitly non-publishable worktree mode. |
| Extracted Compose/native installer and upgrade/configuration `--help`; generated configuration validation | Passed; configuration mode **0600**. |
| Changed Markdown links and code fences | **127** local link targets passed; no unclosed code fences. |
| Upstream prerequisites | Official nginx archive SHA-256 and PGDG key fingerprint verified; both official container tags exist for Linux/amd64. |

No hosted execution had occurred at the initial implementation validation above.
The subsequent first hosted run supplied by the user passed Frontend and reported
**821 passed, 32 errors** in Backend / PostgreSQL. All errors were Docker nginx
fixture setup failures: its first `nginx -t` still attempted the production port
80 before the runtime-only adaptation. Release & Deployment Integrity was
reported otherwise healthy. The fixture now adapts the test listener before
both validations; a new hosted run must confirm this fix and the Node 24 Action
pins. Historical H4 evidence is unchanged. Docker CLI/daemon and Linux systemd
remain unavailable locally; local tests do not establish native lifecycle
acceptance.


## Subsequent operator confirmation — 4 October 2026

During repository documentation preparation, the operator supplied confirmation
that secure setup, MFA, encrypted backup/restore and release/update work were
complete. A Docker-created `.atlasbackup` restored successfully into native/systemd
Atlas, and the packaged native `upgrade.py` flow succeeded in real testing.
The supplied Debian 13 environment used Python 3.13, Node 22, PostgreSQL 17 and
Redis, with Atlas-managed nginx. The operator also reported all current hosted
CI checks green: Backend / PostgreSQL, Frontend and Release & Deployment Integrity.

These are operator-supplied results, not commands rerun by the documentation task.
No finer install/restart/reboot measurements or new test counts are inferred.
Original execution tables and earlier pending-gate statements above remain
historical; this appended confirmation supersedes them for those supplied facts.
