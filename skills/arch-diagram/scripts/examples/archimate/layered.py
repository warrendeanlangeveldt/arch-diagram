"""ArchiMate Layered view of the Service Portal, plus the exchange file.

    python3 layered.py      # writes out/LAYERED.svg|html|png|objects.json,
                            # out/service-portal.xml (ArchiMate exchange),
                            # out/service-portal.objects.csv|relationships.csv
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from ealib import View, load_model, validate, write_catalogue  # noqa: E402
from ealib.exchange import write_archimate_xml  # noqa: E402

model = load_model(os.path.join(HERE, "model.json"))
validate(model)
v = View(model, "LAYERED", title="Service Portal: layered view", viewpoint="Layered")
OUT = os.path.join(HERE, "out")

# business: actor assigned to the process the application serves
act = v.node("BACT-01", 16, 16, 150)
prc = v.node("BPRC-01", 236, 16, 170, h=act["h"])
v.edge([(act["r"] + 2, act["cy"]), (prc["x"] - 2, prc["cy"])], "assignment",
       check=[("BACT-01", "assignment", "BPRC-01")])

svc = v.node("ASVC-01", 236, act["b"] + 36, 170)
v.edge([(svc["cx"], svc["y"] - 2), (svc["cx"], prc["b"] + 2)], "serving",
       check=[("ASVC-01", "serving", "BPRC-01")])

# application: the portal composes its two parts (nesting = composition)
FY = svc["b"] + 40
hh, _ = v.container_header("ACMP-01", 456)
plat, top = v.container("ACMP-01", 16, FY, 456, hh + 10 + 58 + 16)
web = v.node("ACMP-02", 32, top + 10, 170, 58)
case = v.node("ACMP-03", 286, top + 10, 170, 58)
v.edge([(case["cx"], case["y"] - 2), (case["cx"], svc["b"] + 2)], "realization",
       check=[("ACMP-03", "realization", "ASVC-01")])
v.edge([(case["x"] - 2, case["cy"]), (web["r"] + 2, web["cy"])], "serving",
       check=[("ACMP-03", "serving", "ACMP-02")])

# external CRM composing its interface; proposed notification service
RX, RW = 540, 184
chh, _ = v.container_header("ACMP-CRM", RW)
crm, ctop = v.container("ACMP-CRM", RX, FY - 44, RW, chh + 8 + 40 + 22, fill_opacity=0.9)
aif = v.node("AIF-01", RX + 10, ctop + 8, RW - 20, 40)
iy = case["y"] + 14
v.edge([(aif["x"] - 2, aif["cy"]), (504, aif["cy"]), (504, iy), (case["r"] + 2, iy)], "serving",
       check=[("AIF-01", "serving", "ACMP-03")])
fy = case["b"] - 14
note = v.node("ACMP-NOTIFY", RX, fy - 23, RW, 46)
v.edge([(case["r"] + 2, fy), (RX - 2, fy)], "flow",
       label=((case["r"] + RX) / 2, fy - 6),
       check=[("ACMP-03", "flow", "ACMP-NOTIFY")])

# data written by the case service
dat = v.node("DOBJ-01", RX, plat["b"] + 40, RW, 46)
v.edge([(case["cx"] + 40, case["b"] + 2), (case["cx"] + 40, dat["cy"]), (RX - 2, dat["cy"])], "access",
       check=[("ACMP-03", "access", "DOBJ-01")])

# technology: the region aggregates the platform, which composes PostgreSQL
TY = plat["b"] + 30
lhh, _ = v.container_header("LOC-01", 456)
loc, ltop = v.container("LOC-01", 16, TY, 456, lhh + 12 + 92 + 14)
nhh, _ = v.container_header("NODE-01", 300)
node, ntop = v.container("NODE-01", 32, ltop + 12, 300, 92, icon="ECS")
pg = v.node("SSW-01", 48, ntop + 8, 160, 40, icon="PostgreSQL")
v.edge([(node["r"] - 40, node["y"] - 2 - 0), (node["r"] - 40, plat["b"] + 2)], "serving",
       check=[("NODE-01", "serving", "ACMP-01")])
v.edge([(pg["r"] + 2, pg["cy"]), (case["cx"] - 30, pg["cy"]), (case["cx"] - 30, case["b"] + 2)],
       "serving", check=[("SSW-01", "serving", "ACMP-03")])

y = v.legend(max(loc["b"], dat["b"]) + 20)
y = v.key_line(y - 2, ["Box in a box: composition (application, node) or aggregation (location)"])
for p in v.save(y + 4, OUT):
    print(p)
print(write_archimate_xml(model, os.path.join(OUT, "service-portal.xml"), views=[v]))
for p in write_catalogue(model, OUT):
    print(p)
