# 0013 — Exact sequence-one consumer bootstrap trust approval

Status: **Accepted**

Date: 2026-10-25

## Decision

The project owner approved the **complete, unchanged** Atlas-owned
`BOOTSTRAP_POLICY_PROPOSAL` on 25 October 2026, including the restricted
`atlas-bootstrap-sequence1-exception-v1` historical exception described in
[ADR 0012](0012-official-catalogue-publication-authorization.md).
The fixed decision reference is `atlas-owner-2026-10-25-adr-0013`.

Activate that exact proposal using the existing `AtlasApprovedBootstrapPolicy`
through the no-argument release-owned `approved_bootstrap_policy()` function in
[`catalogue_trust.py`](../../apps/api/app/services/catalogue_trust.py).
Its canonical compact sorted `asdict` JSON SHA-256 is
`d11992962353b4141d734ae28e9dd5d38362bcaaf92029f8278502bd50703867`.
Any alteration to the full proposal, including nested signing, authority or
historical identity pins, fails this activation comparison. Producer metadata,
downloaded policy, environment variables and arbitrary approval strings cannot
activate trust. Pin changes require a reviewed Atlas release and decision.

The approved policy version remains
`atlas-bootstrap-consumer-policy-proposal-v1`; its original name and values are
preserved. The authorization basis is `single-maintainer-v1` with these explicit
independent authority pins:

| Identity | Approved value |
| --- | --- |
| Maintainer / repository / owner | `93822871` / `1414494920` / `93822871` |
| Publication / package environments | `24999137498` / `24617213627` |
| Publisher App / slug / bot user | `5422372` / `atlas-catalogue-publisher` / `346232650` |
| Publication workflow | `392548804` |
| Main / history / bootstrap / current / publication-tag rulesets | `25618213` / `25618809` / `25628137` / `25618684` / `25618901` |
| Reviewed activation source | `51f8693fbcca1e4c6c9615662bca368839ea0757` |

The approval applies only to original sequence **1**, pointer digest
`a275f63d0ac818a193826478328ee324be62353addc5c97a2ed0a28d217b5372`, catalogue digest
`55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd`, release
`catalogue-000001` / `421426993`, catalogue asset `667867351`, and parentless root
`a1597730687be993d766ddb465a0d3362aef2d02`. Original selection run **39896288128**,
attempt **1**, source `8ce0b80c74d6ceb8ce75ac7ec8693f5bba78b305`, and catalogue
build source `91dfd86f18d0b59ff977bb1e8a5fef42c5329943` are distinct from activation.
Issuer, hosted runner, SLSA profile, CLI 2.102.1 and frozen roots are the exact
existing release-owned values in the fingerprinted proposal and ADR 0011.

Only withheld historical `bypass_actors` for the five pinned rulesets may be
tolerated. Contradictory present arrays and every other missing/invalid public
observation reject. Phase 2A's partial-evidence blockers remain intact; its result
does not become general publication authority. Acceptance separately requires
both genuine signature profiles, actual immutable release/asset identity, exact
original bytes, root/source binding, fresh current-ref confirmation and atomic
PostgreSQL trust/history/audit updates.

## Scope and risks

No historical privileged evidence was recovered. Public observations cannot prove
uninterrupted protections or exclude hidden present-day bypass changes. One human
provides no independent veto; compromise of that account, provider, trusted code,
Apps or signing infrastructure remains relevant. Full-database rollback is not
detectable using that database alone. Restore must invalidate currentness and
require renewed live verification while preserving accepted history.

Sequence two and above require the separate stronger publication evidence contract.
ADR 0012 remains **Proposed** for that broader design. This decision refines the
consumer bootstrap approval without rewriting or superseding accepted ADRs 0006
and 0011. Catalogue trust grants no executable eligibility: historical Proxmox
0.2.0 has a mutable package release and remains remotely non-installable. No
installer, runtime, SDK, producer or credential architecture changes are approved.
