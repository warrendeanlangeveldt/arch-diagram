# Changelog

## 2.0.0 — 2026-10-17

ArchiMate, TOGAF, Essential and BPMN join CoreEA as framework options, and the plugin reaches into EA tools and the cloud vendors' icon sets.

- CoreEA is now one metamodel in the shared engine (`metamodels/coreea.json`), so CoreEA models get the same validation, viewpoint checks, matrices, icons, CSV export and OrbusInfinity import as the other frameworks. `coreea_lib.py` keeps its API, and existing scripts and models run unchanged; the example now lives in `scripts/examples/coreea/` and renders identically.
- ArchiMate 3.2: all 62 element types, the full relationship table, the standard notation (type symbols, and line styles and ends for all eleven relationships) and the 25 example viewpoints. Exports the ArchiMate exchange format with each view's layout, nesting and bendpoints.
- TOGAF Content Metamodel: entities, relationships and the catalogs, matrices and diagrams of phases A to E, drawn in the house EA box. Matrices are drawn as tables whose cells come from relationships.
- Essential Meta-Model: the core meta-classes of each layer, with relationships named after Essential's slots and relation classes.
- BPMN 2.0: validation of BPMN's flow rules, the BPMN notation, and BPMN 2.0 XML with diagram interchange.
- One engine (`ealib`) and command line (`ea.py`) for all five frameworks: validate, rules, types, viewpoints, export.
- OrbusInfinity import over its REST API: discover the tenant's types, plan a reviewable payload, push it within the rate limit, and re-push as updates using a ledger.
- Icon packs: the official AWS, Azure and Google Cloud icons, fetched by each user under the vendor's terms, with a resolver that maps component names to platform icons and falls back to generic glyphs. The generic set grew from 40 to 64 glyphs.
- Tests: CoreEA compatibility, metamodel rules, validation, both XML exports against the official schemas, icon indexing and resolution, and the Orbus push against a local server implementing the published API.

## 1.0.0 — 2026-10-16

First release as a Claude Code plugin.

- Ten house diagram types, each with a recipe and an SVG skeleton: deployment, system context, integration, data flow, sequence, deploy path, steps, state, swimlane and phases.
- C4 methodology: system context, container, component, deployment and dynamic views in the house design system, with C4's labelling rules and a key on every diagram.
- CoreEA methodology: enterprise-architecture viewpoints (Application Context, Application Integration, Logical Data, Infrastructure, Capability, Business Strategy, Project Context, Risk Catalogue, Organization, CRUD matrix) drawn from one object model, so ids and names agree across views and the model exports as a repository catalogue.
- `coreea_lib.py`: view drawing helpers plus `validate()` for a model's ids, types, verbs and endpoints. Standard library only; renders PNGs with headless Chrome (`CHROME_PATH` overrides the lookup).
- 40-glyph vendor-agnostic icon set with AWS, Azure and GCP aliases.
