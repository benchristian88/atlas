# Catalogue 2 review and operator sequence

**Inactive candidate. Do not execute publication, deployment or installation from
this document without the separately recorded approvals below.** No such action
was performed during implementation. Neither Docker LXC was accessed.

The [security remediation report](../catalogue2-security-remediation-report.md)
records request-budget, pre-finalization deadline and generated-workflow corrections.
Local regression success does not supply any approval listed below.

The new development LXC is `192.168.3.220`. Rebuilding it requires explicit operator
approval. The historical `atlas-test-docker` instance is excluded from every step.
There is no application-data migration requirement; existing migrations still
initialize a fresh PostgreSQL database. No database or installed package is erased
by catalogue refresh or withdrawal.

## Review and approvals

1. Review both uncommitted candidates as two coherent implementation PRs. Preserve
   Connectors Phase 1 and Atlas's clean `dev` baseline. Do not accept Proposed
   [ADR 0018](../decisions/0018-catalogue-durable-publication-evidence.md) implicitly.
2. Explicitly accept or reject historical 900/300-second bounds, supported witness
   semantics and original-run time checks, same-C/run selection binding, the seven
   assets and **disabled recovery** disposition. If permanent recovery audit is
   required before publication, that remains an implementation blocker.
3. After review, populate the producer's release-owned `SuccessorApproval` and
   canonical SHA-256 fingerprint with the accepted decision references and exact
   policy digest. Freeze/review that implementation as immutable successor **S**.
   S is deliberately not embedded in its own approval record: the existing
   independently reviewed caller/workflow/verifier trust pins authenticate S.
4. Prepare both inactive workflow outputs using the frozen S:

   ```bash
   .venv/bin/python tools/prepare_evidence_workflow.py --revision REVIEWED_S \
     --kind publisher --output /tmp/catalogue-publish.review.yml
   .venv/bin/python tools/prepare_evidence_workflow.py --revision REVIEWED_S \
     --kind catalogue-build --output /tmp/catalogue-build.review.yml
   ```

   These commands run in atlas-connectors. Replace `REVIEWED_S` with its actual
   40-hex SHA; placeholders reject. Review the complete generated workflows, then
   separately approve adopting them at the existing `catalogue-publish.yml` and
   `catalogue.yml` paths. Keep the existing isolated reusable signer path/profile;
   it is pinned at S. The build workflow must build `catalogue/candidate-v2`, matching
   the driver, rather than the still-preserved active sequence-one registry.
   Generation now uses byte-pinned historical S4 templates. Review the separate
   adoption PR's active-control preservation fingerprints deliberately; preserve
   historical S4 coverage and run the successor-specific security tests for both
   generated outputs. Do not disable those checks to adopt the workflow.
5. Separately approve all producer pin/setting changes, including exact equality
   between workflow implementation S, reusable workflow S, source verifier-trust S
   and independently administered verifier policy S. Keep
   `CONNECTOR_PUBLICATION_ENABLED` disabled: Proxmox 0.2.2 is already published and
   needs no package publication. The proposed new `CATALOGUE_EVIDENCE_ENABLED`
   remains unset/false until its separate owner activation.
6. Independently populate Atlas `FuturePublicationPolicy` plus its canonical
   fingerprint: accepted successor S (also the reviewed producer revision), exact
   policy SHA-256, all numeric identities/rulesets/workflow, explicit time limits
   and owner decision references. Use Atlas's existing release-owned binary/root
   pins, never pins fetched with the archive. Approve remote executable eligibility
   separately using `RemoteInstallationPolicy` plus its own fingerprint, bound to
   that publication-policy fingerprint and Docker Compose mode.
7. Run hosted producer Python 3.12 CI/security acceptance and a genuine successor
   preflight with publication disabled. Check exact certificate/statement identity,
   isolation and original bytes. A signed `acceptance_only: true` result is never
   ordinary-publication authority. Obtain independent review before activation.

No S, future run ID, catalogue release ID or approval reference is invented here.
A future approval is a reviewed change, not an API/env override on Atlas.

## Publish after approvals only

In the reviewed atlas-connectors source at final main commit **C**:

1. Build twice with `tools/build_catalogue_candidate.py --output NEW_DIRECTORY`
   and compare the exact numbered snapshot digest. Check sequence 2, retained
   0.2.0 identity with only withdrawal status changed, and published 0.2.2:
   release `429608780`, package asset `693849044`, source
   `e58788a667c0c0006477ac149e8ad28aedda0745`, package SHA-256
   `2d66fc69b9cf9c70d7df117fe41bff3e3e056299f1908cde965e9e3f75e59abf`.
   Independently reverify immutable release/tag, complete asset inventory and
   genuine package bundle. Never modify those historical immutable assets.
2. Require successful required CI at C and no further main changes. Run the
   existing catalogue build workflow at C/main and retain its actual run ID and
   genuine build attestation. For example, after explicit authorization:

   ```bash
   gh workflow run catalogue.yml --ref main
   gh run watch ACTUAL_BUILD_RUN_ID --exit-status
   ```

3. After independent live-gate approval set only the reviewed catalogue evidence
   enable setting. Require a fresh first-attempt human publication dispatch at C:

   ```bash
   gh workflow run catalogue-publish.yml --ref main \
     -f operation=publish -F acceptance_only=false
   gh run watch ACTUAL_PUBLICATION_RUN_ID --exit-status
   ```

   The driver admits the original signed preflight before write credentials,
   stages its exact archive first, saves runner-local checkpoints after observed
   writes, obtains the original selection signature, verifies seven assets,
   finalizes immutably, rereads identities/bytes and CAS-advances current.
   It must have at least thirty seconds remaining inside the original publication
   window immediately before finalization. A provider delay or ambiguous write
   can still strand an immutable release; failed post-publication verification
   leaves current unchanged. Stop and preserve evidence for independent review.
   Do not rerun an ambiguous/expired job, invent a checkpoint or use the frozen
   four-asset publisher for this release. Cross-job recovery remains disabled.
4. Anonymous independent GET verification must establish exactly seven immutable
   assets at `catalogue-000002`, by-ID/by-tag agreement, original selection/build/
   preflight signatures, exact policy bytes, all temporal constraints, and complete
   contiguous 1→2 selection history ending at the original pinned root. Record
   actual numeric release/asset IDs and original-byte hashes. Re-disable the new
   live catalogue gate after publication under the operator's reviewed procedure.

## New Docker instance, after separate deployment approval

1. Explicitly confirm target `192.168.3.220` and obtain any rebuild approval. Do not
   select, connect to or reset `atlas-test-docker`. Use the reviewed Atlas build
   containing both independently approved consumer policies. No existing local
   signed-release enrollment is transferred or bypassed.
2. Verify the release artifact and follow [fresh Docker installation](installation.md):
   from the new verified package root run `python3 infra/install/compose.py`.
   Keep its generated secret file private; finish initial administrator setup.
   Use the normal runtime-enabled installation and verify Docker Compose runtime
   health/baseline. The exact approved Atlas build/release identity is still TBD.
3. Open Integrations → Catalogue as a global package administrator. Check official
   catalogue. Confirm accepted sequence 2 and retained sequence-one trust/history;
   Proxmox 0.2.0 must appear withdrawn and have no install action.
4. Resolve global mappings for Proxmox 0.2.2. Existing taxonomy may lack Cluster or
   Member Of records; deliberately create/select suitable managed records using
   normal administrator controls. Do not auto-create taxonomy from downloaded
   labels or suppress mapping checks.
5. Choose **Review installation**, verify 0.2.2 and the exact digest above, check the
   confirmation and choose **Verify and install**. Confirm the installed identity,
   independent runtime verification and activation audit. A changed catalogue,
   withdrawn entry, wrong digest/asset, source conflict, missing approval or failed
   verification must preserve the previous active package.
   Fresh refresh plus installation is regression-bounded to forty anonymous REST
   requests, with asset/CDN transfers counted separately. Shared-IP traffic, retries
   and secondary limits can still cause rejection; respect the reported backoff.
   Do not add an administrative-token fallback or repeat refresh during cooldown.
6. Use Add Integration for the installed Connector, choose the authorized customer/
   site, configure it through the existing secret-safe forms, test connection and
   perform a deliberate read-only discovery run. This requires separately approved
   real-source credentials and operational qualification; none was done here.
7. Restart services and verify installed package/configuration continuity. Temporarily
   deny catalogue egress in the approved test environment: previously installed
   package verification and configured operation must remain available, while new
   remote install/refresh fails safely. Restore egress and verify unchanged refresh,
   backup/restore currentness invalidation, RBAC and retained history.

Record exact Atlas build, catalogue/pointer/package identities, screenshots,
request/audit results and genuine source qualification. Only then assess feature
closure. Local synthetic/Docker tests do not qualify LXC networking, Proxmox ACLs,
source compatibility or live successor publication controls.
