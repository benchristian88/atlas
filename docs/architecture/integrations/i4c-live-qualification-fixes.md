# I4C live qualification findings and local fixes

## 18 October 2026 — diagnostic successor

Operator evidence for `.2`, digest
`sha256:3dcf374e487a65a4398fe3ec2b3c0158c9fbdeaa5c8f885b85d8c3361904ffb5`:
COMPLETED/PARTIAL, 179 observations, 48 reconciliation items created, outward
`invalid_source_record`. The increase from `.1`'s 140 observations supports the
`exists:null` fix; `.2` still failed live qualification. Source booleans and guest
references to active bridges/storage were already checked by the operator. No
further validator is relaxed or source privilege changed in this pass.

The next candidate is **0.2.0-i4b.3**, a diagnostic successor, still **UNQUALIFIED**
with no qualified source versions. Generic normal diagnostics explain stage,
object and rule; administrators can arm debug for one next run, retained at most
48 hours. No raw source logging, SDK/AIP change, source call, live acceptance or
automatic reconciliation decision occurs here. `.1`/`.2` remain immutable failed
qualification evidence and production bootstrap stays `0.1.0`. See the
[contract](discovery-diagnostics.md) and [validation report](i4c-diagnostics-report.md).

The remainder preserves the earlier fix-pass evidence.

Updated 13 October 2026. This fix pass starts at Connector checkpoint
`76af2507bd29934192d1d89428a618d081e4f4a0` and Atlas checkpoint
`efde1d7b7a6bbb4f9098b1f7d228e4b834d096b4`, on their existing I4C feature
branches. It stops before commit/push. No source call, deployment, activation,
merge, tag, release, publication or I4C-B promotion is performed here. SDK source,
contracts, runtime/dependency locks and production bootstrap are unchanged.

## Live evidence supplied by the operator

The first real Proxmox VE 9.2.11 discovery used unqualified `0.2.0-i4b.1`,
`atlas-ansible-i4a-v1` / 1.2.0, runtime 0.3.1. It was **PARTIAL**, with
140 observations, `invalid_source_record`, no Bridge Assets and guest interfaces
from current guest config. No absence processing occurred, correctly.

A valid bridge `vmbr0` was accompanied by a legitimate separate VLAN row
`vmbr0.99` containing `exists: null`. Raw transport validation included this
unused field among strict boolean flags, rejecting the entire network response
before collection/normalization. Only `exists` is removed from that set.
`active`, `autostart` and `bridge_vlan_aware` remain strict 0/1/bool. There is no
version-specific exception, arbitrary coercion, general relaxation, ACL change
or weaker COMPLETE policy.

The new regression retains the ordinary vmbr0 fixture and adds a separate VLAN
row with the real shape, including null exists. Otherwise-complete discovery
remains COMPLETE and emits `bridge/node-a/vmbr0` and bridge connectivity. Malformed
topology flags still prevent COMPLETE.

## Reconciliation and capability presentation

All Open previously fetched only the newest 200 records with no paging. Category
queues could therefore reveal records absent from All Open. The new additive
`GET /reconciliation-items/page` returns `items`, filtered/scoped `total`, `limit`,
`next_cursor` and bounded `related_new_entities`. The existing list route keeps
its array response/default bounds. Both use the existing permission/context
filters; no new permissions or authorization model are introduced.

Pages default to 50 items, maximum 200. Timestamp/UUID keyset ordering is
deterministic even when creation timestamps tie. The initial upper boundary
excludes newer arrivals until refresh; a decision or removal on an earlier page
does not shift later items. Membership/status changes remain live: scoped totals
are recalculated, and refreshing includes arrivals/reopened items. Cursors are
bounded and structurally validated. Previous navigates the stored cursor history;
queue/workspace changes reset it. Resolved uses accepted plus rejected in one
ordered stream. Counts describe queue items, excluding related entity context.
The footer reuses the Assets page's `.pagination` layout, shared secondary Buttons,
Previous / Page / Next labels and disabled edges. No unbounded table is loaded.

Initial fact grouping is presentation only. The API supplies scoped new-entity
context, including when the entity is outside the current page/category. Grouping
requires matching Asset/source/run/external identity/customer/site, matching first
observation time, no prior competing predicate claim, no current-value change and
no conflicted assertion. The first-observation check also protects against a
coalesced older assertion being assigned a later run. Genuine later Changed cards
and contradictions remain separate. The UI reuses assertion-group native details;
every underlying item keeps its own Accept/Reject/Defer actions, audit and assertion.
Accepting an entity never accepts its facts automatically. No acceptance, provenance,
audit/history or reconciliation storage logic changes.

Test Connection renders the existing generic bounded diagnostic schema: capability,
state, generic path category and optional privilege. Ready, Limited, Unproven and
Unavailable use the central status registry with visible text in both themes.
Malformed/unknown state/category/extra-field/over-limit lists are rejected as at
the API boundary. Valid generic identifiers do not require a vendor capability
allowlist. No raw ACL paths, bodies, credentials or arbitrary backend error text
are rendered. Existing API diagnostic validation is unchanged.

## Deliberate exclusions and candidate identity

Dynamic/DHCP/guest-agent/runtime guest IP enrichment remains omitted. Only explicit
static guest config IPs are emitted. Tagged/trunk guest attachments still omit
unsupported logical Network membership. Guest-to-bridge connectivity must be
rechecked after bridge discovery succeeds.

The apparent five `uses_storage` relationships among roughly 30 LXCs are
**unverified**, because the old All Open view was truncated. Storage logic is
unchanged; reassess after paging and a COMPLETE new run against the source.

The next candidate is **0.2.0-i4b.2**, with identity in the existing candidate
Manifest/SPDX metadata and verifier. Its reproducible local archive digest is
`sha256:3dcf374e487a65a4398fe3ec2b3c0158c9fbdeaa5c8f885b85d8c3361904ffb5`.
Two builds and detached manifests compare equal; independent verification checks
all 18 packaged files and dependency/contracts. Dirty-worktree provenance records
contextual HEAD only; committed-source verification must happen after separate
operator review/checkpoint, before live staging.

Immutable `.1` remains at
`sha256:d283441dfa70d8e589fd3da868075bdb795a8cda938a78931437432b572166c8`;
its saved archive compares with the prior I4C-A archive. Production/default
`0.1.0` builds compare byte-for-byte with the pre-fix default archive; Atlas's
bootstrap/catalogue are unchanged and remain probe-only. `.1`, `.2` and source
9.2.11 remain **UNQUALIFIED**, with no qualified source versions. I4/I4C are
incomplete. Historical I4A/I4B/I4C-A reports have not been rewritten.

## Additional operator-review decisions

### Human-facing discovered names and managed LXC recommendation

`reconciliation_response` now uses a valid bounded observed Asset `name` for an
unlinked candidate's `entity_name`, so the existing card/group heading is
`joomla-lab`. Scoped reconciliation CSS preserves observed-name casing instead of
capitalizing headings. Missing, blank, non-string or overlong names fall back to the existing
external identity. An already linked Asset keeps its accepted canonical name until
an operator accepts a source rename. This is generic presentation; it does not
change `candidate_external_id`, assertion `subject_external_id`, matching,
EntitySourceLink identity, evidence, provenance or audit. Regressions exercise
both list/page responses, possible duplicates, LXC/QEMU and opaque source IDs,
and accepted renames retaining one Asset and the same source link.

The secondary guest context `LXC 1008 · pve3` / `VM 203 · pve1` is **deferred**.
The existing candidate response does not provide generic bounded guest-kind,
VMID and host-presentation fields. The current normalized namespaced facts and
relationships do not constitute that presentation contract. No frontend external-ID
parser or Proxmox business logic is added to Atlas core.

Atlas's reference-data migration `20260714_0004_auth_rbac_reference_data.py`
defines the managed key **`lxc_container`**, label **LXC Container**, category
Compute; the migrated PostgreSQL regression verifies that existing active record.
The `.2` candidate Manifest now recommends `proxmox.lxc` → `lxc_container`;
`proxmox.qemu` → `virtual_machine` is unchanged. No duplicate/type creation or
core vendor mapping is introduced. The active Connector runbook records the
new recommendation; shared packaged discovery documentation retains its older
`container` recommendation to preserve production `0.1.0` package bytes. The
`.2` Manifest/runbook supersede that older recommendation.

The previously reported `.2` digest
`sha256:556fa209f5672e37fff609bb21e33264f20109888f7bba3bc06d2111d2f89f76`
is **provisional/superseded**, not the final local checkpoint identity. The new
deterministic digest above replaces it. Source qualification stays UNQUALIFIED
and `qualified_versions` stays empty. This remains an uncommitted local build;
clean-commit provenance verification is still a later gate.

### Archived runs and active reconciliation — stopped on provenance ambiguity

**No archive-based reconciliation filter is implemented.** This follows the
operator's explicit stop condition, not a new dismissal/rejection policy.

Inspection of `KnowledgeAssertion`, `ReconciliationItem`, `EvidenceRecord`,
`RunObservedEntity`, `DiscoveryBatchReceipt`, `record_assertion`, `create_item`,
AIP finalisation and run lifecycle found:

- An item owns one assertion ID and has no discovery-run ownership/history field.
- Identical same-source claims reuse one assertion and unresolved item. Coalescing
  replaces `discovery_run_id` and `evidence_record_id` with the latest observation;
  `first_observed_at` remains original and `last_observed_at` advances.
- Run observations/evidence and immutable AIP receipts survive, but there is no
  durable assertion-to-every-contributing-observation/run association. Membership
  is entity-level, not predicate/value provenance. Raw payload schemas and reference
  resolution differ by ingestion path and can change between identical claims.
- For example, active run A observes name N. Later run B observes the same N but
  a different status; N coalesces, while the two evidence payload hashes differ.
  Archiving B leaves N supported by active A. Filtering only N's latest archived
  pointer would incorrectly hide that item. Conversely, first-run ownership would
  hide a later active re-observation after archiving A. Matching whole evidence
  hashes or entity membership cannot reliably prove predicate-level attribution.

Two real PostgreSQL/AIP audit regressions cover archiving the first/latest PARTIAL
run of this sequence: the same assertion/item survives, only latest provenance
pointers remain, both runs' receipts/evidence/observations survive, and archive
does not reject the claim/item. These are **provenance audit tests**, not acceptance
of the requested queue suppression. Existing lifecycle/acceptance/scoping tests
are rerun. Coalesced/reobserved work is protected by leaving queue filters and
decisions unchanged; no current claim is hidden by an archive heuristic.

Existing archive semantics remain: archive metadata/audit changes, the run leaves
the default Discovery list, Include archived and run details remain available,
and knowledge/history are retained. Reconciliation rows, summaries and pagination
totals still include unresolved archived-run work. Archiving never implicitly
rejects, removes or reverts accepted knowledge. The new requirement that solely
archived-run work leave active queues, and its full requested acceptance matrix,
remain **unimplemented** pending a scoped provenance/ownership design that can
distinguish mixed archived/active contributions, including absence episodes.
No schema change is introduced in this pass.

### Discovery summary table presentation

The existing DataTable is composed by `DiscoveryRunsTable`. Source / Integration
shows the friendly `source_name` as the primary Integration link; run/Integration
UUIDs are absent from normal row text. Connector IDs are generically presented
as labels (for example Proxmox), with version on the primary line and the bounded
trigger label (Manual/Scheduled/Onboarding/Retry) on a secondary line. The existing
`.table-cell-identity` grid supplies an explicit 4 px gap. Status and completeness
use separate accessible groups/lines and the central status registry; Partial
has its own warning presentation. No backend status meaning is merged.

Coverage uses the existing structured `is_complete_snapshot` flag:
Full scope / Partial scope, or Unspecified when absent. It does not infer actual
completeness or parse/truncate `coverage_key`. Opaque coverage keys, UUIDs and
digests stay in the unchanged API/detail/provenance contexts; no compensating raw
identifier content is added to the summary. Existing detail coverage, run identity
and Integration links are unchanged. Caption/column headers, keyboard table
scrolling, archive/restore/delete controls and permissions remain intact. Focused
UI regressions and production-browser checks cover these contracts.

No Source Facts card, custom VMID field, guest-agent/DHCP IP enrichment, CPU/memory/
disk telemetry or tagged/trunk logical Network membership change is added.

## Validation after operator review

All results below were executed in this additional pass. The complete Connector,
API, frontend, release-critical, contracts/docs and production-browser checks
preserve the prior fix acceptance for implemented scope. Archived-run queue
suppression is explicitly excluded from acceptance because it stopped at the
provenance ambiguity above.

The focused API checks used the prior disposable PostgreSQL instance after a
restart. The broad API rerun used a new localhost-only PostgreSQL container and
the existing CI preparation script: **15 new isolated databases**, including ten
empty migration databases, with a generated non-superuser owner. Existing populated
test databases were retained. Redis used a disposable localhost-only 7.4.6 container.
Private test configuration/credentials were not copied into this report or Git.
The first local connection attempts lacked running/correctly configured test
services; the later focused/full runs passed after service preparation. No real
source endpoint or source credential was used. Tests do not qualify a live source.

| Check actually run | Result |
| --- | --- |
| Focused API: reconciliation listing, I3 discovery and knowledge lifecycle | **78 passed**; listing alone comprises 29 cases |
| Focused Connector: checkpoint/mapping and discovery | **29 passed** |
| Complete Connector suite, including actual Ansible Runner fixtures | **103 passed** |
| Complete API suite with all optional PostgreSQL suites enabled | **1,164 passed, 68 skipped** |
| Release-critical selector | **572 passed**, no skips |
| Contracts/repository documentation/Markdown selector | **95 passed** |
| Focused frontend: reconciliation, diagnostics, knowledge, Discovery and lifecycle | **30 passed** |
| Complete frontend suite | **304 passed** |
| Production Next build | **Passed**, including final name-casing correction |
| I4C production Chrome acceptance | **16 scenarios passed** on the final build |
| Existing I3 production Chrome lifecycle acceptance | **24 scenarios passed** |
| Candidate archive and detached Manifest/checksum/index comparisons | **Byte-identical** across two builds |
| Independent candidate verification | **Passed**, all 18 packaged files and contracts/dependencies |
| Immutable `.1` and production `0.1.0` byte comparisons | **Passed**, production remains probe-only |
| Alembic heads | Unchanged single head **20261012_0029** |
| Both repository whitespace checks | **Clean** |

The 68 API skips are the existing real nginx gateway cases requiring nginx >=1.28
or `ATLAS_TEST_NGINX`; no suitable local executable was configured. No new skip or
weakened test was introduced. Existing dependency deprecation warnings remain.
This pass adds **19 regression cases**: 11 naming/identity/managed-type API cases,
two real AIP coalescing/archive provenance audit cases, one Connector mapping case,
and five frontend naming/Discovery cases. The audit cases do not claim archive
queue suppression is implemented.

The I4C browser matrix covers light/dark themes, default/blue/purple accents,
1440/1024/800/390 px, 237 queue items across five pages, category/reset/previous/next,
independent facts/changes/conflicts, safe diagnostics, and the Discovery table.
It checks friendly source names, hidden internal row IDs/coverage/digests, Full
scope independent of Partial completeness, caption/headers/keyboard focus, measured
4 px line gaps and no document overflow. Table scrolling remains intentionally
contained on narrow screens. Final observed-name casing is asserted and its
screenshot inspected. Discovery desktop/mobile screenshots in both themes were
inspected; existing I3 detail/lifecycle checks preserve technical identity and
coverage inspection. All API browser responses are fixtures, not live evidence.

Commands actually executed (logs/artifacts under
`/private/tmp/atlas-i4c-operator-review`; shell setup uses private disposable test
configuration and the pinned native-style I4A runtime):

```bash
# atlas-connectors
PYTHONPATH=/private/tmp/atlas-connectors-build-venv/lib/python3.14/site-packages ATLAS_TEST_COLLECTIONS_PATH=/private/tmp/atlas-i4a-validation/runtime/collections ATLAS_TEST_RUN_ANSIBLE=1 /private/tmp/atlas-i4a-runtime-venv/bin/python -m pytest tests/test_i4c_checkpoint.py tests/test_proxmox_discovery.py -q --tb=short
PYTHONPATH=/private/tmp/atlas-connectors-build-venv/lib/python3.14/site-packages ATLAS_TEST_COLLECTIONS_PATH=/private/tmp/atlas-i4a-validation/runtime/collections ATLAS_TEST_RUN_ANSIBLE=1 /private/tmp/atlas-i4a-runtime-venv/bin/python -m pytest -q --tb=short
/private/tmp/atlas-connectors-build-venv/bin/python tools/build_bundle.py --candidate --output /private/tmp/atlas-i4c-operator-review/candidate-a
/private/tmp/atlas-connectors-build-venv/bin/python tools/build_bundle.py --candidate --output /private/tmp/atlas-i4c-operator-review/candidate-b
cmp /private/tmp/atlas-i4c-operator-review/candidate-a/proxmox-0.2.0-i4b.2.tar.gz /private/tmp/atlas-i4c-operator-review/candidate-b/proxmox-0.2.0-i4b.2.tar.gz
cmp /private/tmp/atlas-i4c-operator-review/candidate-a/manifest.json /private/tmp/atlas-i4c-operator-review/candidate-b/manifest.json
/private/tmp/atlas-connectors-build-venv/bin/python tools/verify_candidate.py --directory /private/tmp/atlas-i4c-operator-review/candidate-a --expected-digest sha256:3dcf374e487a65a4398fe3ec2b3c0158c9fbdeaa5c8f885b85d8c3361904ffb5
/private/tmp/atlas-connectors-build-venv/bin/python tools/build_bundle.py --output /private/tmp/atlas-i4c-operator-review/production
cmp /private/tmp/atlas-i4c-fixes/original-production/proxmox-0.1.0.tar.gz /private/tmp/atlas-i4c-operator-review/production/proxmox-0.1.0.tar.gz
cmp /private/tmp/atlas-i4c-fixes/original-candidate/proxmox-0.2.0-i4b.1.tar.gz /private/tmp/atlas-i4c-a/before/proxmox-0.2.0-i4b.1.tar.gz

# atlas/apps/api; focused API first used the prior disposable PostgreSQL environment
.venv/bin/python -m pytest tests/test_reconciliation_listing.py tests/test_i3_discovery.py tests/test_knowledge_lifecycle.py -q --tb=short
.venv/bin/python ../../infra/ci/prepare-postgres.py --config /private/tmp/atlas-i4a-validation/test-config.env --port 15436 --env-file /private/tmp/atlas-i4c-operator-review/tests.env
set -a
source /private/tmp/atlas-i4a-validation/test-config.env
source /private/tmp/atlas-i4c-operator-review/tests.env
set +a
export PATH="$PWD/.venv/bin:$PATH"
export PYTHONPATH=../../plugins/sdk:../../plugins/proxmox
export ATLAS_TEST_RUNTIME_PYTHON=/private/tmp/atlas-i4a-runtime-venv/bin/python
export REDIS_URL=redis://127.0.0.1:16379/0
export ATLAS_TEST_H3_REDIS_URL=redis://127.0.0.1:16379/0
python -m pytest -q --tb=short -rs
bash ../../infra/ci/release-critical.sh
python -m alembic heads

# atlas root
PYTHONPATH=plugins/sdk:plugins/proxmox apps/api/.venv/bin/python -m pytest docs/architecture/integrations/contracts/tests apps/api/tests/test_repository_docs.py apps/api/tests/test_markdown_docs.py -q --tb=short
export ATLAS_PLAYWRIGHT_MODULE=/private/tmp/atlas-i1-browser-tools/node_modules/playwright/index.mjs
export ATLAS_CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
export ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3141
export ATLAS_BROWSER_OUTPUT=/private/tmp/atlas-i4c-operator-review/browser
node apps/web/scripts/check-i4c-qualification-browser.mjs
export ATLAS_BROWSER_OUTPUT=/private/tmp/atlas-i4c-operator-review/browser-i3
node apps/web/scripts/check-i3-discovery-browser.mjs

# atlas/apps/web
node --test tests/reconciliation-navigation.test.mjs tests/integration-configuration.test.mjs tests/knowledge-v2-ui.test.mjs tests/discovery.test.mjs tests/knowledge-lifecycle-ui.test.mjs
npm test
npm run build
npm run start -- --hostname 127.0.0.1 --port 3141

# both repositories
git diff --check
git status --short --untracked-files=all
```

A separate invariant audit compared saved pre-edit hashes for 109 Atlas
runtime/SDK/bootstrap/contract files and two Connector SDK/vendor files; all are
unchanged. Candidate archives, detached manifests, SHA256SUMS and indexes compare
byte-for-byte. Immutable `.1` still hashes to
`sha256:d283441dfa70d8e589fd3da868075bdb795a8cda938a78931437432b572166c8`;
production `0.1.0` still hashes to
`sha256:b83ec2b3938b1747d12be5f0675dbc3e9da13c6259c2ab40f5daa994ee59ea60`
and its inspected Manifest/archive remains test-connection-only, with no discovery
entry point. The new final local `.2` digest is
`sha256:3dcf374e487a65a4398fe3ec2b3c0158c9fbdeaa5c8f885b85d8c3361904ffb5`.

**No migrations required.** No existing API route/array contract, DiscoveryRun
identity/storage/provenance/API semantics or decision semantics is removed.
Reconciliation naming changes only the existing presentation field.
RBAC/customer/site filters still apply to page rows, counts and companion entities;
Discovery uses the existing authorized API and lifecycle controls. No extra raw
source/credential data is rendered. Archive suppression remains unimplemented;
its active-queue totals intentionally retain the existing behavior.

## Remaining live steps

The additional archive/reconciliation decision remains blocked by the exact
predicate-level provenance ambiguity described above. Resolve that ownership/
provenance design before claiming archived-only work suppression is accepted.
Guest secondary context remains deliberately deferred pending generic bounded
presentation fields.

After separate operator review/checkpoint, rebuild twice from both exact clean
commits, independently verify `.2` and its new detached provenance, and follow
[the existing contained qualification procedure](../../deployment/connector-qualification.md)
on the isolated test LXC. Re-run Test Connection/readiness, actual Runner/AIP
discovery, Bridge/guest connectivity, complete reconciliation queue review and
storage coverage. Establish a safe COMPLETE baseline, repeatability/history,
PARTIAL/no-absence behavior, tenancy and safe negative checks. Unsupported/missing
classes and unsafe mutation scenarios remain untested. Native/systemd LIVE
acceptance and I4C-B/release decisions remain separate gates.

## Material files

Atlas:

- `apps/api/app/services/reconciliation_listing.py`: shared scoped filters, bounded keyset pagination and conservative presentation context.
- `apps/api/app/routes/knowledge.py`: additive page route, existing list adapter and presentation fields.
- `apps/api/app/schemas.py`: additive item fields and explicit page envelope.
- `apps/api/tests/test_reconciliation_listing.py`: >200/category union, cursor bounds/ties/decisions/arrivals, RBAC/tenancy, grouping/history and observed-name/managed-type/source-rename regression cases.
- `apps/api/tests/test_i3_discovery.py`: real AIP coalescing/archive provenance audit for both first/latest PARTIAL runs, retained receipts/evidence and unchanged open claim/item status.
- `apps/web/app/discovery-runs/page.js`: compose the cleaned-up summary table while retaining lifecycle controls/permissions.
- `apps/web/components/discovery-runs-table.js`: friendly source/connector/trigger/scope presentation and independent accessible status/completeness lines using the existing DataTable/grid.
- `apps/web/lib/discovery.mjs`: bounded generic summary presentation from existing fields, without coverage-ID parsing or API changes.
- `apps/web/tests/discovery.test.mjs`: source/identity visibility, structured scope, separate typography/status semantics and table accessibility regressions.
- `apps/web/app/reconciliation/page.js`: bounded queue navigation, scoped counts, refresh/reset and grouped presentation.
- `apps/web/app/reconciliation/reconciliation.module.css`: scoped responsive wrapping, bounded grid sizing and preserved observed-name casing.
- `apps/web/components/reconciliation-cards.js`: existing card/action presentation extracted for reuse; native fact groups and Assets-style pagination.
- `apps/web/lib/reconciliation-queues.mjs`: bounded request codec and guarded presentation grouping.
- `apps/web/components/integration-configuration.js`: generic capability diagnostic rendering.
- `apps/web/lib/integration-configuration.mjs`: diagnostic schema checks matching the API.
- `apps/web/lib/status.mjs`: central capability readiness labels/tones and independent Partial completeness presentation.
- `apps/web/tests/helpers/components.mjs`: register reconciliation and discovery helpers for component tests.
- `apps/web/tests/reconciliation-navigation.test.mjs`: bounded queue coverage, paging contract, grouping, independent decisions and observed-name headings with unchanged grouping identity.
- `apps/web/tests/integration-configuration.test.mjs`: ready/limited/unavailable/unproven/absent/malformed diagnostics.
- `apps/web/tests/knowledge-v2-ui.test.mjs`: retained absence-action checks follow the extracted component.
- `apps/web/scripts/check-i4c-qualification-browser.mjs`: production-browser acceptance with fixture screenshots, observed-name casing, Discovery source/coverage/identifier visibility, measured line gaps and accessible table focus at all required widths/themes.
- `infra/ci/release-critical.sh`: include reconciliation API regressions.
- `docs/architecture/integrations/integration-roadmap.md`: truthful first PARTIAL run and next-candidate boundary.
- `docs/product/feature-ledger.md`: reachable pagination/grouping/diagnostics/naming/Discovery summaries, LXC recommendation and explicit archive-provenance limitation; production discovery remains partial/unqualified.
- `docs/architecture/ui-architecture.md`: shared status/paging/grouping contracts; remove two legacy trailing-space lines required by the modified-doc whitespace gate.
- `docs/architecture/integrations/i4c-live-qualification-fixes.md`: this live-findings/acceptance record.

atlas-connectors:

- `connectors/proxmox/module_utils/atlas_transport.py`: remove unused exists flag from strict network booleans.
- `tests/test_proxmox_discovery.py`: real separate VLAN exists:null regression, strict topology flags and metadata-derived test version.
- `connectors/proxmox/candidate/manifest.json`: new .2 identity and existing lxc_container recommendation; unqualified with no qualified source versions.
- `connectors/proxmox/candidate/sbom.spdx.json`: matching successor SPDX identity.
- `tools/verify_candidate.py`: require the exact .2 archive/Manifest/SPDX identity.
- `tests/test_i4c_checkpoint.py`: successor identity retains an existing .1 archive; built candidate recommends lxc_container and retains virtual_machine.
- `connectors/proxmox/docs/i4c-live-qualification.md`: active findings, operator-review decisions, new .2 digest/checkpoint, archived-work provenance stop and unchanged live gates; stop before commit/push in this pass.
- `README.md`: current candidate/live-runbook pointer.

No SDK source or contracts were modified.

## Final repository state

Both original feature branches/HEADs are unchanged. Prior passing fix-pass work
is retained; the additional operator-review files are included below. Nothing
is staged or committed. Exact `git status --short --untracked-files=all`:

atlas-connectors:

```text
 M README.md
 M connectors/proxmox/candidate/manifest.json
 M connectors/proxmox/candidate/sbom.spdx.json
 M connectors/proxmox/docs/i4c-live-qualification.md
 M connectors/proxmox/module_utils/atlas_transport.py
 M tests/test_i4c_checkpoint.py
 M tests/test_proxmox_discovery.py
 M tools/verify_candidate.py
```

atlas:

```text
 M apps/api/app/routes/knowledge.py
 M apps/api/app/schemas.py
 M apps/api/tests/test_i3_discovery.py
 M apps/web/app/discovery-runs/page.js
 M apps/web/app/reconciliation/page.js
 M apps/web/components/integration-configuration.js
 M apps/web/lib/discovery.mjs
 M apps/web/lib/integration-configuration.mjs
 M apps/web/lib/reconciliation-queues.mjs
 M apps/web/lib/status.mjs
 M apps/web/tests/discovery.test.mjs
 M apps/web/tests/helpers/components.mjs
 M apps/web/tests/integration-configuration.test.mjs
 M apps/web/tests/knowledge-v2-ui.test.mjs
 M apps/web/tests/reconciliation-navigation.test.mjs
 M docs/architecture/integrations/integration-roadmap.md
 M docs/architecture/ui-architecture.md
 M docs/product/feature-ledger.md
 M infra/ci/release-critical.sh
?? apps/api/app/services/reconciliation_listing.py
?? apps/api/tests/test_reconciliation_listing.py
?? apps/web/app/reconciliation/reconciliation.module.css
?? apps/web/components/discovery-runs-table.js
?? apps/web/components/reconciliation-cards.js
?? apps/web/scripts/check-i4c-qualification-browser.mjs
?? docs/architecture/integrations/i4c-live-qualification-fixes.md
```
