# Administer knowledge profiles

Open **Administration → Asset types**, then select **Configure** in the Knowledge profile column. The profile shows global requirements and rules anchored to that database-defined Asset Type.

Use **Add requirement** to choose a level, severity, and structured rule. Asset Types, Relationship Types, and Custom Field Definitions are loaded from Atlas; administrators never paste internal UUIDs. A requirement may be required, conditional, or recommended. Severity expresses operational impact independently of that level.

Typical starter profiles are policy examples, not built-in type-name logic:

- Global: name/type/tenancy are already core identity; consider description or purpose as recommended.
- Workload: require a selected outgoing hosting relationship; recommend an IP; use a bounded one-of rule for interface versus an explicit host-networking custom-field state.
- Compute host: require a management interface and optionally a management IP; recommend a physical network connection.
- Switch: require an uplink unless a selected network-role custom field is `root` or `core`; recommend model, firmware, location, and management IP.
- Firewall/router: require a management interface, select appropriate internal/WAN relationships, and recommend backup/configuration knowledge.

Rules reference stable record IDs, so renaming display names is safe. Atlas blocks deletion of referenced definitions. Deactivation marks affected configuration invalid and prevents the evaluator from silently declaring assets complete. Correct the reference or deactivate the requirement, then reevaluate affected assets.

Changing a profile may open or resolve gaps on its assets. Atlas performs a bounded synchronous pass and exposes a batch reevaluation API for controlled follow-up. Existing assets remain valid even when policy finds gaps.

Gap actions live on Asset detail and in Reconciliation's **Missing knowledge** queue:

- Provide information opens the relevant asset editor.
- Defer records a reason and optional review time.
- Exception records a justified decision and optional expiry.
- Reopen removes the active waiver and evaluates again.

Exceptions should document reality, not conceal unknowns. Prefer providing the missing field, interface, relationship, or sourced assertion when it is available.
