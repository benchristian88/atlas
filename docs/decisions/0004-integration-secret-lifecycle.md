# 0004 — Reuse application-key secrets with separate control and callback credentials

Status: **Accepted**

Date: 2026-10-11

## Context

`config.py:data_encryption_key`, `mfa.py` AESGCM and `encrypted_data.py`
all-adapter rewrap are maintained foundations. Only MFA encrypted records exist;
a generic Integration SecretProvider has not been implemented.

## Decision

Integration secrets reuse `ATLAS_DATA_ENCRYPTION_KEY`; add no operator-managed
credential master key. Use maintained AESGCM, fresh nonces and Integration-specific
versioned AAD as specified by SecretProvider. Add a registered Integration adapter
to existing atomic all-adapter rewrap and portable encrypted-backup lifecycle.

User/API secrets are write-only; return configured state only. Internal leases
are field/job/expiry bound, redact logs/events/errors and revoke/remove material
on success/failure/cancel/recovery. Runtime control uses a generated independent
per-install high-entropy service secret on every private HTTP operation. AIP uses
separate short-lived run/Integration-bound audience/JTI/expiry tokens. Neither
credential derives user-session authority or uses the encryption key as a token.

## Alternatives considered

A second master key fragments operator recovery. Reusing AUTH_SECRET/data key
for runtime traffic merges unrelated authority. Browser secret reveal and durable
runtime credentials violate the job-scoped/write-only boundary.

## Consequences and validation

I2 adds secret records/provider/rewrap tests; I1 adds protected control credentials;
I3 adds callback issuance/revocation. Preserve destination-local control/auth
secrets, invalidate restored leases/tokens and authenticate every encrypted field
before releasing restore maintenance. Existing MFA context/behaviour is unchanged.

See the [Integration alignment audit](../architecture/integrations/integration-alignment-matrix.md),
[active v1.3 design](../architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md)
and [staged contracts](../architecture/integrations/contracts/README.md).
Implementation status remains in the feature ledger; acceptance of this decision
is not evidence that runtime/catalogue/vendor code exists. Revisit through a
superseding ADR if these authority, execution or ownership boundaries must change.
