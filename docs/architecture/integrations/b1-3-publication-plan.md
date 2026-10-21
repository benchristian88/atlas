# B1.3 publication prerequisite: separate implementation plan

Status: **Required, not applied**. Inspection date: 21 October 2026.

The current `atlas-connectors/.github/workflows/catalogue.yml` performs preparation,
attestation and candidate-artifact upload only, with contents-read permission.
The established `catalogue-v1` release holds both the updateable `catalogue.json`
and numbered historical assets. Its API reports `immutable: false`. Making that
release immutable would also prevent the alias from advancing. Replacing assets
inside it cannot supply immutable history. Build attestations do not establish
publication approval; environment names do not prove reviewer configuration.

No connector repository, workflow, release, tag or setting was modified in B1.3.
No alternate current URL has been invented or enabled. This plan refines the
existing accepted immutable-publication boundary without rewriting ADR history.

A separate operator-authorized publication task should:

1. Preserve sequence-1 bytes and genuine attestations permanently. Do not rebuild,
   replace or reinterpret them. Audit existing connector release mutability too.
2. Define and approve one versioned immutable catalogue release per sequence, with
   exact original bytes and retained attestations. Publish via a draft, verify
   every asset against genuine provenance, then finalize with GitHub immutability.
   Record release ID, snapshot asset ID, digest, sequence and source commit.
3. Define a separate mutable current-discovery document/channel whose exact URL,
   serialization, atomic update method and signing/approval profile are reviewed
   before consumer implementation. It must identify the selected immutable
   sequence/release/asset/digest and bind approval evidence independently of build
   provenance. Choose an endpoint deliberately; this document establishes none.
4. Establish and audit protected main reviews, publication authority, release/tag
   protection and reviewer settings. Record how a consumer can independently
   enforce approval/selection. A convention or an environment label is insufficient.
5. Publish the immutable snapshot before advancing the pointer. Make sequence
   allocation serial and monotonic; retain withdrawals and immutable Manifest,
   digest, tag and asset identities. Test interrupted publication and pointer races.
6. Implement a reviewed Atlas source-policy/adapter update using that established
   contract. Verify pointer authority, immutable snapshot identity and provenance,
   then reread the pointer before transactional acceptance. Retain the existing
   B1.1/B1.2 profiles unless an explicit reviewed trust-policy change is necessary.
7. Re-run genuine live acceptance and adversarial pointer/history tests. Mark B1.3
   fully accepted only after trusted promotion, unchanged confirmation, higher
   sequence advancement, restart and last-known-good recovery are demonstrated.

Executable package releases need equivalent immutable publication and independent
eligibility before B3. Generalize producer connector-release triggers deliberately
for future connectors. Atlas's generic parser, history index and projection do
not require connector-specific acceptance logic.
