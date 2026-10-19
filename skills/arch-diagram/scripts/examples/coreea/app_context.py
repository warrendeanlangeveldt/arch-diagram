"""Application Context Diagram from the tiny model in model.json, placed by
hand with the Python API. views.ead draws the same view from a few lines of
the view language; this script shows the API it builds on.

    python3 app_context.py            # writes out/script/ACD.svg|html|png|objects.json

draw(model, vid) is what a view file calls for  view ACD script="app_context.py".
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from coreea_lib import load_model, validate, View  # noqa: E402


def draw(model, vid="ACD"):
    v = View(model, "ACD", title="Service Portal: application context")

    # actors across the top
    c = v.node("ACT-01", 60, 16, 120)
    a = v.node("ACT-02", 220, 16, 120, h=c["h"])

    # the application as a container holding its parts (parent). The Case
    # service sits half a box lower so the interface pill on its top edge is
    # level with the web app that uses it.
    FY = c["b"] + 44
    hh, _ = v.container_header("APP-01", 456)
    plat, top = v.container("APP-01", 16, FY, 456, hh + 8 + 28 + 56 + 14)
    web = v.node("APP-02", 32, top + 8, 170, 56)
    case = v.node("APP-03", 270, web["cy"], 186, 56)
    pw = v.pill_width("INT-01")
    p1 = v.pill("INT-01", case["r"] - pw - 10, case["y"] - 11, pw)  # exposed: on its edge

    for act, oid, x, tx in ((c, "ACT-01", 120, web["cx"] - 30), (a, "ACT-02", 280, web["cx"] + 30)):
        pts = [(x, act["b"]), (x, FY - 14), (tx, FY - 14), (tx, web["y"] - 2)]
        v.edge(pts, "uses", label=(x + 4, act["b"] + 18), label_anchor="start",
               check=[(oid, "uses", "APP-02")])
    v.edge([(web["r"], p1["cy"]), (p1["x"] - 2, p1["cy"])], "uses",
           label=((web["r"] + p1["x"]) / 2, p1["cy"] - 5), check=[("APP-02", "uses", "INT-01")])

    # external application with its interface pill, right column
    RX, RW = 560, 164
    hh, _ = v.container_header("APP-CRM", RW)
    crm, ctop = v.container("APP-CRM", RX, FY, RW, hh + 4 + 22 + 10, fill_opacity=0.9)
    p2 = v.pill("INT-02", RX + 8, ctop + 4, RW - 16)
    ey, ex = case["y"] + 16, 500  # leave from the consumer, elbow in the gap
    v.edge([(case["r"], ey), (ex, ey), (ex, p2["cy"]), (p2["x"] - 2, p2["cy"])], "consumes",
           label=(ex + 4, (ey + p2["cy"]) / 2 + 3), label_anchor="start",
           check=[("APP-03", "consumes", "INT-02")])

    notify = v.node("APP-NOTIFY", RX, crm["b"] + 24, RW)
    ny = notify["cy"]
    v.edge([(plat["r"], ny), (RX - 2, ny)], "depends on",
           label=((plat["r"] + RX) / 2, ny - 5), check=[("APP-01", "depends on", "APP-NOTIFY")])

    # hosting and location below
    by = plat["b"] + 40
    tec = v.node("TEC-01", 16, by, 180)
    v.edge([(tec["cx"], plat["b"]), (tec["cx"], by - 2)], "hosted on",
           label=(tec["cx"] + 4, plat["b"] + 24), label_anchor="start",
           check=[("APP-01", "hosted on", "TEC-01")])
    loc = v.node("LOC-01", 256, by, 180, h=tec["h"])
    v.edge([(tec["r"], tec["cy"]), (loc["x"] - 2, tec["cy"])], "located in",
           label=((tec["r"] + loc["x"]) / 2, tec["cy"] - 5), check=[("TEC-01", "located in", "LOC-01")])

    y = v.legend(max(tec["b"], notify["b"]) + 20)
    y = v.key_line(y - 2, ["Box inside a box: part of it (parent)",
                           "Pill on an application: interface it exposes"])
    return v, y + 4


if __name__ == "__main__":
    model = load_model(os.path.join(HERE, "model.json"))
    validate(model)
    v, height = draw(model)
    for p in v.save(height, os.path.join(HERE, "out", "script")):
        print(p)
