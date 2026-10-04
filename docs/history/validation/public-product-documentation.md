> **Historical documentation and validation record — 4 October 2026.** Records this review's work and executed checks; current product guidance remains in the active documentation.

# Public product documentation completion report

Branch: `feature/release-documentation`. Base HEAD:
`e63b552c1149c883cc9b103d9aa6c85eb129a717`. Starting tree was clean.
No commit, push, merge, rebase, tag, publication or repository settings change occurred.

## 1. Repository/public documentation audit

The former README was a long engineering notebook mixing source development,
operator instructions and milestone sequencing. The main documentation index
promoted internal release plans and old acceptance gates. Operator pages used
milestone filenames and language; some still described restore/Updates as future
work or native acceptance as pending despite subsequent supplied confirmation.

The current code, models/migrations, relevant routes and tests establish secure
setup, MFA, encrypted backup/restore, both package installation methods, upgrades,
update awareness, scoped knowledge/graph/dependency capabilities and CI. Live
plugin operation and guided onboarding remain substantial upcoming work.
Brand assets exist, but no current product screenshot collection suitable for
publication was found; final screenshots were deliberately deferred.

## 2. Files added, changed and moved

Every material path is listed in the inventory below. Most apparent deletions in
unstaged Git status are documented moves, not discarded history. Deployment
pages were renamed to product names, old plans/reviews/prompts/validation records
were archived, and links were relocated. Current architecture remains active.

## 3. Licence implementation

Root LICENSE is the verbatim [official GNU AGPL version 3 text](https://www.gnu.org/licenses/agpl-3.0.txt).
Its SHA-256 is `0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`.
The Atlas identifier is **AGPL-3.0-only** in public policies, About, web metadata,
the lockfile root entry, both plugin package metadata files and final OCI image
labels. Python metadata uses the existing build-system-compatible licence text
field; build dependency minimums and runtime dependencies are unchanged.
No invented Atlas copyright owner, per-file headers, bespoke licence or CLA.

## 4. Commercial licensing position

Exact document wording (excluding its heading):

> The public Atlas Impact repository is licensed **AGPL-3.0-only**. This repository
> grants only the licence in [LICENSE](../../../LICENSE).
>
> Organisations or individuals who need alternative licence terms may contact
> the project owner/maintainer through the existing
> [project identity, benchristian88](https://github.com/benchristian88).
> Alternative commercial licensing may be available separately. Commercial terms
> are separate from the AGPL licence; no commercial terms are granted here.

The existing `benchristian88` project identity is used; no email, legal entity,
automated purchase flow, commercial support or commercial terms are invented.

## 5. Contribution policy

Issues, bug reports, feedback and feature discussion are welcome. External code
contributions should be discussed with the maintainer before submission.
Acceptance may require separate future contributor/licensing terms; none are
established or drafted here. Development flow and relevant CI/UI requirements
remain documented in CONTRIBUTING.md and the development guides.

## 6. README and feature claims

README now opens with Atlas Impact's purpose and homelab value, then describes
current capabilities, beta status, package installation, security/recovery,
documentation, licence and contribution/support paths. Only the existing CI
badge is used; no fake release/download badge or stale screenshot is added.
Dependency impact is hypothetical and grounded in recorded rules. Structural
connections alone do not imply failure, live health or recovery readiness.
The concise active project status names integration/onboarding, final UX/docs/
screenshots and security/release qualification before 1.0.0, with no date promise.
The feature reference preserves implemented/partial/planned/deferred distinctions.

## 7. Supported installation methods

Docker Compose and native/systemd release packages remain the two production
paths. Source execution has a separate development guide. Installer behaviour,
same-origin `/api`, protected configuration and recovery contracts are preserved.

## 8. Docker quick start

Download both archives, the matching release manifest and SHA256SUMS from the
same official HTTPS release. Run `sha256sum -c SHA256SUMS` before extraction
(`shasum -a 256 -c SHA256SUMS` on macOS). Every file must report OK.
Using the downloaded version rather than assuming the example is published:

```bash
ATLAS_VERSION=0.1.0
tar -xzf "atlas-docker-compose-${ATLAS_VERSION}.tar.gz"
cd "atlas-docker-compose-${ATLAS_VERSION}"
python3 infra/install/compose.py
```

Prerequisites: Python 3, Linux iproute2 for LAN address detection, Docker Engine
enabled at boot and Compose v2 with `up --wait`. The helper generates `.env`
mode 0600, independent secrets and the data key, starts the stack and prints
the usable URL/setup code. Default port is 3000 with detected IPv4 or safe
loopback fallback. Gateway alone publishes; API/web/database/Redis stay private.
Reboot, optional proxy trust, restart/resume and volume retention are documented.

## 9. Native/systemd quick start

After verifying the same release/checksums and preparing the host:

```bash
ATLAS_VERSION=0.1.0
tar -xzf "atlas-systemd-${ATLAS_VERSION}.tar.gz"
cd "atlas-systemd-${ATLAS_VERSION}"
sudo python3 infra/install/native.py
```

Prerequisites are a Debian/Ubuntu host booted with systemd, Python >=3.12 with
working venv/ensurepip, Node >=22 at `/usr/bin/node`, npm, matching PostgreSQL
16/17 server/client tools, running PostgreSQL/Redis services, local postgres peer
administration and required account tools. Atlas installs distribution nginx if
absent and manages only its own ingress files. Node 22 may need a suitable
upstream/system package; no unsafe remote root installer is prescribed.
API is loopback 8000; Next is loopback 3001; nginx exposes one Atlas endpoint.
Real Debian 13 evidence uses Python 3.13, Node 22, PostgreSQL 17 and Redis;
this is not a claim that every Debian/Ubuntu version is qualified.

## 10. Upgrade paths

Both run from the **new verified extracted package**. Preserve existing secrets,
state and database; do not run a fresh installer over an installation.

Docker, using the actual existing protected configuration path:

```bash
python3 infra/install/upgrade.py --method docker_compose \
  --env-file /srv/atlas-current/.env --validate-only
python3 infra/install/upgrade.py --method docker_compose \
  --env-file /srv/atlas-current/.env --backup-confirmed
```

Create/download an encrypted backup before the replacement command. Keep the
old package/configuration directory and Compose project identity; volumes stay.

Native, from the new verified package outside `/opt/atlas`:

```bash
sudo python3 infra/install/upgrade.py --method systemd --validate-only
```

Create/download the encrypted backup and retain its passphrase separately, then:

```bash
sudo python3 infra/install/upgrade.py --method systemd --backup-confirmed
systemctl status nginx atlas-api atlas-web atlas-worker
```

Confirm `/api/health`, login/MFA, representative data and About version/build.
There is no automatic code/schema rollback or self-update. Configuration and
target-local secrets remain intact. CLI help/errors now use product terminology.

## 11. Security and support routes

Support uses existing GitHub Issues for reproducible bugs/feature discussion.
Templates request version/install context, reproduction and redacted diagnostics.
Private security reporting is **not established in repository evidence**.
SECURITY.md asks users to request a private route through the existing owner
identity before sharing sensitive details and forbids exploitable public reports.
No private email, enabled Discussions/private-reporting feature or SLA is invented.
The owner must establish a usable private vulnerability-reporting route.

## 12. About UI

The existing System Settings About card retains installed version, channel,
build and method, using the shared installation labels. It adds AGPL-3.0-only
and fixed Source, Documentation, Security and Commercial licensing links.
It reuses `ops-card`, the section shell and `detail-list`; no bespoke CSS or
raw legal text. External links have `noopener noreferrer`. No remote fetch,
runtime Git, update-check duplication or backend metadata schema expansion.

## 13. Information architecture

The public documentation index now groups Getting started, Operations, Knowledge
and administration, Architecture, and Development. Historical records are mentioned
as a separate storage class without prominent links into the old milestone journey.
The public roadmap is `docs/product/status.md`; the detailed internal roadmap is
archived. Production guides have milestone-free names and stable product wording.
Later integrations/onboarding can extend guides and screenshots without rebuilding
the overall documentation structure.

## 14. Historical material

Old product brief, development roadmap, readiness audit, release plan, prior
detailed feature ledger, prompts and dated validation reports are classified
as historical. UI migration sequencing and obsolete split-origin migration
instructions are also retained outside active guidance. Accepted ADR decisions
are unchanged; the operational graph ADR receives only a relocated evidence link.
Original execution tables and milestone terminology remain intact. Subsequent
operator-supplied native restore/upgrade and hosted-CI confirmation is appended
to the backup, distribution and CI records rather than backdated into tables.

## 15. Package/release metadata

The package manifest now includes/requires LICENSE, commercial/security/support
policies and third-party notices, and requires the renamed operator guides.
Both package types contain current deployment guidance; internal history and
product plans are excluded. Web/plugin metadata and OCI labels agree on licence
and source identity. Canonical release version/channel/schema and publication
workflows are unchanged. Update guide URLs point to the renamed product guide;
API response schemas, routes and authorization contracts are preserved.

## 16. Tests and validation actually executed

Local runtime: Python 3.14.7, Node 24.19.0, PostgreSQL/client 17.11, Redis 7.4.6,
nginx 1.28.3 on macOS. CI retains its configured Python 3.12/Node 22 Linux gates.

| Executed command/check | Result |
| --- | --- |
| Focused `python -m pytest tests/test_repository_docs.py tests/test_markdown_docs.py tests/test_ci_workflow.py tests/test_updates.py tests/test_release_distribution.py -q` from apps/api | 112 passed using the complete temporary test venv. The initial repository venv run had 111 passes and one missing-cryptography environment error; rerun resolved it. |
| `python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests -q -rs --tb=short --junitxml=/private/tmp/atlas-public-backend.xml` through the disposable local infrastructure harness | 862 passed, zero skips, 142.15 seconds; real PostgreSQL/migration/Redis/nginx suites enabled. JUnit has no failures/errors. |
| `bash ../../infra/ci/release-critical.sh` from apps/api, with complete venv PATH and source plugin PYTHONPATH | 258 passed; final rerun after CLI/error wording change also 258 passed, 12.45 seconds. |
| Final `python -m pytest tests/test_repository_docs.py tests/test_ci_workflow.py tests/test_backups.py -q` | 48 passed; includes current metadata, active docs/link boundaries, issue forms and workflow contracts. |
| `npm test` from apps/web | 280 passed, zero failed/skipped. |
| `NEXT_TELEMETRY_DISABLED=1 npm run build` from apps/web | Production build passed. |
| `python -m compileall -q apps/api/app apps/api/scripts apps/api/tests infra/install infra/release` | Passed. |
| Alembic heads and single-head assertion in full infrastructure run | Single existing `20261004_0026` head. |
| `python3 infra/release/release.py build --dry-run --worktree --output /tmp/atlas-public-release-complete` and independent `verify --output /tmp/atlas-public-release-complete` | Both packages and manifest passed; explicitly non-publishable working-tree artifacts. |
| `shasum -a 256 -c SHA256SUMS` in the candidate output directory | Both package archives and manifest reported OK. |
| Markdown targets, fragments, active language and code fences; `git diff --check` | Passed; final documentation tests include the full local target scan. |

The full regression and browser harnesses use fresh loopback-only PostgreSQL,
Redis/nginx and random test credentials, remove disposable databases/processes
and secrets, and retain only protected diagnostic/artifact outputs. Existing
deprecation warnings remain. No dependency versions changed and npm audit was
not rerun; known historical findings are not claimed fixed. Docker daemon/image
builds and a real Linux systemd install/reboot were not run on this macOS host.
Their supplied acceptance is recorded as operator evidence, not local execution.
Hosted CI was not triggered by this uncommitted task; workflows were not changed.

## 17. Browser/visual acceptance

`node scripts/check-updates-browser.mjs` ran through the existing opt-in API update
harness on a disposable real Atlas API/PostgreSQL/Redis/nginx and production Next
build. 24 combinations passed: light/dark, default/blue/purple accents, widths
1440/1024/800/390. About licence/identity/links, sibling padding/radius/border/
background/heading parity and no page overflow were checked. Existing current/
newer/native/development/offline update states and refresh behaviour also passed.
No browser API interception, page exceptions or outside requests. The test-only
update transport uses local controlled release data; it is not a public GitHub
network test. Desktop light and mobile dark captures were visually inspected.
Artifacts: `/private/tmp/atlas-public-browser-2ox5dd3p/artifacts/report.json` and
theme/viewport PNGs there. These validation captures are not public product screenshots.

## 18. Security and legal consistency review

Review found no new credentials, setup codes, private inventory or production
host details in active documentation. New ingress address examples use reserved
documentation addresses. Installer commands execute local verified package code,
not downloaded root shell pipelines. Checksum guidance requires all matching
assets and distinguishes corruption checks from signatures. Production API/DB/
Redis exposure, proxy trust, cookie policy, scoped authorization and target-local
backup secrets remain intact. No unrestricted contribution/CLA, invented legal
entity or commercial promise; third-party licences are distinguished. Safe
external About links do not fetch remote content. Historical records preserve
their original context without becoming production guidance or package payload.

## 19. Remaining owner decisions and deferred work

- Establish a private vulnerability-reporting route. Existing project identity
  is sufficient to identify the maintainer, but is not itself a private mailbox.
- Integration/onboarding work, final feature screenshots/docs freeze and final
  dependency/whole-product security/release qualification remain the stated path
  toward 1.0.0. No date, publication or new acceptance claim is promised.

No database migration was required. API/UI routes and data schemas remain
compatible; only public wording, documentation links and licence/project metadata
change. Backend global permissions/customer/site isolation are untouched and
their regressions passed.

## 20. Repository state

`git status --short`:

```text
 M README.md
 M apps/api/Dockerfile
 M apps/api/app/services/backup_postgres.py
 M apps/api/app/services/updates.py
 M apps/api/scripts/backup.py
 M apps/api/tests/test_release_distribution.py
 M apps/api/tests/test_updates.py
 M apps/web/Dockerfile
 M apps/web/app/admin/system-settings/page.js
 M apps/web/package-lock.json
 M apps/web/package.json
 M apps/web/scripts/check-updates-browser.mjs
 M apps/worker/Dockerfile
 M docs/README.md
 M docs/admin/knowledge-profiles.md
 M docs/admin/service-types-and-criticality.md
 M docs/architecture/architecture-v0.md
 M docs/architecture/authentication-and-access-control.md
 M docs/architecture/data-model-v0.md
 M docs/architecture/dependency-analysis.md
 M docs/architecture/deployment-and-upgrades.md
 M docs/architecture/encrypted-backup-restore.md
 M docs/architecture/entity-lifecycle.md
 M docs/architecture/homelab-operations-experience.md
 M docs/architecture/knowledge-completeness.md
 M docs/architecture/local-two-factor-authentication.md
 M docs/architecture/operational-graph.md
 M docs/architecture/release-distribution.md
 M docs/architecture/service-dependencies.md
 M docs/architecture/service-model.md
 M docs/architecture/showcase.md
 M docs/architecture/ui-architecture.md
 M docs/decisions/0001-shared-operational-graph.md
 M docs/decisions/README.md
 D docs/deployment/h1-installation.md
 D docs/deployment/h2-mfa.md
 D docs/deployment/h3-backup-restore.md
 D docs/deployment/h4-releases.md
 D docs/deployment/h4-upgrades.md
 M docs/deployment/reverse-proxy-examples.md
 M docs/deployment/single-origin.md
 D docs/deployment/split-origin-migration.md
 M docs/history/implementation-prompts/README.md
 M docs/history/implementation-prompts/atlas-codex-context.md
 D docs/product/c2-readiness-audit.md
 D docs/product/development-roadmap.md
 M docs/product/feature-ledger.md
 D docs/product/mvp-brief.md
 D docs/product/release-c2-plan.md
 D docs/prompts/codex-system-instructions.md
 D docs/testing/asset-icon-cache.md
 M docs/testing/auth-shell-test-plan.md
 M docs/testing/continuous-integration.md
 D docs/testing/dependency-impact-ux.md
 D docs/testing/dependency-presentation-followup.md
 D docs/testing/expanded-knowledge-graph.md
 D docs/testing/h1-docker-ingress.md
 D docs/testing/h1-release-foundation.md
 D docs/testing/h2-local-two-factor-authentication.md
 D docs/testing/h3-encrypted-backup-restore.md
 D docs/testing/h4-release-distribution.md
 D docs/testing/homelab-service-mvp.md
 D docs/testing/infrastructure-topology-compact-pickers.md
 D docs/testing/infrastructure-topology-disclosure.md
 D docs/testing/infrastructure-topology-external-rails.md
 D docs/testing/infrastructure-topology-identity.md
 D docs/testing/infrastructure-topology-interactions.md
 D docs/testing/infrastructure-topology-layered-layout.md
 D docs/testing/infrastructure-topology-layers.md
 D docs/testing/infrastructure-topology-local-positions.md
 D docs/testing/infrastructure-topology-orthogonal-layout.md
 D docs/testing/infrastructure-topology-polish.md
 D docs/testing/infrastructure-topology-positions.md
 D docs/testing/infrastructure-topology-search.md
 D docs/testing/infrastructure-topology-stable-groups.md
 D docs/testing/infrastructure-topology-v0.md
 D docs/testing/interface-first-ip-transition.md
 D docs/testing/knowledge-completeness-v1.md
 D docs/testing/knowledge-foundation-v1.md
 D docs/testing/knowledge-foundation-v2.md
 D docs/testing/knowledge-graph-edge-routing.md
 D docs/testing/release-c2-entity-detail-ux-polish.md
 D docs/testing/release-c2-explainable-dependency-analysis.md
 D docs/testing/release-c2-homelab-operations-experience.md
 D docs/testing/release-c2-lean-dependency-semantics.md
 D docs/testing/release-c2-operational-graph.md
 D docs/testing/release-c2-usability-lifecycle-polish.md
 M docs/testing/security-and-access-test-plan.md
 D docs/testing/showcase-adaptive-width.md
 D docs/testing/showcase-compact-poster.md
 D docs/testing/showcase-networks-off.md
 D docs/testing/showcase-position-bands.md
 D docs/testing/showcase-routing.md
 D docs/testing/showcase-shared-geometry.md
 D docs/testing/showcase-typography-parity.md
 D docs/testing/showcase-upscale.md
 D docs/testing/showcase-visual-correctness.md
 D docs/testing/showcase.md
 D docs/testing/topology-audit-ui-polish.md
 D docs/testing/ui-system.md
 M infra/install/upgrade.py
 M infra/release/package-manifest.json
 M plugins/proxmox/pyproject.toml
 M plugins/sdk/pyproject.toml
?? .github/ISSUE_TEMPLATE/
?? .github/pull_request_template.md
?? COMMERCIAL-LICENSING.md
?? CONTRIBUTING.md
?? LICENSE
?? SECURITY.md
?? SUPPORT.md
?? THIRD-PARTY-NOTICES.md
?? apps/api/tests/test_repository_docs.py
?? apps/web/tests/about.test.mjs
?? docs/admin/administration.md
?? docs/deployment/backup-restore.md
?? docs/deployment/installation.md
?? docs/deployment/mfa.md
?? docs/deployment/releases.md
?? docs/deployment/upgrades.md
?? docs/development/
?? docs/history/README.md
?? docs/history/deployment/
?? docs/history/implementation-prompts/codex-system-instructions.md
?? docs/history/product-plans/
?? docs/history/product-reviews/feature-ledger-2026-10-04.md
?? docs/history/validation/
?? docs/product/status.md
```


## Material file inventory

| File | Purpose |
| --- | --- |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Useful bug/feature/PR guidance and redaction reminders; no workflow change. |
| `.github/ISSUE_TEMPLATE/config.yml` | Useful bug/feature/PR guidance and redaction reminders; no workflow change. |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Useful bug/feature/PR guidance and redaction reminders; no workflow change. |
| `.github/pull_request_template.md` | Useful bug/feature/PR guidance and redaction reminders; no workflow change. |
| `COMMERCIAL-LICENSING.md` | Public licence, commercial/contribution/security/support or third-party policy. |
| `CONTRIBUTING.md` | Public licence, commercial/contribution/security/support or third-party policy. |
| `LICENSE` | Public licence, commercial/contribution/security/support or third-party policy. |
| `README.md` | Public product overview and normal documentation journey. |
| `SECURITY.md` | Public licence, commercial/contribution/security/support or third-party policy. |
| `SUPPORT.md` | Public licence, commercial/contribution/security/support or third-party policy. |
| `THIRD-PARTY-NOTICES.md` | Public licence, commercial/contribution/security/support or third-party policy. |
| `apps/api/Dockerfile` | Standard first-party licence/source metadata; dependency versions unchanged. |
| `apps/api/app/services/backup_postgres.py` | Public CLI/error copy uses product terms; behaviour unchanged. |
| `apps/api/app/services/updates.py` | Renamed official upgrade-guide URL; response/authorization unchanged. |
| `apps/api/scripts/backup.py` | Public CLI/error copy uses product terms; behaviour unchanged. |
| `apps/api/tests/test_release_distribution.py` | Documentation, package, URL, metadata or About regression validation. |
| `apps/api/tests/test_repository_docs.py` | Documentation, package, URL, metadata or About regression validation. |
| `apps/api/tests/test_updates.py` | Documentation, package, URL, metadata or About regression validation. |
| `apps/web/Dockerfile` | Standard first-party licence/source metadata; dependency versions unchanged. |
| `apps/web/app/admin/system-settings/page.js` | About licence/project links and shared installation labels. |
| `apps/web/package-lock.json` | Standard first-party licence/source metadata; dependency versions unchanged. |
| `apps/web/package.json` | Standard first-party licence/source metadata; dependency versions unchanged. |
| `apps/web/scripts/check-updates-browser.mjs` | Documentation, package, URL, metadata or About regression validation. |
| `apps/web/tests/about.test.mjs` | Documentation, package, URL, metadata or About regression validation. |
| `apps/worker/Dockerfile` | Standard first-party licence/source metadata; dependency versions unchanged. |
| `docs/README.md` | Public product overview and normal documentation journey. |
| `docs/admin/administration.md` | Current administrator instructions and navigation. |
| `docs/admin/knowledge-profiles.md` | Current administrator instructions and navigation. |
| `docs/admin/service-types-and-criticality.md` | Current administrator instructions and navigation. |
| `docs/architecture/architecture-v0.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/authentication-and-access-control.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/data-model-v0.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/dependency-analysis.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/deployment-and-upgrades.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/encrypted-backup-restore.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/entity-lifecycle.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/homelab-operations-experience.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/knowledge-completeness.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/local-two-factor-authentication.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/operational-graph.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/release-distribution.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/service-dependencies.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/service-model.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/showcase.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/architecture/ui-architecture.md` | Current product language and truthful architecture/compatibility boundaries. |
| `docs/decisions/0001-shared-operational-graph.md` | Navigation/evidence links only; accepted decisions preserved. |
| `docs/decisions/README.md` | Navigation/evidence links only; accepted decisions preserved. |
| `docs/deployment/backup-restore.md` | Canonical supported installation/verification/upgrade/recovery guidance. |
| `docs/deployment/installation.md` | Canonical supported installation/verification/upgrade/recovery guidance. |
| `docs/deployment/mfa.md` | Canonical supported installation/verification/upgrade/recovery guidance. |
| `docs/deployment/releases.md` | Canonical supported installation/verification/upgrade/recovery guidance. |
| `docs/deployment/reverse-proxy-examples.md` | Canonical supported installation/verification/upgrade/recovery guidance. |
| `docs/deployment/single-origin.md` | Canonical supported installation/verification/upgrade/recovery guidance. |
| `docs/deployment/upgrades.md` | Canonical supported installation/verification/upgrade/recovery guidance. |
| `docs/development/from-source.md` | Separate source and maintainer workflows. |
| `docs/development/releasing.md` | Separate source and maintainer workflows. |
| `docs/history/README.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/deployment/split-origin-migration.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/implementation-prompts/README.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/implementation-prompts/atlas-codex-context.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/implementation-prompts/codex-system-instructions.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/product-plans/c2-readiness-audit.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/product-plans/development-roadmap.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/product-plans/mvp-brief.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/product-plans/release-c2-plan.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/product-plans/ui-migration-sequence.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/product-reviews/feature-ledger-2026-10-04.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/asset-icon-cache.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/continuous-integration.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/dependency-impact-ux.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/dependency-presentation-followup.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/expanded-knowledge-graph.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/h1-docker-ingress.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/h1-release-foundation.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/h2-local-two-factor-authentication.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/h3-encrypted-backup-restore.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/h4-release-distribution.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/homelab-service-mvp.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-compact-pickers.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-disclosure.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-external-rails.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-identity.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-interactions.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-layered-layout.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-layers.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-local-positions.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-orthogonal-layout.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-polish.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-positions.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-search.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-stable-groups.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/infrastructure-topology-v0.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/interface-first-ip-transition.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/knowledge-completeness-v1.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/knowledge-foundation-v1.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/knowledge-foundation-v2.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/knowledge-graph-edge-routing.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/public-product-documentation.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/release-c2-entity-detail-ux-polish.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/release-c2-explainable-dependency-analysis.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/release-c2-homelab-operations-experience.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/release-c2-lean-dependency-semantics.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/release-c2-operational-graph.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/release-c2-usability-lifecycle-polish.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/showcase-adaptive-width.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/showcase-compact-poster.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/showcase-networks-off.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/showcase-position-bands.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/showcase-routing.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/showcase-shared-geometry.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/showcase-typography-parity.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/showcase-upscale.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/showcase-visual-correctness.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/showcase.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/topology-audit-ui-polish.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/history/validation/ui-system.md` | Historical classification/evidence, relocated links or appended supplied results. |
| `docs/product/feature-ledger.md` | Concise public status or repository-grounded feature scope. |
| `docs/product/status.md` | Concise public status or repository-grounded feature scope. |
| `docs/testing/auth-shell-test-plan.md` | Active repeatable testing guidance, separated from dated execution evidence. |
| `docs/testing/continuous-integration.md` | Active repeatable testing guidance, separated from dated execution evidence. |
| `docs/testing/security-and-access-test-plan.md` | Active repeatable testing guidance, separated from dated execution evidence. |
| `infra/install/upgrade.py` | Public CLI/error copy uses product terms; behaviour unchanged. |
| `infra/release/package-manifest.json` | Require notices and renamed operator docs; keep history excluded. |
| `plugins/proxmox/pyproject.toml` | Standard first-party licence/source metadata; dependency versions unchanged. |
| `plugins/sdk/pyproject.toml` | Standard first-party licence/source metadata; dependency versions unchanged. |


## Moves and historical preservation

| Original path | Retained path |
| --- | --- |
| `docs/deployment/h1-installation.md` | `docs/deployment/installation.md` |
| `docs/deployment/h2-mfa.md` | `docs/deployment/mfa.md` |
| `docs/deployment/h3-backup-restore.md` | `docs/deployment/backup-restore.md` |
| `docs/deployment/h4-releases.md` | `docs/deployment/releases.md` |
| `docs/deployment/h4-upgrades.md` | `docs/deployment/upgrades.md` |
| `docs/deployment/split-origin-migration.md` | `docs/history/deployment/split-origin-migration.md` |
| `docs/product/c2-readiness-audit.md` | `docs/history/product-plans/c2-readiness-audit.md` |
| `docs/product/development-roadmap.md` | `docs/history/product-plans/development-roadmap.md` |
| `docs/product/feature-ledger.md` | `docs/history/product-reviews/feature-ledger-2026-10-04.md` |
| `docs/product/mvp-brief.md` | `docs/history/product-plans/mvp-brief.md` |
| `docs/product/release-c2-plan.md` | `docs/history/product-plans/release-c2-plan.md` |
| `docs/prompts/codex-system-instructions.md` | `docs/history/implementation-prompts/codex-system-instructions.md` |
| `docs/testing/asset-icon-cache.md` | `docs/history/validation/asset-icon-cache.md` |
| `docs/testing/dependency-impact-ux.md` | `docs/history/validation/dependency-impact-ux.md` |
| `docs/testing/dependency-presentation-followup.md` | `docs/history/validation/dependency-presentation-followup.md` |
| `docs/testing/expanded-knowledge-graph.md` | `docs/history/validation/expanded-knowledge-graph.md` |
| `docs/testing/h1-docker-ingress.md` | `docs/history/validation/h1-docker-ingress.md` |
| `docs/testing/h1-release-foundation.md` | `docs/history/validation/h1-release-foundation.md` |
| `docs/testing/h2-local-two-factor-authentication.md` | `docs/history/validation/h2-local-two-factor-authentication.md` |
| `docs/testing/h3-encrypted-backup-restore.md` | `docs/history/validation/h3-encrypted-backup-restore.md` |
| `docs/testing/h4-release-distribution.md` | `docs/history/validation/h4-release-distribution.md` |
| `docs/testing/homelab-service-mvp.md` | `docs/history/validation/homelab-service-mvp.md` |
| `docs/testing/infrastructure-topology-compact-pickers.md` | `docs/history/validation/infrastructure-topology-compact-pickers.md` |
| `docs/testing/infrastructure-topology-disclosure.md` | `docs/history/validation/infrastructure-topology-disclosure.md` |
| `docs/testing/infrastructure-topology-external-rails.md` | `docs/history/validation/infrastructure-topology-external-rails.md` |
| `docs/testing/infrastructure-topology-identity.md` | `docs/history/validation/infrastructure-topology-identity.md` |
| `docs/testing/infrastructure-topology-interactions.md` | `docs/history/validation/infrastructure-topology-interactions.md` |
| `docs/testing/infrastructure-topology-layered-layout.md` | `docs/history/validation/infrastructure-topology-layered-layout.md` |
| `docs/testing/infrastructure-topology-layers.md` | `docs/history/validation/infrastructure-topology-layers.md` |
| `docs/testing/infrastructure-topology-local-positions.md` | `docs/history/validation/infrastructure-topology-local-positions.md` |
| `docs/testing/infrastructure-topology-orthogonal-layout.md` | `docs/history/validation/infrastructure-topology-orthogonal-layout.md` |
| `docs/testing/infrastructure-topology-polish.md` | `docs/history/validation/infrastructure-topology-polish.md` |
| `docs/testing/infrastructure-topology-positions.md` | `docs/history/validation/infrastructure-topology-positions.md` |
| `docs/testing/infrastructure-topology-search.md` | `docs/history/validation/infrastructure-topology-search.md` |
| `docs/testing/infrastructure-topology-stable-groups.md` | `docs/history/validation/infrastructure-topology-stable-groups.md` |
| `docs/testing/infrastructure-topology-v0.md` | `docs/history/validation/infrastructure-topology-v0.md` |
| `docs/testing/interface-first-ip-transition.md` | `docs/history/validation/interface-first-ip-transition.md` |
| `docs/testing/knowledge-completeness-v1.md` | `docs/history/validation/knowledge-completeness-v1.md` |
| `docs/testing/knowledge-foundation-v1.md` | `docs/history/validation/knowledge-foundation-v1.md` |
| `docs/testing/knowledge-foundation-v2.md` | `docs/history/validation/knowledge-foundation-v2.md` |
| `docs/testing/knowledge-graph-edge-routing.md` | `docs/history/validation/knowledge-graph-edge-routing.md` |
| `docs/testing/release-c2-entity-detail-ux-polish.md` | `docs/history/validation/release-c2-entity-detail-ux-polish.md` |
| `docs/testing/release-c2-explainable-dependency-analysis.md` | `docs/history/validation/release-c2-explainable-dependency-analysis.md` |
| `docs/testing/release-c2-homelab-operations-experience.md` | `docs/history/validation/release-c2-homelab-operations-experience.md` |
| `docs/testing/release-c2-lean-dependency-semantics.md` | `docs/history/validation/release-c2-lean-dependency-semantics.md` |
| `docs/testing/release-c2-operational-graph.md` | `docs/history/validation/release-c2-operational-graph.md` |
| `docs/testing/release-c2-usability-lifecycle-polish.md` | `docs/history/validation/release-c2-usability-lifecycle-polish.md` |
| `docs/testing/showcase-adaptive-width.md` | `docs/history/validation/showcase-adaptive-width.md` |
| `docs/testing/showcase-compact-poster.md` | `docs/history/validation/showcase-compact-poster.md` |
| `docs/testing/showcase-networks-off.md` | `docs/history/validation/showcase-networks-off.md` |
| `docs/testing/showcase-position-bands.md` | `docs/history/validation/showcase-position-bands.md` |
| `docs/testing/showcase-routing.md` | `docs/history/validation/showcase-routing.md` |
| `docs/testing/showcase-shared-geometry.md` | `docs/history/validation/showcase-shared-geometry.md` |
| `docs/testing/showcase-typography-parity.md` | `docs/history/validation/showcase-typography-parity.md` |
| `docs/testing/showcase-upscale.md` | `docs/history/validation/showcase-upscale.md` |
| `docs/testing/showcase-visual-correctness.md` | `docs/history/validation/showcase-visual-correctness.md` |
| `docs/testing/showcase.md` | `docs/history/validation/showcase.md` |
| `docs/testing/topology-audit-ui-polish.md` | `docs/history/validation/topology-audit-ui-polish.md` |
| `docs/testing/ui-system.md` | `docs/history/validation/ui-system.md` |

The UI migration sequence was extracted from the active UI architecture to
`docs/history/product-plans/ui-migration-sequence.md`. The original CI execution
narrative is retained in `docs/history/validation/continuous-integration.md`.
