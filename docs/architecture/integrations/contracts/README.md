# Integration contracts

The sole canonical AIP and Manifest schemas now live in the Apache-2.0
`atlas-connector-sdk` repository, version **1.1.0**. Atlas and `atlas-connectors`
consume the same hash-pinned wheel in `vendor/sdk`. The JSON files in this directory
are non-authoritative `$ref` pointers; production never reads them. Contract tests
import SDK package resources and validators. The original AIP 1.0 and Manifest 1.0
schema bytes and identities are unchanged. Legacy AGPL plugin code remains intact;
no application or legacy plugin implementation was moved into Apache projects.

Manifest **1.1** is an operator-approved additive extension: `discover: false`
permits a real verified Test Connection-only package with no discovery entry point,
scopes, object/relationship classes or facts. Its qualification may be explicitly
`unqualified` or `untested`. Discovery-capable packages retain their declarations.
Atlas continues to reject `example` manifests for executable activation. A verified
probe package is executable only through its declared fixed Test Connection entry.
This is a Manifest 1.x evolution, not an AIP change or architecture redesign.

The I0 examples below remain specification fixtures, not executable packages.
See the historical [I0](../i0-completion-report.md)/[I1](../i1-completion-report.md)
records and the current [I3 implementation evidence](../i3-completion-report.md).

## Artifacts and validation

- [AIP v1](aip-v1.schema.json) and [Manifest v1](connector-manifest-v1.schema.json).
- Three [example manifests](manifests) and ten [AIP messages](fixtures).
- [IntegrationRuntime](integration-runtime.md) and [SecretProvider](secret-provider.md).
- [Deterministic identity inputs](identity-examples.json),
  [contract validator/tests](tests/test_contracts.py) and
  [test-only dependency](requirements-i0.txt).

Schemas use [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12).
The validator explicitly enables format checks, then checks cross-document
references and stream constraints that JSON Schema alone cannot express.
These are static contract tests, not simulated production ingestion/runtime tests.
Run with the existing pytest development environment, from the repository root:

```bash
python -m pip install -r docs/architecture/integrations/contracts/requirements-i0.txt
python -m pytest docs/architecture/integrations/contracts/tests -q
```

The three manifests are **non-installable specification examples**:
`source_versions.qualification=example`, `0.0.0-i0`, illustrative digests,
reserved `example.test` URIs, an example repository/workflow and empty dependency
locks. They assert no source-version qualification, real bundle availability,
verified attestation, final runtime baseline or Collection dependency. I1 must
reject example metadata for activation. I4–I6 replace these with qualified
packages/dependencies after research. No credential value is included anywhere.
A declared secret field name/marker is schema metadata, never a secret value.

## AIP envelope and ownership

`observations` batches and `completion` messages both contain protocol version,
Connector ID/SemVer/SHA-256 digest, Integration ID, run ID, observed timestamp,
optional detected source version, and aggregate coverage key/mode/domains.
Run/Integration IDs only validate linkage; they grant no authority. Atlas binds
those values to the persisted run, installed version and token claims, then loads
Customer/Site/DataSource from its own records. Tenant IDs, canonical Atlas entity
IDs, credentials and business-object creation fields are prohibited.

Runtime authenticates callbacks with a short-lived run token, supplied outside
AIP (never a JSON credential field). Audience, expiry/JTI, revocation and run/
Integration binding must be checked before parsing/persisting observations.
The control service credential is a separate installation-local secret.

Coverage key and enabled domains are bound by Atlas dispatch before execution.
The Connector echoes them and cannot change/widen them. Disabled optional/ignored
classes change the selected scope and thus the coverage key; they cannot count
as complete coverage over the previous wider scope. In v1 use one aggregate key
per run; it changes deterministically with meaningful scope/filter/class-selection
changes, never with display labels, run IDs, secrets or per-run ordering.
I3 uses a versioned sorted scope/class/domain/filter encoding; see
[implementation](../i3-implementation.md).

## Batches, replay and finalisation

Observations have a one-based `batch.sequence` and four arrays: Assets, Networks,
Interfaces and relationships. An empty complete observation batch is valid and
can establish a genuinely empty baseline. The same run may span multiple batches;
references may resolve across batches or to an existing authorized durable source
link. The static example validator checks references across all supplied batches.

Atlas must persist receipt identity `(run_id, sequence)` and SHA-256 of the
accepted canonical JSON body alongside the transaction that records evidence.
Canonical JSON here sorts object keys, uses compact separators and UTF-8, rejects
non-finite numbers/duplicate JSON keys, and retains array order. An exact replay
returns its existing receipt without duplicate evidence/history. A different
body at an existing sequence is a conflict and cannot overwrite that receipt.
Retrying unchanged completion is idempotent; a contradictory seal is a conflict.

A completion contains `last_sequence`, status and completeness. Zero is allowed
for a failed/cancelled run that produced no batches. Successful completion must
include at least one observation batch, even for an empty inventory. Out-of-order
receipts may be stored; finalisation requires exactly sequences 1..last_sequence,
matching run/Integration/Connector/coverage/source version and successful semantic
validation of every batch. Completion is explicit; no observation batch means
complete merely because it was the last HTTP request received.

After sealing, reject late/new/modified batches; exact stored replays may return
their receipt while the token remains authorized. Expired/revoked tokens always
fail. Timeout/lost callbacks, unresolved references, conflicting duplicate source
IDs or missing receipts prevent a complete seal. A failed/cancelled run may retain
validated partial evidence but performs no absence reconciliation. Retry creates
a new run identity and leaves prior run/evidence history intact.

I3 records bounded diagnostic codes, derives final status conservatively, and
calls existing snapshot reconciliation only after a successful complete seal.
The runtime cannot raise completion authority beyond Atlas-validated coverage.

## Existing lifecycle mapping

| Contract result | DiscoveryRun status | is_complete_snapshot | completeness_status | Asset absence eligible |
| --- | --- | --- | --- | --- |
| full + completed + complete | completed | true | complete | Yes, after durable seal and matching baseline |
| full + completed + partial | completed | true | partial | No |
| partial + completed + partial | completed | false | partial | No |
| failed | failed | full intent only if dispatched full | failed | No |
| cancelled | cancelled | dispatched intent | unknown | No |

Atlas's `reconcile_complete_snapshot` owns matching DataSource/Customer/Site/
coverage and prior successful-complete baseline selection. First complete run
establishes a baseline. No partial/failed run creates absence or deletes accepted
Assets. Re-observation currently occurs in successful complete runs and retains
retired lifecycle state. Network/Interface absence and independent per-domain
completeness require additive extensions later; this contract makes no claim that
the current service already supports them. Any incomplete enabled domain makes
this aggregate run partial, including permission-limited visibility.

## Canonical observations and facts

Source object classes are declared by the Manifest with `kind=asset/network/interface`.
Asset classes recommend managed Atlas stable keys; exact active compatible
key matches pre-map silently. Networks/Interfaces use canonical fields and
source identity, never hidden fact blobs. Network IP/CIDR/VLAN and Interface
ownership/membership need semantic validation and authorized source-link
resolution before acceptance. Relationship direction is source→target as declared
by its semantic class; mappings must preserve that meaning and type applicability.

Relationship truth uses existing Atlas `observed`/`inferred`. V1 omits user-only
`declared`/`intended`, Services/Business Functions, executable queries and raw
vendor payload blobs. Correlation hints are bounded evidence-only hostname/MAC/
management-IP values; they never name a canonical merge target.

Namespaced facts declare value type, class, cardinality and allowed object
classes in the Manifest. Payload metadata must match exactly. `single` has one
scalar; `multi` has a bounded list of distinct typed scalars. The fact classes
identity/configuration/operational/informational are additive descriptive
metadata, independent of assertion truth and accepted state. A Connector cannot
bypass reconciliation by marking a fact operational. Multi-value knowledge needs
an additive extension to current predicate handling, which defaults unknown
scalar predicates to single-valued. Canonical fields must not be redeclared as
namespaced aliases (for example a fact replacing Network VLAN or Asset status).

Source IDs are deterministic within a retained DataSource. Proxmox fixtures
preserve existing node/guest/shared-storage examples without proving final
shared/local identity rules. Docker workloads use engine/project/service/ordinal;
actual container ID appears only as an informational observation. I5 must prove
ordinal stability and standalone rename/recreation/one-off behaviour. UniFi
examples include only gateway/switch/AP plus Networks/Interfaces; source-site IDs
are technical source IDs and cannot select Atlas tenancy.

## Manifest, bundles and declarative UI

The Manifest schema models the validated combined view of an **in-bundle domain
manifest** and a **detached distribution descriptor**. The descriptor contains
archive SHA-256, immutable release URI and provenance/signature metadata. It is
outside the archive to avoid hashing an archive containing its own digest.
Attestation binds the exact archive digest to the approved repository/workflow;
matching hash or claimed publisher text alone is not trust. The installer checks
that embedded ID/version/domain metadata matches the verified catalogue entry.

Approved trust is instance-global policy, not a manifest-selected bypass.
Official releases require GitHub Artifact Attestations/Sigstore plus SHA-256;
future approved publishers may use the generic signature branch after explicit
policy approval. I1 must choose and exercise an actual verifier, including offline
bootstrap proof, revocation/stale-catalogue behaviour and archive path/link bounds.
No verifier implementation or new external project/workflow is introduced by I0.

Compatibility declares AIP version, SDK/Atlas/runtime baseline bounds and source
qualification/known incompatibilities. Detected source version is Supported only
when qualified; newer/untested warns and allows; known incompatible blocks with
update guidance. Minimum/exclusive maximum versions are ordered SemVer values,
not arbitrary expressions. Entry points are fixed operation identifiers resolved
inside the verified protected package; no arbitrary paths/commands/Git/Galaxy
inputs. Runtime-specific dependency locks are confined to `implementation`;
AIP and Manifest domain fields contain no playbook/inventory concepts.

Published documentation/distribution/provenance URLs use HTTPS, never executable
URL schemes. Atlas escapes labels/help and does not execute their text.
Connection fields are bounded Atlas-owned controls with plain-text help,
non-secret defaults, numeric/length limits and one-field equality visibility.
No expressions, scripts, remote UI, HTML/CSS/JavaScript, raw queries/cron or Atlas
DB migrations are allowed. Secret fields cannot carry defaults/options or be
rehydrated into the browser. Visibility references must name declared non-secret
fields; required conditional fields are required only when visible. Source calls
remain read-only. The validator checks explicit structure and example content;
production still needs output redaction/data minimisation, because arbitrary
source strings can contain sensitive data and JSON Schema cannot prove secrecy.

## Bounds and later acceptance

Specification ceilings: 1000 observations per kind per batch, 128 facts per
entity, 64 values per multi-fact, 64 diagnostics, 10000 sequences. I3 additionally
caps decoded body size at 1 MiB and each run at 5,000 total observations, 256
batches, 20,000 facts and 32 MiB of canonical JSON;
apply whichever bound is smaller. Limits may be tightened after homelab evidence,
never silently bypassed. Set explicit job/API timeout, concurrency, retry and
retention limits before I3 acceptance; the schema ceilings are not performance
qualification. Reject over-limit bodies before persistence; mark truncated
coverage partial. Schemas are strict versioned contracts: additive fields require a new minor
contract/SDK release and negotiated support; preserve released older validators
rather than allowing arbitrary unknown extension fields. These constraints require
no runtime implementation in I0.
