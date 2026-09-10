# Atlas Service model

## Purpose

A **Service** is an operational capability that delivers an outcome. An
**Asset** is a technical thing that implements, hosts, connects, or protects
that capability. Keeping the two concepts separate lets Atlas describe both
"Authentik provides identity and access" and "the Authentik LXC runs on pve1"
without forcing one record to mean both things.

An Application Asset is still an Asset. It can represent a deployed process,
container, appliance, or workload. A Service represents what operators and
users rely on, may depend on several Application Assets, and may survive the
replacement of any one implementation Asset.

Atlas already contains a managed Asset Type named **Service**. Release C1 does
not rename or delete it and does not automatically convert Assets of that type.
That legacy classification and the first-class Service entity are distinct.
Operators should create and link a first-class Service deliberately; automated
association and migration are deferred.

## Records and scope

Every Service belongs to a customer and may be customer-wide or limited to one
site. Its scoped slug is unique among active Services. The API and summary
queries apply the same customer/site authorization rules as the rest of Atlas.
Archiving is non-destructive and preserves dependencies, assertions, gaps, and
history.

The Service record holds:

- identity, purpose, description, lifecycle, and operational status;
- Service Type and Criticality references;
- simple owner, technical contact, and support-group labels;
- documentation and runbook URLs;
- recovery time objective (RTO) and recovery point objective (RPO);
- backup, recovery, and general notes.

RTO and RPO are stored as exact non-negative minutes. The web form accepts
minutes, hours, or days and converts only for display and input convenience.
Criticality may suggest defaults, but selecting a level never silently
overwrites an explicitly entered target.

## Service Type and Criticality

Service Types are managed, stable reference records. C1 seeds Application,
Infrastructure, Platform, Shared, External, Database, Integration, and Business
Service. A type can indicate whether a supporting Asset dependency normally
applies. Inactive types remain readable on existing records.

Criticality levels are also managed records. C1 seeds Critical, High, Medium,
and Low, with ordered ranks and optional suggested RTO/RPO values. Criticality
drives conditional completeness rules; it is not an incident-priority or SLA
engine.

## Ownership and future evolution

C1 intentionally uses plain-text owner/contact/support fields. This is useful
for a homelab and does not pretend that Person, Team, roster, or escalation
records exist. A later release can migrate these labels into Person/Team role
assignments while retaining the original labels as migration evidence.

These fields remain the accepted ownership model for Homelab Ready. C3
People/Teams is an additive internal-IT/MSP/enterprise evolution, not a homelab
release prerequisite.

Likewise, `runbook_url` and `documentation_url` are links today. A future
Knowledge Object model can associate formal runbooks and documents without
changing the meaning of the Service.

F1-lite may expose existing generated `Document` records before that future C4
model exists, provided generated content remains visibly distinct from reviewed
human-authored knowledge.

## Provenance and completeness

Manual Service field edits create declared, accepted assertions. Superseded
values and removed dependency links remain historical. Meaningful Knowledge
Changes appear in the existing Changes timeline.

Service completeness uses the same configuration-driven requirement and gap
foundation as Assets. The seeded profile checks purpose, ownership, recovery
targets for higher criticalities, supporting infrastructure where applicable,
recovery knowledge, and documentation. Recommended gaps remain visible without
turning a Service incomplete. A valid exception can suppress an inapplicable
requirement, such as a local Asset dependency for an External Service.

Full impact analysis, SLO/SLA tracking, incident management, catalogs,
on-call/escalation models, and Person/Team ownership are intentionally outside
Release C1.

## Record lifecycle

C2.6 distinguishes mistaken-record Delete (retained tombstone) from Archive.
See [Service and Business Function lifecycle](entity-lifecycle.md) for exact
eligibility, authorization, historical preservation and concurrency rules.
