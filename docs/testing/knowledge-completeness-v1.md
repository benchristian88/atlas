# Knowledge completeness v1 test plan

## Automated coverage

Run backend tests from `apps/api` with `pytest`, web tests from `apps/web` with `npm test`, and build the web production bundle with Node 22 or newer. Model tests cover the additive tables and UUID convention. Service tests cover idempotent gap opening/resolution, structured interface/relationship/one-of rules, reference validation, and disabled ownership rules. Existing security, CRUD, reconciliation, lifecycle, and UI suites remain regression coverage.

## Manual acceptance

### Workload hosting

1. Select an existing workload-like Asset Type and open its Knowledge profile.
2. Add a critical required outgoing relationship rule, selecting the existing hosting relationship and allowed host Asset Type.
3. Create a workload with no relationship. Confirm it saves, shows a critical gap, appears in Missing knowledge, and updates dashboard counts.
4. Add the required relationship. Confirm the gap resolves, both endpoints reevaluate, the Asset status changes, and Changes contains one resolution event.
5. Reevaluate twice and confirm no duplicate active gap or timeline event appears.

### Interface and exception

1. Add an interface requirement (or bounded one-of policy) to an Asset Type.
2. Create an asset without an interface and confirm an open gap.
3. Record the reason `Uses host networking and has no independent interface` with an optional review date.
4. Confirm exception status, exception counts, and no duplicate gap after reevaluation.
5. Reopen it, add an interface/IP, and confirm automatic resolution.

### Relationship and applicability

1. Configure a switch-like upstream relationship using existing database records and an optional structured `unless` custom-field rule.
2. Confirm missing uplink, automatic resolution after addition, reopening after removal, and non-applicability when the configured root/core state matches.

### Discovery

1. Simulate and accept a new asset with discovered interface and relationship data.
2. Confirm accepted operational data is applied before evaluation and only genuinely missing knowledge creates gaps.

### Security and scope

1. Verify a Viewer can read completeness but cannot edit requirements or create exceptions.
2. Verify a scoped administrator sees and acts only within assigned customer/site scope.
3. Change customer/site context and confirm dashboard, Asset filters, Missing knowledge, and summaries agree.
4. Deactivate a referenced definition and confirm an admin warning rather than an HTTP 500 or false `complete` result.

No test should reset the database. Browser Network should remain idle after page loads; completeness pages do not poll.
