# Official catalogue consumer approval and Docker Compose installation

The owner has authorised release-owned publication acceptance and, separately,
Docker Compose remote Connector installation in this change. These approvals
trust the reviewed publication authority and policy for subsequent authenticated
catalogues; they are not a sequence-two exception or a Proxmox allowlist.
[Accepted ADR 0018](../decisions/0018-catalogue-durable-publication-evidence.md)
defines the unchanged architecture. Its approval-unset statements describe the
architectural decision at acceptance; the records below are the later activation.
The earlier [preparation report](../catalogue2-adr0018-approval-report.md) and
[security remediation report](../catalogue2-security-remediation-report.md) retain
historical evidence, rather than current executable approval status.

**Code acceptance is separate from live deployment qualification.** The immutable
publication and locally authenticated original evidence are identified below.
No Atlas service has been deployed, restarted, refreshed or used to download or
install a Connector during this change. Neither development LXC `192.168.3.220`
nor the protected historical `atlas-test-docker` was accessed. GitHub CI and fresh
LXC ingestion/installation/source qualification remain outstanding. Publication
is complete; do not dispatch publication again or change either producer gate.

## Published evidence

[Catalogue 2](https://github.com/benchristian88/atlas-connectors/releases/tag/catalogue-000002)
is immutable and has exactly seven assets: `catalogue-000002.json`,
`catalogue.sigstore.json`, `current.json`, `current.sigstore.json`, `policy.json`,
`preflight.json` and `preflight.sigstore.json`.

| Identity | Exact published value |
| --- | --- |
| Sequence / release ID / catalogue asset ID | `2` / `435045367` / `712971861` |
| Catalogue SHA-256 | `1340146fa9ef10a630a6f6fea86c8f6374acec343ff2dec80f9b738f0f2c6c7c` |
| Publication source C | `f79f5815501d203b13c9079b9b1e09585a8e87bc` |
| Frozen signer S | `4be90c5292f931497473595a0958cc5e0f9d1beb` |
| Original policy SHA-256 | `c9a88eeb6c7e6d0a7f1a08eaa07eeed5ea251449db7104f7757626842cf1bbe9` |
| Original publication run / attempt | `42009358751` / `1` |
| GitHub publication timestamp | `2026-11-05T10:18:48Z` |
| Original current-pointer SHA-256 | `669fc75defe008398ddf017fbb4009c10ae4d57bf686ced59cc74692dbcdb8ce` |
| Selection commit observed at review | `e8cc0915a67fb3b309aa0b02a2dd10233fec9fe1` |
| Previous pointer SHA-256 (sequence one) | `a275f63d0ac818a193826478328ee324be62353addc5c97a2ed0a28d217b5372` |

These sequence/release/asset/content identities are publication evidence only,
not permanent constraints in either approval. The consumer follows the live,
authenticated `catalogue-current` pointer and verifies complete contiguous signed
history to the existing root `a1597730687be993d766ddb465a0d3362aef2d02`.
Catalogue 1's exact ADR 0013 bootstrap approval and original bytes remain valid;
its exception never authorises later publications. Retain Proxmox 0.2.0 as withdrawn.

Anonymous release metadata and all seven original downloaded hashes were checked.
The actual pinned offline verifier authenticated the genuine selection and original
preflight under S, the exact original policy and the 900/300-second historical
bounds. This is focused original-evidence verification, not a completed Atlas
refresh or live effective-permissions/isolation qualification. Never substitute
GitHub transport timestamps for authenticated transparency witnesses.

## Approved publication authority

`APPROVED_FUTURE_POLICY` in
`apps/api/app/services/catalogue_future_authorization.py` is exactly:

```json
{
  "expectations": {
    "consumer_review": {
      "allowed_maintainer_id": 93822871,
      "bootstrap": {
        "pointer_sha256": "a275f63d0ac818a193826478328ee324be62353addc5c97a2ed0a28d217b5372",
        "sequence": 1
      },
      "owner_id": 93822871,
      "package_environment_id": 24617213627,
      "policy_id": "single-maintainer-v1",
      "publication_environment_id": 24999137498,
      "publisher_app_id": 5422372,
      "publisher_app_slug": "atlas-catalogue-publisher",
      "publisher_bot_user_id": 346232650,
      "repository_id": 1414494920,
      "reviewed_producer_revision": "4be90c5292f931497473595a0958cc5e0f9d1beb",
      "schema_version": "1.0",
      "signing": {
        "oidc_issuer": "https://token.actions.githubusercontent.com",
        "predicate_type": "https://slsa.dev/provenance/v1",
        "runner_environment": "github-hosted",
        "trust_root_id": "sigstore-public-good-2026-10-21",
        "trust_root_sha256": "3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1",
        "verifier_version": "2.102.1"
      }
    },
    "rulesets": {
      "bootstrap_lock": 25628137,
      "catalogue_current": 25618684,
      "history_lock": 25618809,
      "main": 25618213,
      "publication_tags": 25618901
    },
    "workflow_id": 392548804
  },
  "historical_decision": "https://github.com/benchristian88/atlas/blob/76031dc6358a81c3babd15f74d407e22f0778dee/docs/decisions/0018-catalogue-durable-publication-evidence.md#historical-authorization",
  "policy_sha256": "c9a88eeb6c7e6d0a7f1a08eaa07eeed5ea251449db7104f7757626842cf1bbe9",
  "publication_seconds": 300,
  "recovery_decision": "disabled-pending-permanent-archive-decision",
  "selection_binding_decision": "https://github.com/benchristian88/atlas/blob/76031dc6358a81c3babd15f74d407e22f0778dee/docs/decisions/0018-catalogue-durable-publication-evidence.md#selection-binding",
  "selection_seconds": 900,
  "signer_revision": "4be90c5292f931497473595a0958cc5e0f9d1beb",
  "verification_environment_id": 25016263801
}
```

Its literal `APPROVED_FUTURE_POLICY_SHA256` is:

```text
83766234eaf1caa24ad067eae414ca3ab381bdbcf9842b10359e200e9dc7324d
```

The existing independent Atlas bootstrap review supplies numeric publisher,
maintainer, repository, environment, workflow, five rulesets and verifier/root
identities; only its reviewed producer revision is replaced with S in the future
policy. The bootstrap approval itself is unchanged. Historical and selection
references are pinned to accepted ADR 0018 at immutable Atlas commit
`76031dc6358a81c3babd15f74d407e22f0778dee`. Recovery remains
`disabled-pending-permanent-archive-decision`.

## Separate Docker Compose installation authority

`APPROVED_REMOTE_INSTALLATION` in
`apps/api/app/services/remote_connector_packages.py` is exactly:

```json
{
  "approval_reference": "atlas-owner-2026-11-05-official-catalogue-docker-compose-installation",
  "packaging_mode": "docker_compose",
  "publication_policy_sha256": "83766234eaf1caa24ad067eae414ca3ab381bdbcf9842b10359e200e9dc7324d"
}
```

Its literal `APPROVED_REMOTE_INSTALLATION_SHA256` is:

```text
a375a626042e7f02c14f0bc2d11b2723263394327888a1d73611ffcaaf1605f5
```

The approval reference records the explicit owner instruction implemented by this
change, including the clarification that later catalogues and Connectors use the
same authority. It does not claim a separate earlier approval event. It approves
Docker Compose remote installation of individually selected eligible official
packages under this publication authority, not automatic installation or any
specific Connector/version. Its binding is the **Atlas publication-policy
fingerprint**, distinct from the producer's original-policy digest.

Both fingerprints use the existing production
`sha256(official_catalogue_ingestion.canonical(asdict(policy)))`: sorted JSON keys,
two-space indentation, UTF-8, `ensure_ascii=False`, `allow_nan=False` and one final
newline. They are separately pinned literals, never dynamically repaired.
Reproduce from `apps/api` without provider calls:

```bash
.venv/bin/python -B - <<'PYCODE'
from dataclasses import asdict
from hashlib import sha256
from app.services import catalogue_future_authorization as future
from app.services import remote_connector_packages as remote
from app.services.official_catalogue_ingestion import canonical
for policy, expected in [
    (future.approved_future_policy(), future.APPROVED_FUTURE_POLICY_SHA256),
    (remote.approved_remote_installation(), remote.APPROVED_REMOTE_INSTALLATION_SHA256),
]:
    assert sha256(canonical(asdict(policy))).hexdigest() == expected
    print(canonical(asdict(policy)).decode(), expected)
PYCODE
```

## Future catalogues and installation safeguards

Catalogue 3, Catalogue 4 and subsequent properly authenticated releases under the
same S/policy/identities require no new approval fingerprint or Atlas code change
merely because sequence, release/asset IDs, content/pointer digest, Connector ID or
version advances. New active entries become discoverable and eligible for
individual administrator review. A changed signing authority or publication policy
still requires independent approval. Existing capacity bounds remain: 32 revisions,
32 MiB total input, 8 MiB evidence per revision, 240-second retrieval and 300-second
lease. This change does not remove the documented finite-history capacity limit;
exceeding it fails closed and requires separate history-capacity work.

The existing Master Administrator permission/global scope, exact
Connector/version/digest/catalogue/asset confirmation, current-pointer rereads,
immutable release/asset identity, genuine package hash/Sigstore verification,
PackageStore safety, mappings, compatibility, independent runtime verification,
activation audit and local-release restrictions remain enforced. No fallback
selects an unlisted, withdrawn or different Connector/version. Already installed
ordinary packages continue to operate offline.

Native/systemd remote installation remains unsupported with
`remote_install_requires_docker`. Existing operator-staged/bundled native packages
remain supported. Catalogue, Manifest and immutable package bytes stay independent
of deployment mode, so future native support needs no package republication.

The labelled synthetic forward-compatibility regression advances full history
through sequences 3 and 4, changes numeric release/asset identities and introduces
new versions and a new Connector while holding both approval records/fingerprints
fixed. Each new selection still requires exact confirmation. Synthetic verifier
outputs are confined to test fixtures; genuine package verification is separately
exercised by the existing unchanged signed Proxmox package tests.

## Remaining fresh Docker deployment qualification

The new development LXC is `192.168.3.220`; rebuilding/accessing it requires separate
operator authorisation. Exclude `atlas-test-docker` from every operation. This is a
fresh disposable development installation with no historical application-data
migration requirement. Existing migrations initialise PostgreSQL; none is added.

1. Review/commit this local change through the human PR process and pass GitHub CI.
   Record the exact approved Atlas build/release identity; it is not yet established.
2. After separate target/rebuild approval, verify that Atlas release artifact and
   follow [fresh Docker installation](installation.md). Run
   `python3 infra/install/compose.py` from its verified package root, retain generated
   secrets privately and complete initial administrator setup. Verify Compose
   runtime health and its approved baseline.
3. As a Master Administrator open Integrations → Catalogue and check the official
   catalogue. Record the actual current sequence and full accepted history. If
   current is still Catalogue 2, require the exact identities above, retained
   sequence-one history, withdrawn 0.2.0 and eligible 0.2.2. Do not force a rollback
   if a later valid catalogue has become current. Respect provider cooldown/backoff;
   no token fallback or cooldown bypass is authorised.
4. Deliberately resolve managed mappings. Do not create taxonomy automatically from
   downloaded labels. Review and individually confirm the intended package identity.
   For unchanged [Proxmox 0.2.2](https://github.com/benchristian88/atlas-connectors/releases/tag/proxmox-v0.2.2),
   the immutable release is `429608780`, tag `proxmox-v0.2.2`, package asset
   `693849044`, source `e58788a667c0c0006477ac149e8ad28aedda0745`, package SHA-256
   `2d66fc69b9cf9c70d7df117fe41bff3e3e056299f1908cde965e9e3f75e59abf`.
   Never rebuild, modify or republish it. Choose **Verify and install** and record
   genuine package/runtime verification, installed identity and activation audit.
5. Configure an Integration in its authorised customer/site using normal secret-safe
   forms and separately authorised real-source credentials. Test connection and
   perform deliberate read-only discovery. This source qualification remains open.
6. Under separate operational approval, verify restart continuity, offline installed
   operation, renewed live currentness after restore, RBAC and retained history.
   Record Atlas/catalogue/pointer/package identities, audit/results and screenshots.

Local tests and original-evidence checks do not establish LXC networking, Proxmox
ACL/source compatibility, deployed ingestion, package installation or operational
acceptance. Producer gate changes, signing, publication and either LXC are outside
this local approval change.
