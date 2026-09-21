# Relationship Types

In **System → Reference Data → Relationship Types**, administrators maintain
relationship names, source/target/inverse labels, direction, allowed Asset Types,
typed endpoint applicability, availability and **Topology class**. The list shows
the configured class; Add/Edit uses a compact select.

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
