# C2.3 Explainable Dependency Analysis validation and acceptance

Status: implemented on the feature working tree; **subsequent live LXC acceptance complete**.
C2.1, C2.2 and C2.3 are complete. C2.4 is next/planned; F1-lite, B2-lite and
Homelab Ready remain undelivered.

## Implementation-time context

The following context, automated evidence and original manual checklist are
preserved from the implementation report. Statements about pending manual work
describe that report's historical validation boundary. Actual later results are
recorded separately under [Subsequent live LXC acceptance](#subsequent-live-lxc-acceptance).

Implementation-report status (historical):

> Status: implemented on the feature working tree; **test-LXC acceptance pending**.
> C2.1 and C2.2 remain complete. C2.4 and Homelab Ready remain planned.

Branch: `feature/c2-3-explainable-dependency-analysis`.
Base: `1b7077a80b6a2898c9cc6cc64228242439cf80b1`, the C2.2 merge on `dev`.
Remote `refs/heads/dev` was verified at that commit before implementation.
No commit, push or migration is part of this increment.

See [analysis architecture](../architecture/dependency-analysis.md) for the
versioned contract, assumptions, exact evaluation rules and limits.

## Automated coverage

`apps/api/tests/test_dependency_analysis.py` covers Asset/Service focus, all three
failure effects, Required/Optional, ungrouped uncertainty, complete `all`/`any`
sets and alternatives, multi-hop/diamond paths, conservative aggregation,
degraded propagation, delayed explicit consequences, cycles, stable ordering,
current-valid temporal rules, ended memberships/dependencies, structural Asset
and Business Function boundaries, Viewer API input validation and non-disclosing
404s, customer/site/mixed permissions, hidden intermediates/downstream Services,
partially authorized redundancy, and depth/result/path/node/edge limits.
Paths retain canonical edges and never contain missing intermediate nodes.

`test_dependency_analysis_postgres.py` runs against an explicitly configured
disposable database upgraded through Alembic. It commits only test fixtures,
then enforces PostgreSQL `SET TRANSACTION READ ONLY` for analysis. It checks
mixed Service/Asset redundancy and ended memberships/dependencies with real SQL.
The database must be disposable; the fixture records are intentionally committed.

Web tests exercise request construction/error propagation and presentation
labels. They also check the component's Viewer permission gating, reason/path
rendering, empty/truncated/error states, focus/workspace reset, keyboard controls
and live-region markup against the repository's existing Node test conventions.
Production compilation is checked separately. These tests do not claim a real
browser/device accessibility audit or deployed LXC acceptance.

## Commands and execution evidence

Executed on 8 September 2026 (commands run from the indicated directory):

| Directory | Command | Result |
| --- | --- | --- |
| `apps/api` | `.venv/bin/pytest -q tests/test_dependency_analysis.py tests/test_dependency_semantics.py tests/test_operational_graph.py` | **72 passed** (43 C2.3, 13 C2.2, 16 C2.1) |
| `apps/api` | `.venv/bin/pytest -q` with `ATLAS_TEST_DATABASE_URL` set to the disposable PostgreSQL socket database | **231 passed**, including the real PostgreSQL integration test |
| `apps/web` | `npm test` | **81 passed** |
| `apps/web` | `npm run build` | **passed**, 33 pages generated |
| root | `apps/api/.venv/bin/python -m pytest -q plugins/sdk` | **5 passed** |
| root | `PYTHONPATH=plugins/sdk:plugins/proxmox apps/api/.venv/bin/python -m pytest -q plugins/proxmox/tests` | **22 passed** |
| `apps/api` | `.venv/bin/python -m compileall -q app tests` | **passed** |
| `apps/api` | `.venv/bin/alembic heads` | **one head**, `20260908_0014` |
| `apps/api` | `.venv/bin/alembic upgrade head` with `DATABASE_URL` set to the disposable database | **passed**, fresh PostgreSQL 17 migration through all 14 revisions |
| root | `git diff --check` | **passed** |

The API reports 483 existing-library deprecation warnings (Starlette/AnyIO and
FastAPI on Python 3.14); no test failures. No separate Python lint/type tool is
configured by this repository. Compilation and Next.js's build checks passed.
Docker is not installed; native PostgreSQL 17 supplied the real database check.
Sandbox restrictions initially prevented shared memory/socket access; approved
execution outside the sandbox enabled the disposable local-only test cluster.
No production or test-LXC database was used. Without `ATLAS_TEST_DATABASE_URL`,
the opt-in PostgreSQL test is skipped; unit/API tests remain self-contained.

The new Markdown links were checked locally. Real browser/device accessibility
validation and deployed LXC acceptance remain manual work; no such pass is claimed.

## Manual test-LXC acceptance

Deploy the working tree to the test LXC through the normal deployment process.
No schema change is required beyond existing head `20260908_0014`. Sign in and
select the customer/site containing the real topology. Use actual IDs from the
detail page URLs; do not create artificial redundancy solely for acceptance.

For each scenario, open the specified detail page, find **Dependency analysis**,
and select **Preview unavailable**. Alternatively, send an authenticated
`POST /api/dependency-analysis` with normal Atlas context headers:

```json
{"focus_type":"service","focus_id":"<actual UUID>","state":"unavailable"}
```

Use `focus_type: "asset"` for an Asset. The response must retain the focus
separately, and each result must have stable Service identity, state, reasons
and complete paths. Paths run scenario→consequence; edge `source_key` remains
the dependent Service and `target_key` remains its provider.

1. **A — DNS Service unavailable.** Open **DNS Resolution and Filtering** at
   `/services/<DNS UUID>`. Preview unavailable. **Reverse Proxy and Application
   Publishing** must be **unavailable**, **direct**, distance 1, because its
   **Core Operation** group is Required + All required + Service unavailable.
   The reason must include both DNS and Nginx Proxy Manager as members, with
   DNS unavailable and Nginx Proxy Manager unaffected by this scenario.
2. **B — Nginx Proxy Manager unavailable.** Open its Asset detail at
   `/assets/<NPM UUID>` and preview unavailable. **Reverse Proxy and Application
   Publishing** must be **unavailable**, **direct**, distance 1, through the
   same Core Operation group.
3. **C — AdGuard Home with ungrouped DNS dependency.** Confirm on the DNS Service
   that **Provided by → AdGuard Home** remains ungrouped and shows Unknown.
   Open `/assets/<AdGuard UUID>` and preview unavailable. **DNS Resolution and
   Filtering** must be **unknown**, **direct**, with
   `ungrouped_consequence_unknown`. Reverse Proxy must be **unknown**,
   **downstream**, if DNS's unresolved state is its only affected member:
   degraded/unknown is not automatically unavailable.
4. **D — Explicit DNS provider effect.** As an operator permitted to manage
   dependencies, deliberately add a **Dependency behaviour** on the DNS Service
   selecting its existing AdGuard Home dependency: Required, All required,
   Service unavailable. This is a manual accepted-knowledge edit, separate from
   analysis. Preview AdGuard unavailable again. DNS must be **unavailable**,
   **direct**; Reverse Proxy must be **unavailable**, **downstream**, distance 2.
   The complete path is AdGuard ← Provided by — DNS ← Depends on — Reverse Proxy.
5. **Structural boundary.** Preview **PVE1** unavailable at `/assets/<PVE1 UUID>`.
   The **AdGuard Home Runs on PVE1** Asset relationship must not propagate an
   AdGuard/DNS/Proxy outage. Only independently recorded Service→PVE1 dependencies
   may yield results. Linked Business Functions receive no outage state.
6. **Viewer and scope.** Repeat A as a Viewer with appropriate view permissions;
   preview works without manage/edit controls. Substitute a different customer
   focus UUID in the API and expect `404 {"detail":"Record not found"}`. A
   site-restricted caller must receive no hidden Service, intermediate path,
   member ID/name, group metadata or inaccessible count. A partially visible
   `any` set cannot conclude all providers failed; it yields unknown when no
   authorized available alternative can establish satisfaction.
7. **Bounds and preservation.** After D, request AdGuard with `max_depth: 1`:
   only complete direct explanation paths appear and truncation is explicit.
   Try `max_results: 1`; any returned path must still embed all intermediate
   nodes and edges. Reload Asset/Service details after previews and verify their
   accepted operational state, dependencies and history have not changed.
8. **Readable UI.** At desktop and narrow/mobile widths, check wrapping, keyboard
   activation of Preview and Explanation paths, visible state words (not colour
   alone), error/empty/truncation messages, and the hypothetical/non-live wording.
   Switch workspace/focus and confirm the old analysis is cleared.

A/B/C/D are acceptance expectations based on the supplied real topology, not
claims that the deployed environment was inspected or these steps were executed.
`any` remains covered automatically if there is no genuine redundant provider
pair in the LXC.

## Subsequent live LXC acceptance

C2.3 completed live manual acceptance on the deployed PostgreSQL-backed test
LXC. The operator-reported results below are subsequent evidence, separate from
the implementation-time automated commands and the original checklist above.
Scenario labels A–E below identify the completed acceptance scenarios; they do
not mark every item in the original checklist as executed.

### Scenario A — direct Service consequence

With **DNS Resolution and Filtering = unavailable**, **Reverse Proxy and
Application Publishing** returned **unavailable**, **direct consequence**,
**1 hop**. Its persisted `Core Operation` behaviour was **Required**, **All
required**, **If unavailable → Service unavailable**.

The explanation showed Nginx Proxy Manager unaffected by this scenario and DNS
Resolution and Filtering unavailable. The dependency set was therefore
unsatisfied and applied the recorded `unavailable` failure effect. The path
preserved the actual Service dependency relationship and canonical direction;
it did not create a synthetic impact edge.

### Scenario B — explicit unknown

With **DNS Resolution and Filtering → AdGuard Home** still ungrouped and lacking
explicit failure-effect semantics, **AdGuard Home = unavailable** returned
**DNS Resolution and Filtering = unknown**, **direct consequence**, **1 hop**.
Atlas explained that the dependency exists but its operational consequence is
not known. It did not infer `unavailable` from `required_for_operation`.

### Scenario C — downstream unknown propagation

In the same AdGuard unavailable scenario, **Reverse Proxy and Application
Publishing** returned **unknown**, **downstream consequence**, **2 hops**.
DNS Resolution and Filtering was `unknown`, so Atlas could not determine whether
Reverse Proxy's **All required** `Core Operation` set was satisfied. This
confirmed conservative downstream propagation of unknown state.

### Scenario D — explicit multi-hop unavailable propagation

After configuring the existing DNS→AdGuard dependency with `DNS Provider`,
**Required**, **All required**, **If unavailable → Service unavailable**,
**AdGuard Home = unavailable** returned:

| Service | State | Classification | Distance |
| --- | --- | --- | --- |
| DNS Resolution and Filtering | `unavailable` | Direct consequence | 1 hop |
| Reverse Proxy and Application Publishing | `unavailable` | Downstream consequence | 2 hops |

Atlas consumed the persisted C2.2 semantics across both hops. The downstream
Reverse Proxy explanation retained `Core Operation`, **Required**, **All
required**, **If unavailable → Service unavailable**, with DNS the unavailable
member and Nginx Proxy Manager unaffected by this scenario. Configuring
`DNS Provider` was an explicit accepted-knowledge edit, separate from analysis.

### Scenario E — structural Asset relationship does not propagate failure

With **PVE1 = unavailable**, the result was **No Service consequences were
found**, despite the accepted structural **AdGuard Home → Runs on → PVE1**
Asset relationship.

No Service consequence was derived from current accepted C2.3 dependency
semantics. C2.3 has no authorized dependency semantics that justify a Service
consequence from this scenario; arbitrary Asset→Asset structural relationships
are not operational failure rules. This is not evidence that a real PVE1
failure has no real-world consequence.

### Cross-tenant non-disclosure — security regression pass

A principal in another tenant attempted direct access to the AdGuard Asset and
received the normal non-disclosing **Record not found** response. The C2.3
analysis surface was therefore not reachable and no analysis information was
exposed. This records the observed access boundary; it does not claim a separate
manual call to the analysis API or a site-isolation exercise.

### Coverage and regression boundary

Live coverage exercised Asset-unavailable and Service-unavailable inputs,
direct and downstream consequences, `unavailable`, explicit `unknown`,
conservative and multi-hop propagation, consumption of C2.2 dependency semantics,
structural Asset non-propagation, and cross-tenant non-disclosure. `unaffected`
was observed as a member state for Nginx Proxy Manager, not as a separate
Service result from a redundant set.

`degraded` analysis, `any`, cycles, truncation and other limits, site isolation,
mixed permissions, hidden intermediates, temporal eligibility, and Business
Function non-propagation remain implementation-time automated coverage; they
were not manually exercised in this C2.3 acceptance record. The earlier C2.2
live persistence of a degraded effect is not a live C2.3 degraded analysis test.
The original checklist's separate Nginx Proxy Manager unavailable scenario,
Viewer-specific checks, state/history reload checks, and browser/device
accessibility checks are not claimed as completed here.

These scenarios also provide contained regression confirmation: C2.3 consumed
persisted C2.2 `Core Operation` and `DNS Provider` semantics, and explanations
remained compatible with actual C2.1 graph relationships and canonical dependency
direction. Earlier C2.1/C2.2 acceptance records remain unchanged.

Hypothetical analysis is not live health. `unaffected` means unaffected by the
specific scenario, not verified healthy; `unknown` is a valid result. Business
Function support relationships still have no Business Function outage semantics.
This lean acceptance completes C2.3 without claiming full Impact Analysis or
completion of every optional manual checklist item. All original automated
counts, command results and implementation-time environment limitations above
remain unchanged.

## Deferred

C2.4 visual redesign; full Impact Analysis; Business Function impact;
Asset→Asset failure semantics; minimum/quorum; weighted/conditional dependency
rules; confidence scoring; probability; recovery analysis; change simulation;
scenario persistence; discovery/plugin expansion.
