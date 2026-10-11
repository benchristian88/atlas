# Integration alignment matrix — I0

Audit date: **11 October 2026**. Baseline: `feature/integration-rel-0`,
`90e04a76982c314fff2191e84ca6bd1a8cabcb07`. The initial working tree contained
only untracked integration design/history/assets supplied by the operator.
Recent relevant history includes core hardening acceptance (`5a1652d`), public
licence/documentation (`32dc6e8`), and release packaging (`d66426b`). This audit
was written before designing the staged contracts. Code and tests establish
current behaviour; the [v1.3 design](Atlas_Integration_Architecture_and_Design_Specification_v1.3.md)
establishes target policy. No production code changes are part of I0.

Paths below are repository-relative. Test names identify actual checked-in
regressions, not claims that every environment-dependent test has executed.

## Responsibility ownership

Each row has exactly one classification. Totals: **10 REUSE EXISTING,
13 EXTEND EXISTING, 10 GENUINELY NEW** (33 responsibilities).

| # | Responsibility | Classification | Current evidence; target owner and action |
| --- | --- | --- | --- |
| 1 | Scoped Integration configuration | EXTEND EXISTING | `apps/api/app/models.py:Integration` has mandatory Customer/Site, `plugin_id`, `base_url`, `username_or_token_id`, `secret_reference`, `verify_tls`, `status`. Add generic Connector/config/enabled/schedule/reference fields later; no reachable configured Integration CRUD today. |
| 2 | Integration provenance DataSource | EXTEND EXISTING | `models.py:DataSource`, `services/data_sources.py:manual_inventory_source`, `routes/knowledge.py:create_data_source/list_data_sources`. No Integration↔DataSource 1:1 FK; `source_type` is a checked list. Add generic publisher/source identity without pretending Connector #25 fits the current enum. |
| 3 | Run lifecycle and immutable execution metadata | EXTEND EXISTING | `models.py:DiscoveryRun`, `routes/knowledge.py:list_discovery_runs/get_discovery_run`, `services/knowledge_lifecycle.py`; `tests/test_knowledge_lifecycle.py`. Preserve status, coverage, archive/delete safety and add Connector/runtime/source-version/trigger metadata. |
| 4 | Run-observed membership | REUSE EXISTING | `models.py:RunObservedEntity` has unique `(discovery_run_id, entity_type, external_id)`; `services/discovery_observations.py:record_observed_entity`; `test_knowledge_foundation.py:test_run_observed_entity_flush_populates_uuid_without_explicit_id`. Membership does not itself accept an entity. |
| 5 | Complete/partial snapshot eligibility | REUSE EXISTING | `DiscoveryRun.coverage_key/is_complete_snapshot/completeness_status`; `discovery_observations.py:_previous_complete_run/reconcile_complete_snapshot`; `test_partial_snapshot_never_creates_missing_items`, `test_different_coverage_key_does_not_compare_snapshots`, `test_failed_complete_run_cannot_process_absence` in `test_knowledge_foundation.py`. Atlas, never Connector/runtime, owns baseline selection. |
| 6 | No-longer-observed / re-observed episodes | REUSE EXISTING | `discovery_observations.py:reconcile_complete_snapshot/_resolve_reobservation`; `reconciliation.py:_accept_absence`; `test_complete_snapshot_detects_missing_once_without_mutating_asset`, `test_reobserved_entity_resolves_missing_episode`, `test_retired_asset_is_not_silently_reactivated_when_reobserved`, `test_absence_decision_changes_status_but_never_deletes_asset`. Current absence processing is asset-only and re-observation runs only for successful complete snapshots. |
| 7 | Source identity and cross-source links | EXTEND EXISTING | `models.py:EntitySourceLink` is constrained to Assets; `entity_resolution.py:resolve_asset_identity/ensure_asset_link`; `test_ambiguous_match_requires_explicit_link_and_does_not_duplicate_asset`, `test_linking_asset_identity_unblocks_same_run_relationship`. Extend existing resolution for Networks/Interfaces and evidence-only hints. Durable source links precede matching; no Connector merge authority. |
| 8 | Immutable evidence | REUSE EXISTING | `models.py:EvidenceRecord`, `simulated_discovery.py:run_simulation/_payload_hash`, `test_simulation_creates_run_evidence_assertions_and_new_asset_item`. Persist sanitised payload/hash/run/source context; reuse evidence storage, not arbitrary raw vendor responses. |
| 9 | Source-current vs accepted assertions | REUSE EXISTING | `KnowledgeAssertion.is_source_current/is_accepted/truth_classification`; `knowledge_assertions.py:record_assertion/accept_assertion`; `test_new_discovery_value_is_source_current_but_not_automatically_accepted`, `test_multi_valued_relationship_assertions_remain_current_from_one_source`. Existing vocabulary is observed/declared/intended/inferred; Connector relationships use observed/inferred. Confirmation alone is not acceptance. |
| 10 | Reconciliation queues/actions | REUSE EXISTING | `reconciliation.py:create_item/accept_item/link_item_to_asset/reject_item/defer_item`, `routes/knowledge.py` scoped decision routes; `test_reject_and_defer_never_mutate_operational_asset`, `test_accepting_new_asset_and_relationship_updates_operational_view`. Extend this pipeline through adapters; never build a second queue. |
| 11 | Meaningful Changes and audit | REUSE EXISTING | `knowledge_changes.py:record_assertion_change/record_change`, `app/audit.py:add_audit_event`, `routes/changes.py`, `test_accepting_changed_fact_records_one_meaningful_change`, `test_administration.py:test_audit_metadata_redacts_passwords_tokens_and_hashes`. Credential operations audit field names/state only. |
| 12 | Managed Asset/Relationship Type lifecycle | REUSE EXISTING | `models.py:AssetType.key/RelationshipType.key/active`, `routes/reference_data.py` create/update/deactivate/guarded-delete, taxonomy FK/restrictions; `test_administration.py:test_system_and_used_asset_types_cannot_be_deleted`, `test_relationship_type_restrictions_reject_unknown_asset_types`; `test_discovery_sync.py:test_discovery_does_not_reuse_an_inactive_type_for_a_new_asset`. Use active exact keys and existing creation workflow. |
| 13 | Version-global Connector taxonomy mappings | GENUINELY NEW | No installed-Connector mapping model/route exists. Atlas catalogue owns exact-key pre-mapping and unresolved-class activation gates globally per version. Preserve existing type lifecycle and endpoint applicability. |
| 14 | Manifest-declared namespaced facts | EXTEND EXISTING | `models.py:AssetFact`, SDK `NormalizedFact`, `services/predicate_definitions.py:predicate_cardinality` and `knowledge_assertions.py`. No value-type/fact-class/manifest cardinality registry today. Fact classes identity/configuration/operational/informational are new descriptive metadata, independent of existing truth classification and acceptance; no automatic acceptance based on class. |
| 15 | Canonical Networks/Interfaces and bounded multi-domain coverage | EXTEND EXISTING | `models.py:Network/AssetInterface`, `routes/networks.py`, `routes/asset_interfaces.py`; `reconciliation.py:_create_interfaces` matches Network by name today, `simulated_discovery.py` records interface-IP assertions. `DiscoveryRun` has one coverage key, not per-domain completion. Extend existing ingestion/resolution for source IDs; do not silently project multi-domain complete/partial onto one complete run. |
| 16 | Customer/Site authority | REUSE EXISTING | `authorization.py:Principal/require_scope/scope_condition/get_active_context`; composite context FKs in models; `test_discovery_sync.py:test_sync_rejects_context_that_does_not_match_integration_ownership`, `test_administration.py:test_site_scoped_user_cannot_attach_a_hidden_customer_wide_network`. Ingestion derives scope from persisted Integration/run/source; Connector cannot select tenancy. |
| 17 | Permission model | EXTEND EXISTING | `permissions.py:PERMISSIONS/ROLE_PERMISSION_KEYS`, `authorization.py:require_global/require_scope`; current keys `integrations.view`, `integrations.manage`, `discovery_runs.archive/delete`, `reconciliation.view/decide`. No `integrations.run`, runtime or Connector permission keys exist. Add only deliberate capabilities later; global package operations must use global administrator checks, scoped Integrations retain current grant model. |
| 18 | Dispatch, presets, overlap prevention, retry/backoff | EXTEND EXISTING | `apps/worker/worker/main.py:main` only logs/sleeps and honours maintenance marker; Compose already supplies Redis. No scheduling/queue consumer/retry engine is implemented. Atlas worker is the correct future owner (I3); PostgreSQL stores durable intent/run state and Redis supports dispatch. Reuse `services/backup_runtime.py` normal-operation/quiescence guards. |
| 19 | SecretProvider and application encryption context | EXTEND EXISTING | `config.py:data_encryption_key`, `mfa.py:encrypt_seed/decrypt_seed` use maintained `cryptography` AESGCM with fresh 12-byte nonces and `atlas-mfa:v1:<user>` AAD; `infra/install/configuration.py:add_data_encryption_key` preserves existing key; `test_mfa.py` validates malformed/missing keys and authenticated encryption. Only MFA encrypted records currently exist. Add an Integration secret record/provider with separate versioned AAD; do not call MFA seed functions on arbitrary secrets. |
| 20 | Portable encrypted secret backup/restore | EXTEND EXISTING | `services/encrypted_data.py:ENCRYPTED_DATA_ADAPTERS/rewrap_application_data` currently includes only `rewrap_mfa`; `backups.py` restores/migrates/rewraps under maintenance; `backup_archive.py` encrypts the source key within the portable archive; `test_backup_postgres.py:test_rewrap_all_adapters_active_pending_atomic_wrong_key_and_corrupt`. Register Integration adapter in that transaction in I2; keep target-local auth/control secrets and fail closed on any bad ciphertext. |
| 21 | Runtime-control and run-ingestion credentials | GENUINELY NEW | No runtime service secret or run-scoped ingestion token issuer/consumer. Atlas owns independent per-install control authentication and short-lived run-token audience/expiry/JTI/revocation; neither reuses user session authority or the data key. |
| 22 | Runtime-neutral IntegrationRuntime | GENUINELY NEW | SDK has `DiscoveryPlugin` protocols, but no isolated runtime-control API/health/jobs/verified references. Atlas adapter owns private authenticated HTTP; runtime executes without database authority. |
| 23 | Isolated Ansible execution and secret leases | GENUINELY NEW | No `apps/runtime` or Runner process exists. Runtime source belongs in main Atlas repo, separately deployed, private Compose/loopback systemd, protected read-only verified bundle store and bounded ephemeral jobs. |
| 24 | Deployment/release/update packaging | EXTEND EXISTING | `infra/release/release.py`, `package-manifest.json`, `infra/install/compose.py/native.py/upgrade.py`, `services/updates.py`; `test_release_distribution.py/test_native_install.py/test_updates.py`. Current packages build API/web/worker, checksums are not signatures, application update checking is informational. I1 extends existing installers/package boundaries; final qualified offline bundles and cross-deployment acceptance arrive I4–I8. |
| 25 | Bootstrap and official catalogue metadata | GENUINELY NEW | No Connector catalogue/index/cache. Atlas embeds local snapshot and qualified three-bundle set in the integration release, checks metadata daily, and continues offline. Existing application updater is a security/reference pattern, not a Connector installer. |
| 26 | One-active-version package lifecycle | GENUINELY NEW | No installed Connector state or install/update/rollback/uninstall. Instance-global explicit admin actions; validate every dependent Integration/mapping/runtime before switching, block uninstall for enabled or disabled live connections, retain historical runs after removal. |
| 27 | Signed bundle provenance and protected store | GENUINELY NEW | Current H4 release checksums do not implement attestation verification. New catalogue verifier checks SHA-256 plus approved repository/workflow/publisher and independently verified runtime store. Generic trust metadata supports future approved publishers. |
| 28 | Existing plugin/Proxmox technical semantics | REUSE EXISTING | `plugins/sdk/atlas_plugin_sdk/{models,interfaces}.py`, `plugins/proxmox/atlas_proxmox/{client,connection,discovery,normalization}.py`; SDK `test_structural_plugin_and_sync_contracts`, `test_connection_repr_never_contains_credentials`; Proxmox `test_discovers_raw_resources_and_normalizes_assets`, `test_missing_required_vendor_identity_fails_normalization`, `test_rejected_or_underprivileged_token_is_sanitized`, `test_unsafe_base_urls_are_rejected_before_request`. Preserve token/TLS/redaction/identity tests and raw-vs-normalized separation, extend their scope in I4 without deleting compatible legacy adapters. |
| 29 | Integrations web surface | EXTEND EXISTING | `apps/web/app/integrations/page.js` is permission-gated PageHeader + unavailable EmptyState, not mock configured data. Extend route, shared `components/{page-header,button,entity-identity,data-table,filter-toolbar,catalogue-filters}.js`, auth/workspace context and `lib/status.mjs`; apply canonical UI guide and preserved v1.2 mockups. |
| 30 | Run/history/review UI | EXTEND EXISTING | `apps/web/app/discovery-runs/page.js` fetches real scoped runs with archive/delete actions; `app/discovery-runs/[id]/page.js`, `app/reconciliation/page.js`, `app/changes/page.js`. Extend these reachable surfaces with additive provenance/coverage fields; preserve lifecycle interactions and existing knowledge UI tests. |
| 31 | AIP ingress adapter | GENUINELY NEW | No AIP callback route exists. I3 adds authenticated/bounded ingestion and mapping adapters into existing evidence/assertion/reconciliation services, not `AtlasDiscoverySync._sync`. |
| 32 | Resumable guided initial knowledge onboarding | GENUINELY NEW | `routes/setup.py` and web `/setup` handle protected first administrator, not Connector onboarding. I7 follows existing setup/context conventions and manual-only path. |
| 33 | Batch replay/finalisation ledger | GENUINELY NEW | Run membership uniqueness and assertion coalescing exist, but no durable AIP sequence/body-hash replay ledger or final seal. I3 implements receipt/finalisation transaction and bounded recovery before calling existing snapshot reconciler. |

## Discrepancies and compatibility decisions

1. **Legacy direct sync differs materially from target policy.**
   `discovery_sync.py:AtlasDiscoverySync._sync` creates unknown taxonomy,
   overwrites accepted Asset fields, and marks omitted Assets `stale` without
   coverage eligibility. `test_missing_assets_are_marked_stale_not_deleted`
   intentionally covers this legacy behaviour. Preserve code and regressions
   in I0. New AIP must use the safer `simulated_discovery.py` evidence/assertion/
   reconciliation service ownership, with additive generic adapters. Do not
   silently route AIP through direct sync or change the old contract.
2. **Entity resolution already has heuristics.** `resolve_asset_identity`
   can link a unique same-scope name/type/hostname match automatically; this is
   existing Atlas policy, not Connector authority. New cross-source hints are
   evidence only and must require explicit Atlas review when ambiguous or when
   only a new hint motivates the association. Preserve existing behaviour;
   neither suppress all existing matches nor introduce silent hint-driven merges.
3. **One coverage key and asset-only absence are current limits.** Initially
   retain one aggregate scope per run. Any incomplete enabled domain makes the
   whole run partial. Independently complete domain absence requires an
   additive Atlas-owned coverage representation before it is enabled; never
   infer it by relabelling a partial run complete. No Network/Interface absence
   or partial-run re-observation support is claimed by the existing service.
4. **Fact metadata is additive.** The four proposed fact classes have no current
   database equivalent. They do not replace `truth_classification`, cardinality
   rules, or operator acceptance. Unknown scalar predicates currently default
   to single; multi-valued Connector facts need a deliberate extension later.
5. **Current permissions and UI differ from the draft.** Run/test/runtime/package
   permissions are target additions, not seeded keys. Integrations has no mock
   list to replace. Existing run UI already has meaningful lifecycle behaviour.
6. **Existing SDK/plugin licensing is AGPL-3.0-only.** Their `pyproject.toml`
   records cannot be mechanically relabelled Apache. New staging contracts are
   intended for verbatim Apache-2.0 SDK extraction before I1; source ownership
   review must resolve rights for those new artifacts. Existing AGPL modules
   stay unchanged; transfer of their implementation requires rights review or
   fresh implementation, not an assumed permissive legacy SDK.
7. **Hardening remains the foundation.** Existing package/recovery/MFA/update
   behaviour stays intact. I8 qualifies integration-specific additions and
   carries forward the existing acceptance gaps; it does not reimplement H1–H5.

## Implementation hand-off

I1: extract staged SDK schemas verbatim to the separate sole canonical SDK,
choose verification implementation/protected store layout, build private default
runtime health/control and catalogue shell on existing packaging. I2 adds scoped
generic config/secret provider, crypto adapter/mapping/update validation and
bounded Test Connection. I3 adds dispatch, tokens, receipt ledger, evidence
adapter and finalisation. I4/I5/I6 prove source implementations; I7 onboarding;
I8 integration security/package acceptance. See the active design for gates.
