# Reconciling discoveries from multiple sources

Use **Reconciliation** in the correct customer/site context. Review source,
external identity and observed information under **Evidence and details** before
associating records. Similar names suggest candidates; they do not prove identity.

For example, Source A already supplied `grafana` and its `eth0` interface. Source B
reports the same LXC using different external IDs:

1. On the possible-duplicate Asset, open **Link an existing asset**, choose the
   accepted Grafana Asset and select **Link asset**. This retains its UUID and
   existing source associations. Facts and technical proposals remain independent.
2. Expand **Network** on the refreshed card. On the observed Interface, open
   **Link existing interface**. Choices belong only to the accepted Asset. Compare
   interface name, MAC, IP and available Network ID before selecting **Link interface**.
   If no candidates exist, confirm whether this is a new interface before accepting
   it. Existing same-name interfaces must be linked explicitly or the conflict
   resolved by an operator; Atlas will not create a second `eth0` automatically.
3. Linking retains the existing Interface UUID and configuration. Review the
   resulting **Accepted configuration** and **Observed configuration awaiting
   review**. **Accept interface changes** applies the observed values. Reject or
   defer to preserve the accepted values. Source-specific facts remain separate.
4. If the observation references a Network, review its entity card. Use **Link
   existing network** when it represents an existing Network in this customer and
   site, or accept it as new after verifying that it is distinct. Review VLAN,
   CIDR, gateway and membership carefully. `vmbr0` alone is not an authoritative
   Atlas Network identity.
5. Review remaining facts and relationships. Subsequent discovery uses the stored
   source identities; it should not ask to match those same identities again.

**Waiting** names an actual missing prerequisite. Linking an Asset does not link
its Interfaces or Networks. An Interface's identity can be linked while its
configuration still waits for a Network. Relationships wait for both endpoints;
source facts wait for their subject. Follow **Review …** to the prerequisite and
use **Return to previous entity** to retain your queue position. Refresh after a
stale-decision error and review the latest version before retrying.

**Accept all** decides the explicit proposal set in the current filtered review.
It accepts eligible records in dependency phases and retains successful decisions
if another fails. The result lists accepted, already resolved, waiting and failed
records with reasons. It does not accept another Asset/Network on your behalf,
perform identity matching, or guarantee an atomic group transaction. A duplicate
name error means an explicit link is required, not that evidence should be removed.
New configuration reviews created by a link require a fresh review.

Candidate browsing requires `networks.view`; technical linking additionally needs
`networks.edit` and `reconciliation.decide`. Asset linking also needs `assets.edit`.
The backend validates every target regardless of what the browser offered.
Native disclosures, selectors and buttons support keyboard navigation; use Tab,
Enter/Space and the selector's arrow keys.

Do not delete the original Asset/Interface, rename records to evade uniqueness,
change source external IDs, or reset discovery history to resolve duplicates.
Keep ambiguous observations deferred until their identity can be established.
Do not infer an expected final inventory count from the number discovered.

For local signed-release acceptance, review the [exact-build deployment
constraint](../deployment/local-release-acceptance.md#reconciliation-fix-build-transition)
before planning any deployment. Updating the enrolled live instance is separate
from reviewing this workflow.

## Reading Asset knowledge after linking

The **Summary** tab separates **Accepted Atlas value**, **Operational Atlas value**
and **Latest source observations**. Two sources agreeing on `lxc_container` are
**Observed / Awaiting acceptance** until a field assertion is explicitly accepted;
agreement alone is not an unresolved conflict. Different unaccepted values are
**Unresolved**, while observations differing from selected knowledge are
**Conflicting**. Legacy data can have an operational Asset Type without an
accepted matching assertion. Atlas reports that discrepancy rather than inventing
historical acceptance. Review the corresponding field proposal in Reconciliation.

For two Proxmox sources reporting one LXC and its `runs_on` relationship to one
verified host, **Runs on** shows the host's name and an authorized Asset link.
Expand **Provenance** to see both sources, their observation/acceptance times and
assertion IDs. One logical value does not mean one source assertion was deleted.
Different hosts with the same name remain separate values. An unknown or hidden
target has a safe fallback and no target link. Individual historical, rejected
and retracted observations remain retained in storage. **Raw assertions** shows
up to 200 rows by default (API maximum 1,000); **History** shows at most 500.
Asset detail currently does not page either tab. Summary counts can exceed the
rows these tabs show. Each returned assertion retains its original value and
details actions. Complete retained-history browsing is a separate backlog item.

## Concurrent edits and source re-observation

A proposal reviewed before an administrator changes its canonical Asset field
must be refreshed. An individual stale decision returns HTTP 409; Accept all
reports that record as failed while retaining independent eligible successes.
Review the updated operational value before deciding again. The browser supplies
the reviewed version. Legacy API clients without it cannot overwrite an
intervening field change from the stored review snapshot. A versionless field
request needs a verifiable original canonical baseline; older proposals without
one return 409 even if the displayed value appears unchanged. Refresh and send
the reviewed version. This also detects changed-back values after overlapping
manual transactions. Unavailable canonical records show no current value, rather
than presenting historical proposal text as current.

The refreshed comparison and its evidence details show the actual canonical
Asset value, rather than the proposal's original snapshot. Acceptance records
the value actually overwritten in Changes. If another edit occurs after refresh,
review again. Absence acceptance always requires `expected_version`, including
legacy API callers. `mark_missing`, `mark_inactive`, `mark_retired`/`retire`
declare the selected status explicitly and preserve the prior assertion.
`keep_active` keeps the existing status, even if inactive/retired; `exception`
records an exception without changing status. Bulk cannot choose dispositions.

Selecting one source's scalar value replaces the effective accepted assertion;
all observations and prior decisions remain available. Separate serialized
namespaced decisions can both succeed, with the later decision selected. Source
freshness is independent: the previous source may legitimately report its value
again and offer a fresh review. Repeated identical observations coalesce and never
select themselves. Retraction remains an explicit lifecycle decision.

For an expected database concurrency conflict, refresh and inspect the current
state before retrying. Successful identity linking includes its independent
configuration/name review in the same transaction; failed linking retains neither
a partial association nor a security audit claiming success.

Migration 0032 refuses duplicate accepted scalars and ambiguous/overwritten legacy
lineage before changing schema or rows. A legacy source-stale pointer alone
cannot prove that acceptance did not overwrite source history. Retained accepted
review records do not recover a lost source edge. Keep the verified backup and
0031 schema, gather independent observation/decision evidence, and obtain a
reviewed repair procedure or restore a verified pre-loss backup. Do not clear
links, delete evidence or choose a winning source to bypass refusal. Downgrade
also refuses any lineage that cannot round-trip losslessly through the old single
pointer, including dual lineage. See the [migration contract](../deployment/upgrades.md#reconciliation-integrity-migration-0032).
This is separate from the enrolled live instance's unsupported exact-build
transition. No deployment or enrollment change is authorized by this guide.
