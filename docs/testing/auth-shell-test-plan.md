# Authenticated application shell test plan

This is the manual browser smoke test for the Atlas cookie session, profile,
active context, and permission-aware shell. Use the automation and migration
coverage matrix in
[security-and-access-test-plan.md](security-and-access-test-plan.md) alongside
it; unchecked cases are not evidence of an existing passing test.

## Test accounts and contexts

Prepare at least these isolated records:

- Customer A / Site A1 and Site A2, with distinct assets and relationships.
- Customer B / Site B1, with distinct assets and relationships.
- A global Master Administrator.
- A Customer Administrator assigned only to Customer A.
- A Viewer assigned only to Site A1.
- A user with Viewer assignments to Site A2 and Site B1.

Use synthetic passwords and data. Never run destructive lifecycle cases against
the only production Master Administrator.

## Bootstrap and forced password change

- [ ] Start with an empty database and all three valid
  `ATLAS_BOOTSTRAP_ADMIN_*` values; exactly one active global Master
  Administrator is created.
- [ ] Restart with the same values; no user, assignment, or role is duplicated
  and no password changes.
- [ ] Start an already-initialised database with different bootstrap values; no
  account or password changes.
- [ ] Start an empty database with no bootstrap values; startup succeeds but no
  account is created.
- [ ] Partial or invalid bootstrap configuration fails safely without printing
  the password.
- [ ] The bootstrap account can log in but protected navigation is restricted to
  password change.
- [ ] Wrong current password and mismatched confirmation produce useful errors.
- [ ] A successful replacement clears forced-change state and invalidates the
  pre-change session.

## Login, cookie, and protected routes

- [ ] `/` and every protected page redirect to `/login` while logged out.
- [ ] Valid login sets `atlas_session` with `HttpOnly`, `SameSite=Lax`, and the
  expected `Secure` setting; no session/token appears in `localStorage`.
- [ ] Invalid credentials use a generic error and create no session.
- [ ] Repeated failures trigger the temporary lock behavior without
  revealing whether an email exists.
- [ ] Disabled and locked users cannot log in.
- [ ] `/auth/me` and a protected data page remain authenticated after refresh.
- [ ] The header shows the current user's display name and profile access on
  every protected page.
- [ ] Logout works from every protected page, removes the cookie, invalidates
  the old session version, and redirects to `/login`.
- [ ] Reusing a cookie captured before logout or password change returns `401`.
- [ ] A legacy `atlas_access_token` local-storage value is discarded and does
  not authenticate a request.

## Profile

- [ ] Profile shows email, display name, roles, and assignment scope without
  showing internal password/session data.
- [ ] A user can change only their display name through profile editing.
- [ ] A normal user cannot submit role, assignment, email, active-state, or
  session-version fields to expand access.
- [ ] Password policy and confirmation are enforced by the API, not only the
  form.

## Active customer/site context

- [ ] The Viewer assigned only Site A1 is automatically placed in Customer A /
  Site A1 without an unnecessary prompt.
- [ ] The multi-site user can select only Site A2 and Site B1; changing customer
  clears the old site and filters the options.
- [ ] The current `Customer / Site` appears in the header and persists across
  protected navigation and refresh.
- [ ] A stored stale, malformed, or newly unauthorized selection is cleared and
  cannot retrieve data.
- [ ] Global/all-customers context is available only to an appropriately scoped
  user, and create actions require a concrete customer/site.
- [ ] Asset, network, relationship, dashboard, and topology screens all update
  to the selected context.
- [ ] New assets inherit the active context; request tampering to another
  context is rejected.
- [ ] A relationship picker contains only valid same-site endpoints and the API
  rejects manually submitted cross-customer/cross-site IDs.

## Navigation and administration

- [ ] Viewer navigation has no create/edit/delete or administration actions;
  direct API attempts still return `403`/non-disclosing `404`.
- [ ] Customer Administrator sees only permitted administration functions and
  cannot discover Customer B data or totals.
- [ ] Users without `users.view`, `roles.view`, managed-type permissions, or
  `audit.view` do not see those sections and cannot open them directly.
- [ ] Permission-dependent navigation does not flash inaccessible controls while
  `/auth/me` is loading.
- [ ] The final usable global Master Administrator cannot be disabled, demoted,
  or stripped of its last master assignment.

## Managed data UI

- [ ] Active asset/relationship types appear in creation choices; inactive
  types remain labelled on existing records but not offered for new ones.
- [ ] The UI explains why referenced/system types cannot be deleted and offers
  deactivation where allowed.
- [ ] Applicable custom fields render in configured order and use the correct
  input type; Viewer values are read-only.
- [ ] Inactive fields with existing values remain visible as historical data.
- [ ] Asset icons resolve override, type default, then generic fallback in list,
  detail, relationship, and topology views; a broken remote image falls back.
- [ ] Audit filters work and no edit/delete affordance is present.

## Shell stability and accessibility

- [ ] Customer/site/context queries do not repeatedly refetch while idle.
- [ ] Empty, loading, forbidden, and server-error states are stable and useful.
- [ ] `/dashboard` and `/` do not render duplicate nested shells.
- [ ] Context selectors, menus, dialogs, and forms are keyboard usable and have
  accessible labels/focus behavior.
- [ ] Narrow-screen layout keeps the current context and logout/profile actions
  reachable.
