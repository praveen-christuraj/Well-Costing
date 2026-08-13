# Enterprise configuration data model

Migration `20260813_0011` adds:

- configurable hierarchy: node types, allowed parent-child rules, nodes;
- versioned cost breakdown structures and nodes;
- versioned rate books and rate links;
- versioned estimate templates and lines;
- versioned reporting mappings.

All records have timestamps and actors. Hierarchy shape is data-driven; no Organization→Asset→Field sequence is seeded. Published financial configuration is immutable by policy; this foundation creates drafts only. Existing project/well records remain operational records and can be mapped in a later approved linkage step.
