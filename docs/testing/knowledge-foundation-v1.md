# Knowledge Foundation v1 manual test

This test confirms the discovery → evidence → assertion → reconciliation flow
without bypassing Atlas's accepted operational asset and relationship model.

## Prerequisites

- Apply migrations through `20260719_0006` and start the API and web services.
- Sign in as a user with `integrations.manage`, `assets.view`, `assets.edit`,
  `relationships.create`, and access to the test customer/site.
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

## Asset provenance

1. Open the docker01 asset detail page.
2. Confirm **Current provenance assertions** lists predicate, value, source,
   truth classification, confirmation state, first/last observation, and
   confidence.
3. Refresh the page. Confirm the accepted asset, relationship, and assertions
   persist and no page makes repeated requests while idle.

## Scope and audit checks

1. Repeat list calls as a user scoped to a different customer/site and confirm
   the test run, assertions, and reconciliation items are absent.
2. Confirm the audit log includes the simulated run and each reconciliation
   decision without raw credentials or tokens.
3. Confirm existing manual assets, networks, interfaces, and topology views
   still behave as before.
