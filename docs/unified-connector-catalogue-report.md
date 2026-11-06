# Unified Connector catalogue — engineering report

Date: 6 November 2026 (Pacific/Auckland)
Branch: `feature/unified-connector-catalogue`
Base HEAD: `c3039a6b62322ae848241be8669634f5ca17ac5d`
Readiness: **PASS for human commit/PR review**. No commits, pushes, PRs, merges or deployments performed.

## Result and metadata reconciliation

Integrations → Catalogue now has one responsive card per Connector identity,
using the established Atlas card, identity, status, filter and button components.

The single presentation reconciliation layer chooses the installed package's
locally verified Manifest metadata first, otherwise the newest active accepted
official release, otherwise the bundled entry. Installed and available versions
remain distinct. Semantic version precedence handles future releases and
prereleases without Connector-specific or catalogue-sequence-specific rules.
Digests, verification state and action authority stay attached to their original
package objects. Withdrawn and historical official versions and bundled packages
remain in expandable card history. Docker and UniFi retain planned metadata-only
cards until an executable official release exists.

With accepted Catalogue 2 and the installed-package projection, Proxmox presents
0.2.2, Installed and Verified, with its actual inventory-discovery description.
Withdrawn 0.2.0 and bundled 0.1.0 remain in history. Installed packages and
installed-only identities remain visible when official status is unavailable.
Local verification failures retain the installed identity with an explicit warning.

The restrained status area shows sequence, historical confirmation and the outcome
of an explicit authenticated check. Reloading displayed state does not check the
remote source. Publication evidence and detailed timestamps remain expandable.

## Exact changed files

| File | Purpose |
| --- | --- |
| `apps/api/app/routes/integrations.py` | Add global-runtime-view-only `installed_entries` to the existing catalogue response. |
| `apps/api/app/services/connector_catalogue.py` | Read selected installed Manifest fields after existing local PackageStore verification; isolate verification failures. |
| `apps/api/tests/test_integration_catalogue_api.py` | Cover additive API compatibility, global versus scoped access, real temporary-store integrity, offline metadata and unresolved mappings. |
| `apps/web/app/integrations/page.js` | Compose the unified catalogue; clear denied local responses. |
| `apps/web/app/integrations/integrations.module.css` | Responsive card actions, status area and history styling using existing tokens. |
| `apps/web/components/integration-panels.js` | Reuse ConnectorCard for all sources; display status, history, exact mappings and package actions. |
| `apps/web/components/official-catalogue.js` | Coordinate unified search/cards and retained official-status/install lifecycle; expand exact selection review. |
| `apps/web/lib/integrations.mjs` | Reconcile intact source identities; normalize official card metadata and order versions. |
| `apps/web/lib/status.mjs` | Register the withdrawn lifecycle label centrally. |
| `apps/web/scripts/check-catalogue2-browser.mjs` | Expand production-browser acceptance to unified states, future releases, offline use, permissions, confirmation, mappings and cooldown. |
| `apps/web/scripts/check-integrations-browser.mjs` | Adapt existing navigation/status/runtime regressions to unified cards and updated controls. |
| `apps/web/tests/integrations.test.mjs` | Update presentation contracts and cover reconciliation, history, future versions, authority isolation and offline failures. |
| `docs/deployment/official-catalogue.md` | Document the unified UI, additive installed projection and preserved authority boundaries. |
| `docs/product/feature-ledger.md` | Record the implemented catalogue presentation without expanding operational-qualification claims. |
| `docs/unified-connector-catalogue-report.md` | This review and validation record. |

## Database, compatibility and security

No migrations, persisted schema changes or new installation APIs were required.
Existing routes and catalogue `entries` remain intact. `installed_entries` is an
additive display-only field and is empty without a global runtime-view grant.
Customer/site runtime grants cannot disclose that metadata or authorize package
management. Configured integrations retain their existing scoping.

Official installation still submits the exact backend-approved Connector/version,
package digest, catalogue sequence/digest and numeric release asset with explicit
confirmation. The unchanged backend independently verifies selection, freshness,
provenance, package integrity, compatibility, mappings, dependent configuration,
activation and audit. UI reconciliation cannot confer installation authority.
Mappings target the installed version when present. Identical installed tuples do
not display a redundant remote installation action.

Published Catalogue 1/2, packages, Manifests, release-owned policies, Sigstore,
signed-history verification, PackageStore security and migrations were not changed.
No protected test Docker or development LXC was contacted or modified.

## Executed validation

- `cd apps/web && node --test tests/integrations.test.mjs tests/integration-configuration.test.mjs`: **22 passed**.
- `cd apps/web && npm test`: **335 passed**.
- `cd apps/web && npm run build`: **passed**, production Next.js compilation and page generation.
- `PYTHONPATH=apps/api:plugins/sdk:plugins/proxmox apps/api/.venv/bin/python -m pytest apps/api/tests/test_integration_catalogue_api.py -q`: **37 passed**.
- `PYTHONPATH=apps/api:plugins/sdk:plugins/proxmox apps/api/.venv/bin/python -m pytest apps/api/tests/test_repository_docs.py -q`: **14 passed**.
- `cd apps/web && node scripts/check-catalogue2-browser.mjs`, with the local Playwright module and Chrome path: **336 viewport/theme/accent/state checks passed**, plus real React search, mapping navigation/update, checkbox confirmation, failure handling, exact request-body/header checks and refresh/cooldown interactions.
- `cd apps/web && node scripts/check-integrations-browser.mjs`, with the same browser environment: **576 checks passed**, including unchanged Configured/Runtime behavior, refresh result/error cases, stale-response isolation, navigation and shared-surface comparison.
- `git diff --check`: **clean**.

Both browser scripts used the local production build at `http://127.0.0.1:3137`
and intercepted API fixtures. They did not perform a real remote check, package
installation or source discovery. The current Proxmox description was taken from
the existing package Manifest fixture. The matrix covered 1440, 1024, 800 and 390 px;
light/dark mode; default, blue and purple accents; accepted, unaccepted,
unavailable, stale, withdrawn, cooldown, future and permission-limited states.
Desktop and mobile screenshots were visually inspected, including dark mode.
No page overflow or clipped catalogue controls was found.

An exploratory combined API/remote-package test run had 26 PostgreSQL-dependent
remote cases skipped because no disposable test database was configured. Those
cases are not claimed as validated. The directly affected API suite subsequently
passed in full. The full historical cryptography/publication suite and live
installation/operational qualification were not rerun.

## Browser artifacts

- Unified results: `/private/tmp/atlas-unified-catalogue-browser/report.json`
- Existing integration results: `/private/tmp/atlas-i1-ui-browser/report.json`
- Desktop light: `/private/tmp/atlas-unified-catalogue-browser/1440-light-installed.png`
- Mobile light: `/private/tmp/atlas-unified-catalogue-browser/390-light-installed.png`
- Desktop dark: `/private/tmp/atlas-unified-catalogue-browser/1440-dark-installed.png`
- Mobile dark: `/private/tmp/atlas-unified-catalogue-browser/390-dark-installed.png`
- Additional future-release and offline screenshots are in the same directory.

## Remaining issues and repository state

No unresolved implementation issues were found within this task. Browser fixtures
and local verification tests do not establish live deployment or discovery readiness.
The unrelated PostgreSQL-only remote cases remain unexecuted as described above.
Changes are uncommitted. Final `git status --short`:

```text
 M apps/api/app/routes/integrations.py
 M apps/api/app/services/connector_catalogue.py
 M apps/api/tests/test_integration_catalogue_api.py
 M apps/web/app/integrations/integrations.module.css
 M apps/web/app/integrations/page.js
 M apps/web/components/integration-panels.js
 M apps/web/components/official-catalogue.js
 M apps/web/lib/integrations.mjs
 M apps/web/lib/status.mjs
 M apps/web/scripts/check-catalogue2-browser.mjs
 M apps/web/scripts/check-integrations-browser.mjs
 M apps/web/tests/integrations.test.mjs
 M docs/deployment/official-catalogue.md
 M docs/product/feature-ledger.md
?? docs/unified-connector-catalogue-report.md
```
