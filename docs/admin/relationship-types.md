# Relationship Types

In **System → Reference Data → Relationship Types**, administrators maintain
relationship names, source/target/inverse labels, direction, allowed Asset Types,
typed endpoint applicability, availability and **Topology class**. The list shows
the configured class; Add/Edit uses a compact select.

The `/api/relationship-types` response's `in_use_count` includes only readable
relationships with two readable endpoints. Each family uses its operational
read permission and Customer/Site scope: Asset relationships use
`relationships.view`, Service dependencies use `service_dependencies.view`,
and Service–Business Function links use `business_functions.view`. Endpoint
reads additionally require `assets.view`, `services.view` or
`business_functions.view` as applicable. Asset relationship counts also follow
the selected Customer/Site context, as their list does. Typed counts retain
current links (`valid_to` is null), as their dependency lists do. Global
definitions remain visible to authorised definition readers; without the
operational permissions, their visible usage is zero.
An unavailable selected operational context also yields zero usage without
hiding global definitions.

| Topology class | Connectivity default |
| --- | --- |
| Platform / containment | On |
| Physical / network | On |
| Data / resilience | Off |
| Logical / operational | Off |
| Other | Off |

New custom types default to **Other**. Deliberately choose **Physical / network**
for a custom technical link such as Connected by fibre. A custom Talks to type
can use **Logical / operational**. A Paired with type left at Other stays hidden
until that class is enabled temporarily in Connectivity Filters.

Topology class controls Infrastructure Topology Connectivity eligibility only.
It does not change direction, configured labels, permitted endpoints, Platform
parent/child semantics, Knowledge Graph inclusion or dependency analysis. It
creates no relationships. Inactive types retain their configured class and
existing recorded relationships; activation governs new relationship choices.

Logical/application relationships belong primarily in Knowledge Graph.
Connectivity can temporarily include them, data/resilience relationships and
Other through its class filters. Custom types are never classified by their name.

Network membership is separately derived from **AssetInterface** records and
belongs to Physical / network presentation. It is not a Relationship Type.
**Routes** currently belongs to Other because Atlas does not model full L3
routing topology. Enabling Other shows eligible recorded routes without inferring
a routing model.

See [Infrastructure Topology](infrastructure-topology.md) for filters, focus,
traversal bounds and resets.
