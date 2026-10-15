# scripts — CoreEA helper

| File | What it is |
|---|---|
| `coreea_lib.py` | Notation helper: `View` with `node`, `group`, `container`, `frame`, `pill`, `edge`, `tag`, `legend`, `key_line`, `save`; plus `validate(model)`, `catalogue_rows(model)`, `make_theme(...)`. Python 3 stdlib only. |
| `model_schema.json` | JSON Schema for the object model (structure). `validate()` adds the semantic checks. |
| `example/` | A 12-object model and the Application Context Diagram drawn from it. |

## Minimal example

`example/model.json` (abridged):

```json
{
  "objects": [
    {"id": "ACT-01", "type": "Actor", "name": "Customer"},
    {"id": "APP-01", "type": "Application", "name": "Service Portal", "status": "Built"},
    {"id": "APP-02", "type": "Application", "name": "Portal web app", "parent": "APP-01"},
    {"id": "APP-NOTIFY", "type": "Application", "name": "Notification service", "status": "Proposed"}
  ],
  "relationships": [
    {"from": "ACT-01", "type": "uses", "to": "APP-02"},
    {"from": "APP-01", "type": "depends on", "to": "APP-NOTIFY"}
  ]
}
```

A view script (the full one is `example/app_context.py`):

```python
import sys; sys.path.insert(0, "<skill dir>/scripts")  # <skill dir>: the skill base directory
from coreea_lib import load_model, validate, View

model = load_model("model.json")
validate(model)                                   # raises ModelError listing every problem
v = View(model, "ACD", title="Service Portal: application context")

c = v.node("ACT-01", 60, 16, 120)                 # returns a box: x y w h r b cx cy
plat, top = v.container("APP-01", 16, c["b"] + 44, 456, 130)
web = v.node("APP-02", 32, top + 8, 170, 56)      # child drawn inside its parent
v.edge([(120, c["b"]), (120, web["y"] - 2)], "uses",
       label=(124, c["b"] + 18), label_anchor="start",
       check=[("ACT-01", "uses", "APP-02")])      # refuses an edge not in the model

y = v.legend(plat["b"] + 20)                      # only the types drawn (+ dashed if used)
y = v.key_line(y - 2, ["Box inside a box: part of it (parent)"])
v.save(y + 4, "out")                              # out/ACD.svg .html .png .objects.json
```

Run and look:

```bash
cd <skill dir>/scripts/example
python3 app_context.py          # then Read out/ACD.png
python3 ../coreea_lib.py model.json   # validate only
```

`save()` renders the PNG with headless Chrome at 2× scale. `ACD.objects.json` lists the ids drawn, which is what makes a view traceable back to the catalogue.

## Theme

`View(model, vid, theme=make_theme(...))` overrides any house token: `font`, `width`, `ink`, `body`, `muted`, `id`, `rule`, `paper`, `tag`, and per-layer `(stroke, fill)` under `layers`, e.g. `make_theme(layers={"Application": ("#1d4ed8", "#eff6ff")})`. Keep layer colours distinct; a legend that cannot be told apart is worse than none.

## Extending the verbs

`validate(model, extra_verbs={"governs": (["Organization"], ["Principle"])})` admits a verb the architecture office has agreed. Do not add verbs to make an awkward relationship pass; pick the right object type instead.

## Catalogue export

`catalogue_rows(model)` returns `(objects, relationships)` as flat dicts, names resolved, ready for `csv.DictWriter`: the two sheets OrbusInfinity imports.
