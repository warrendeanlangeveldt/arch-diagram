# scripts

Python 3.9+, standard library only. Headless Chrome renders the PNGs
(`CHROME_PATH` overrides the lookup); `xmllint`, when installed, validates the
XML exports in the tests.

| Path | What it is |
|---|---|
| `ea.py` | Command line: `render`, `validate`, `types`, `rules`, `viewpoints`, `export`, `orbus discover / plan / push` |
| `icons.py` | Command line: `status`, `fetch`, `search`, `resolve`, `svg`, `sheet` |
| `ealib/metamodel.py` | Loads a metamodel, validates a model against it, flattens it to catalogue rows and CSVs |
| `ealib/dsl.py` | The view language (`references/dsl.md`): parses a `.ead` file into the model and its views |
| `ealib/layout.py` | Automatic layout: layer bands, rows, orthogonal line routing and label placement for EA views; pools, lanes and columns for BPMN; warnings when a layout isn't clean; runs the script for a hand-placed view |
| `ealib/views.py` | `View`: ArchiMate notation and the house EA box notation, legends, matrices, viewpoint checks |
| `ealib/archimate_icons.py` | The ArchiMate type symbols |
| `ealib/bpmn.py` | BPMN validation, `BpmnView`, BPMN 2.0 XML with BPMNDI |
| `ealib/exchange.py` | ArchiMate exchange format export |
| `ealib/orbus.py` | OrbusInfinity REST import: discover, plan, push, ledger |
| `ealib/icons.py` | Icon packs: fetch, index, search, resolve, inline |
| `metamodels/` | `archimate.json` (62 types, the 3.2 relationship table, viewpoints), `togaf.json`, `essential.json`, `coreea.json`; each relationship's `layout` (up, down, across) and the layer band order drive the automatic layout |
| `icon_aliases.json` | Component names and product terms → platform icon or generic glyph |
| `model_schema.json` | JSON Schema for `model.json` |
| `examples/` | One model per framework with its views as a view file (`views.ead`, output in `out/`) and as a hand-placed script (output in `out/script/`) |

## Quick start

```bash
python3 ea.py validate examples/archimate/model.json
python3 ea.py rules archimate "Application Component" "Business Process"
python3 ea.py render examples/archimate/views.ead --export archimate   # then Read examples/archimate/out/LAYERED.png
python3 examples/archimate/layered.py        # the same view placed by hand: out/script/LAYERED.png
python3 ea.py export examples/bpmn/model.json --format bpmn
python3 icons.py resolve "Cosmos DB"
```

A view file (`references/dsl.md`):

```
model "model.json"
view V1 "V1 Application cooperation" {
  viewpoint "Application Cooperation"
  ACMP-01 icon=EKS
  ACMP-02
}
```

The same view as a script, for placement by hand. A script the view file
names (`view V1 script="v1.py"`) puts this in `draw(model, vid)` and returns
`(v, y + 4)` instead of saving:

```python
import sys; sys.path.insert(0, "<skill dir>/scripts")
from ealib import View, load_model, validate
from ealib.exchange import write_archimate_xml

model = load_model("model.json"); validate(model)
v = View(model, "V1", title="V1 Application cooperation", viewpoint="Application Cooperation")
a = v.node("ACMP-01", 16, 16, 180, icon="EKS")
b = v.node("ACMP-02", 300, 16, 180, h=a["h"])
v.edge([(a["r"] + 2, a["cy"]), (b["x"] - 2, b["cy"])], "flow",
       check=[("ACMP-01", "flow", "ACMP-02")])
y = v.legend(a["b"] + 24)
v.save(y + 4, "out")
write_archimate_xml(model, "out/model.xml", views=[v])
```

Tests live in the repository's `tests/` directory:
`python3 -m unittest discover -s tests`.
