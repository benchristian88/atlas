# Knowledge Foundation v2 manual test

## Prerequisites

- Apply Alembic migrations through `20260719_0009`.
- Sign in with `discovery.simulate`, `reconciliation.view`,
  `reconciliation.decide`, and `changes.view` in the test customer/site.
- Create **Home Lab / Home** with existing assets **pve1** and **docker01**.

## Complete snapshot and absence

1. Open **Discovery → Simulate discovery**.
2. Use coverage key `homelab-assets`, enable **Complete snapshot**, and submit
   observations for `manual:pve1` and `manual:docker01`.
3. Confirm the result says **First baseline** and creates no no-longer-observed
   item.
4. Submit a second complete snapshot with the same coverage key containing only
   `manual:pve1`.
5. Confirm the result reports one **No longer observed** item.
6. Confirm docker01 still exists and remains unchanged.
7. Repeat the same snapshot. Confirm no duplicate open item appears.
8. Open **Reconciliation → Actionable**, filter **No longer observed**, and
   confirm source, entity, last-observed time, missing-since time, and proposed
   actions are readable.
9. Choose **Mark inactive** (or another disposition) and confirm the asset is
   updated only after that decision.

## Re-observation

1. For an open missing episode, submit another complete snapshot containing
   docker01 again.
2. Confirm the missing item moves out of Actionable and the simulation reports
   one reobserved entity.
3. Confirm **Changes** shows the missing and reobserved events once each.
4. If docker01 was previously marked inactive, confirm Atlas creates a
   reviewable proposal to restore active rather than silently changing it.
5. Repeat with a retired test asset and confirm it remains retired.

## Timeline, history, scope, and stability

1. Open **Changes** and test change-type and text filters plus pagination.
2. Confirm relationship creation/deletion and assertion retraction appear as
   meaningful events, while login and access changes remain in **Audit**.
3. Open docker01 and expand **Fact history**. Confirm current, superseded, and
   retracted values remain ordered and missing provenance displays
   **Unavailable**.
4. Confirm dashboard reconciliation counts match the queue page.
5. Repeat as a user scoped to another customer/site and confirm these runs,
   items, counts, changes, and facts are not visible.
6. Leave Dashboard, Changes, Reconciliation, and asset detail idle. Confirm the
   browser Network panel shows no uncontrolled polling or render-loop requests.
