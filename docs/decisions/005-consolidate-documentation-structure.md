# ADR 005: Consolidate Documentation Structure

## Status
Accepted (2026-05-01)

## Context
The `docs/` folder had grown organically with 20+ files in the root:

```
docs/
  ├── ARCHITECTURE.md
  ├── MICROSERVICES-REFERENCE.md
  ├── API-REFERENCE.md
  ├── DATABASE-SCHEMA.md
  ├── ERD.md
  ├── SRS.md
  ├── FLOWCHARTS.md
  ├── TESTING-GUIDE.md
  ├── AI-SYSTEM-CONTEXT.md
  ├── MICROSERVICES-REVIEW.md
  ├── DEVELOPMENT.md
  ├── ... (many more)
```

Problems:
- New developers couldn't find what they needed
- No clear separation between architecture, API, database, and operational docs
- No record of why decisions were made
- Review docs mixed with reference docs

## Decision
Reorganize into a structured hierarchy:

```
docs/
├── README.md                          ← Docs index
├── decisions/                         ← ADRs (Architecture Decision Records)
│   ├── 001-use-modular-monolith.md
│   ├── 002-rename-services-to-domain-language.md
│   ├── 003-adopt-ddd-folder-structure.md
│   ├── 004-remove-dead-microservices.md
│   └── 005-consolidate-documentation-structure.md
├── architecture/                      ← System-level architecture
│   ├── overview.md                    ← (was ARCHITECTURE.md)
│   ├── service-boundaries.md          ← (was MICROSERVICES-REFERENCE.md)
│   ├── ai-system-context.md           ← (was AI-SYSTEM-CONTEXT.md)
│   ├── srs.md                         ← (was SRS.md)
│   ├── flowcharts.md                  ← (was FLOWCHARTS.md)
│   ├── c4/                            ← C4 model diagrams
│   └── reviews/                       ← Architecture reviews
├── api/                               ← API contracts
│   └── reference.md                   ← (was API-REFERENCE.md)
├── database/                          ← Data layer docs
│   ├── schema.md                      ← (was DATABASE-SCHEMA.md)
│   └── er-diagram.md                  ← (was ERD.md)
├── services/                          ← Per-service deep dives
├── development/                       ← Developer onboarding
│   ├── setup.md                       ← (was DEVELOPMENT.md)
│   └── testing.md                     ← (was TESTING-GUIDE.md)
└── runbooks/                          ← Operations
```

## Consequences

### Positive
- **New developer can find anything in 3 clicks** — `README.md` → section → doc
- **Decisions are traceable** — `decisions/` folder shows why the system is this way
- **Architecture is visual** — `c4/` folder has diagrams at 3 zoom levels
- **Service docs are discoverable** — `services/` mirrors `services/` code folder
- **Ops is separate from dev** — `runbooks/` for SRE, `development/` for engineers

### Negative
- **Broken links** — existing bookmarks and references need updating
- **Mental model shift** — team must learn new locations
- **Migration effort** — moving files, updating cross-references

## Related Decisions
- All previous ADRs in this session
