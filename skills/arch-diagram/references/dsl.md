# The view language

A view file (`.ead`) holds the model, or points at a `model.json`, and the
views drawn from it. You list what each view shows; `ea.py render` works out
where everything goes, routes the lines and draws the same SVG, HTML and PNG
as a hand-placed view script. Adding an object or a relationship is one line,
and the views that show it rearrange themselves.

```
model "model.json"

view ACD "Service Portal: application context" {
  ACT-01
  ACT-02
  APP-01 {
    APP-02
    APP-03
  }
  INT-01 on APP-03
  APP-CRM {
    INT-02
  }
  APP-NOTIFY
  TEC-01
  LOC-01
  key "Box inside a box: part of it (parent)" "Pill on an application: interface it exposes"
}
```

```bash
python3 scripts/ea.py render views.ead                        # out/ACD.svg|html|png|objects.json
python3 scripts/ea.py render views.ead --export archimate     # plus the exchange file with this layout
python3 scripts/ea.py validate views.ead                      # model and every view, no drawing
```

Each framework's example has a `views.ead` beside its `model.json`
(`scripts/examples/<framework>/`).

## The file

Statements run one per line (`;` also ends one); `#` starts a comment. Text
with spaces goes in double quotes.

| Statement | Meaning |
|---|---|
| `metamodel archimate` | `coreea` (the default), `archimate`, `togaf`, `essential` or `bpmn` |
| `name "Service Portal"`, `description "…"` | the model's name and description |
| `model "model.json"` | objects and relationships from a file (path relative to the `.ead`); at most one |
| `ACMP-01: Application Component "Service Portal" status=Built` | an object: id, a colon, the type, the name in quotes, then any fields |
| `ACMP-03 -[flow]-> ACMP-NOTIFY "case events" note=async` | a relationship: from, `-[type]->`, to, an optional name in quotes, then any fields |
| `view ID "Title" { … }` | a view |
| `view ID script="acd.py"` | a view placed by hand, drawn by that script (see below) |

Fields are `key=value`, with the value in quotes when it has spaces:
`owner="Customer Service"`, `default=true`, `access=read`. A dotted key nests:
`properties.classification=Confidential`. Objects and relationships declared
in the file are added to the imported model; an id that's already there is an
error. The model is validated exactly as `model.json` is (`ea.md`), so ids
still carry their type's prefix and every relationship has to be allowed by
the framework.

`ea.py validate`, `export` and `orbus plan` take a `.ead` wherever they take a
`model.json`.

## In a view

| Statement | Draws |
|---|---|
| `APP-01` | the object as a box |
| `APP-01 { APP-02  APP-03 }` | a box holding others: nesting stands for the relationship between them, so that line isn't drawn (say which relationship in a `key`) |
| `INT-01 on APP-03` | an interface or service as a pill on the top edge of a box already in the view; the relationship between them isn't drawn |
| `pill ASVC-01` | a service or interface as a pill on its own (ArchiMate; in the box notation, pill types are always pills) |
| `group "Requirements" REQ-01 REQ-02 REQ-03` | one box standing for several objects of one type; their lines join it |
| `frame "External" { … }` | a grouping that is not a model object; `dashed=true`, `icon=aws:…` |
| `JOR-01` | an ArchiMate junction (by its type) |
| `matrix "operates on" rows DAT-01 DAT-02 cols PAC-01 PAC-02` | a matrix whose cells come from that relationship; `rows "Data Entity"` takes every object of a type; CoreEA's CRUD form is `matrix writes=CU reads=R rows … cols …`; `row_w=`, `col_w=`, `title=`, `mark=`. A matrix view holds only the matrix and its key |
| `key "…" "…"` | the plain-text key under the legend |

Box attributes go after the id:

| Attribute | On | Effect |
|---|---|---|
| `icon=EKS` | box, container, frame | a platform or generic icon (`icons.md`) |
| `sub="Node 20, Fargate"` | box, container, group | a muted sub-line |
| `w=200`, `h=60` | box (`w` on containers and groups) | fix the size instead of fitting the text |
| `type_label=off` / `type_label="System"` | box (box notation) | hide or replace the type label |
| `dashed=true` / `dashed=false` | box | override the status-driven dashing |
| `fill_opacity=0.9` | container | container fill |

### Lines

Every relationship in the model between two objects the view shows is drawn,
except the ones nesting or a pill on its host already say. The box notation
labels each line with the relationship's `name`, else its `note`, else its
type; ArchiMate labels only named relationships.

| Statement | Effect |
|---|---|
| `ACMP-03 -[flow]-> ACMP-NOTIFY "case events"` | label this line (or, with `edges explicit`, draw it) |
| `ACMP-03 --> ACMP-NOTIFY` | the same, when only one relationship joins the two |
| `hide AIF-01 -[serving]-> ACMP-03` | leave a relationship out of this view |
| `edges explicit` | draw only the lines listed in the view |
| `labels verb` / `labels none` | label every line with its type, or none |

### Steering the layout

The layout comes from the model, and most views need no hints:

- Layers are horizontal bands, top to bottom in the framework's order
  (ArchiMate: Motivation, Strategy, Business, Application, Technology,
  Physical, Implementation, Migration, Other). A box holding others sits in
  its own type's band.
- Within a band, relationships the metamodel marks `"layout": "up"` put their
  target above their source (realization, realises, provides, supports), and
  `"down"` below it (composition and aggregation drawn as lines, hosted on).
  Every other relationship runs across a row.
- Boxes with nothing above or below them join the row of what they connect to.
- Within a row, boxes keep the order the view lists them in, unless reordering
  removes crossings. Each box is then pulled over the boxes it connects to, so
  most lines run straight.
- A row wider than the page puts its last boxes in a column beside a taller
  box when they fit, otherwise on the next row.
- Lines are orthogonal, keep 8px clear of every box they don't belong to,
  cross container edges but never run along them, and avoid the text in
  container headers. Two lines that cross are routed again in the other order
  when that removes the crossing. Labels go where they touch no box, label or
  other line.

When the result isn't what the view needs:

| Statement | Effect |
|---|---|
| `same ACP-01 ACP-02` | these boxes share a row |
| `ASVC-01 above ACMP-01` | the first goes in a higher row (same band only) |
| `bands Business Application Technology` | band order for this view; layers left out go last |
| `bands off` | one band: rows come only from the relationships |
| list order | left-to-right order where nothing else decides it |
| `width 960` | page width (the default is 740, widened when a row can't be narrower) |

## When the layout isn't clean

`render` and `validate` warn when the automatic layout drew a view but not
cleanly, and say what's wrong:

```
warning: LAYERED: layout: a row is too wide for the page, so ACMP-NOTIFY, DOBJ-01 moved to a row below
warning: ACD: layout: lines ACT-02 -[uses]-> APP-02 and APP-02 -[uses]-> INT-01 cross
```

The warnings cover a row wrapped onto the next one, a view wider than the
page, two lines crossing, a line the router found no clear path for (drawn as
a plain elbow that may cross boxes), and a label with no free spot. They're
also in the view's `objects.json`. A warning doesn't always mean the view is
wrong: a crossing between a message flow and a sequence flow is often the
best a BPMN collaboration can do. Read the PNG and decide.

When the result isn't good enough, try the hints first (`same`, `above`,
`bands`, `width`, `hide`). Place the view by hand only when the hints can't
fix it, or when the view needs something the language can't say, such as an
exact position someone has asked for. A hand-placed view loses what the
language gives you: a new object means editing that view's coordinates again.

A hand-placed view stays in the view file, so one `render` still draws every
view and the exports still carry them all:

```
model "model.json"

view ACD script="app_context.py"     # placed by hand
view INT "Integration" {             # laid out automatically
  …
}
```

The script, with its path relative to the `.ead`, defines `draw(model, vid)`.
It draws the view with the View API (`ea.md`) and returns `(view, height)`.
`render` passes it the view file's model, so ids, names and colours match the
other views, and the script must draw the view id it was asked for. A script
can draw several views and pick one by `vid`. The title and every setting
come from the script, so the line takes only `script=`. Each example's
`*.py` in `scripts/examples/<framework>/` follows this shape and still runs
on its own, writing to `out/script/`.

## BPMN views

A BPMN view draws the whole process from the model, so it takes only
`width`, `pools P-CUST P-SVC` (which pools, in order; the default is every
participant), `legend off` and `key`. Pools stack in model order with their
lanes inside them, nested lanes included. Flow nodes go in columns by their
longest sequence-flow distance from the start and in tracks within their lane,
so a branch takes the next track. Boundary events sit on their activity's
lower edge, with room underneath for their flows. Data objects and annotations
go beside what they're associated with, and an expanded sub-process lays out
its own contents. Message flows between a pool and a node run straight when
nothing is in the way.

## Errors

The file is read in full before anything is drawn, and every problem comes
back at once with its line:

```
views.ead:
  line 2: ACMP-01 is already defined in model.json
  line 4: NOPE is not in the model
  line 7: the model has no relationship ACMP-03 -[access]-> ACMP-02
```

`ea.py validate views.ead` lays every view out without drawing, so it also
catches problems that only show at layout time, such as an attribute that
doesn't apply to that kind of box.
