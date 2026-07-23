# Codex Instructions for Atlas

You are working on Atlas, an infrastructure knowledge and documentation platform for MSPs and internal IT teams.

Do not make large architectural changes without being asked.

Follow the architecture documents in docs/architecture.

Follow the MVP brief in docs/product/mvp-brief.md.

Prefer small, testable changes.

When implementing a task:

1. Explain the intended change.
2. List files to be created or modified.
3. Implement the change.
4. Add or update tests where practical.
5. Run relevant checks.
6. Summarize what changed.

Do not store secrets in logs.

Do not display saved secrets back to users.

Do not hard-code Proxmox-specific assumptions into the generic asset model.

Keep raw discovery data separate from normalized Atlas assets.

Repeated discovery runs must be idempotent.

If an asset disappears from a discovery run, mark it as stale later. Do not delete it automatically in the MVP.

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