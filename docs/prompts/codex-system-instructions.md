# Codex Instructions for Atlas

You are working on Atlas, an infrastructure knowledge and documentation platform for MSPs and internal IT teams.  Atlas documents infrastructure, applications, business functions,
services, dependencies and operational procedures.

# Working rules

- Do not make large architectural changes without being asked.
- Follow the architecture documents in docs/architecture.
- follow all product and other documents in docs/
-  Read and follow the following project documents:
   - docs/architecture
   - docs/decisions
   - docs/deployment
   - docs/prompts
   - docs/admin
   - docs/testing
   - docs/product
- Follow the MVP brief in docs/product/mvp-brief.md.
- Prefer small, testable changes.
- Inspect existing implementations before adding new patterns.
- Keep API contracts backward compatible unless the task explicitly permits a breaking change.
- Do not add production dependencies without explaining the reason.
- Run relevant tests, linting and type checking after changes.
- Update documentation when behaviour or architecture changes.
- Do not edit generated files manually.

When implementing a task:

1. Explain the intended change.
2. List files to be created or modified.
3. Implement the change.
4. Add or update tests where practical.
5. Run relevant checks.
6. Summarize what changed.

# Development rules
- Do not store secrets in logs.
- Do not display saved secrets back to users.
- Do not hard-code Proxmox-specific assumptions into the generic asset model.
- Keep raw discovery data separate from normalized Atlas assets.
- Repeated discovery runs must be idempotent.
- If an asset disappears from a discovery run, mark it as stale later. Do not delete it automatically in the MVP.
- Reconcile requested work with the current codebase before implementation.
- Identify conflicts rather than silently overriding established decisions.

Significant changes must update:
- architecture documentation;
- the roadmap or release record;
- tests and manual acceptance instructions;
- an ADR where an architectural decision changes.


## Product documentation rule

After implementing or discussing a product feature, update
`docs/product/feature-ledger.md`.

For each feature, record:

- Whether it is planned, partial, implemented, deferred, or abandoned.
- The original product intent.
- Evidence such as files, tests, commits, issues, or conversation transcripts.
- Remaining work and unresolved decisions.

Do not mark a feature as implemented without confirming it exists in the
codebase and, where applicable, has tests.

Also update any documentation that needs changing as a result of the new features, or ardchitecture. 

## Completion criteria
Before reporting completion:
1. Run relevant tests.
2. Run linting and type checking.
3. Review the diff for unrelated changes.
4. Summarise files changed, design decisions and remaining risks.