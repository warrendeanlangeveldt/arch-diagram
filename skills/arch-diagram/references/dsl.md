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
python3 scripts/ea.py render views.ead --scale 3              # PNGs at 3x (the file's 'scale', else 2)
python3 scripts/ea.py validate views.ead                      # model and every view, no drawing
```

Each framework's example has a `views.ead` beside its `model.json`
(`scripts/examples/<framework>/`). `scripts/examples/coreea-sad/views.ead` is
a dense one: six SAD views of a model of 131 objects declared in the file
itself, using `edges explicit`, `same`, `before`, `join`, `direction`,
`same by=`, a repeated box and containers with pills.

## The file

Statements run one per line (`;` also ends one); `#` starts a comment. Text
with spaces goes in double quotes.

| Statement | Meaning |
|---|---|
| `metamodel archimate` | `coreea` (the default), `archimate`, `togaf`, `essential` or `bpmn` |
| `name "Service Portal"`, `description "…"` | the model's name and description |
| `model "model.json"` | objects and relationships from a file (path relative to the `.ead`); at most one |
| `scale 3` | PNG pixels per SVG unit for every view (default 2; `render --scale` overrides) |
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
| `TEC-15#dev` | another box for an object already drawn: `#` and a tag name it (see below) |
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
| `icon=EKS` | box, container, group, frame | a platform or generic icon (`icons.md`); a narrow box carries it small, before its type label |
| `sub="Node 20, Fargate"` | box, container, group | a muted sub-line |
| `w=200`, `h=60` | box (`w` on containers and groups) | fix the size instead of fitting the text; the layout never narrows a box with `w` |
| `type_label=off` / `type_label="System"` | box (box notation) | hide or replace the type label |
| `dashed=true` / `dashed=false` | box | override the status-driven dashing |
| `fill_opacity=0.9` | container | container fill |

An object can be drawn more than once: give each extra box a tag, such as
`TEC-15#dev` and `TEC-15#prod` inside two subscription containers. A
relationship joins the boxes of its two objects like this: when either object
has one box, every box of the other; when both have several, the boxes with
the same tag. A line the view lists (`TEC-15#dev -[depends on]-> TEC-H`)
joins the boxes it names, and an untagged id names every box of the object.
When nesting already shows a relationship for one box, it isn't drawn from the
others. The ArchiMate exchange file gets one node per box.

### Lines

Every relationship in the model between two objects the view shows is drawn,
except the ones nesting or a pill on its host already say. A view that draws
more than one and a half lines per box (and more than six lines) warns, since
a model built for a SAD joins most of its objects to most others; list the
lines the view is about with `edges explicit`. The box notation (CoreEA,
TOGAF, Essential) labels each line with its verb; ArchiMate labels only named
relationships.

| Statement | Effect |
|---|---|
| `ACMP-03 -[flow]-> ACMP-NOTIFY "case events"` | label this line (or, with `edges explicit`, draw it) |
| `ACMP-03 --> ACMP-NOTIFY` | the same, when only one relationship joins the two |
| `hide AIF-01 -[serving]-> ACMP-03` | leave a relationship out of this view |
| `edges explicit` | draw only the lines listed in the view |
| `labels text` / `labels verb` / `labels none` | label each line with the relationship's `name`, else its `note`, else its type; or with its type; or not at all |
| `join in` / `join out` / `join both` | lines of one verb into one box (`in`), or out of one box (`out`), share a trunk, one arrowhead or one start, and one label; say so in a `key` |

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
  removes crossings; a line into a box inside a container counts where that
  box sits. Each box is then pulled over the boxes it connects to, so most
  lines run straight.
- Boxes sit 24px apart, or far enough apart for the label of a line running
  between them.
- A row wider than the page first narrows its boxes, wrapping names onto two
  lines; then puts its last boxes in a column beside a taller box; then
  narrows the containers in it, whose children lay out again in less room;
  then carries boxes onto the next row. Moving a box is a warning when lines
  join the row's boxes. A row of boxes with nothing between them just flows
  on, which is how a container's parts pack.
- Three or more containers with no lines between them (data categories,
  application categories) flow into as many columns as fit, each to the
  shortest column.
- Boxes listed one under another inside a container take one width and sit
  close together.
- Lines are orthogonal, keep 8px clear of every box they don't belong to,
  cross container edges but never run along them, and avoid the text in
  container headers. A line from a large box leaves in line with the box it
  goes to. Two lines that cross are routed again in the other order and, at a
  box both meet, with each kept off the port it took there; the way that
  crosses least is kept. Labels go where they touch no box, label or other
  line.

When the result isn't what the view needs:

| Statement | Effect |
|---|---|
| `same ACP-01 ACP-02` | these boxes share a row. The row holds: its boxes narrow to three-line names and close up before anything breaks it, and if it still doesn't fit, the page widens with a warning. Two `same` rows too wide together take a row each |
| `same by=buildsOn` | each box shares a row with the boxes its field names (here the object field `buildsOn`). Across two containers side by side, the paired boxes line up level, and the containers share the page |
| `ASVC-01 before ACMP-01 ACMP-02` | the first goes in an earlier row (a column to the left with `direction lr`); same band only. It wins over the order a relationship implies. `above` says the same |
| `direction lr` / `direction tb` | columns read left to right, or rows top to bottom. A viewpoint can set it (CoreEA's Business Strategy Diagram, Project Context and Risk Catalogue are `lr`) |
| `bands Business Application Technology` | band order for this view; layers left out go last |
| `bands off` | one band: rows come only from the relationships |
| list order | left-to-right order where nothing else decides it |
| `width 960` | page width (the default is 740, widened when a row can't be narrower) |
| `platform azure` | icon names resolve to that platform's pack first (`icons.md`) |

With `direction lr`, what the rules above say about rows holds for columns:
bands and the up/down relationships make the columns, a column is as wide as
its widest box and every box in it takes that width, boxes stack down it, and
each box is pulled level with the boxes it connects to. Columns narrow (names
on up to three lines) when they don't fit the page. Lines between columns
leave and enter boxes on their sides.

## When the layout isn't clean

`render` and `validate` warn when the automatic layout drew a view but not
cleanly, and say what's wrong:

```
warning: V1: layout: a row is too wide for the page, so External, PAC-04 moved to a row below
warning: LODGEMENT: layout: flows T-ASSESS -[sequenceFlow]-> T-NOTIFY and B-SLA -[sequenceFlow]-> T-ESC cross
```

The warnings cover a row wrapped onto the next one, a `same` row or a set of
columns that can't fit the page, a view wider than the page, a view with more
lines than it can show clearly, two lines crossing, a line the router found no
clear path for (drawn as a plain elbow that may cross boxes), and a label with
no free spot. They're
also in the view's `objects.json`. A warning doesn't always mean the view is
wrong: a crossing between a message flow and a sequence flow is often the
best a BPMN collaboration can do. Read the PNG and decide.

When the result isn't good enough, try the hints first (`edges explicit`,
`same`, `before`, `direction`, `join`, `bands`, `width`, `hide`). Place the view by hand only when the hints can't
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
