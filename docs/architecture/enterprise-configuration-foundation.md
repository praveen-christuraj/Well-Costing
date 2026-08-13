# Enterprise configuration foundation decisions

Selected scope: full enterprise foundation, configurable typed hierarchy, and bootstrap System Administrator writes.

The hierarchy uses typed nodes plus explicit parent-child rules rather than a fixed oil-and-gas tree or unrestricted EAV model. Stable financial concepts remain relational. Cost structures, rate books, estimate templates, workflow profiles, and reporting mappings are versioned configuration families.

The existing development/CI seed script assigns `admin`; non-admin writes return 403. Reads remain authenticated. No business formula or configuration publication is activated. Users may add the enterprise structure one audited record at a time and later submit draft publication rules for approval.
