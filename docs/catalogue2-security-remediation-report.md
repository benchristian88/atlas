# Catalogue 2 — independent acceptance remediation

Date: 4 November 2026 (Pacific/Auckland).

## Result and authority boundary

H1, H2 and M1 are remediated as inactive implementation candidates on the existing
`feature/catalogue-v2-consumption` and `feature/catalogue-v2-publication-evidence`
branches. No owner approval record, authority pin, enabled publication gate or
active workflow was changed. No commit, push, PR, merge, release, publication,
signing, deployment, live installation or LXC access occurred. Package activation
and discovery in regression tests use temporary stores and synthetic source I/O.

The implementation is eligible for inactive PR review after the validation below;
this report supplies no Publisher activation or installation authorization. The
proposed ADR 0018 decisions and genuine successor/live qualification remain open.

## H1 — anonymous request budget

The original adapter was reproduced before edits: fresh 1→2 retrieval made 62 REST
API requests and the installation download adapter made nine, **71 combined**.
The baseline source and both working trees were preserved under
`/private/tmp/atlas-catalogue2-remediation/baseline` before remediation.

The permanent PostgreSQL regression now performs fresh transactional 1→2 refresh
followed by normal route activation of the genuine, unchanged Proxmox 0.2.2 package:

| Requests actually counted at the HTTP session boundary | Count |
| --- | ---: |
| Refresh REST API GETs | 34 |
| Installation REST API GETs | 6 |
| Combined REST API requests | **40** |
| Constructed official release download GETs | 14 |
| Distribution GETs following their redirects | 14 |
| All HTTP GETs, including distribution | **68** |

The before/after REST comparison is **62 → 34** for refresh and **9 → 6** for
installation. The after regression includes the complete normal installation
route and final runtime/package verification, rather than counting only its
download helper. Baseline reproduction uses the preserved original implementations;
neither before nor after measurement contacts GitHub or a live source.

This leaves twenty REST requests below GitHub's ordinary sixty-request anonymous
hourly allowance. It does not promise immunity to other instances sharing an IP,
secondary limits, retries or a depleted allowance. Backoff remains authoritative.
Asset/CDN traffic is explicitly counted; it is not represented as eliminated traffic.

Each refresh owns one bounded, public observation set. Every original latest run,
attempt one, actor/account, workflow, source CI, repository, environment, App and
ruleset validation still executes. Repeated reads of that same set reuse encoded
bytes and decode a new object for each validator. Created-at checks use those
same independently fetched original run records. Failure responses never enter
the set. Each reader clears its state on close/reentry, rejects reuse past its
deadline and caps observations at 128 entries/four MiB. Separate operations and
concurrent refreshes share no reader state or cache. No persistent cache exists.

Git transport reconstructs and authenticates the exact two-regular-file tree from
the independently checked original blob bytes and the commit's tree hash. Extra
entries, changed modes/names and substituted blobs still reject, without a redundant
tree-listing request. The root remains parentless and independently pinned; future
commits remain single-parent with contiguous signed predecessor digests.

The initial numeric release/asset REST inventory still binds IDs, names, immutable
state, source, digest, size and official URLs. Future release identity is independently
read back by tag after download and compared using stable fields, including checked
App actors. The exact approved immutable root identity/bytes are reused within the
operation. Download counters are not immutable identity. The final current-selection
ref is always an uncached GET, both for refresh and for installation.

Only byte transfer uses an application-constructed official
`github.com/benchristian88/atlas-connectors/releases/download/TAG/NAME` route instead
of a REST asset request that redirects to the same distribution service. Provider
URLs do not select destinations. Strict route, public DNS, HTTPS, redirect, size,
digest and genuine signature controls remain. Numeric identity is not inferred
from a filename. The frozen bootstrap-only adapter retains its numeric download path.

Permanent regressions cover request counts, concurrent independent chains, real
PostgreSQL refresh coalescing, failed/transient requests, immutable identity
substitution, tree integrity, route escapes, observation mutation/expiry/reentry,
uncached final-ref changes and failed-operation invalidation. Remote locked
reselection tests model refresh-in-progress, invalidated currentness and withdrawal
after download, preserving the previous active identity and activation audit.

Code references: `apps/api/app/services/catalogue_chain.py:31` (reader lifetime),
`:53` (observations), `:68` (numeric asset binding), `:78` (byte transfer),
`:170` (complete chain), `:248` (original-run timestamps), `:261` (immutable
readback), and `:272` (uncached current). The exact-tree implementation is
`apps/api/app/services/official_catalogue_ingestion.py:95`; strict download
routing is `apps/api/app/services/catalogue_source.py:69`. The combined regression
is `apps/api/tests/test_catalogue_request_budget.py:33`, and locked reselection
cases are `apps/api/tests/test_remote_connector_packages.py:199`.

## H2 — admission before immutable finalization

The original +600-second case was independently reproduced: it raised
`archive_publication_time` after making the successor immutable, while leaving
current unchanged. With the fix, the same case raises
`archive_finalization_deadline` before PATCH: draft remains true, immutable remains
false, no finalization is observed and current remains unchanged.

The original signed preflight/selection binding supplies the latest authenticated
selection witness. Immediately after the last potentially slow source-tag read,
the Publisher requires the current runner time plus a fixed thirty-second reserve
to fit within the original publication window. The reserve covers the existing
twenty-second request timeout plus ten seconds of scheduling/clock headroom. It
does not extend either proposed 900/300-second limit or the same-job lifetime.
Exactly thirty seconds remaining is permitted; less headroom rejects. Clock
rollback before the witness and invalid clocks reject.

Actual provider `published_at`, immutable state, original bytes and identities are
still independently verified afterward. A provider can delay or complete an
ambiguous write after local admission/timeout. The new regression demonstrates
that a resulting late immutable release still cannot advance current. No local
margin creates a distributed transaction or repairs such an immutable release.
Preserve evidence and stop for a separately reviewed disposition; cross-job
recovery remains disabled and no retrospective exception is introduced.

## M1 — successor workflow readiness

The generator now consumes byte-pinned historical S4 templates outside the active
workflow directory. Later adoption cannot make generation depend on the caller
it is replacing. The old S4 trust, token, admission and bootstrap assertions remain
exercised against preserved historical inputs. The active seven workflows and
trust/policy files remain independently protected by the original preservation
regression; their bytes and production authority are unchanged.

Existing security tests also exercise the generated successor profile. Additional
tests assert independent full-SHA signer/checkout/environment pins, source C as
data, original preflight download and authorization before token minting, exact
baseline permissions, no inherited secrets, publish-only inputs and commands,
acceptance-only skip and the separate unset publication gate. Generated unsupported
bootstrap/recovery steps and temporary Workflows permission input are removed.
The driver still rejects recovery even with a valid synthetic test-only approval.

Both Publisher and candidate-build CLI outputs are tested for exclusive creation,
inactivity and unchanged live controls. Security mutations of pins, source,
ordering, gates, permissions, commands and secret placement must fail the same
successor assertions. The build candidate signs only the shared candidate registry
through the existing catalogue-build profile, without Publisher credentials.
Historical and successor profiles are both exercised; no production pin is inferred
or automatically accepted. A later adoption PR must deliberately update the
active-control preservation fingerprints as part of its separate pin review.

## Files and compatibility

Atlas remediation files:

- `catalogue_source.py`: restricted constructed-release transport opt-in.
- `official_catalogue_ingestion.py`: exact tree reconstruction and reuse of an
  already retrieved release observation through the same validator.
- `catalogue_chain.py`: bounded operation observations, numeric asset binding,
  original-byte downloads, immutable identity reuse/readback and uncached current.
- `test_catalogue_future.py`: HTTP-only fixture supports/counts real release redirects.
- `test_catalogue_request_budget.py`: new budget, isolation, failure and integrity tests.
- `test_remote_connector_packages.py`: post-download locked reselection regressions.
- `infra/ci/run-catalogue2-tests.py`: include request-budget tests in Docker security acceptance.
- This report, the prior engineering report, proposed ADR, runbook and feature ledger:
  truthful remediation and still-inactive authority boundaries.

The companion producer report inventories its timing, workflow generation,
historical template and regression changes. All previous development remains in
the working trees. No database migration, SDK/package format, public route or
request/response contract changed. No frontend source changed during remediation.
Global package administration, customer/site configuration isolation, secret-safe
forms, exact runtime dependencies, mappings, rollback/activation and local operator
authority retain their existing owners and checks. PostgreSQL remains authoritative.

## Validation

Evidence directory: `/private/tmp/atlas-catalogue2-remediation`.

| Executed validation | Result |
| --- | --- |
| Complete Atlas API `pytest tests` with PostgreSQL 17, Redis, exact isolated runtime and nginx 1.28.3 | **2,770 passed**, zero failed/errors; 83 root-only host skips |
| Disposable Docker/Python 3.12 security acceptance, `infra/ci/run-catalogue2-tests.py` | **205 passed, zero skipped**, including all 83 root-only tests |
| Request-budget, isolation and failure module within both runs | **18 passed**; combined normal refresh/install **40 REST requests** |
| Future-chain and remote-package modules within both runs | **47 + 24 passed** |
| Actual nginx gateway cases within complete API run | **68 passed**, no nginx skips |
| Complete producer `pytest` suite | **2,897 passed**, zero failed/errors/skipped |
| `npm test`, complete frontend suite | **331 passed**, zero skipped |
| `npm run build`, production Next.js build | Passed |
| `node scripts/check-integrations-browser.mjs`, production build / synthetic API | **576 passed** |
| `node scripts/check-catalogue2-browser.mjs`, production build / synthetic API | **8 passed** |
| Alembic heads | Single existing head `20261101_0032`; no migration added |
| Seven active and two generated workflow candidates, actionlint 1.7.12 | Passed; shellcheck/pyflakes disabled |
| Both `git diff --check` checks and remediation-file whitespace scan | Passed |
| Prior work and authority audit | All 34 Atlas / 17 producer baseline files retained; 27 frozen producer controls byte-identical; approval records unset |

Focused module counts are subsets of the complete suites. The Docker run executes
every host root-only skip, so no API test remains undemonstrated because of a host
skip. Host Python is 3.14; Docker security acceptance uses production Python 3.12.
Hosted complete-suite Python 3.12 CI is still required. The host API run reports
9,886 dependency deprecation/field-metadata warnings, without test failures.
The producer run reports 180 Ansible dependency deprecation warnings.

The final API command was `python -B -m pytest -q -rs -p no:cacheprovider tests
--tb=short --junitxml=.../atlas-complete.xml`, with only newly generated protected
test-database URLs and loopback Redis supplied through the existing test environment
variables. The Docker runner asserts no failed, errored or skipped test cases.
Docker commands explicitly used the local Docker Desktop Unix socket and the new
`atlas-catalogue2-remediation-local` project; no LXC or existing project was accessed.
The gateway binary was built in temporary storage from the existing CI-pinned
nginx source archive. Browser tests intercepted API traffic and contacted only the
temporary loopback frontend server.

Earlier attempts exposed disposable-environment problems: host Redis reachability,
an installed `typing_extensions` version different from the unchanged runtime pin,
and migration databases that must be empty on every run. These were corrected only
in temporary infrastructure, and the complete final suite used fifteen newly
created databases. A reused-database rerun was interrupted and replaced; no test
assertion was relaxed. Original logs and final XML remain alongside the preserved
baseline. The temporary servers/containers and generated test credentials were
removed after validation.

Evidence files include `h1-before-combined.log`, `h2-before.log`, `h2-after.log`,
`atlas-complete.xml`, `connectors-full-final.xml`, `docker-security.log`,
`web-tests.log`, `web-build.log`, both browser logs/reports and `preservation.json`.

## Remaining risks and PR assessment

The current implementation is suitable for inactive implementation PRs after its
local regression results are reviewed. Hosted Python 3.12 CI and independent
security reacceptance remain required. No live workflow was adopted or dispatched.
Owner decisions, a frozen reviewed successor S, independent pins, genuine successor
signing/isolation and full published seven-asset evidence remain activation gates.
Separate Atlas executable eligibility and authorized Docker/source qualification
remain installation gates. Synthetic future verified output is not genuine future
cryptographic evidence; unchanged bootstrap and package fixtures use real crypto.

The initial release retains disabled cross-job recovery, bounded complete-history
retrieval and Docker-only remote writing. No new administrative credentials,
permission expansion, persistent cache, authority service or recovery exception
was introduced. Both original feature branches and HEADs remain unchanged.

The shortest safe continuation is inactive PR review, hosted CI and independent
security reacceptance; then explicit resolution of the proposed ADR 0018 temporal
and preflight/selection binding decisions. Keep the proposed 900/300 limits and
disabled recovery boundary. Freeze and review successor S independently, review
its exact workflow/policy/identity pins and demonstrate genuine successor signing,
isolation and seven-asset publication before separately enabling publication.
Atlas remote executable eligibility and authorized disposable Docker/source
qualification remain separate prerequisites to live installation. None of these
steps is authorized or performed by this remediation report.

## Repository state

`git status --short` (includes all preserved pre-remediation development):

```text
 M apps/api/app/routes/integration_connections.py
 M apps/api/app/routes/integrations.py
 M apps/api/app/services/catalogue_source.py
 M apps/api/app/services/connector_catalogue.py
 M apps/api/app/services/official_catalogue_ingestion.py
 M apps/api/app/services/trusted_catalogue.py
 M apps/api/tests/test_catalogue_backup_postgres.py
 M apps/api/tests/test_integration_catalogue_api.py
 M apps/web/app/integrations/page.js
 M apps/web/components/integration-panels.js
 M apps/web/components/official-catalogue.js
 M apps/web/lib/integrations.mjs
 M apps/web/tests/integrations.test.mjs
 M docs/decisions/README.md
 M docs/deployment/official-catalogue.md
 M docs/product/feature-ledger.md
?? apps/api/app/services/catalogue_chain.py
?? apps/api/app/services/catalogue_future_authorization.py
?? apps/api/app/services/publication_contracts/
?? apps/api/app/services/remote_connector_packages.py
?? apps/api/tests/fixtures/future_publication/
?? apps/api/tests/test_catalogue_future.py
?? apps/api/tests/test_catalogue_request_budget.py
?? apps/api/tests/test_remote_connector_packages.py
?? apps/web/scripts/check-catalogue2-browser.mjs
?? docs/catalogue2-engineering-report.md
?? docs/catalogue2-security-remediation-report.md
?? docs/decisions/0018-catalogue-durable-publication-evidence.md
?? docs/deployment/catalogue2.md
?? infra/ci/run-catalogue2-tests.py
```
