# Service Types and Criticality administration

Release C1 adds two managed reference-data areas under **Administration**.
Users need `service_types.manage` or `criticality_levels.manage` to change them;
view-only users can still read active definitions used by Services.

## Service Types

Service Types classify an operational Service. Atlas seeds Application,
Infrastructure, Platform, Shared, External, Database, Integration, and Business
Service. Administrators can add a type, edit its label and description, change
sort order, and activate or deactivate it. Stable keys should be treated as API
identifiers rather than display text.

`requires_asset_dependency` supplies the default applicability hint used by the
Service completeness profile. Use `false` only where a local supporting Asset
is not normally expected, such as an externally provided capability. Existing
Services retain an inactive type for historical readability; new Services can
select only active types.

The **Service** Asset Type shown under Asset Types is not this taxonomy. C1
preserves that older Asset classification and never converts it automatically.

## Criticality levels

Criticality levels have a display name, key, rank, colour, description, sort
order, and optional suggested RTO/RPO minutes. Atlas seeds Critical, High,
Medium, and Low. Higher ranks can activate conditional completeness rules.

Suggested recovery values are guidance only. They appear next to the Service
form and detail values but never overwrite an operator's explicit RTO/RPO.
Change defaults with care because they influence future guidance and rule
applicability, not a contractual SLA.

## Relationship endpoint applicability

Relationship Type administration now exposes endpoint pairs. Enable only
semantically valid combinations such as `service → asset` or `service →
service`. Existing Asset-to-Asset relationship behavior remains available.
Removing applicability prevents new links but does not destroy historical
links.

## Completeness profiles

The migration seeds a default Service knowledge profile using the shared
requirement-definition model. Requirements may be global or limited to a
Service Type, and conditional JSON can use Criticality rank or Service Type
configuration. The current C1 UI evaluates and manages resulting gaps; broader
visual profile authoring for Services can build on the same API in a later
release.
