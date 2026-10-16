"""TOGAF Phase C artifacts for the Service Portal: an Application
Communication diagram and the Application/Data matrix.

    python3 views.py     # out/V1.*, out/V2.*, out/service-portal.*.csv
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from ealib import View, load_model, validate, write_catalogue  # noqa: E402

model = load_model(os.path.join(HERE, "model.json"))
validate(model)
OUT = os.path.join(HERE, "out")

# V1 Application Communication diagram
v = View(model, "V1", title="V1 Application Communication diagram",
         viewpoint="Application Communication diagram")
web = v.node("PAC-01", 16, 40, 170, icon="user-browser")
case = v.node("PAC-02", 286, 40, 170, h=web["h"], icon="server")
crm = v.node("PAC-03", 552, 40, 164, h=web["h"], icon="saas")
v.frame(540, 16, 184, crm["b"] + 12 - 16, "External")
v.edge([(web["r"], web["cy"]), (case["x"] - 2, case["cy"])], "communicates with",
       label=((web["r"] + case["x"]) / 2, web["cy"] - 6), label_text="HTTPS / JSON",
       check=[("PAC-01", "communicates with", "PAC-02")])
v.edge([(case["r"], case["cy"]), (crm["x"] - 2, crm["cy"])], "communicates with",
       label=((case["r"] + crm["x"]) / 2, case["cy"] - 6), label_text="customer lookup",
       check=[("PAC-02", "communicates with", "PAC-03")])
note = v.node("PAC-04", 286, web["b"] + 60, 170, h=web["h"], icon="notify")
v.edge([(case["cx"], case["b"]), (case["cx"], note["y"] - 2)], "communicates with",
       label=(case["cx"] + 6, case["b"] + 32), label_anchor="start", label_text="case events",
       check=[("PAC-02", "communicates with", "PAC-04")])
y = v.legend(note["b"] + 20)
y = v.key_line(y - 2, ["Edge label: what flows between the components"])
for p in v.save(y + 4, OUT):
    print(p)

# V2 Application/Data matrix (cells are the 'operates on' notes: C R U D)
m = View(model, "V2", title="V2 Application/Data matrix", viewpoint="Application/Data matrix")
rows = ["DAT-01", "DAT-02", "DAT-03"]
cols = ["PAC-01", "PAC-02", "PAC-03", "PAC-04"]
y = m.matrix(16, 16, rows, cols, m.cells_from("operates on", rows, cols), row_w=200, col_w=126)
y = m.key_line(y + 10, ["C create", "R read", "U update", "D delete", "Cells come from the model's 'operates on' relationships"])
for p in m.save(y + 4, OUT):
    print(p)
for p in write_catalogue(model, OUT):
    print(p)
