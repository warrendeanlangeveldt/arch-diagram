# Enterprise-architecture models: the shared workflow

Five frameworks share one engine, `scripts/ealib`. Pick the framework,
then read its own reference as well as this one:

| Framework | Owner and status | Use it for | Reference |
|---|---|---|---|
| ArchiMate 3.2 | The Open Group, open standard | Layered architecture views with a standard notation that most EA tools read | `archimate.md` |
| TOGAF Content Metamodel | The Open Group, open standard | TOGAF ADM deliverables: the catalogs, matrices and diagrams of phases A to E | `togaf.md` |
| Essential Meta-Model | Essential Project, open source | Capability-led portfolio work, and models that will be loaded into Essential | `essential.md` |
| CoreEA | OrbusInfinity's metamodel (proprietary) | SAD views for organisations that run OrbusInfinity; models to load into it | `coreea.md` |
| BPMN 2.0 | OMG, open standard | Process flows: pools, lanes, tasks, events and gateways | `bpmn.md` |

TOGAF prescribes content, not notation, so a TOGAF model drawn in ArchiMate
notation is common. When the person wants TOGAF deliverables but ArchiMate
pictures, model in ArchiMate and name each view after the TOGAF artifact it
stands for.

## Model first

Every view is drawn from one `model.json` (schema: `scripts/model_schema.json`).
Never hand-type a name or id into a view.

```json
{"metamodel": "archimate", "name": "Service Portal",
 "objects": [{"id": "ACMP-01", "type": "Application Component", "name": "Service Portal",
              "status": "Built", "owner": "Customer Service", "ref": "FR-04"}],
 "relationships": [{"from": "ACMP-01", "type": "realization", "to": "ASVC-01"}]}
```

The same object then has the same id, name and type in every view, the model
exports to the person's EA tool, and a reviewer can trace every box to a record.

1. Build `model.json` from the source documents. Keep the source's own ids in
   `ref`. Owners are organisations or roles from the brief, never invented.
   Status is honest: Built / Built in UAT / Designed / Proposed / Not started /
   Retired.
2. `python3 scripts/ea.py validate model.json` until it passes. It reports every
   problem at once: unknown types, ids without the type's prefix, a
   relationship the framework does not allow between those two types (with the
   ones it does allow), missing endpoints, parent loops.
   `ea.py types <framework>` lists types and prefixes;
   `ea.py rules archimate "Application Component" "Business Process"` lists the
   relationships allowed between two types.
3. Write the views in a view file, `views.ead` (`dsl.md`), and draw them with
   `python3 scripts/ea.py render views.ead`. The layout is worked out from the
   model, so a new object or relationship is one line and the views rearrange
   around it. Only a view the automatic layout can't get right needs a script
   with the View API below (start from `scripts/examples/<framework>/*.py`);
   there every `edge()` passes `check=[(from, type, to)]`, so a line that is not
   in the model cannot be drawn. The script defines `draw(model, vid)` and the
   view file names it (`view ACD script="acd.py"`, `dsl.md`), so the other
   views stay in the language.
4. Render, read the PNG, fix, repeat (SKILL.md step 5). With a view file the
   fix is usually a hint (`same`, `A above B`, `hide`) rather than coordinates.
   `render` warns when a layout isn't clean (wrapped rows, crossing lines,
   labels with no free spot); read those views' PNGs first.
5. Export for the person's tools (`exports.md`).

Scope: model the subject solution in detail. A neighbouring system with its
own design document is one object ("CRM, defined in the CRM SAD"), with nothing
inside it.

## The View API

```python
import sys; sys.path.insert(0, "<skill dir>/scripts")
from ealib import View, load_model, validate

model = load_model("model.json"); validate(model)
v = View(model, "V1", title="V1 Application cooperation", viewpoint="Application Cooperation")
```

| Call | Draws | Returns |
|---|---|---|
| `node(oid, x, y, w, h=None, sub=None, icon=None)` | one object; height fits the name when `h` is omitted; `icon` adds a platform or generic icon at the left | box `{x y w h r b cx cy}` |
| `container(oid, x, y, w, h, icon=None)` / `container_header(oid, w)` | an object holding others | `(box, content_top)` |
| `group(type, title, members, x, y, w)` | many objects of one type as one box (`REQUIREMENT ×7`) | box |
| `pill(oid, x, y, w=None)` | a service or interface as a pill | box |
| `junction(oid, cx, cy)` | ArchiMate And / Or junction | box |
| `frame(x, y, w, h, label, icon=None)` | a grouping that is not a model object ("External", "AWS Cloud") | box |
| `edge(points, type, label=None, check=[…])` | an orthogonal connector in the framework's notation | |
| `matrix(x, y, rows, cols, cells)` + `cells_from(type, rows, cols)` | a catalogue matrix with cells derived from relationships | y below |
| `tag(x, y, "NOT BUILT")` | an annotation pill | width |
| `legend(y)`, `key_line(y, notes)` | each layer drawn with its types, the line styles drawn, plus what nesting means here | y below |
| `save(height, outdir)` | `<vid>.svg/.html/.png/.objects.json` | paths |

Passing `viewpoint=` makes the view warn (at save) about any type outside that
viewpoint. Viewpoints in all three standards are guidance that organisations
tailor, so this is a warning, not a refusal. Fix the view, or say why the
extra type belongs.

## Notation shared by every framework

- Colour says the layer, shade says the type. Every type the model uses gets
  its own shade of its layer's colour, the same in every view of the model.
  The legend lists each layer drawn as a heading in the layer colour,
  followed by its types drawn as they appear in the view (a pill when the view
  only draws that type as a pill). Types shown only in a matrix carry no
  colour and stay out of the legend.
- Objects with status Proposed / Designed / Not started are dashed, driven by
  the model and never set by hand. The legend adds the dashed swatch when one is
  drawn.
- Nesting (box in a box) means one thing per nesting level, and the key line
  says which. It replaces the line it stands for; do not draw both.
- Group more than about six siblings with `group()`; the catalogue still lists
  each one.
- A box with no model object behind it is a `frame()`, never a `node()`.
- Lines leave the object that owns the relationship (the consumer, not its
  container). Labels never cross a box.
- Wide views (more than about 20 nodes): group, or split the view. Never shrink
  fonts below the anatomy sizes.
- A view is named `V<n> <Name>`, and its caption names the viewpoint or artifact
  it implements, so it can be rebuilt in the person's EA tool.

## Theme

`View(model, vid, theme=make_theme(...))` overrides house tokens (`font`,
`width`, `ink`, `body`, `muted`, `id`, `rule`, `paper`), per-layer colours
(`make_theme(layers={"Application": ("#1d4ed8", "#eff6ff")})`, from which the
type shades are derived) and per-type colours
(`make_theme(types={"Application Interface": ("#1e40af", "#dbeafe")})`, which
win over the shades). `make_theme(type_shades=False)` draws every type in its
plain layer colour, for houses that colour by layer only. Keep layer colours
distinct; a legend whose swatches can't be told apart is worse than none.
