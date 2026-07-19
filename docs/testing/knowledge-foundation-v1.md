# Knowledge Foundation v1 manual test

This test confirms the discovery → evidence → assertion → reconciliation flow
without bypassing Atlas's accepted operational asset and relationship model.

## Prerequisites

- Apply migrations through `20260719_0008` and start the API and web services.
- Sign in as a user with `integrations.manage`, `assets.view`, `assets.edit`,
  `relationships.create`, `discovery_runs.archive`, `discovery_runs.delete`,
  `assertions.retract`, `assertions.delete`, and access to the test
  customer/site.
- Create customer **Home Lab**, site **Home**, and an asset named **pve1**.
- Ensure `virtual_machine` is an active asset type and `runs_on` is an active
  relationship type.

## Discovery and provenance

1. Select **Home Lab / Home** in the app header.
2. Open **Discovery → Simulate discovery**.
3. Keep the example `manual:docker01` observation. If necessary, update its
   asset type to an active key and its target to `manual:pve1`.
4. Run the simulation. Confirm the result reports one evidence record, sourced
   assertions, and reconciliation items.
5. Open **Discovery** and confirm the completed run is listed with **Manual
   Discovery Simulation** as its source.
6. Confirm docker01 is not yet present in **Assets** or **Knowledge Graph**.

## Reconciliation decisions

1. Open **Reconciliation** and locate the newly discovered docker01 item.
2. Defer it. Confirm it disappears from the open list and docker01 is not
   created. Run the simulation again if a new open item is needed.
3. Reject a new item and again confirm no asset or relationship is created.
4. Run the simulation again, accept the docker01 asset item, and confirm
   docker01 now appears in **Assets**.
5. Accept the `docker01 → runs_on → pve1` relationship item. If Atlas reports
   that an endpoint is missing, accept both asset items first and retry.
6. Open **Knowledge Graph → Platform** and confirm docker01 appears beneath
   pve1 through the accepted relationship.

## Existing asset and relationship matching

1. Create **pve1** and **docker01** manually in the same customer/site.
2. Optionally create `docker01 → runs_on → pve1` manually.
3. Simulate asset observations with external IDs `manual:pve1` and
   `manual:docker01`, plus the `runs_on` relationship.
4. Confirm Atlas links both external identities to the existing assets instead
   of offering duplicate assets.
5. If the relationship already exists, confirm no open relationship item is
   created and the observed and declared assertions appear as provenance.
6. Delete the relationship and rerun simulation. Confirm the item displays
   **Current: No current relationship**, **Observed: docker01 → runs on →
   pve1**, and both endpoint statuses are resolved.
7. Accept it and confirm topology updates immediately.
8. To test ambiguity, create two same-site assets with the same normalized name
   and type. Confirm Atlas creates a **possible duplicate** item and does not
   link either automatically. Select the intended asset with **Link asset** and
   confirm related relationship items become acceptable after the refresh.

## Asset provenance

1. Open the docker01 asset detail page.
2. Confirm **Current provenance assertions** lists predicate, value, source,
   truth classification, confirmation state, first/last observation, and
   confidence.
3. Refresh the page. Confirm the accepted asset, relationship, and assertions
   persist and no page makes repeated requests while idle.

## Safe cleanup and lifecycle controls

Deletion is only for unused development/test evidence. Archive a run whenever
it supports confirmed assertions, accepted reconciliation decisions, source
identity links, or later provenance. Archiving keeps the run, evidence,
assertions, source links, and reconciliation history in PostgreSQL.

Retraction preserves assertion and evidence history while marking the assertion
non-current. Deleting or retracting an assertion does not reverse accepted
assets, interfaces, relationships, networks, or facts. Reversing operational
knowledge requires a separate reconciliation workflow.

1. Run a simulation and leave every reconciliation item unaccepted.
2. Open **Discovery**, delete that run, and confirm its evidence, assertions,
   and unaccepted reconciliation items disappear. Confirm the DataSource
   remains.
3. Run another simulation and accept an asset or relationship.
4. Confirm **Delete** is unavailable for that run. Archive it with a reason and
   confirm the operational asset and its provenance remain.
5. Enable **Include archived**, confirm the Archived badge and reason, then
   restore the run.
6. Open an asset with assertions. Delete an unused unreviewed assertion and
   confirm its asset and evidence are unchanged.
7. Retract a confirmed assertion with a reason. If Atlas warns that this is the
   only current provenance, explicitly confirm the gap.
8. Confirm the assertion displays **Retracted**, its details and evidence remain
   available, and the operational asset is unchanged.
9. Resize the asset page. Confirm the assertions table remains within its card,
   scrolls horizontally where needed, and long JSON values are contained in the
   details dialog.

## Scope and audit checks

1. Repeat list calls as a user scoped to a different customer/site and confirm
   the test run, assertions, and reconciliation items are absent.
2. Confirm the audit log includes the simulated run and each reconciliation
   decision, archive/restore/delete action, and assertion retraction/deletion
   without raw credentials or tokens.
3. Confirm existing manual assets, networks, interfaces, and topology views
   still behave as before.
