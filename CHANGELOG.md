# Changelog

## 2.2.0 — 2026-10-20

The automatic layout handles denser views: rows narrow before they wrap, lines can join, views can run left to right, and an object can be drawn more than once. CoreEA lines are labelled with their verb by default.

### Added

- `direction lr` lays a view out in columns read left to right. CoreEA's Business Strategy Diagram, Project Context and Risk Catalogue viewpoints default to it, as `coreea.md` describes them, with the band order their recipes use.
- `join in`, `join out` and `join both` join lines of one verb into, or out of, one box into a single trunk with one label, as hand-drawn SAD views do.
- An object can be drawn more than once in a view (`TEC-15#dev`, `TEC-15#prod`). Relationships join the matching boxes, and the ArchiMate exchange file gets a node per box.
- `same by=FIELD` puts each box in a row with the boxes its object field names. Across two containers side by side, the pairs line up level.
- `A before B C` places boxes in earlier rows (or columns to the left), and wins over the order a relationship implies. `above` still works and also takes several boxes.
- `platform azure` in a view resolves icon names to that platform first; `icon=` works on a group; `scale 3` in the view file or `render --scale 3` sets the PNG resolution.
- A view that draws every relationship between its boxes and ends up with more than one and a half lines per box warns, and suggests `edges explicit` or `hide`.
- `scripts/examples/coreea-sad/`: six SAD views (application context, logical data, business strategy, capability, risk, infrastructure) of a 131-object CoreEA model declared in the view file.

### Changed

- The box notation labels each line with its verb by default, as `coreea.md` says. `labels text` shows the relationship's name or note, as before.
- A `same` row holds. Its boxes narrow to three-line names and close up first; if it still doesn't fit, the page widens and the view warns. Two `same` rows too wide together take a row each.
- A row too wide for the page narrows its boxes (names on two lines) and its containers before it moves anything to another row. Boxes with no line between them sit 24px apart rather than 40.
- Unconnected boxes flow into rows without a warning, so a container's parts pack into its width. Three or more containers with no lines between them flow into columns.
- Boxes listed one under another in a container take one width and sit closer together.
- Row order takes account of where a line meets a box inside a container, and a line from a large box leaves in line with the box it goes to.
- Icon names resolve to a fetched pack's icon of that exact name before a concept alias, so "Application Gateway", "Container Registry", "Managed Identity", "Application Insights", "AI Foundry" and "Network Security Group" get their own icons. "Entra ID" is the Entra Domain Services icon, and Web PubSub, Document Intelligence, Static Web Apps, Private DNS and Microsoft Graph have aliases. A generic glyph's own name, such as "server", stays generic unless a platform is given.
- An icon on a box under 120px wide, or one that would make the name wrap further, goes before the type label at 12px.

### Fixed

- Lines that run along the same channel count as overlapping even when their routes are built on different grids. Before, three lines could share one vertical and read as joined.
- Two lines that cross are routed again in the other order even when they share no box.
- A vendor icon's ids are numbered per view, so drawing a view twice gives the same SVG.

## 2.1.0 — 2026-10-19

Views can be written as text and laid out automatically, with warnings when the layout isn't clean and hand placement for the views that need it. Colour now separates types within a layer.

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
- Two lines meeting the same box no longer cross just because each took its own cheapest port: the router also tries each line with its port on that box ruled out, and keeps the routing that crosses least. The CoreEA example's Service agent line no longer crosses the line to the Case API.

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
