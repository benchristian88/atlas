# Core hardening acceptance closure

**Historical validation record — 4 October 2026.** Branch:
`feature/hardening-acceptance-closure`. Base revision:
`4f6556a1db339466a4ffd2afa525a01bca9dbfda`. Starting working tree was clean.
Canonical release metadata at review: `0.1.0`, channel `beta`.

## Purpose and evidence policy

This record consolidates accumulated core hardening evidence and closes the
former H6 acceptance gate sufficiently to proceed to integration/plugin and
onboarding development. It does not constitute final 1.0.0 release qualification
or whole-product security certification. No product, database or API behaviour
changes, deployments, upgrades, restores, publication or hosted CI runs were
performed for this closure.

PASS means the cited execution or supplied acceptance establishes the stated
scope, subject to the row's limits. PARTIAL means supporting validation exists
but part of the lifecycle remains unproven. NOT PROVEN means the required real
event is not established by repository records. Code, architecture and test
plans establish contracts and intended checks, not successful execution.

Evidence types below are automated tests/checks, live local browser acceptance,
operator-supplied real deployment acceptance, and operator-supplied hosted CI.
The latter is recorded confirmation, not independently retrieved Actions logs;
no hosted run ID or exact revision is supplied in those confirmations. Temporary
artifact paths in earlier reports are historical references, not durable bundled
test outputs. No new counts are inferred from operator statements.

## Evidence sources

The matrix uses these source IDs. Original execution tables remain unchanged;
later operator confirmation is cited separately where it supersedes a pending
statement for a specific fact.

| ID | Repository record | Evidence relevant to closure |
| --- | --- | --- |
| F | [Installation foundation](h1-release-foundation.md#tests-and-actual-validation-sz) | Executed setup/auth/settings, migration and protected-configuration tests; live production first-run browser; original platform limitations. |
| D | [Docker ingress acceptance](h1-docker-ingress.md) | Opening supplied acceptance explicitly records fresh Debian Docker/LXC installation, setup/login, actual reboot/recovery, LAN access and one-upstream HTTPS proxy. Original local table did not execute Docker. |
| M | [Local MFA acceptance](h2-local-two-factor-authentication.md#validation-actually-performed) | PostgreSQL behaviour/security/concurrency tests and real production browser enrollment, TOTP/recovery and local-module reset. Opening supplied Docker acceptance does not enumerate physical-authenticator or deployed-wrapper actions. |
| B | [Encrypted backup acceptance](h3-encrypted-backup-restore.md#evidence-actually-executed) | 681 backend/plugin/PostgreSQL tests, 276 frontend tests, production build, real browser create/overwrite/fresh restore and injected failure/recovery tests; opening user confirmation accepts documented real Docker tests. |
| BO | [Later backup operator confirmation](h3-encrypted-backup-restore.md#subsequent-operator-confirmation--4-october-2026) | Successful Docker-created archive restored into native/systemd, packaged native upgrade and green hosted checks; Debian 13, Python 3.13, Node 22, PostgreSQL 17, Redis and Atlas-managed nginx. |
| R | [Release/native remediation validation](h4-release-distribution.md#remediation-files-validation-and-security-review) and [original release/browser evidence](h4-release-distribution.md#validation-actually-performed) | Final remediation: 848 backend tests, 258 release-critical cases, 279 frontend tests, production build, package verification/extraction/help and independent checksums. Original update browser covers current/newer/offline states. Local macOS checks do not prove Docker builds or systemd lifecycle. |
| RO | [Later release operator confirmation](h4-release-distribution.md#subsequent-operator-confirmation--4-october-2026) | Confirms native packaged upgrade, Docker-to-native restore and all three hosted checks green. Does not enumerate fresh-install/restart/reboot measurements. |
| C | [CI validation and later operator confirmation](continuous-integration.md) | Local full suite: 853 passed, zero skipped. Initial hosted fixture failure retained; appended confirmation reports Backend / PostgreSQL, Frontend and Release & Deployment Integrity green. |
| W | [Checked-in CI workflow](../../../.github/workflows/ci.yml) and [CI scope](../../testing/continuous-integration.md) | Defines what green jobs cover, including packaged Compose validation and API/web/worker builds, zero backend skips and single head. Workflow existence alone is not execution evidence. |
| P | [Public documentation completion](public-product-documentation.md#16-tests-and-validation-actually-executed) | Later local full regression: 862 passed, zero skipped; release-critical: 258 passed; frontend: 280 passed; production build, single head, package/manifest/checksum verification and documentation checks. These are historical counts, not closure reruns. |

Also inspected: [repository instructions](../../../AGENTS.md),
[README](../../../README.md), [documentation index](../../README.md),
[project status](../../product/status.md), [feature reference](../../product/feature-ledger.md),
[history index](../README.md), the remaining validation record inventory,
deployment and testing guides, relevant architecture and model/migration records,
[security policy](../../../SECURITY.md), [support](../../../SUPPORT.md),
[release metadata](../../../apps/api/app/release.json),
[package allowlist](../../../infra/release/package-manifest.json),
[release workflow](../../../.github/workflows/release.yml),
[release procedure](../../development/releasing.md), installers/upgrade helper and
the corresponding checked-in regression tests. These corroborate current
contracts; they do not manufacture missing lifecycle results.

## Acceptance matrix

| # | Requirement | Result | Evidence type | Reference | Notes / gaps |
| --- | --- | --- | --- | --- | --- |
| 1 | Fresh Docker Compose installation | PASS | Operator; automated; live browser | D; F | Real fresh Debian Docker/LXC installer/setup accepted. Original acquisition was a fresh clone, not a newly verified release archive; package buildability is covered separately in row 20. |
| 2 | Fresh native/systemd installation | PARTIAL | Automated; operator | R; RO | Helper/preflight/ingress validated; real Debian 13 managed-ingress deployment, restore and upgrade confirmed. A fresh remediated installer run is not explicitly recorded by the later confirmation. |
| 3 | Restart/reboot persistence — Docker | PASS | Operator; automated | D; F | Actual LXC reboot/recovery and authenticated access accepted; restart-policy contracts tested. No inference of a new reboot for every subsequent change. |
| 4 | Restart/reboot persistence — native/systemd | NOT PROVEN | Static/automated contracts; adjacent operator evidence | F; R; RO | Unit enable/restart/ordering contracts exist. Later native upgrade implies service activation, but explicitly supplies no finer restart/reboot measurements; no real boot-persistence result is established. |
| 5 | Package-based Docker upgrade | PARTIAL | Automated/release validation | R; P; W | Helper preservation/order tests, package identity/checksum validation and hosted packaged builds exist. No operator upgrade of an existing installation using the packaged `upgrade.py --method docker_compose` is recorded. |
| 6 | Package-based native/systemd upgrade | PASS | Operator; automated | RO; BO; R | Later confirmation explicitly reports real packaged native `upgrade.py` success. Original macOS table remains historical. |
| 7 | Version/build/install-method reporting | PASS | Automated; live browser | F; R; P | Protected build-info/About and artifact identity tested; update browser covers all method labels. No runtime Git requirement or inference of an operator checking every deployed field. |
| 8 | Protected settings/configuration persistence | PASS | Automated; live browser; operator | F; M; B; R; RO | Exclusive protected secret files, key-addition preservation, settings restore and simulated upgrades tested; real earlier Docker data preservation and native upgrade confirmed. |
| 9 | MFA enrolment | PASS | Automated; live browser; operator | M; BO | Real production enrollment/QR/manual-key/confirmation tested with locally generated real-time TOTP. Physical authenticator actions are not individually established. |
| 10 | MFA authentication challenge | PASS | Automated; live browser | M | Password-only isolation, scoped challenge, valid TOTP, expiry/replay/attempt/race protections executed. |
| 11 | MFA recovery codes | PASS | Automated; live browser | M; B | Consumption, reuse rejection, regeneration/old-code rejection and restored verifiers tested. |
| 12 | Administrative MFA reset / break-glass | PARTIAL | Automated; live browser/local CLI | M | Protected admin reset and actual `scripts.mfa` module reset passed; password/session/audit effects checked. Actual Docker exec and native management-wrapper resets are not established. |
| 13 | Encrypted backup creation | PASS | Automated; live browser; operator | B; BO | Encrypted UI download/CLI and crypto/parser tests passed; Docker-created archive independently confirmed by subsequent native restore. |
| 14 | Restore to same deployment method | PASS | Automated; live browser; operator | B | Real source overwrite and fresh-target restore tested locally; opening supplied acceptance confirms documented real Docker tests. No new native-to-native operator drill is inferred. |
| 15 | Cross-method backup portability | PASS | Operator; automated | BO; RO; B | Docker-to-native restore explicitly succeeded, with target-key rewrap covered by tests. Reverse native-to-Docker operator acceptance is not established. |
| 16 | Restore rollback/failure behaviour | PASS | Automated PostgreSQL/fault injection; live browser | B | Wrong-passphrase preflight, post-replacement rollback, failed rollback/crash fail-closed state and local recovery executed. Real power-loss recovery was not independently proven. |
| 17 | Release package generation | PASS | Automated/tool execution | R; C; P | Both source packages and manifest built and independently verified. Worktree dry runs explicitly non-publishable; no live publication claim. |
| 18 | Release manifest/package identity | PASS | Automated/tool execution | R; P | Version/channel/method/commit, sizes, contents and negative identity/archive tests passed. |
| 19 | SHA-256 verification | PASS | Automated; independent checksum tools | R; C; P | Both archives and manifest verified with standard checksum commands. SHA-256 is not a signature. |
| 20 | Docker release package validity/buildability | PASS | Automated; operator-supplied hosted CI | R; P; C; W | Local package validation plus supplied green Release & Deployment Integrity, whose workflow builds extracted packaged API/web/worker images. No local daemon build or real upgrade is inferred. |
| 21 | systemd release package validity | PASS | Automated; operator | R; P; RO | Required templates/helpers/units, verified extraction/help and identity validated; actual packaged native upgrade confirmed. Broader host/fresh/reboot qualification remains bounded by rows 2/4. |
| 22 | Update checker — current version | PASS | Automated; live browser | R; P | Controlled loopback release-source harness verifies current/up-to-date and cache/refresh UI. Not a live public GitHub-source test. |
| 23 | Update checker — newer version | PASS | Automated; live browser | R; P | Supported beta/stable selection, safe link and method-specific instructions tested. No download/self-update performed. |
| 24 | Update checker — offline/failure | PASS | Automated; live browser | R; P | Unavailable source and continued Dashboard/API operation verified; timeout/HTTP/JSON/size failures covered. |
| 25 | GitHub-hosted CI | PASS | Operator-supplied hosted CI | C; RO; W | Later confirmation reports all three jobs green after the original fixture failure. No exact run ID/revision or new closure-branch execution claimed. |
| 26 | Backend/PostgreSQL regression | PASS | Recorded automated execution | P; C; R | Latest cited full local suite: 862 passed, zero skipped, real PostgreSQL/migrations/Redis/nginx enabled. Not rerun for this documentation task. |
| 27 | Frontend tests | PASS | Recorded automated execution | P | Latest cited local `npm test`: 280 passed, zero failed/skipped. |
| 28 | Production frontend build | PASS | Recorded build execution | P; C | Production builds passed; hosted Frontend green also supplied. |
| 29 | Database migrations / single Alembic head | PASS | Recorded automated PostgreSQL/Alembic execution | P; C; M | Single `20261004_0026` head, optional migration suites executed. No migration required by closure. |
| 30 | Release-critical regression | PASS | Recorded automated execution | P; R; C | Shared selector: 258 passed; same selector in CI/release workflow. No new full selector execution for closure. |
| 31 | Fresh first-run setup | PASS | Automated; live browser; operator | F; D; B | Real administrator creation/login/setup closure, locking/rollback/reset and setup-authorized restore tested; real Docker setup accepted. Guided knowledge onboarding remains upcoming. |
| 32 | Targeted security/auth/access smoke coverage | PASS | Automated; live browser; targeted diff review | F; M; B; R; P | Authentication, RBAC/customer/site isolation, Origin/cookies, secret redaction, setup takeover/races, MFA, backup access/parser and installer/release boundaries covered. Not a whole-product security certification. |
| 33 | Documentation/operator workflow validation | PASS | Automated docs checks; live browser; operator | P; D; BO; RO | Local links/language/fences/hygiene and actual setup, backup, update and native upgrade workflows corroborate guides. Broad supported-platform acceptance and final screenshots remain deferred. |

**Summary: 29 PASS, 3 PARTIAL (2, 5, 12), 1 NOT PROVEN (4).** PASS rows retain
their explicit scope limits; this is not acceptance of every platform, backup
direction, physical device or failure mode.

## Lifecycle evidence boundaries

The packaged Docker upgrade is **not proven as a real operator lifecycle**.
M's real Docker upgrades used the key-addition helper and Compose rebuild;
D's ingress update used Compose directly. Neither establishes execution of the
later packaged `infra/install/upgrade.py --method docker_compose` against an
existing installation. Dry-run packages, helper tests and hosted image builds
are complementary evidence, not substitutes. That one outstanding Docker check
does not block integration development and remains a pre-1.0 acceptance item.

The appended BO/RO/C confirmations establish native packaged upgrade,
Docker-to-native restore and green hosted CI, superseding earlier pending
statements for those facts. They deliberately exclude finer install/restart/reboot
measurements. Fresh remediated native installation and native boot persistence
therefore remain incompletely evidenced. Real deployment-wrapper MFA resets,
physical-authenticator acceptance, reverse cross-method restore and the final
supported-platform matrix can be covered during final cross-deployment acceptance;
none is silently promoted by a general operator statement that MFA or release
work was complete.

## Security and dependency position

Current authentication/access controls have recorded regression coverage. MFA
and backup encryption received targeted test/browser acceptance; installer,
ingress and release paths received security-conscious testing and diff review.
Secret/configuration/exposure regressions were checked within those scopes.
This is sufficient core development evidence, not final production security
certification, a penetration-test claim or a clean dependency-audit claim.

The last recorded npm audit in M/B/R reported **five unresolved findings**:

| Dependency | Recorded severity |
| --- | --- |
| `next` | Critical |
| `nanoid`, `postcss`, `sharp` | High (three findings) |
| `baseline-browser-mapping` | Moderate |

P states dependency versions were unchanged and audit was not rerun. Current
package/lockfile inspection and the changes since P's base show licence/source
metadata edits rather than dependency remediation. No repository evidence closes
these findings. They remain known, temporarily retained beta risks; CI deliberately
omits audit as a merge gate. This is not a finding-specific risk assessment,
claim of harmlessness or permanent security waiver. Reassessment, remediation
or an explicit supported disposition is required before 1.0. No CVE identifiers
or current internet-scan results are inferred. Mutable base-image inputs,
Python dependency resolution and signing/attestation policy also remain final
release/supply-chain review considerations, not newly discovered vulnerabilities.

Whole-product security/release qualification is deliberately deferred until after
the initial infrastructure integrations/plugins (Proxmox, Docker, UniFi or the
selected equivalents), integration credential storage/execution and guided
onboarding/setup flows. Those features introduce credentials, remote APIs,
execution paths, trust boundaries, network access and new attack surfaces. Their
completed implementation must be included in the meaningful final gate before
1.0.0. Nothing in this closure declares those features implemented.

## Documentation closure and validation

Active project status now states that core hardening is substantially complete,
identifies integrations/plugins and guided onboarding as next, and separates
residual lifecycle checks from final dependency/security/release qualification.
The feature reference retains implemented upgrade code while disclosing missing
real packaged Docker acceptance. History navigation links this archival record;
public README/operator entry points do not gain a milestone journey.
The active auth-shell checklist's obsolete disabled-restore instruction is
corrected to reflect the implemented setup-authorized restore choice. Other
planned/deferred labels found in active guides describe genuinely unfinished
capabilities and remain intact. Original historical tables are not rewritten.

Proportional validation executed for this documentation-only change:

| Command / check | Actual result |
| --- | --- |
| From `apps/api`: `PYTHONDONTWRITEBYTECODE=1 /private/tmp/atlas-h1-venv/bin/python -m pytest tests/test_repository_docs.py tests/test_markdown_docs.py tests/test_ci_workflow.py -q` | **23 passed**. Includes repository Markdown/local-link tests, filesystem whitespace checks including untracked files, active-vs-history product-language boundaries, status/feature-reference fence checks and CI contract tests. Uses the existing complete temporary venv. |
| Inline Python check of the five changed Markdown files and the acceptance matrix | Passed: **29 local link targets, 8 fragments**, balanced code fences and all **33 ordered rows** with the stated result counts. |
| `git diff --check` | Passed. New-file whitespace is also covered by the filesystem documentation tests above. |

Historical suite totals above are not new validation. No dependency scans,
full backend/frontend/build reruns, large browser suites, deployment drills or
hosted CI were triggered. No commits, pushes, merges, rebases, tags, releases
or GitHub settings changes occurred. Database, API/UI contracts, authentication
and customer/site authorization behaviour remain unchanged.

## Residual pre-1.0 acceptance items

- Real packaged Docker upgrade of an existing installation using the supported
  helper, preserving configuration/project/volumes and validating data/auth/identity.
- Explicit fresh remediated native installer and native restart/reboot persistence
  evidence; final supported-platform and cross-deployment retesting, including
  deployment MFA recovery commands and remaining portability/device checks.
- Reassess/remediate or explicitly disposition the known dependency findings;
  review dependency/container/release supply-chain policy.
- Complete integrations/plugins and guided onboarding, then whole-product
  security review, final cross-deployment acceptance and release qualification.
- Final UX, current screenshots, documentation freeze and supported-platform
  matrix. No promised 1.0.0 date or publication acceptance is inferred.

## Closure decision

**PASS — CORE HARDENING ACCEPTANCE CLOSED**

Atlas's current core platform provides sufficient installation, authentication
and access-control, backup/recovery, release, upgrade, CI and operator-documentation
maturity to proceed to integration/plugin and onboarding development. Strong
recorded automated, live-browser and real operator evidence supports this
decision with the bounded residual work above. Individual PARTIAL and NOT PROVEN
items remain open for pre-1.0 acceptance; this closure does not replace final
whole-product security/release qualification.
