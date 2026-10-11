# Historical records

This directory preserves dated planning, review, implementation and validation
evidence. It is not the active roadmap, installation manual or current feature
reference. Original milestone/branch names and past execution results are
retained for traceability. Later supplied results are appended, never backdated
into earlier execution tables.

- `product-plans/`: superseded development roadmap, product brief and release plans.
- `product-reviews/`: dated feature and UI audits, including the previous detailed ledger.
- `implementation-prompts/`: completed implementation prompts and agent context.
- `deployment/`: superseded deployment migration guidance.
- `integrations/`: superseded Integration design provenance; current target is
  [v1.3](../architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md).
- `validation/`: historical implementation, test and acceptance records.

The [core hardening acceptance closure](validation/core-hardening-acceptance-closure.md)
consolidates earlier validation and later operator confirmation, with residual
pre-1.0 acceptance gaps. It supports proceeding to integrations/onboarding;
it is not final whole-product security or release qualification.

Current guidance is in the documentation index and `docs/product/status.md`.
Architecture Decision Records remain in `docs/decisions/` because accepted
architectural rationale is still relevant; they do not declare feature status.
