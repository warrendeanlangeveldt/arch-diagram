# Changelog

## 1.0.0 — 2026-10-16

First release as a Claude Code plugin.

- Ten house diagram types, each with a recipe and an SVG skeleton: deployment, system context, integration, data flow, sequence, deploy path, steps, state, swimlane and phases.
- C4 methodology: system context, container, component, deployment and dynamic views in the house design system, with C4's labelling rules and a key on every diagram.
- CoreEA methodology: enterprise-architecture viewpoints (Application Context, Application Integration, Logical Data, Infrastructure, Capability, Business Strategy, Project Context, Risk Catalogue, Organization, CRUD matrix) drawn from one object model, so ids and names agree across views and the model exports as a repository catalogue.
- `coreea_lib.py`: view drawing helpers plus `validate()` for a model's ids, types, verbs and endpoints. Standard library only; renders PNGs with headless Chrome (`CHROME_PATH` overrides the lookup).
- 40-glyph vendor-agnostic icon set with AWS, Azure and GCP aliases.
