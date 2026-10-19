# Changelog

## Unreleased

### Added

- A view language. A `.ead` file lists what each view shows, and `ea.py render` lays it out and draws it: layers as bands, rows from relationships such as realises and hosted on, lines routed around the boxes, labels where they touch nothing. Adding an object or relationship is a line, not a redraw. The file can import a `model.json` or declare the model itself, and `validate`, `export` and `orbus plan` accept it. Hints (`same`, `A above B`, `bands`, `hide`, `edges explicit`) steer a view without coordinates. BPMN views lay out pools, nested lanes, columns, boundary events and expanded sub-processes from the model. The ArchiMate exchange file and BPMN XML carry the computed layout. Reference: `references/dsl.md`.
- Layout warnings. `render` and `validate` say when the automatic layout drew a view but not cleanly: a row wrapped onto the next, a view wider than the page, crossing lines, a line with no clear route, a label with no free spot. They also go in the view's `objects.json`, and BPMN views' `objects.json` now lists warnings too.
- Hand-placed views in a view file. `view ID script="file.py"` draws that view with the script's `draw(model, vid)`, using the file's model, so a view the layout can't get right is placed by hand while the others stay as text and one `render` still draws them all. The example scripts have this shape and still run on their own.
- Each relationship in the CoreEA, ArchiMate, TOGAF and Essential metamodels says whether it runs up, down or across a layer band (`"layout"`), and ArchiMate and TOGAF set their band order (`"bands"`).
- Every example has a `views.ead`; its output is in `out/`. The hand-placed example scripts still run and now write to `out/script/`.

### Changed

- Colour now says the layer and shade says the type. Each type the model uses gets its own shade of its layer's colour, the same in every view, so an Application and an Interface, or a Business Domain and a Business Capability, no longer share one swatch. `make_theme(types={...})` sets a type's colour outright and `make_theme(type_shades=False)` goes back to plain layer colours.
- The legend lists each layer drawn as a heading in the layer's colour, followed by its types.

### Fixed

- The legend draws a type as a pill when the view only draws it as one; it showed a filled box in the layer colour before.
- Types that appear only in a matrix are no longer in the legend, since the matrix doesn't colour them.

## 2.0.0 — 2026-10-19

ArchiMate, TOGAF, Essential and BPMN join CoreEA as framework options, the plugin exports to EA tools including OrbusInfinity, and diagrams can use the AWS, Azure and Google Cloud icon sets.

### Added

- ArchiMate 3.2: all 62 element types, the full relationship table, the standard notation (type symbols, and line styles and ends for all eleven relationships) and the 25 example viewpoints. Exports the ArchiMate exchange format with each view's layout, nesting and bendpoints; the file validates against the Open Group schema.
- TOGAF Content Metamodel: entities, relationships and the catalogs, matrices and diagrams of phases A to E, drawn in the house EA box. Matrices are tables whose cells come from relationships.
- Essential Meta-Model: the core meta-classes of each layer, with relationships named after Essential's slots and relation classes, and those names carried into the CSV export.
- BPMN 2.0: validation of BPMN's flow rules, the BPMN notation, and BPMN 2.0 XML with diagram interchange; the file validates against the OMG schema and parses cleanly in bpmn-moddle.
- One engine (`ealib`) and command line (`ea.py`) for all five frameworks: validate, types, rules, viewpoints, export. Views warn when they draw a type outside their viewpoint.
- OrbusInfinity import over its REST API: discover the tenant's types, plan a reviewable payload, push it within the rate limit, and re-push as updates using a ledger. Tested against a local server built to the published API, not yet against a live tenant.
- Icon packs: the official AWS, Azure and Google Cloud icons, fetched by each user under the vendor's terms (`icons.py fetch`), with a resolver that maps component names to platform icons and falls back to generic glyphs. The generic set grew from 40 to 64 glyphs.
- Test suite in `tests/`.

### Changed

- CoreEA is now one metamodel of the shared engine (`metamodels/coreea.json`), so CoreEA models also get viewpoint checks, matrices, icons and the OrbusInfinity import. `coreea_lib.py` keeps its 1.x API on top of the engine; its rules match 1.0.0 for every verb and type pair, and the example renders the same SVG.
- A model without a `metamodel` field is read as CoreEA, so 1.x model files work as they are.
- The CoreEA example moved from `scripts/example/` to `scripts/examples/coreea/`.
- `references/icon-aliases.md` became `references/icons.md`; the alias table itself is now `scripts/icon_aliases.json`.
- Python 3.9 or later is required.

## 1.0.0 — 2026-10-16

First release as a Claude Code plugin.

- Ten house diagram types, each with a recipe and an SVG skeleton: deployment, system context, integration, data flow, sequence, deploy path, steps, state, swimlane and phases.
- C4 methodology: system context, container, component, deployment and dynamic views in the house design system, with C4's labelling rules and a key on every diagram.
- CoreEA methodology: enterprise-architecture viewpoints (Application Context, Application Integration, Logical Data, Infrastructure, Capability, Business Strategy, Project Context, Risk Catalogue, Organization, CRUD matrix) drawn from one object model, so ids and names agree across views and the model exports as a repository catalogue.
- `coreea_lib.py`: view drawing helpers plus `validate()` for a model's ids, types, verbs and endpoints. Standard library only; renders PNGs with headless Chrome (`CHROME_PATH` overrides the lookup).
- 40-glyph vendor-agnostic icon set with AWS, Azure and GCP aliases.
