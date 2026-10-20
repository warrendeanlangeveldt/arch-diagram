# CoreEA — enterprise-architecture views (OrbusInfinity metamodel)

CoreEA is the metamodel OrbusInfinity uses: typed objects, typed
relationships, and named viewpoints that each show a slice of one model.
Use this when the request names CoreEA, OrbusInfinity, an EA viewpoint,
or a SAD view (Application Context, Application Integration, Logical
Data, Infrastructure, Capability, Business Strategy, Project Context,
Risk Catalogue, Organization, CRUD matrix).

## Rule zero — model first

Every view is drawn from **one object model** (`model.json`, schema in
`scripts/model_schema.json`). Never hand-type a name or id into a view.

```json
{
  "objects": [
    {"id": "APP-01", "type": "Application", "name": "Case Platform",
     "description": "…", "status": "Built", "owner": "ORG-01",
     "ref": "FR-04", "parent": null, "sad": "7.2"}
  ],
  "relationships": [
    {"from": "APP-01", "type": "realises", "to": "CAP-03", "note": ""}
  ]
}
```

Why: the same object then has the same id, name and type in every view;
the model exports as the catalogue the architecture office imports
(`catalogue_rows()`); and a reviewer can trace every box to a record.
Workflow:

1. Build `model.json` from the source documents. Keep the source's own
   ids in `ref` (FR-04, SEC-RISK-02). Owners are organisations or roles
   from the brief, never invented. Status is honest: Built / Built in
   UAT / Designed / Proposed / Not started / Retired.
2. `python3 scripts/ea.py validate model.json` (or
   `python3 scripts/coreea_lib.py model.json`) until it validates. A model
   without a `metamodel` field is read as CoreEA, so 1.x model files work
   as they are.
3. One generator script per view using `scripts/coreea_lib.py` (or `ealib`,
   whose View API is the same and is described in `ea.md`); every
   `edge()` passes `check=[(from, verb, to)]`, so a line that is not in
   the model cannot be drawn.
4. Render, read the PNG, fix, repeat (SKILL.md step 5).

Scope rule: model the subject solution in detail. A neighbouring
solution or platform with its own design document is ONE object
("Platform X — defined in the Platform X SAD"); nothing inside it.

## Object types and id prefixes

| Layer | Type → prefix |
|---|---|
| Motivation | Driver DRV · Goal GOL · Objective OBJ · Requirement REQ · Principle PRN |
| Business | Capability CAP · Value Stream VST · Process PRC · Organization ORG · Actor ACT · Role ROL |
| Application | Application APP · Application Category APC · Interface INT |
| Data | Data Entity DAT · Data Category DTC |
| Technology | Technology TEC · Technology Category TCC · Location LOC |
| Governance | Risk RSK · Control CTL · Project PRJ |

Ids are prefix + stable suffix (`APP-01`, `APP-CRM`). Never renumber.

## Relationship verbs (only these)

| Verb | Source → target |
|---|---|
| `motivates` | Driver → Goal |
| `achieved by` | Goal → Objective |
| `supports` | Capability → Objective; Application → Process |
| `realises` | Application → Capability; Control → Requirement |
| `owns` | Organization → Application / Data Entity / Technology |
| `performs` | Role → Process |
| `assigned to` | Actor → Role |
| `uses` | Actor / Role / Application → Application / Interface |
| `exposes` · `consumes` | Application → Interface |
| `reads` · `writes` | Application → Data Entity |
| `relates to` | Data Entity → Data Entity (logical data diagram associations; add a `note` with cardinality) |
| `classified as` | Data Entity → Data Category |
| `hosted on` | Application → Technology |
| `located in` | Technology → Location |
| `categorised as` | Application → Application Category; Technology → Technology Category |
| `satisfies` | Application / Technology → Requirement |
| `constrains` | Principle → Application / Technology |
| `mitigates` | Control → Risk |
| `applies to` | Control → Application / Data Entity / Technology / Interface |
| `threatens` | Risk → Application / Data Entity |
| `delivers` | Project → Application / Technology |
| `depends on` | Application / Technology → Application / Technology |
| `supported by` | Application → Organization / Role |

`parent` (object field, same type only) is the part-of link: component
of an application, sub-capability. `validate()` enforces all of this.

## Notation

Layer colours (stroke / fill), configurable via `make_theme`:

| Layer | Stroke | Fill |
|---|---|---|
| Motivation | #734c74 | #f4eef4 |
| Business | #b46a12 | #fdf3e6 |
| Application | #3f7f8c | #eef6f8 |
| Data | #3b6a8f | #edf3f8 |
| Technology | #4f7d3a | #eff5ea |
| Risk | #b4443c | #fbeeed |
| Control | #475569 | #f1f5f9 |
| Project | #64748b | #f8fafc |

- **Node**: rect r4, layer stroke 1.2 + fill. Type label top-left
  UPPERCASE 7.5px 700 letter-spacing 0.6 in the layer colour; name
  centred 10.5px 600 ink (wraps); optional sub-line 8.5px muted; id
  bottom-right 7px `#94a3b8`. `node()`.
- **Dashed (4 3) = proposed / designed / not started.** Driven by the
  object's `status`, never by hand. The legend adds the dashed swatch
  whenever one is drawn.
- **Edge**: 1.2px body, orthogonal, canonical arrowhead, stop 2px short;
  verb label 8.5px italic muted with a white halo. Label = the verb,
  exactly (the view language's default; `labels text` shows a relationship's
  name or note instead). Edges leave the object that owns the relationship (the
  consumer, not its container).
- **Interface**: a pill (r11, white fill, Application stroke) sitting
  on the top edge of the application that exposes it, or listed inside
  an external application's box. `pill()`. Consumers point at the pill.
- **Nesting** (`container()`): box-in-box means ONE of — part of
  (`parent`), `categorised as`, `classified as`, `located in`. A view
  uses one meaning per nesting level and states it in the key line
  ("Box inside a box: part of it (parent)"). Nesting replaces the line;
  do not draw both.
- **Grouping** (`group()`): many objects of one type become one box —
  type label carries the count (`REQUIREMENT ×7`), the title names the
  group, the id slot shows the range (`REQ-01–REQ-07`). Dashed only when
  every member is unbuilt. Use it whenever more than ~6 siblings would
  otherwise crowd the view; the catalogue still lists each.
- **Plain frame** (`frame()`): a visual grouping that is not an object
  ("External", "No data category in the model"). Thin muted stroke,
  UPPERCASE 8px label.
- **Tag** (`tag()`): a small red pill annotation such as NOT BUILT.
  Annotation, not an object; use sparingly.

**Legend rules**: a legend row at the bottom, divider line above,
listing only the types drawn in that view (metamodel order), plus the
dashed swatch if used; then the key line(s) for nesting and pills. Every
view has both. No colour that is not in the legend.

## Standard viewpoints

| View | CoreEA view type | Objects included | Typical SAD section | Layout recipe |
|---|---|---|---|---|
| Solution context | Core EA Master Diagram | Project, key Requirements, Capabilities, Applications, Interfaces, Data Entities, Technology, top Risks/Controls | Solution overview | layered rows top→bottom (motivation → business → application → data → technology) |
| Project traceability | Project Context | Project → Requirements (grouped) → Applications/Controls that satisfy/realise them; Principles constraining | Scope / requirements | `steps`-like left→right columns |
| Business outcome alignment | Business Strategy Diagram | Drivers → Goals → Objectives → Capabilities/Requirements | Business context | left→right columns, one per type |
| Current landscape | Application Landscape Diagram | Current Applications in Application Categories (nested), owning Organizations | Current state | category containers in a grid |
| Capability alignment | Capability Diagram | Capabilities (nested by parent) each realised by an Application; Processes supported | Capability / target state | capability grid, app node under each |
| Target solution context | **Application Context Diagram** | Subject Applications (parts nested), Actors, exposed/consumed Interfaces, external Applications, Technology, Location | Target state | `system-context`: actors top, subject centre, externals right/bottom |
| Application components | Application Reference Model | Components by Application Category, hosted-on Technology | Application architecture | category containers |
| Integration flows | Application Integration Diagram | Applications ↔ Interfaces ↔ Data Entities, middleware Technology | Integration | `integration`: subject left, partners right, contract lane between |
| Logical data | Logical Data Diagram | Data Entities nested in Data Categories (classification as category sub-line), `relates to` links | Data architecture | category containers, 2–3 columns |
| Infrastructure | Infrastructure Diagram | Technology by Technology Category, nested in Location; Applications hosted on them | Infrastructure | `deployment`: location frame → category bands |
| Control traceability | Risk Catalogue | Risks → Controls → Requirements; applies-to targets | Security / risk | three columns left→right |
| Operational support | Organization Diagram | Organizations, Roles, Actors; Applications/Technology they own or support | Operations / support | `swimlane`: one lane per organisation |
| CRUD matrix | (catalogue report) | rows Data Entities × columns Applications/Roles, cells C/R/U/D | Data | **a table, not a diagram**: `v.matrix(x, y, rows, cols, v.cells_from({"writes": "CU", "reads": "R"}, rows, cols))` |

Name each view `V<n> <View>` and record its CoreEA view type in the
caption so the office can recreate it in OrbusInfinity.

In the view language (`dsl.md`), a view that names its viewpoint takes the
recipe's direction. Business Strategy Diagram, Project Context and Risk
Catalogue read left to right in columns; Project Context runs Project,
Motivation, Application, Technology, Control, and Risk Catalogue runs Risk,
Control, then what the controls realise and apply to. The other viewpoints
stack layers top to bottom. `direction` and `bands` in the view override
either. A SAD model is dense, so list each view's lines (`edges explicit`);
`scripts/examples/coreea-sad/views.ead` is a worked set of six SAD views on a
model of 131 objects.

## Skeleton — Application Context Diagram

Prefer the helper (`scripts/examples/coreea/app_context.py` is this diagram).
Hand-written SVG must follow the same anatomy:

```svg
<svg viewBox="0 0 740 370" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system, 'Helvetica Neue', Arial, sans-serif">
  <defs><marker id="arr-acd" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 1 L 9 5 L 0 9 z" fill="#475569"/></marker></defs>
  <!-- actor node -->
  <rect x="60" y="16" width="120" height="36" rx="4" fill="#fdf3e6" stroke="#b46a12" stroke-width="1.2"/>
  <text x="66" y="26" font-size="7.5" font-weight="700" letter-spacing="0.6" fill="#b46a12">ACTOR</text>
  <text x="120" y="39" text-anchor="middle" font-size="10.5" font-weight="600" fill="#0f172a">Customer</text>
  <text x="175" y="48" text-anchor="end" font-size="7" fill="#94a3b8">ACT-01</text>
  <!-- subject application as a container (parts nested by parent) -->
  <rect x="16" y="96" width="456" height="140" rx="5" fill="#eef6f8" fill-opacity="0.45" stroke="#3f7f8c" stroke-width="1.2"/>
  <text x="23" y="107" font-size="7.5" font-weight="700" letter-spacing="0.6" fill="#3f7f8c">APPLICATION</text>
  <text x="466" y="107" text-anchor="end" font-size="7" fill="#94a3b8">APP-01</text>
  <text x="23" y="120" font-size="10.5" font-weight="600" fill="#0f172a">Service Portal</text>
  <!-- child component node at (32, 134) …; interface pill on its top edge -->
  <rect x="356" y="160" width="90" height="22" rx="11" fill="#ffffff" stroke="#3f7f8c" stroke-width="1.2"/>
  <text x="365" y="174.5" font-size="8.5" font-weight="600" fill="#0f172a">Case API</text>
  <text x="437" y="174.5" text-anchor="end" font-size="7" fill="#94a3b8">INT-01</text>
  <!-- edge with verb label (halo keeps it legible over lines) -->
  <polyline points="120,52 120,134" fill="none" stroke="#475569" stroke-width="1.2" marker-end="url(#arr-acd)"/>
  <text x="124" y="70" font-size="8.5" font-style="italic" fill="#64748b" stroke="#fff" stroke-width="3" paint-order="stroke">uses</text>
  <!-- proposed external: dashed -->
  <rect x="560" y="186" width="164" height="36" rx="4" fill="#eef6f8" stroke="#3f7f8c" stroke-width="1.2" stroke-dasharray="4 3"/>
  <!-- legend: divider, type swatches 16×10, dashed swatch, then key line -->
  <line x1="16" y1="320" x2="724" y2="320" stroke="#e2e8f0"/>
</svg>
```

## Pitfalls

- An interface pill on a child's top edge covers its type label unless
  right-aligned with ≥8px clear of the label.
- Lines from a container edge hide which part owns the relationship;
  start them at the owning node.
- Wide views (> ~20 nodes): group, or split the view; never shrink fonts
  below the anatomy sizes.
- A box with no model object behind it is a `frame()`, never a `node()`.

## Into OrbusInfinity

CoreEA is OrbusInfinity's own metamodel, so a tenant's type names should
match the model's and `ea.py orbus discover` should fill most of the mapping by
name; anything it leaves empty needs the tenant's type id. The model then
loads through the Orbus REST API with `plan` and `push`. `exports.md` has the steps. The
`catalogue_rows()` CSVs remain the route for a spreadsheet import.

Icons: `View.node(..., icon="S3")` and `references/icons.md`, as for the other
frameworks. `View(..., viewpoint="Application Context Diagram")` warns when a
view draws a type outside that CoreEA view type.
