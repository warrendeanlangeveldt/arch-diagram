"""Essential views for the Service Portal: Business Capability to
Application, and the Application to Information CRUD matrix.

    python3 views.py     # out/script/V1.*, V2.*, service-portal.*.csv
                         # (views.ead lays the same views out automatically)

draw(model, vid) is what a view file calls for  view V1 script="views.py".
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from ealib import View, load_model, validate, write_catalogue  # noqa: E402

OUT = os.path.join(HERE, "out", "script")


def _v1(model):
    v = View(model, "V1", title="V1 Business Capability to Application",
             viewpoint="Business Capability to Application")
    # capabilities nested in their domain and parent capability
    hh, _ = v.container_header("BDM-01", 708)
    dom, dtop = v.container("BDM-01", 16, 16, 708, hh + 10 + 108 + 14)
    chh, _ = v.container_header("BCP-01", 440)
    cap, ctop = v.container("BCP-01", 32, dtop + 10, 440, 108)
    intake = v.node("BCP-02", 48, ctop + 8, 196, 52)
    assess = v.node("BCP-03", 260, ctop + 8, 196, 52)
    comms = v.node("BCP-04", 496, dtop + 10, 212, 108)

    # application capabilities supporting them
    AY = dom["b"] + 44
    hc = v.node("ACP-01", 140, AY, 224)
    mc = v.node("ACP-02", 508, AY, 188, h=hc["h"])
    for tgt, x in ((intake, intake["cx"]), (assess, assess["cx"])):
        v.edge([(hc["cx"] + (x - hc["cx"]) * 0.35, hc["y"]), (hc["cx"] + (x - hc["cx"]) * 0.35, AY - 22),
                (x, AY - 22), (x, tgt["b"] + 2)], "supports capability",
               check=[("ACP-01", "supports capability", "BCP-02" if tgt is intake else "BCP-03")])
    v.text(hc["cx"] + 6, AY - 26, "supports capability", 8.5, v.t["muted"], italic=True, halo=True)
    v.edge([(mc["cx"], mc["y"]), (mc["cx"], comms["b"] + 2)], "supports capability",
           label=(mc["cx"] + 6, comms["b"] + 26), label_anchor="start",
           check=[("ACP-02", "supports capability", "BCP-04")])

    # services (pills) realise the application capabilities; providers below provide them
    SY = hc["b"] + 44
    pw1, pw2, pw3 = v.pill_width("ASV-01"), v.pill_width("ASV-02"), v.pill_width("ASV-03")
    p1 = v.pill("ASV-01", hc["cx"] - pw1 - 8, SY, pw1)
    p2 = v.pill("ASV-02", hc["cx"] + 8, SY, pw2)
    p3 = v.pill("ASV-03", mc["cx"] - pw3 / 2, SY, pw3)
    for p, oid in ((p1, "ASV-01"), (p2, "ASV-02")):
        v.edge([(p["cx"], p["y"]), (p["cx"], hc["b"] + 2)], "realises",
               label=(p["cx"] + 5, hc["b"] + 22), label_anchor="start", check=[(oid, "realises", "ACP-01")])
    v.edge([(p3["cx"], p3["y"]), (p3["cx"], mc["b"] + 2)], "realises",
           label=(p3["cx"] + 5, mc["b"] + 22), label_anchor="start", check=[("ASV-03", "realises", "ACP-02")])

    PY = p1["b"] + 40
    sp = v.node("APR-01", p1["x"] - 20, PY, p2["r"] - p1["x"] + 40, 58, icon="server")
    ns = v.node("APR-03", mc["x"], PY, mc["w"], 58, icon="notify")
    for p, oid, prov, lab in ((p1, "ASV-01", sp, True), (p2, "ASV-02", sp, False), (p3, "ASV-03", ns, True)):
        v.edge([(p["cx"], prov["y"]), (p["cx"], p["b"] + 2)], "provides",
               label=(p["cx"] + 5, p["b"] + 24) if lab else None, label_anchor="start",
               check=[("APR-01" if prov is sp else "APR-03", "provides", oid)])
    v.edge([(sp["r"], sp["cy"]), (ns["x"] - 2, ns["cy"])], "sends information to",
           label=((sp["r"] + ns["x"]) / 2, sp["cy"] - 6), label_text="case events",
           check=[("APR-01", "sends information to", "APR-03")])

    y = v.legend(sp["b"] + 24)
    y = v.key_line(y - 2, ["Box in a box: belongs to (domain) or part of (parent capability)",
                           "Pill: application service"])
    return v, y + 4


def _v2(model):
    m = View(model, "V2", title="V2 Application to Information CRUD matrix",
             viewpoint="Application to Information CRUD matrix")
    rows, cols = ["IRP-01", "IRP-02"], ["APR-01", "APR-02", "APR-03"]
    y = m.matrix(16, 16, rows, cols, m.cells_from("uses information", rows, cols), row_w=220, col_w=150)
    y = m.key_line(y + 10, ["C create", "R read", "U update", "D delete",
                            "Cells come from APP_PRO_TO_INFOREP_RELATION ('uses information', crud)"])
    return m, y + 4


def draw(model, vid):
    return {"V1": _v1, "V2": _v2}[vid](model)


if __name__ == "__main__":
    model = load_model(os.path.join(HERE, "model.json"))
    validate(model)
    for vid in ("V1", "V2"):
        view, height = draw(model, vid)
        for p in view.save(height, OUT):
            print(p)
    for p in write_catalogue(model, OUT):
        print(p)
